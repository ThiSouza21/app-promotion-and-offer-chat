#!/usr/bin/env python3
"""Painel local de achadinhos. Apenas biblioteca padrão; nenhum envio automático."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import hashlib
from pathlib import Path
import re
import signal
import sqlite3
import sys
import threading
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener
import uuid
import webbrowser

from automation import AutomationError, AutomationService
from meta_webhook import WebhookService


ROOT = Path(__file__).resolve().parent
APP_ID = "achadinhos"
DELIVERY_MODE = "manual_whatsapp"
STATUSES = {"draft", "scheduled", "ready", "sent", "archived"}
OFFER_FIELDS = (
    "title", "url", "store", "category", "price", "original_price",
    "coupon", "notes", "scheduled_at", "status",
)
DEFAULT_SETTINGS = {"channel_name": "Achadinhos de Lagarto"}
MAX_OFFERS = 5000


class ValidationError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def timestamp(value, label="Data", optional=False):
    if optional and value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{label} inválida.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")
    except (ValueError, OverflowError):
        raise ValidationError(f"{label} deve incluir horário e fuso horário.") from None


def text_field(value, label, limit, required=False):
    if not isinstance(value, str):
        raise ValidationError(f"{label} deve ser um texto.")
    value = value.strip()
    if required and not value:
        raise ValidationError(f"Preencha {label.lower()}.")
    if len(value) > limit:
        raise ValidationError(f"{label}: limite de {limit} caracteres.")
    if any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise ValidationError(f"{label} contém caracteres inválidos.")
    return value


def money(value, optional=False):
    if optional and value in (None, ""):
        return ""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValidationError("Informe um preço válido, como 49,90.")
    raw = str(value).strip().removeprefix("R$").strip()
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    if not re.fullmatch(r"\d+(?:\.\d{1,2})?", raw):
        raise ValidationError("Informe um preço com até duas casas decimais, como 49,90.")
    try:
        amount = Decimal(raw)
        if not amount.is_finite() or not Decimal("0") < amount <= Decimal("10000000"):
            raise InvalidOperation()
        return format(amount.quantize(Decimal("0.01")), "f")
    except InvalidOperation:
        raise ValidationError("O preço deve ser maior que zero e até R$ 10.000.000,00.") from None


def validate_offer(data, existing=None, restoring=False):
    if not isinstance(data, dict):
        raise ValidationError("A oferta deve ser um objeto JSON.")
    values = {key: existing[key] for key in OFFER_FIELDS} if existing else {
        "title": "", "url": "", "store": "", "category": "Casa e dia a dia",
        "price": "", "original_price": "", "coupon": "", "notes": "",
        "scheduled_at": None, "status": "draft",
    }
    values.update({key: data[key] for key in OFFER_FIELDS if key in data})
    for key, label, limit, required in (
        ("title", "Nome do produto", 180, True),
        ("url", "Link de afiliado", 2048, True),
        ("store", "Loja", 80, False),
        ("category", "Categoria", 80, False),
        ("coupon", "Cupom", 100, False),
        ("notes", "Observações", 1000, False),
    ):
        values[key] = text_field(values[key], label, limit, required)
    try:
        link = urlsplit(values["url"])
        valid_link = link.scheme in {"http", "https"} and link.hostname and not link.username and not link.password
        if any(c.isspace() for c in values["url"]):
            valid_link = False
        link.port  # Também valida portas malformadas.
    except ValueError:
        valid_link = False
    if not valid_link:
        raise ValidationError("Use um link de afiliado HTTP ou HTTPS válido, sem espaços.")
    values["price"] = money(values["price"])
    values["original_price"] = money(values["original_price"], optional=True)
    if values["original_price"] and Decimal(values["original_price"]) <= Decimal(values["price"]):
        raise ValidationError("O preço anterior deve ser maior que o preço da oferta.")
    if not isinstance(values["status"], str) or values["status"] not in STATUSES:
        raise ValidationError("Situação da oferta inválida.")
    if not existing and not restoring and values["status"] not in {"draft", "scheduled", "ready"}:
        raise ValidationError("Uma oferta nova deve ser rascunho, agendada ou pronta.")
    values["scheduled_at"] = timestamp(values["scheduled_at"], "Agendamento", optional=True)
    if values["status"] == "scheduled" and not values["scheduled_at"]:
        raise ValidationError("Escolha a data e o horário do agendamento.")
    return values


def reais(value):
    return "R$ " + format(Decimal(value), ",.2f").replace(",", "_").replace(".", ",").replace("_", ".")


def make_message(offer, channel_name):
    lines = [f"✨ {channel_name}", "", f"🛍️ {offer['title']}"]
    if offer["store"]:
        lines.append(f"🏪 {offer['store']}")
    if offer["original_price"]:
        lines.append(f"De: {reais(offer['original_price'])}")
    lines.append(f"💰 Por: {reais(offer['price'])}")
    if offer["coupon"]:
        lines.append(f"🎟️ Cupom: {offer['coupon']}")
    if offer["notes"]:
        lines.extend(["", offer["notes"]])
    lines.extend([
        "", f"👉 {offer['url']}", "",
        "Preço e disponibilidade podem mudar. Confira frete, cupom e condições na loja.",
        "Publicidade • link de afiliado. Posso receber comissão pela compra.",
    ])
    return "\n".join(lines)


class Store:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "achadinhos.sqlite3"
        self.instance_key = hashlib.sha256(str(self.data_dir).encode("utf-8")).hexdigest()
        self.lock = threading.RLock()
        with self.db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS offers (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, url TEXT NOT NULL,
                store TEXT NOT NULL, category TEXT NOT NULL, price TEXT NOT NULL,
                original_price TEXT NOT NULL, coupon TEXT NOT NULL, notes TEXT NOT NULL,
                scheduled_at TEXT, status TEXT NOT NULL, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, sent_at TEXT
            )""")
            db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("CREATE INDEX IF NOT EXISTS offers_schedule ON offers(status, scheduled_at)")
            for key, value in DEFAULT_SETTINGS.items():
                db.execute("INSERT OR IGNORE INTO settings VALUES (?, ?)", (key, value))

    @contextmanager
    def db(self):
        with self.lock:
            conn = sqlite3.connect(self.path, timeout=10)
            conn.row_factory = sqlite3.Row
            try:
                with conn:
                    yield conn
            finally:
                conn.close()

    def settings(self):
        with self.db() as db:
            return {row["key"]: row["value"] for row in db.execute("SELECT * FROM settings")}

    def set_settings(self, data):
        if not isinstance(data, dict) or "channel_name" not in data:
            raise ValidationError("Informe o nome do canal.")
        name = text_field(data["channel_name"], "Nome do canal", 100, True)
        with self.db() as db:
            db.execute("UPDATE settings SET value=? WHERE key='channel_name'", (name,))
        return self.settings()

    def promote_due(self):
        now = utc_now()
        with self.db() as db:
            db.execute("UPDATE offers SET status='ready', updated_at=? WHERE status='scheduled' AND scheduled_at<=?", (now, now))

    def decorate(self, offer):
        offer = dict(offer)
        offer["message"] = make_message(offer, self.settings()["channel_name"])
        return offer

    def get(self, offer_id):
        with self.db() as db:
            row = db.execute("SELECT * FROM offers WHERE id=?", (offer_id,)).fetchone()
        if row is None:
            raise KeyError("Oferta não encontrada.")
        return self.decorate(row)

    def list(self):
        self.promote_due()
        settings = self.settings()
        with self.db() as db:
            rows = db.execute("SELECT * FROM offers ORDER BY created_at DESC, id DESC").fetchall()
        return [dict(row, message=make_message(row, settings["channel_name"])) for row in rows]

    def insert(self, db, offer):
        keys = ("id", *OFFER_FIELDS, "created_at", "updated_at", "sent_at")
        db.execute(
            f"INSERT INTO offers ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})",
            tuple(offer[k] for k in keys),
        )

    def create(self, data):
        values = validate_offer(data)
        now = utc_now()
        values.update(id=str(uuid.uuid4()), created_at=now, updated_at=now, sent_at=None)
        with self.db() as db:
            if db.execute("SELECT COUNT(*) FROM offers").fetchone()[0] >= MAX_OFFERS:
                raise ValidationError("Este painel comporta até 5.000 ofertas. Guarde um backup antes de iniciar um novo acervo.")
            self.insert(db, values)
        self.promote_due()
        return self.get(values["id"])

    def update(self, offer_id, data):
        with self.lock:
            old = self.get(offer_id)
            values = validate_offer(data, existing=old)
            values["updated_at"] = utc_now()
            values["sent_at"] = (old["sent_at"] or utc_now()) if values["status"] == "sent" else None
            keys = (*OFFER_FIELDS, "updated_at", "sent_at")
            with self.db() as db:
                db.execute(
                    f"UPDATE offers SET {','.join(key + '=?' for key in keys)} WHERE id=?",
                    (*tuple(values[k] for k in keys), offer_id),
                )
            self.promote_due()
            return self.get(offer_id)

    def backup(self):
        offers = [{key: value for key, value in offer.items() if key != "message"} for offer in self.list()]
        return {"version": 1, "exported_at": utc_now(), "settings": self.settings(), "offers": offers}

    def restore(self, data):
        if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
            raise ValidationError("Este arquivo não é um backup versão 1 do Achadinhos.")
        offers = data.get("offers")
        if not isinstance(offers, list) or len(offers) > MAX_OFFERS:
            raise ValidationError("O backup deve conter uma lista com até 5.000 ofertas.")
        validated = []
        ids = set()
        for offer in offers:
            values = validate_offer(offer, restoring=True)
            offer_id = offer.get("id")
            try:
                if str(uuid.UUID(offer_id)) != offer_id or offer_id in ids:
                    raise ValueError()
            except (ValueError, AttributeError, TypeError):
                raise ValidationError("O backup contém um identificador de oferta inválido ou repetido.") from None
            ids.add(offer_id)
            values.update(
                id=offer_id,
                created_at=timestamp(offer.get("created_at"), "Criação"),
                updated_at=timestamp(offer.get("updated_at"), "Atualização"),
                sent_at=timestamp(offer.get("sent_at"), "Envio", optional=True),
            )
            if values["status"] == "sent" and not values["sent_at"]:
                raise ValidationError("Uma oferta enviada no backup deve conter a data de envio.")
            if values["status"] != "sent":
                values["sent_at"] = None
            validated.append(values)
        imported = 0
        with self.db() as db:
            existing_ids = {row[0] for row in db.execute("SELECT id FROM offers")}
            if len(existing_ids | ids) > MAX_OFFERS:
                raise ValidationError("A importação ultrapassaria o limite de 5.000 ofertas do painel.")
            for offer in validated:
                if offer["id"] in existing_ids:
                    continue
                self.insert(db, offer)
                imported += 1
        self.promote_due()
        return {"imported": imported, "skipped": len(validated) - imported}


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, store):
        self.store = store
        self.automation = AutomationService(store, validate_offer, make_message)
        self.webhook = WebhookService(store)
        self.allowed_hosts = {f"127.0.0.1:{address[1]}", f"localhost:{address[1]}"}
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    server_version = "Achadinhos/1.0"

    def log_message(self, fmt, *args):
        # Não registrar links, mensagens ou conteúdo dos cadastros.
        pass

    def send_bytes(self, content, status=200, content_type="application/json; charset=utf-8", attachment=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if attachment:
            self.send_header("Content-Disposition", f'attachment; filename="{attachment}"')
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, data, status=200, attachment=None):
        content = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_bytes(content, status, attachment=attachment)

    def allowed_request(self, mutation=False):
        host = self.headers.get("Host", "")
        if host not in self.server.allowed_hosts:
            self.send_json({"error": "Acesso permitido somente pelo endereço local do aplicativo."}, 403)
            return False
        if mutation:
            origin = self.headers.get("Origin")
            if self.headers.get("X-Achadinhos-Request") != "1" or (origin and origin != f"http://{host}"):
                self.send_json({"error": "Abra o painel local para fazer esta alteração."}, 403)
                return False
        return True

    def body(self):
        if self.headers.get_content_type() != "application/json":
            raise ValidationError("Use conteúdo JSON.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValidationError("Tamanho da solicitação inválido.") from None
        # Um backup do acervo inteiro é maior que uma operação individual.
        limit_mb = 128 if urlsplit(self.path).path == "/api/restore" else 2
        if not 0 < length <= limit_mb * 1024 * 1024:
            raise ValidationError(f"A solicitação deve ter até {limit_mb} MB.")
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValidationError("Não foi possível ler o JSON enviado.") from None
        if not isinstance(data, dict):
            raise ValidationError("Envie um objeto JSON.")
        return data

    def do_GET(self):
        if not self.allowed_request():
            return
        path = urlsplit(self.path).path
        try:
            if path == "/api/health":
                self.send_json({"status": "ok", "app": APP_ID, "delivery_mode": DELIVERY_MODE, "instance_key": self.server.store.instance_key})
            elif path == "/api/state":
                self.send_json({"offers": self.server.store.list(), "settings": self.server.store.settings(), "server_time": utc_now(), "delivery_mode": DELIVERY_MODE})
            elif path == "/api/automation/state":
                self.send_json(self.server.automation.state())
            elif path == "/api/webhook/state":
                self.send_json(self.server.webhook.state())
            elif path == "/api/backup":
                self.send_json(self.server.store.backup(), attachment=f"achadinhos-backup-{datetime.now().strftime('%Y-%m-%d')}.json")
            elif path in {"/", "/index.html", "/app.js", "/styles.css"}:
                filename = "index.html" if path == "/" else path.lstrip("/")
                mime = {"index.html": "text/html; charset=utf-8", "app.js": "text/javascript; charset=utf-8", "styles.css": "text/css; charset=utf-8"}[filename]
                self.send_bytes((ROOT / "web" / filename).read_bytes(), content_type=mime)
            elif path == "/favicon.ico":
                self.send_bytes(b"", 204, "image/x-icon")
            else:
                self.send_json({"error": "Página não encontrada."}, 404)
        except AutomationError as exc:
            self.send_json({"error": str(exc)}, 400)
        except (OSError, sqlite3.Error):
            self.send_json({"error": "Não foi possível ler os arquivos locais. Verifique a pasta e suas permissões."}, 500)

    def mutate(self):
        if not self.allowed_request(mutation=True):
            return
        path = urlsplit(self.path).path
        try:
            data = self.body()
            store = self.server.store
            if self.command == "POST" and path == "/api/offers":
                self.send_json({"offer": store.create(data)}, 201)
            elif self.command == "PATCH" and re.fullmatch(r"/api/offers/[a-f0-9-]{36}", path):
                self.send_json({"offer": store.update(path.rsplit("/", 1)[1], data)})
            elif self.command == "POST" and path == "/api/settings":
                self.send_json({"settings": store.set_settings(data)})
            elif self.command == "POST" and path == "/api/restore":
                self.send_json(store.restore(data))
            elif self.command == "POST" and path == "/api/automation/config":
                self.send_json(self.server.automation.configure(data))
            elif self.command == "POST" and path == "/api/automation/evaluate":
                self.send_json(self.server.automation.evaluate(data))
            elif self.command == "POST" and path == "/api/automation/approve":
                self.send_json(self.server.automation.approve(data))
            elif self.command == "POST" and path == "/api/automation/meta/test":
                self.send_json(self.server.automation.test_meta(data))
            elif self.command == "POST" and path == "/api/webhook/config":
                self.send_json(self.server.webhook.configure(data))
            elif self.command == "POST" and path == "/api/webhook/verify-token":
                self.send_json({"verify_token": self.server.webhook.verify_token()})
            else:
                self.send_json({"error": "Operação não encontrada."}, 404)
        except (ValidationError, AutomationError) as exc:
            self.send_json({"error": str(exc)}, 400)
        except KeyError:
            self.send_json({"error": "Oferta não encontrada."}, 404)
        except (sqlite3.Error, OSError):
            self.send_json({"error": "Não foi possível salvar. Verifique espaço livre e permissão da pasta de dados."}, 500)

    do_POST = mutate
    do_PATCH = mutate


def existing_instance(url):
    try:
        # Acesso estritamente local, independentemente de proxies do computador.
        opener = build_opener(ProxyHandler({}))
        with opener.open(url + "/api/health", timeout=2) as response:
            health = json.load(response)
        return health if health.get("app") == APP_ID and health.get("status") == "ok" else None
    except (URLError, OSError, ValueError, AttributeError):
        return None


def main():
    parser = argparse.ArgumentParser(description="Achadinhos: painel local de ofertas para envio manual.")
    parser.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1", "localhost"])
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--webhook-port", type=int, help="Porta local isolada para webhook (padrão: 8766).")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("A porta deve estar entre 1 e 65535.")
    webhook_port = args.webhook_port if args.webhook_port is not None else (8766 if args.port == 8765 else 0)
    if not 0 <= webhook_port <= 65535 or webhook_port == args.port:
        parser.error("Escolha uma porta de webhook diferente da porta do painel.")
    url = f"http://127.0.0.1:{args.port}"
    server = None
    try:
        running = existing_instance(url)
        expected_key = hashlib.sha256(str(args.data_dir.resolve()).encode("utf-8")).hexdigest()
        if running and running.get("instance_key") != expected_key:
            print("Já existe um Achadinhos aberto a partir de outra pasta.", file=sys.stderr)
            print("Feche a janela do iniciador anterior e abra esta cópia novamente.", file=sys.stderr)
            return 1
        if running:
            print("O Achadinhos já está aberto neste computador.", flush=True)
            if not args.no_browser:
                webbrowser.open(url)
            return 0
        store = Store(args.data_dir)
        server = LocalServer((args.host, args.port), store)
        server.webhook.start(webhook_port)
    except (OSError, sqlite3.Error, AutomationError) as exc:
        if server:
            server.server_close()
        print(f"Não foi possível iniciar o Achadinhos: {exc}", file=sys.stderr)
        print("Verifique se a pasta permite gravação ou se a porta já está sendo usada.", file=sys.stderr)
        return 1
    stop = threading.Event()

    def scheduler():
        while not stop.is_set():
            try:
                store.promote_due()
            except (sqlite3.Error, OSError):
                print("Não foi possível atualizar a fila. Verifique a pasta de dados; nova tentativa em 15 segundos.", file=sys.stderr, flush=True)
            stop.wait(15)

    def terminate(signum, frame):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, terminate)
    worker = threading.Thread(target=scheduler, daemon=True)
    worker.start()
    print(f"\nAchadinhos aberto em {url}", flush=True)
    print(f"Dados salvos em: {store.data_dir}", flush=True)
    print(f"Webhook isolado na porta {server.webhook.server.server_port}; configure em Webhooks no painel.", flush=True)
    print("Mantenha esta janela aberta. Pode minimizá-la.", flush=True)
    print("As mensagens são preparadas aqui; o envio no WhatsApp é manual.", flush=True)
    print("Para encerrar, feche esta janela ou pressione Ctrl+C.\n", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        print("\nAchadinhos encerrado. Suas ofertas continuam salvas.", flush=True)
    finally:
        stop.set()
        server.server_close()
        server.webhook.close()
        worker.join(timeout=2)
    return 0


if __name__ == "__main__":
    if sys.version_info < (3, 10):
        sys.exit("O Achadinhos precisa do Python 3.10 ou mais recente.")
    raise SystemExit(main())
