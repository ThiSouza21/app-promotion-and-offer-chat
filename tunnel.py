#!/usr/bin/env python3
"""Iniciador Linux para túnel HTTPS de teste, somente para a porta do webhook."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import signal
import subprocess
import sys
from urllib.request import urlopen, build_opener, ProxyHandler

from automation import _write_json

ROOT = Path(__file__).resolve().parent
VERSION = '2026.10.7'
# SHA-256 publicados na release oficial, conferidos em 08/11/2026:
# https://github.com/cloudflare/cloudflared/releases/tag/2026.10.7
CHECKSUMS = {
    'x86_64': ('amd64', '1f99fb518b83dec2ba8d870a7cc991d82a77e6196295a3d2754ba17ab9f91872'),
    'aarch64': ('arm64', '3df43aedc9ff291d1735b5cb576cb97e0b157488796db2e32b28aecabb445775'),
}


def callback_origin(line):
    # Mensagens de erro também mencionam api.trycloudflare.com; não é um callback.
    if any(word in line.lower() for word in ('error', 'failed', ' err ')):
        return None
    match = re.search(r'https://([a-z0-9-]+)\.trycloudflare\.com(?:\s|\||$)', line)
    if match and match[1] not in {'api', 'www'}:
        return 'https://' + match[1] + '.trycloudflare.com'
    return None


def ensure_binary(directory):
    if platform.system() != 'Linux' or platform.machine() not in CHECKSUMS:
        raise ValueError('Este iniciador HTTPS suporta Linux x86_64 e ARM64. Use um túnel próprio em outros sistemas.')
    arch, digest = CHECKSUMS[platform.machine()]
    directory.mkdir(parents=True, exist_ok=True)
    binary = directory / ('cloudflared-' + VERSION + '-' + arch)
    if binary.exists() and hashlib.sha256(binary.read_bytes()).hexdigest() == digest:
        binary.chmod(0o700)
        return binary
    temporary = directory / (binary.name + '.part')
    print('Baixando o conector oficial Cloudflare; a integridade será conferida antes de executar.', flush=True)
    try:
        with urlopen(f'https://github.com/cloudflare/cloudflared/releases/download/{VERSION}/cloudflared-linux-{arch}', timeout=30) as source, temporary.open('wb') as target:
            size = 0
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                if size > 150 * 1024 * 1024:
                    raise ValueError('Download maior que o esperado.')
                target.write(chunk)
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != digest:
            raise ValueError('A verificação SHA-256 falhou. O arquivo não será executado.')
        temporary.chmod(0o700)
        temporary.replace(binary)
    finally:
        temporary.unlink(missing_ok=True)
    return binary


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-port', type=int, default=8765)
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data')
    args = parser.parse_args()
    opener = build_opener(ProxyHandler({}))
    base = f'http://127.0.0.1:{args.app_port}'
    with opener.open(base + '/api/health', timeout=3) as response:
        health = json.load(response)
    expected = hashlib.sha256(str(args.data_dir.resolve()).encode()).hexdigest()
    if health.get('app') != 'achadinhos' or health.get('instance_key') != expected:
        raise ValueError('O programa aberto pertence a outra pasta. Feche a cópia anterior e abra esta pasta.')
    with opener.open(base + '/api/webhook/state', timeout=3) as response:
        state = json.load(response)
    if not state.get('listening') or not isinstance(state.get('port'), int):
        raise ValueError('Abra a versão atualizada do aplicativo antes do túnel.')
    state_file = args.data_dir / 'tunnel.json'
    if platform.system() != 'Linux':
        raise ValueError('Este iniciador é para Linux.')
    import fcntl
    lock_file = (args.data_dir / 'tunnel.lock').open('a')
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_file.close()
        raise ValueError('Já existe um túnel aberto nesta pasta. Use a janela existente.') from None
    def terminate(*args):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGHUP, terminate)
    process = None
    try:
        state_file.unlink(missing_ok=True)
        binary = ensure_binary(ROOT / 'tools')
        process = subprocess.Popen([str(binary), '--no-autoupdate', 'tunnel', '--url', f"http://127.0.0.1:{state['port']}", '--protocol', 'http2'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        print('Mantenha esta janela e o aplicativo abertos. O túnel encaminha somente o receptor de webhook.', flush=True)
        for line in process.stdout:
            url = callback_origin(line)
            if url:
                _write_json(state_file, {'url': url})
                print('\nURL de callback: ' + url + '/webhooks/whatsapp', flush=True)
                print('No painel, abra Webhooks → Atualizar eventos e URL. A URL gerada não garante conexão: valide-a na Meta.', flush=True)
            elif any(word in line for word in ('ERR', 'failed', 'error')):
                print(line.strip(), flush=True)
        if process.wait() != 0:
            raise ValueError('O túnel não conseguiu conectar. Confira internet/firewall e as mensagens acima.')
    except KeyboardInterrupt:
        print('\nTúnel encerrado.', flush=True)
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        state_file.unlink(missing_ok=True)
        lock_file.close()


if __name__ == '__main__':
    try:
        run()
    except (OSError, ValueError) as exc:
        print('Não foi possível abrir o webhook HTTPS: ' + str(exc), file=sys.stderr)
        print('Abra o aplicativo primeiro. Se necessário, confira WEBHOOKS.md.', file=sys.stderr)
        sys.exit(1)
