"""Run Django against this checkout's .env without printing its secrets."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    env_file = ROOT / '.env'
    if not env_file.exists():
        raise SystemExit('Create a local .env from .env.example first.')
    for line in env_file.read_text(encoding='utf-8-sig').splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip())
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.config.settings.local')
    sys.path.insert(0, str(ROOT / 'src'))
    from django.core.management import execute_from_command_line

    execute_from_command_line([str(ROOT / 'manage.py'), *sys.argv[1:]])
