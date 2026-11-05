import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest

spec = importlib.util.spec_from_file_location(
    "inventory_postgres_runner", Path(__file__).resolve().parents[1] / "tools/test_inventory_postgres.py",
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.mark.parametrize("name", ["inet_mag", "postgres", "test_inet_inventory_existing", "test_other"])
def test_runner_refuses_nonisolated_database_names(name):
    with pytest.raises(RuntimeError):
        runner.validate_target(name, "inet_mag")


def test_runner_rejects_working_name_even_if_it_has_test_shape():
    name = "test_inet_inventory_" + "a" * 32
    with pytest.raises(RuntimeError):
        runner.validate_target(name, name)
    runner.validate_target(name, "inet_mag")


@pytest.mark.parametrize("host", ["postgres", "192.0.2.1", "db.example.test"])
def test_runner_refuses_nonlocal_hosts_without_network(monkeypatch, host):
    root = MagicMock()
    (root / ".env").is_file.return_value = False
    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setenv("POSTGRES_HOST", host)
    monkeypatch.setenv("POSTGRES_PASSWORD", "test-only")
    with pytest.raises(RuntimeError):
        runner.load_connection()


def test_runner_does_not_accept_test_target_overrides(monkeypatch):
    monkeypatch.setattr(runner.sys, "argv", ["test_inventory_postgres.py", "--reuse-db"])
    with pytest.raises(RuntimeError):
        runner.main()
