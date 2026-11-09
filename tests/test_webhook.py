import hashlib
import hmac
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, ProxyHandler

from app import Store
from meta_webhook import WebhookService, PATH
from tunnel import callback_origin, ensure_binary


class WebhookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name))
        self.service = WebhookService(self.store)
        self.service.start(0)
        self.addCleanup(self.service.close)
        self.base = f'http://127.0.0.1:{self.service.server.server_port}'
        self.opener = build_opener(ProxyHandler({}))

    def request(self, method, path=PATH, raw=None, signature=None, headers=None):
        hdr = {'Host': 'public-test.trycloudflare.com', 'Content-Type': 'application/json'}
        if signature:
            hdr['X-Hub-Signature-256'] = signature
        hdr.update(headers or {})
        try:
            response = self.opener.open(Request(self.base+path, data=raw, headers=hdr, method=method), timeout=3)
        except HTTPError as exc:
            response = exc
        with response:
            return response.status, response.read().decode()

    def sign(self, raw):
        return 'sha256='+hmac.new(b'test-app-secret', raw, hashlib.sha256).hexdigest()

    def payload(self):
        return {'object':'whatsapp_business_account', 'entry':[{'changes':[{'field':'messages','value':{
            'metadata':{'phone_number_id':'12345'},
            'messages':[{'id':'incoming-1','from':'55111111','timestamp':'100','text':{'body':'Oi'}}],
            'statuses':[{'id':'outgoing-1','recipient_id':'55111111','timestamp':'101','status':'failed',
                         'errors':[{'code':130497,'message':'Business account is restricted from messaging users in this country.'}]}]
        }}]}]}

    def test_verification_challenge_and_invalid_tokens(self):
        query=urlencode({'hub.mode':'subscribe','hub.verify_token':self.service.verify_token(),'hub.challenge':'123456'})
        self.assertEqual(self.request('GET',PATH+'?'+query),(200,'123456'))
        self.assertEqual(self.request('GET',PATH+'?'+query.replace('123456','not-a-challenge'))[0],403)
        self.assertEqual(self.request('GET',PATH+'?'+query.replace('subscribe','invalid'))[0],403)
        self.assertIsNotNone(self.service.state()['last_verified_at'])

    def test_signed_receipts_are_deduplicated_and_persisted(self):
        self.service.configure({'app_secret':'test-app-secret'})
        raw=json.dumps(self.payload()).encode()
        for _ in range(2):
            self.assertEqual(self.request('POST',raw=raw,signature=self.sign(raw))[0],200)
        state=self.service.state()
        self.assertEqual(state['total'],2)
        incoming=next(e for e in state['events'] if e['kind']=='incoming')
        failure=next(e for e in state['events'] if e['kind']=='status')
        self.assertEqual(incoming['body'],'Oi')
        self.assertEqual(failure['status'],'failed')
        self.assertEqual(failure['error_code'],'130497')
        restarted=WebhookService(self.store)
        self.assertEqual(restarted.state()['total'],2)
        self.assertEqual(restarted.verify_token(),self.service.verify_token())
        self.assertNotIn('test-app-secret',json.dumps(state))
        self.assertNotIn(self.service.verify_token(),json.dumps(self.store.backup()))

    def test_signature_required_and_compared_against_original_body(self):
        self.service.configure({'app_secret':'test-app-secret'})
        raw=json.dumps(self.payload()).encode()
        self.assertEqual(self.request('POST',raw=raw)[0],403)
        self.assertEqual(self.request('POST',raw=raw+b' ',signature=self.sign(raw))[0],403)
        self.assertEqual(self.service.state()['total'],0)

    def test_unconfigured_secret_fails_closed(self):
        self.assertEqual(self.request('POST',raw=b'{}',signature=self.sign(b'{}'))[0],503)
        self.assertEqual(self.service.state()['total'],0)

    def test_invalid_payload_cannot_partially_write_a_batch(self):
        self.service.configure({'app_secret':'test-app-secret'})
        payload=self.payload()
        payload['entry'][0]['changes'][0]['value']['statuses'].append(None)
        raw=json.dumps(payload).encode()
        self.assertEqual(self.request('POST',raw=raw,signature=self.sign(raw))[0],400)
        self.assertEqual(self.service.state()['total'],0)

    def test_public_listener_never_serves_admin_or_configuration(self):
        for path in ['/','/api/backup','/api/webhook/state','/api/webhook/verify-token','/app.js']:
            self.assertEqual(self.request('GET',path)[0],404)
            self.assertEqual(self.request('POST',path,raw=b'{}')[0],404)

    def test_failed_database_write_returns_retryable_error(self):
        self.service.configure({'app_secret':'test-app-secret'})
        raw=json.dumps(self.payload()).encode()
        with patch.object(self.store,'db',side_effect=sqlite3.OperationalError('disk full')):
            self.assertEqual(self.request('POST',raw=raw,signature=self.sign(raw))[0],503)

    def test_oversize_request_rejected_before_signature_or_storage(self):
        self.assertEqual(self.request('POST',raw=b'{}',headers={'Content-Length':str(3*1024*1024)})[0],413)

    def test_tunnel_api_error_is_not_mistaken_for_a_callback(self):
        self.assertIsNone(callback_origin('failed to request: https://api.trycloudflare.com/tunnel'))
        self.assertIsNone(callback_origin('https://api.trycloudflare.com'))
        self.assertEqual(callback_origin('| https://four-words-test-example.trycloudflare.com |'),
                         'https://four-words-test-example.trycloudflare.com')

    def test_unverified_binary_is_never_installed(self):
        from io import BytesIO
        with patch('tunnel.urlopen',return_value=BytesIO(b'corrupted binary')):
            with self.assertRaisesRegex(ValueError,'SHA-256'):
                ensure_binary(Path(self.temp.name)/'tools')
        self.assertEqual(list((Path(self.temp.name)/'tools').iterdir()),[])


if __name__=='__main__':
    unittest.main()
