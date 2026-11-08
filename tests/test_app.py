"""Integration checks for the local offer queue; no external services are used."""

from __future__ import annotations

import json
import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone


ROOT = Path(__file__).resolve().parents[1]


class LocalServer:
    """Run the real application with its own disposable database and log."""

    def __init__(self):
        self.directory = tempfile.TemporaryDirectory(prefix="achadinhos-test-")
        self.data_dir = Path(self.directory.name) / "data"
        self.log_path = Path(self.directory.name) / "server.log"
        self.process = None
        self.log = None
        self.base_url = ""
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def start(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        self.base_url = f"http://127.0.0.1:{port}"
        self.log = self.log_path.open("ab")
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTHONUNBUFFERED"] = "1"
        self.process = subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "app.py"),
                "--host", "127.0.0.1",
                "--port", str(port),
                "--no-browser",
                "--data-dir", str(self.data_dir),
            ],
            cwd=ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=self.log,
            stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                break
            try:
                status, body = self.request("GET", "/api/health")
                if status == 200 and body.get("app") == "achadinhos":
                    return self
            except (OSError, ValueError):
                pass
            time.sleep(0.05)
        self.stop()
        raise AssertionError(
            "The local server did not become healthy.\n"
            + self.log_path.read_text(encoding="utf-8", errors="replace")
        )

    def stop(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
            self.process = None
        if self.log is not None:
            self.log.close()
            self.log = None

    def close(self):
        self.stop()
        self.directory.cleanup()

    def request(self, method, path, body=None, *, csrf=True, headers=None):
        request_headers = {"Accept": "application/json"}
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        if csrf and method in {"POST", "PATCH", "DELETE"}:
            request_headers["X-Achadinhos-Request"] = "1"
        if headers:
            request_headers.update(headers)
        request = urllib.request.Request(
            self.base_url + path,
            data=None if body is None else json.dumps(body).encode("utf-8"),
            headers=request_headers,
            method=method,
        )
        try:
            response = self.opener.open(request, timeout=3)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read().decode("utf-8"))


class OfferQueueTests(unittest.TestCase):
    def setUp(self):
        self.server = LocalServer()
        self.addCleanup(self.server.close)
        self.server.start()

    def offer_payload(self, **overrides):
        payload = {
            "title": "Organizador para cozinha",
            "url": "https://example.com/oferta?afiliado=teste",
            "store": "Loja de teste",
            "category": "Casa e dia a dia",
            "price": "39,90",
            "original_price": "49.90",
            "coupon": "CASA10",
            "notes": "Confira o frete para o seu CEP.",
            "status": "ready",
            "scheduled_at": None,
        }
        payload.update(overrides)
        return payload

    def create_offer(self, **overrides):
        status, body = self.server.request(
            "POST", "/api/offers", self.offer_payload(**overrides)
        )
        self.assertIn(status, (200, 201), body)
        return body["offer"]

    def get_state(self, server=None):
        status, state = (server or self.server).request("GET", "/api/state")
        self.assertEqual(status, 200, state)
        return state

    def test_message_is_prepared_but_only_explicit_action_marks_it_sent(self):
        health_status, health = self.server.request("GET", "/api/health")
        self.assertEqual(health_status, 200)
        self.assertEqual(health["status"], "ok")
        self.assertEqual(health["delivery_mode"], "manual_whatsapp")

        offer = self.create_offer()
        self.assertIn(offer["title"], offer["message"])
        self.assertIn(offer["url"], offer["message"])
        self.assertRegex(offer["message"], r"R\$[\s\u00a0]*39,90")
        self.assertIn("afiliad", offer["message"].lower())

        state = self.get_state()
        self.assertEqual(state["delivery_mode"], "manual_whatsapp")
        self.assertEqual(state["offers"][0]["status"], "ready")
        self.assertFalse(state["offers"][0].get("sent_at"))
        # Reading/reviewing the message is never evidence of a WhatsApp send.
        self.assertEqual(self.get_state()["offers"][0]["status"], "ready")

        status, result = self.server.request(
            "PATCH", f"/api/offers/{offer['id']}", {"status": "sent"}
        )
        self.assertEqual(status, 200, result)
        self.assertEqual(result["offer"]["status"], "sent")
        self.assertTrue(result["offer"]["sent_at"])

    def test_offers_and_settings_survive_a_process_restart(self):
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        offer = self.create_offer(status="scheduled", scheduled_at=future)
        status, body = self.server.request(
            "POST", "/api/settings", {"channel_name": "Achadinhos da minha cidade"}
        )
        self.assertEqual(status, 200, body)

        self.server.stop()
        self.server.start()
        state = self.get_state()
        self.assertEqual(state["settings"]["channel_name"], "Achadinhos da minha cidade")
        self.assertEqual(len(state["offers"]), 1)
        restored = state["offers"][0]
        self.assertEqual(restored["id"], offer["id"])
        self.assertEqual(restored["status"], "scheduled")
        self.assertEqual(restored["title"], offer["title"])

    def test_schedule_missed_while_computer_is_off_becomes_ready_after_restart(self):
        due_at = datetime.now(timezone.utc) + timedelta(seconds=1)
        offer = self.create_offer(status="scheduled", scheduled_at=due_at.isoformat())
        self.assertEqual(offer["status"], "scheduled")
        self.server.stop()
        time.sleep(max(0, (due_at - datetime.now(timezone.utc)).total_seconds()) + 0.1)
        self.server.start()

        restored = self.get_state()["offers"][0]
        self.assertEqual(restored["id"], offer["id"])
        self.assertEqual(restored["status"], "ready")
        self.assertFalse(restored.get("sent_at"))

    def test_invalid_offer_data_does_not_enter_the_queue(self):
        invalid_fields = [
            {"url": "javascript:alert(1)"},
            {"price": "0"},
            {"price": "-10.00"},
            {"status": "scheduled", "scheduled_at": "2030-01-01T10:00:00"},
            {"status": "unknown"},
        ]
        for fields in invalid_fields:
            with self.subTest(fields=fields):
                status, body = self.server.request(
                    "POST", "/api/offers", self.offer_payload(**fields)
                )
                self.assertIn(status, (400, 422), body)
                self.assertTrue(body.get("error"))
                self.assertEqual(self.get_state()["offers"], [])

    def test_external_browser_requests_cannot_mutate_the_local_queue(self):
        status, body = self.server.request(
            "POST", "/api/offers", self.offer_payload(), csrf=False
        )
        self.assertEqual(status, 403, body)
        self.assertTrue(body.get("error"))

        status, body = self.server.request(
            "GET", "/api/state", headers={"Host": "untrusted.example"}
        )
        self.assertEqual(status, 403, body)
        self.assertEqual(self.get_state()["offers"], [])

    def test_backup_import_is_repeatable_and_preserves_existing_edits(self):
        original = self.create_offer()
        status, backup = self.server.request("GET", "/api/backup")
        self.assertEqual(status, 200, backup)
        self.assertEqual(backup["version"], 1)
        self.assertEqual(len(backup["offers"]), 1)

        recipient = LocalServer()
        self.addCleanup(recipient.close)
        recipient.start()
        status, result = recipient.request("POST", "/api/restore", backup)
        self.assertEqual(status, 200, result)
        self.assertEqual(result, {"imported": 1, "skipped": 0})
        restored = self.get_state(recipient)["offers"][0]
        self.assertEqual(restored["id"], original["id"])
        self.assertEqual(restored["title"], original["title"])

        status, result = recipient.request(
            "PATCH", f"/api/offers/{original['id']}", {"title": "Título revisado"}
        )
        self.assertEqual(status, 200, result)
        status, result = recipient.request("POST", "/api/restore", backup)
        self.assertEqual(status, 200, result)
        self.assertEqual(result, {"imported": 0, "skipped": 1})
        offers = self.get_state(recipient)["offers"]
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["title"], "Título revisado")

    def test_invalid_backup_is_rejected_without_partial_import(self):
        self.create_offer()
        status, backup = self.server.request("GET", "/api/backup")
        self.assertEqual(status, 200)
        invalid_offer = dict(backup["offers"][0])
        invalid_offer["id"] = "invalid-import-offer"
        invalid_offer["url"] = "javascript:alert(1)"
        backup["offers"].append(invalid_offer)

        recipient = LocalServer()
        self.addCleanup(recipient.close)
        recipient.start()
        status, result = recipient.request("POST", "/api/restore", backup)
        self.assertIn(status, (400, 422), result)
        self.assertTrue(result.get("error"))
        self.assertEqual(self.get_state(recipient)["offers"], [])

    def test_backup_larger_than_two_megabytes_can_be_restored(self):
        # Seed valid local records directly so this regression tests transport
        # and restore limits rather than hundreds of redundant HTTP creates.
        spec = importlib.util.spec_from_file_location("achadinhos_test_backend", ROOT / "app.py")
        backend = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(backend)
        store = backend.Store(self.server.data_dir)
        for index in range(600):
            store.create(self.offer_payload(
                title=f"Oferta {index} " + "Produto " * 20,
                url="https://example.com/" + "p" * 1950,
                store="Loja " + "L" * 70,
                category="Categoria " + "C" * 65,
                coupon="C" * 100,
                notes="N" * 1000,
            ))

        status, backup = self.server.request("GET", "/api/backup")
        self.assertEqual(status, 200)
        self.assertEqual(len(backup["offers"]), 600)
        encoded_size = len(json.dumps(backup, ensure_ascii=False).encode("utf-8"))
        self.assertGreater(encoded_size, 2 * 1024 * 1024)
        self.assertNotIn("message", backup["offers"][0])

        recipient = LocalServer()
        self.addCleanup(recipient.close)
        recipient.start()
        status, result = recipient.request("POST", "/api/restore", backup)
        self.assertEqual(status, 200, result)
        self.assertEqual(result["imported"], 600)
        self.assertEqual(result["skipped"], 0)
        restored = self.get_state(recipient)["offers"]
        self.assertEqual({offer["id"] for offer in restored}, {offer["id"] for offer in backup["offers"]})
        self.assertTrue(all(offer["status"] == "ready" for offer in restored))

    def test_second_folder_cannot_silently_open_the_original_database(self):
        original = self.create_offer(title="Oferta da primeira pasta")
        port = self.server.base_url.rsplit(":", 1)[1]
        other_directory = Path(self.server.directory.name) / "other-copy"
        result = subprocess.run(
            [
                sys.executable, str(ROOT / "app.py"),
                "--host", "127.0.0.1", "--port", port,
                "--no-browser", "--data-dir", str(other_directory),
            ],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertTrue(result.stderr.strip(), "The launcher must explain why the other folder was not opened.")
        state = self.get_state()
        self.assertEqual(len(state["offers"]), 1)
        self.assertEqual(state["offers"][0]["id"], original["id"])
        self.assertEqual(state["offers"][0]["title"], "Oferta da primeira pasta")


if __name__ == "__main__":
    unittest.main()
