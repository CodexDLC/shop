import os
import subprocess
import sys
from pathlib import Path

import pytest

from workers.lifecycle import worker_shutdown, worker_startup
from workers.tasks import engine_status


@pytest.mark.asyncio
async def test_diagnostic_task_lifecycle():
    ctx = {}
    await worker_startup(ctx)
    result = await engine_status(ctx)
    assert result["payments_enabled"] is False
    assert result["ebay_write_enabled"] is False
    await worker_shutdown(ctx)
    assert "engine" not in ctx


def test_worker_import_is_independent_of_django_and_network():
    script = """
import importlib.abc
import socket
import sys

class BlockDjango(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'django' or fullname.startswith('django.'):
            raise AssertionError('Django import: ' + fullname)

def block_network(*args, **kwargs):
    raise AssertionError('network access during import')

sys.meta_path.insert(0, BlockDjango())
socket.create_connection = block_network
socket.socket.connect = block_network
from workers.worker import WorkerSettings
assert WorkerSettings.queue_name == 'inet_mag:arq'
assert WorkerSettings.redis_settings.host == 'example.invalid'
assert WorkerSettings.redis_settings.port == 6380
assert WorkerSettings.redis_settings.database == 3
assert not any(n == 'django' or n.startswith('django.') for n in sys.modules)
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
    env["REDIS_URL"] = "redis://example.invalid:6380/3"
    result = subprocess.run(
        [sys.executable, "-c", script], env=env,
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
