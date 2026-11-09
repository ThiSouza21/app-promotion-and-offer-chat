"""Receptor isolado do painel, com verificação HMAC e persistência idempotente."""
from datetime import datetime, timezone
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import sqlite3
import threading
from urllib.parse import parse_qs, urlsplit

from automation import AutomationError, _json_file, _write_json

PATH = '/webhooks/whatsapp'
MAX_BODY = 2 * 1024 * 1024


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class WebhookService:
    def __init__(self, store):
        self.store = store
        self.lock = threading.RLock()
        self.file = Path(store.data_dir) / 'webhook_credentials.json'
        self.credentials = _json_file(self.file)
        if not isinstance(self.credentials.get('verify_token'), str) or not self.credentials['verify_token']:
            self.credentials['verify_token'] = secrets.token_urlsafe(32)
            _write_json(self.file, self.credentials)
        self.server = None
        self.thread = None
        self.last_verified_at = None
        with store.db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS meta_webhook_events (
                event_key TEXT PRIMARY KEY, received_at TEXT NOT NULL, kind TEXT NOT NULL,
                message_id TEXT NOT NULL, phone_number_id TEXT NOT NULL, sender TEXT NOT NULL,
                recipient TEXT NOT NULL, status TEXT NOT NULL, body TEXT NOT NULL,
                error_code TEXT NOT NULL, error_message TEXT NOT NULL, event_timestamp TEXT NOT NULL
            )''')

    def configure(self, data):
        if not isinstance(data, dict):
            raise AutomationError('Configuração de webhook inválida.')
        with self.lock:
            updated = dict(self.credentials)
            value = data.get('app_secret', '')
            if not isinstance(value, str) or len(value) > 1024 or any(c.isspace() for c in value):
                raise AutomationError('A chave secreta do aplicativo deve ser um texto sem espaços.')
            if value:
                updated['app_secret'] = value
            if data.get('clear_app_secret') is True:
                updated.pop('app_secret', None)
            _write_json(self.file, updated)
            self.credentials = updated
        return self.state()

    def verify_token(self):
        with self.lock:
            return self.credentials['verify_token']

    def verify(self, query):
        values = parse_qs(query, keep_blank_values=True)
        if any(len(values.get(k, [])) != 1 for k in ('hub.mode', 'hub.verify_token', 'hub.challenge')):
            return None
        token = values['hub.verify_token'][0]
        if (values['hub.mode'][0] != 'subscribe' or
                not hmac.compare_digest(token.encode(), self.verify_token().encode())):
            return None
        challenge = values['hub.challenge'][0]
        if not re.fullmatch(r'[0-9]{1,1000}', challenge):
            return None
        self.last_verified_at = now()
        return challenge

    def ingest(self, raw, signature):
        with self.lock:
            secret = self.credentials.get('app_secret')
        if not secret:
            raise AutomationError('Configure a chave secreta do aplicativo antes de receber eventos.')
        expected = 'sha256=' + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        if not isinstance(signature, str) or not hmac.compare_digest(signature.encode(), expected.encode()):
            raise PermissionError('Assinatura inválida.')
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeError):
            raise ValueError('JSON inválido.') from None
        if not isinstance(payload, dict) or payload.get('object') != 'whatsapp_business_account':
            raise ValueError('Objeto de webhook inválido.')
        events = []
        try:
            for entry in payload.get('entry', []):
                for change in entry.get('changes', []):
                    if change.get('field') != 'messages':
                        continue
                    value = change.get('value', {})
                    phone = str(value.get('metadata', {}).get('phone_number_id', ''))[:80]
                    for kind, items in (('incoming', value.get('messages', [])), ('status', value.get('statuses', []))):
                        for item in items:
                            if not isinstance(item, dict) or not isinstance(item.get('id'), str):
                                raise ValueError()
                            message_id = item['id'][:512]
                            status = str(item.get('status', ''))[:80] if kind == 'status' else ''
                            stamp = str(item.get('timestamp', ''))[:40]
                            errors = item.get('errors') or []
                            error = errors[0] if errors and isinstance(errors[0], dict) else {}
                            code = str(error.get('code', ''))[:40]
                            explanation = str(error.get('message') or error.get('title') or '')[:2000]
                            body = str((item.get('text') or {}).get('body', ''))[:4096] if kind == 'incoming' else ''
                            key = hashlib.sha256(json.dumps([phone, kind, message_id, status, stamp, code]).encode()).hexdigest()
                            events.append((key, now(), kind, message_id, phone, str(item.get('from', ''))[:80],
                                           str(item.get('recipient_id', ''))[:80], status, body, code, explanation, stamp))
                            if len(events) > 1000:
                                raise ValueError()
        except (AttributeError, TypeError, KeyError, ValueError):
            raise ValueError('Estrutura do webhook inválida ou lote muito grande.') from None
        inserted = 0
        with self.store.db() as db:
            for event in events:
                cursor = db.execute('INSERT OR IGNORE INTO meta_webhook_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', event)
                inserted += cursor.rowcount
        return {'accepted': len(events), 'new_events': inserted}

    def state(self):
        with self.store.db() as db:
            rows = db.execute('SELECT * FROM meta_webhook_events ORDER BY received_at DESC, rowid DESC LIMIT 50').fetchall()
            total = db.execute('SELECT COUNT(*) FROM meta_webhook_events').fetchone()[0]
        tunnel_file = Path(self.store.data_dir) / 'tunnel.json'
        public_url = ''
        try:
            info = _json_file(tunnel_file)
            url = info.get('url', '')
            parsed = urlsplit(url)
            if parsed.scheme == 'https' and re.fullmatch(r'[a-z0-9-]+\.trycloudflare\.com', parsed.netloc) and not parsed.path:
                public_url = url + PATH
        except (AutomationError, ValueError, TypeError):
            pass
        return {'listening': self.server is not None, 'port': self.server.server_port if self.server else None,
                'path': PATH, 'public_url': public_url, 'app_secret_configured': bool(self.credentials.get('app_secret')),
                'last_verified_at': self.last_verified_at, 'total': total,
                'events': [{k: row[k] for k in row.keys() if k != 'event_key'} for row in rows]}

    def start(self, port):
        self.server = WebhookServer(('127.0.0.1', port), self)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .2}, daemon=True)
        self.thread.start()

    def close(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
            self.thread.join(timeout=2)


class WebhookServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, service):
        self.service = service
        super().__init__(address, WebhookHandler)


class WebhookHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *args):
        pass  # Nunca registrar query de verificação, corpos ou credenciais.

    def reply(self, status, body):
        raw = body.encode()
        self.send_response(status)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path != PATH:
            return self.reply(404, 'Not found')
        challenge = self.server.service.verify(parsed.query)
        return self.reply(200, challenge) if challenge is not None else self.reply(403, 'Verification failed')

    def do_POST(self):
        if urlsplit(self.path).path != PATH:
            return self.reply(404, 'Not found')
        try:
            if self.headers.get('Transfer-Encoding') or self.headers.get_content_type() != 'application/json':
                return self.reply(400, 'JSON body required')
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_BODY:
                return self.reply(413, 'Invalid body size')
            raw = self.rfile.read(length)
            if len(raw) != length:
                return self.reply(400, 'Incomplete body')
            self.server.service.ingest(raw, self.headers.get('X-Hub-Signature-256'))
            self.reply(200, 'EVENT_RECEIVED')
        except PermissionError:
            self.reply(403, 'Invalid signature')
        except AutomationError:
            self.reply(503, 'Webhook not configured')
        except (ValueError, UnicodeError):
            self.reply(400, 'Invalid payload')
        except (sqlite3.Error, OSError):
            self.reply(503, 'Persistence unavailable')
