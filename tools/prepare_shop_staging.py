"""Create fresh, ignored staging credentials without printing secret values."""
import json
import secrets
from pathlib import Path

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]


def prepare():
    folder = ROOT / ".local" / "staging"
    outputs = [folder / ".env.staging", folder / "access.json", folder / "access.txt"]
    if any(path.exists() for path in outputs):
        raise SystemExit("Staging credentials already exist; refusing to rotate or overwrite them.")
    local = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            local[key.strip()] = value.strip().strip("\"'")
    token = secrets.token_hex(32)
    access = {"username": "shop-preview", "password": secrets.token_urlsafe(24),
              "verification_token": token,
              "endpoint": "https://shop.pinlite.dev/integrations/ebay/account-deletion/"}
    env = {"SHOP_ENV_FILE": "/srv/shop/shared/.env.staging", "SHOP_RELEASE": "staging-initial",
           "DJANGO_SECRET_KEY": secrets.token_urlsafe(64), "POSTGRES_DB": "shop_staging",
           "POSTGRES_USER": "shop_staging", "POSTGRES_PASSWORD": secrets.token_hex(24),
           "SHOP_MFA_ENCRYPTION_KEYS": Fernet.generate_key().decode(),
           "EBAY_APP_ID": local.get("EBAY_APP_ID", ""), "EBAY_CERT_ID": local.get("EBAY_CERT_ID", ""),
           "EBAY_NOTIFICATION_VERIFICATION_TOKEN": token}
    if any("\n" in value or "\r" in value or "$" in value for value in env.values()):
        raise SystemExit("Unexpected newline/interpolation characters in environment; nothing written.")
    folder.mkdir(parents=True, exist_ok=True)
    outputs[0].write_text("\n".join(key + "=" + value for key, value in env.items()) + "\n", encoding="utf-8")
    outputs[1].write_text(json.dumps(access, indent=2), encoding="utf-8")
    outputs[2].write_text(
        "Site: https://shop.pinlite.dev/\nBasic Auth username: " + access["username"]
        + "\nBasic Auth password: " + access["password"]
        + "\n\neBay notification endpoint: " + access["endpoint"]
        + "\neBay verification token (not Client Secret): " + token
        + "\n\nThese are private staging credentials. Never commit or publish them.\n",
        encoding="utf-8",
    )
    for path in outputs:
        path.chmod(0o600)
    print("Fresh staging credentials saved under .local/staging; no secrets printed.")


if __name__ == "__main__":
    prepare()
