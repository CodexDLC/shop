import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import pytest

from workers.tasks.inventory_expiry import inventory_expiry, send_expiry, validate_url

TOKEN = 'x' * 32
URL = 'http://127.0.0.1:8000/internal/inventory/expiry/'


@pytest.mark.asyncio
async def test_disabled_never_calls_http(monkeypatch):
    monkeypatch.delenv('INVENTORY_EXPIRY_ENABLED', raising=False)
    with patch('workers.tasks.inventory_expiry.send_expiry') as send:
        await inventory_expiry({})
    send.assert_not_called()


@pytest.mark.parametrize('url', [
    'http://example.com/internal/inventory/expiry/', 'https://user:pass@example.com/internal/inventory/expiry/',
    'https://example.com/internal/inventory/expiry/?x=1', 'https://example.com/other',
    'https://example.com:invalid/internal/inventory/expiry/',
])
def test_reject_unsafe_urls(url):
    with pytest.raises(ValueError):
        validate_url(url)


@pytest.mark.asyncio
async def test_failure_is_not_swallowed(monkeypatch):
    monkeypatch.setenv('INVENTORY_EXPIRY_ENABLED', '1')
    monkeypatch.setenv('INVENTORY_EXPIRY_URL', URL)
    monkeypatch.setenv('INVENTORY_EXPIRY_TOKEN', TOKEN)
    with patch('workers.tasks.inventory_expiry.send_expiry', side_effect=RuntimeError('unsafe secret')):
        with pytest.raises(RuntimeError, match='inventory expiry request failed'):
            await inventory_expiry({})


def test_real_loopback_transport_auth_body_redirect_and_limit(monkeypatch):
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append((self.path, self.headers.get('Authorization'), self.rfile.read(int(self.headers['Content-Length']))))
            if len(requests) == 2:
                self.send_response(302)
                self.send_header('Location', f'http://127.0.0.1:{self.server.server_port}/redirected')
                self.end_headers()
            else:
                self.send_response(200)
                self.end_headers()
                body = b'x' * 8193 if len(requests) == 3 else json.dumps(
                    {'scanned': 1, 'expired': 1, 'skipped': 0, 'has_more': False}).encode()
                self.wfile.write(body)
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f'http://127.0.0.1:{server.server_port}/internal/inventory/expiry/'
        monkeypatch.setenv('http_proxy', 'http://127.0.0.1:1')
        assert send_expiry(url, TOKEN)['expired'] == 1
        with pytest.raises(Exception):
            send_expiry(url, TOKEN)
        with pytest.raises(ValueError, match='response too large'):
            send_expiry(url, TOKEN)
        assert requests == [('/internal/inventory/expiry/', f'Bearer {TOKEN}', b'{}')] * 3
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_cron_opt_in_and_enabled_import_has_no_network():
    import os
    import subprocess
    import sys
    from pathlib import Path

    script = '''
import importlib.abc
import socket
import sys
class BlockDjango(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "django" or fullname.startswith("django."):
            raise AssertionError("Django import")
def block(*args, **kwargs):
    raise AssertionError("network during import")
socket.create_connection = block
socket.socket.connect = block
from workers.worker import WorkerSettings
assert len(WorkerSettings.cron_jobs) == 1
assert WorkerSettings.cron_jobs[0].run_at_startup is False
assert not any(n == "django" or n.startswith("django.") for n in sys.modules)
'''
    env = os.environ.copy()
    env['PYTHONPATH'] = str(Path(__file__).resolve().parents[2] / 'src')
    env['INVENTORY_EXPIRY_ENABLED'] = '1'
    result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(('value', 'expected'), [('1', True), ('true', False), ('on', False), ('0', False), ('', False)])
def test_only_exact_opt_in(monkeypatch, value, expected):
    from workers.tasks.inventory_expiry import enabled
    monkeypatch.setenv('INVENTORY_EXPIRY_ENABLED', value)
    assert enabled() is expected


@pytest.mark.parametrize('payload', [
    {'scanned': 101, 'expired': 101, 'skipped': 0, 'has_more': False},
    {'scanned': 3, 'expired': 1, 'skipped': 1, 'has_more': False},
    {'scanned': 1, 'expired': True, 'skipped': 0, 'has_more': False},
])
def test_reject_invalid_summary(payload):
    class Response:
        def __enter__(self):
            self.chunks = iter([json.dumps(payload).encode(), b''])
            return self
        def __exit__(self, *args):
            pass
        def read1(self, size):
            return next(self.chunks)
    class Opener:
        def open(self, request, timeout):
            assert timeout == 8
            return Response()
    with patch('workers.tasks.inventory_expiry.build_opener', return_value=Opener()):
        with pytest.raises(ValueError, match='invalid response'):
            send_expiry(URL, TOKEN)


def test_drip_response_stops_at_total_deadline():
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read1(self, size):
            return b' '
    class Opener:
        def open(self, request, timeout):
            return Response()
    with patch('workers.tasks.inventory_expiry.build_opener', return_value=Opener()), \
            patch('workers.tasks.inventory_expiry.monotonic', side_effect=[0, 1, 2, 3, 8]):
        with pytest.raises(TimeoutError, match='deadline'):
            send_expiry(URL, TOKEN)
