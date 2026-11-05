"""Run inventory adapter and race tests in a fresh, disposable local PostgreSQL database.

No arguments: no --reuse-db/--keepdb, settings overrides, external host or existing database target.
Only PostgreSQL connection variables are loaded from .env; no provider secrets are loaded.
"""
import os
import re
import sys
import uuid
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
CONNECTION_KEYS = {"POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB"}


def load_connection():
    env_file = ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                if key.strip() in CONNECTION_KEYS:
                    os.environ.setdefault(key.strip(), value.strip())
    host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    if host not in {"127.0.0.1", "localhost", "::1"} or not os.environ.get("POSTGRES_PASSWORD"):
        raise RuntimeError("Inventory PostgreSQL tests require explicit local credentials; remote hosts refused.")
    return {"host": host, "port": os.environ.get("POSTGRES_PORT", "5432"),
            "user": os.environ.get("POSTGRES_USER", "inet_mag"),
            "password": os.environ["POSTGRES_PASSWORD"], "dbname": "postgres", "connect_timeout": 5}


def validate_target(name, working_name):
    if not re.fullmatch(r"test_inet_inventory_[0-9a-f]{32}", name) or name == working_name:
        raise RuntimeError("Refusing a non-isolated database target.")


def main():
    if len(sys.argv) != 1:
        raise RuntimeError("This isolated runner accepts no arguments.")
    connection_values = load_connection()
    name = "test_inet_inventory_" + uuid.uuid4().hex
    validate_target(name, os.environ.get("POSTGRES_DB"))
    from psycopg import sql

    # Refuse even an extraordinarily unlikely UUID collision rather than reusing someone else's database.
    with psycopg.connect(**connection_values, autocommit=True) as connection:
        if connection.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone():
            raise RuntimeError("The generated test database already exists; refusing to reuse it.")
    os.environ["INVENTORY_POSTGRES_TESTS"] = "1"
    os.environ["INVENTORY_TEST_DB_NAME"] = name
    os.environ["DJANGO_SETTINGS_MODULE"] = "web.config.settings.test_postgres"
    os.environ.pop("PYTEST_ADDOPTS", None)
    sys.path.insert(0, str(ROOT / "src"))
    os.chdir(ROOT)
    import pytest

    print("Inventory PostgreSQL tests: fresh isolated database; working database is not a test target.")
    try:
        return pytest.main(["-q", "--ds=web.config.settings.test_postgres",
                            "tests/web/test_inventory_accounting.py",
                            "tests/web/test_inventory_reservations.py",
                            "tests/web/test_inventory_expiry.py",
                            "tests/web/test_inventory_expiry_endpoint.py",
                            "tests/web/test_inventory_expiry_http.py",
                            "tests/web/test_inventory_checkout.py",
                            "tests/web/test_inventory_checkout_notices.py",
                            "tests/web/test_inventory_availability.py",
                            "tests/web/test_staff_inventory.py",
                            "tests/web/test_inventory_final_contract.py",
                            "tests/postgres"])
    finally:
        from django.db import connections
        connections.close_all()
        # Only this fresh name is eligible for cleanup, even when the test runner exits early.
        validate_target(name, os.environ.get("POSTGRES_DB"))
        with psycopg.connect(**connection_values, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
        print("Disposable inventory test database removed.")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, psycopg.Error):
        # Do not expose a DSN, environment values or credential-bearing connection repr.
        raise SystemExit("Inventory PostgreSQL runner refused unsafe or unavailable configuration.") from None
