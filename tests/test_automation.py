"""Behavior checks for local curation; provider calls are mocked, never live."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from app import Store, make_message, validate_offer
from automation import AutomationError, AutomationService


class AutomationTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {
            "ACHADINHOS_AI_API_KEY": "", "OPENAI_API_KEY": "",
            "ACHADINHOS_META_TOKEN": "", "WHATSAPP_ACCESS_TOKEN": "",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        directory = tempfile.TemporaryDirectory(prefix="achadinhos-ai-test-")
        self.addCleanup(directory.cleanup)
        self.data_dir = Path(directory.name)
        self.store = Store(self.data_dir)
        self.service = self.new_service()

    def new_service(self):
        return AutomationService(self.store, validate_offer, make_message)

    def candidate(self, candidate_id="A1", **overrides):
        candidate = {
            "candidate_id": candidate_id,
            "product_id": "product-" + candidate_id,
            "title": "Organizador de cozinha",
            "url": "https://shop.test/item/" + candidate_id + "?affiliate=original",
            "store": "Loja de teste",
            "category": "Casa",
            "price": "29,90",
            "original_price": "49.90",
            "coupon": "CASA10",
            "notes": "Frete não informado pela fonte.",
            "available": True,
            "observed_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
            "expires_at": None,
            "is_demo": False,
        }
        candidate.update(overrides)
        return candidate

    def request(self, *candidates, mode="rules", max_results=2):
        return {
            "mode": mode,
            "niche": "Utilidades para casa",
            "max_results": max_results,
            "candidates": list(candidates or [self.candidate()]),
        }

    def configure_ai(self, **overrides):
        options = {
            "model": "gpt-4.1-mini", "ai_key": "fake-ai-key-for-unit-tests",
            "remember_key": False, "daily_limit": 20,
        }
        options.update(overrides)
        return self.service.configure(options)

    @staticmethod
    def provider_response(selected=("A1",), rejected=(), reason="Adequado ao nicho informado."):
        content = {
            "selected": [{"candidate_id": value, "reason": reason, "template": "direct"} for value in selected],
            "rejected": [{"candidate_id": value, "reason": "Menos relevante para o lote."} for value in rejected],
        }
        return {
            "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(content)}]}],
            "usage": {"input_tokens": 500, "output_tokens": 100},
        }

    def test_rules_filter_invalid_stale_expired_duplicate_and_unavailable_candidates(self):
        now = datetime.now(timezone.utc)
        candidates = [
            self.candidate(),
            self.candidate("duplicate", product_id="product-A1"),
            self.candidate("stale", observed_at=(now - timedelta(hours=25)).isoformat()),
            self.candidate("expired", expires_at=(now - timedelta(minutes=1)).isoformat()),
            self.candidate("bad-price", price="0"),
            self.candidate("unavailable", available=False),
        ]
        with patch("automation._request_openai") as provider:
            result = self.service.evaluate(self.request(*candidates))
        provider.assert_not_called()
        self.assertEqual(result["engine"], "rules")
        self.assertIs(result["ai_called"], False)
        self.assertEqual([value["candidate_id"] for value in result["selected"]], ["A1"])
        self.assertEqual({value["candidate_id"] for value in result["rejected"]}, {
            "duplicate", "stale", "expired", "bad-price", "unavailable",
        })
        self.assertEqual(self.store.list(), [])

    def test_approval_reuses_a_manually_registered_offer_without_changing_its_status(self):
        candidate = self.candidate()
        manual = self.store.create(dict(candidate, status="ready"))
        analysis = self.service.evaluate(self.request(candidate))
        result = self.service.approve({"run_id": analysis["id"], "candidate_id": candidate["candidate_id"]})
        self.assertFalse(result["created"])
        self.assertEqual(result["offer_id"], manual["id"])
        self.assertEqual(len(self.store.list()), 1)
        self.assertEqual(self.store.get(manual["id"])["status"], "ready")

    def test_live_selection_preserves_facts_and_does_not_publish_the_ai_reason(self):
        self.configure_ai()
        original = self.candidate()
        reason = "IA inventou frete grátis e desconto de 99 por cento."
        with patch("automation._request_openai", return_value=self.provider_response(reason=reason)) as provider:
            result = self.service.evaluate(self.request(original, mode="live"))
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(result["engine"], "openai")
        self.assertIs(result["ai_called"], True)
        selection = result["selected"][0]
        self.assertEqual(selection["candidate"]["price"], "29.90")
        self.assertEqual(selection["candidate"]["original_price"], "49.90")
        self.assertEqual(selection["candidate"]["coupon"], original["coupon"])
        self.assertEqual(selection["candidate"]["url"], original["url"])
        self.assertEqual(selection["reason"], reason)
        self.assertNotIn(reason, selection["message"])
        self.assertIn("29,90", selection["message"])
        self.assertIn(original["url"], selection["message"])
        self.assertIn("CASA10", selection["message"])
        self.assertEqual(self.store.list(), [])

    def test_live_without_a_key_fails_instead_of_silently_using_rules(self):
        with patch("automation._request_openai") as provider:
            with self.assertRaises(AutomationError):
                self.service.evaluate(self.request(mode="live"))
        provider.assert_not_called()
        self.assertEqual(self.store.list(), [])

    def test_invalid_model_ids_or_incomplete_decisions_are_rejected(self):
        self.configure_ai()
        cases = [
            (self.provider_response(selected=("unknown",), rejected=("A2",)), 2),
            (self.provider_response(selected=("A1", "A1"), rejected=("A2",)), 2),
            (self.provider_response(selected=("A1",)), 2),
            (self.provider_response(selected=("A1", "A2")), 1),
        ]
        for provider_result, maximum in cases:
            with self.subTest(response=provider_result, maximum=maximum):
                with patch("automation._request_openai", return_value=provider_result):
                    with self.assertRaises(AutomationError):
                        self.service.evaluate(self.request(self.candidate(), self.candidate("A2"), mode="live", max_results=maximum))
        self.assertEqual(self.store.list(), [])

    def test_cache_reuses_a_completed_call_and_daily_limit_survives_restart(self):
        self.configure_ai(daily_limit=1)
        request = self.request(mode="live")
        with patch("automation._request_openai", return_value=self.provider_response()) as provider:
            first = self.service.evaluate(request)
            second = self.service.evaluate(deepcopy(request))
        self.assertEqual(provider.call_count, 1)
        self.assertFalse(first.get("cached", False))
        self.assertTrue(second["cached"])
        restarted = self.new_service()
        restarted.configure({"ai_key": "fake-ai-key-for-unit-tests", "remember_key": False})
        self.assertEqual(restarted.state()["usage"]["used_today"], 1)
        other = deepcopy(request)
        other["candidates"][0]["price"] = "28.90"
        with patch("automation._request_openai") as provider:
            with self.assertRaises(AutomationError):
                restarted.evaluate(other)
        provider.assert_not_called()

    def test_provider_failure_counts_against_the_daily_limit(self):
        self.configure_ai(daily_limit=1)
        with patch("automation._request_openai", side_effect=AutomationError("Falha simulada do provedor.")) as provider:
            with self.assertRaises(AutomationError):
                self.service.evaluate(self.request(mode="live"))
            with self.assertRaises(AutomationError):
                self.service.evaluate(self.request(self.candidate("A2"), mode="live"))
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(self.service.state()["usage"]["used_today"], 1)
        self.assertEqual(self.store.list(), [])

    def test_session_key_is_not_saved_and_secrets_never_enter_state_or_offer_backup(self):
        self.configure_ai()
        self.service.configure({"meta_token": "fake-meta-token-for-unit-tests", "remember_meta_token": False})
        state = self.service.state()
        self.assertTrue(state["config"]["ai_key_configured"])
        serialized = json.dumps({"state": state, "backup": self.store.backup()})
        self.assertNotIn("fake-ai-key-for-unit-tests", serialized)
        self.assertNotIn("fake-meta-token-for-unit-tests", serialized)
        restarted = self.new_service()
        self.assertFalse(restarted.state()["config"]["ai_key_configured"])
        self.assertFalse(restarted.state()["config"]["meta_token_configured"])

    def test_explicitly_remembered_key_is_private_and_survives_restart(self):
        self.configure_ai(remember_key=True)
        path = self.data_dir / "credentials.json"
        self.assertTrue(path.is_file())
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        restarted = self.new_service()
        state = restarted.state()
        self.assertTrue(state["config"]["ai_key_configured"])
        self.assertEqual(state["config"]["ai_key_source"], "saved")
        self.assertNotIn("fake-ai-key-for-unit-tests", json.dumps(state))
        self.assertNotIn("fake-ai-key-for-unit-tests", json.dumps(self.store.backup()))

    def test_approval_creates_one_draft_and_remains_idempotent_after_restart(self):
        result = self.service.evaluate(self.request())
        request = {"run_id": result["id"], "candidate_id": "A1"}
        first = self.service.approve(request)
        second = self.service.approve(request)
        third = self.new_service().approve(request)
        self.assertIs(first["created"], True)
        self.assertIs(second["created"], False)
        self.assertIs(third["created"], False)
        self.assertEqual(first["offer_id"], second["offer_id"])
        self.assertEqual(first["offer_id"], third["offer_id"])
        offers = self.store.list()
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["status"], "draft")
        self.assertIsNone(offers[0]["sent_at"])
        self.assertEqual(offers[0]["price"], "29.90")

    def test_fictional_samples_cannot_be_approved_as_real_offers(self):
        result = self.service.evaluate(self.request(self.candidate(is_demo=True)))
        self.assertIs(result["selected"][0]["candidate"]["is_demo"], True)
        with self.assertRaises(AutomationError):
            self.service.approve({"run_id": result["id"], "candidate_id": "A1"})
        self.assertEqual(self.store.list(), [])

    def test_approval_rechecks_freshness_instead_of_trusting_a_past_selection(self):
        now = datetime.now(timezone.utc)
        result = self.service.evaluate(self.request(self.candidate(
            observed_at=(now - timedelta(hours=23)).isoformat(),
        )))
        self.assertEqual(len(result["selected"]), 1)
        with patch("automation._now", return_value=now + timedelta(hours=2)):
            with self.assertRaises(AutomationError):
                self.service.approve({"run_id": result["id"], "candidate_id": "A1"})
        self.assertEqual(self.store.list(), [])

    def test_meta_test_is_read_only_and_does_not_claim_group_support(self):
        with patch("automation._request_meta") as provider:
            with self.assertRaises(AutomationError):
                self.service.test_meta({})
        provider.assert_not_called()
        self.service.configure({
            "meta_token": "fake-meta-token-for-unit-tests", "remember_meta_token": False,
            "phone_number_id": "123456789012345", "api_version": "v23.0",
        })
        with patch("automation._request_meta", return_value={
            "id": "123456789012345", "display_phone_number": "+55 79 0000-0000",
            "verified_name": "Número fictício", "quality_rating": "GREEN",
        }) as provider:
            result = self.service.test_meta({})
        self.assertEqual(provider.call_count, 1)
        self.assertIs(result["connected"], True)
        self.assertEqual(result["groups_support"], "unverified")
        self.assertNotIn("fake-meta-token-for-unit-tests", json.dumps(result))
        self.assertEqual(self.store.list(), [])


if __name__ == "__main__":
    unittest.main()
