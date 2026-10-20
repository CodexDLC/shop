import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[4]
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = False
ALLOWED_HOSTS = [host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host.strip()]
INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "codex_django.cabinet", "web.shop.apps.ShopConfig",
    "web.localization.apps.LocalizationConfig", "web.catalog.apps.CatalogConfig",
    "web.cart.apps.CartConfig", "web.orders.apps.OrdersConfig", "web.payments.apps.PaymentsConfig",
    "web.customer.apps.CustomerConfig", "web.support.apps.SupportConfig", "web.wishlist.apps.WishlistConfig",
    "web.staff.apps.StaffConfig",
    "web.identity.apps.IdentityConfig", "allauth", "allauth.account", "allauth.mfa",
    "web.ebay_notifications.apps.EbayNotificationsConfig",
    "web.ebay_oauth.apps.EbayOAuthConfig",
]
MIDDLEWARE = [
    "web.ebay_oauth.middleware.OAuthPrivacyMiddleware",
    "django.middleware.security.SecurityMiddleware", "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware",
    "allauth.account.middleware.AccountMiddleware", "web.identity.mfa_guard_middleware.MFAGuardMiddleware",
    "web.identity.auth_headers_middleware.AuthHeadersMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "web.config.urls"
WSGI_APPLICATION = "web.config.wsgi.application"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "src" / "web" / "customer" / "templates", BASE_DIR / "src" / "web" / "templates"], "APP_DIRS": True,
              "OPTIONS": {"context_processors": ["django.template.context_processors.request",
                 "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages",
                 "web.staff.context_processors.staff_cabinet", "web.identity.context_processors.auth_context"]}}]
DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql",
    "NAME": os.environ.get("POSTGRES_DB", "inet_mag"), "USER": os.environ.get("POSTGRES_USER", "inet_mag"),
    "PASSWORD": os.environ["POSTGRES_PASSWORD"], "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
    "PORT": os.environ.get("POSTGRES_PORT", "5432"), "CONN_MAX_AGE": 60}}
AUTH_PASSWORD_VALIDATORS = [{"NAME": "django.contrib.auth.password_validation." + name} for name in (
    "UserAttributeSimilarityValidator", "MinimumLengthValidator", "CommonPasswordValidator", "NumericPasswordValidator")]
LANGUAGE_CODE = "de"
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
LANGUAGES = [("de", "Deutsch"), ("ru", "Русский")]
LOCALE_PATHS = [BASE_DIR / "src" / "web" / "localization" / "locale"]
USE_TZ = True
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "src" / "web" / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"
STORAGES = {"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}
# Local storage is only for development. S3 wiring follows with media import.
MEDIA_ROOT = BASE_DIR / "media"
LOGIN_URL = "staff:login"
LOGIN_REDIRECT_URL = "staff:home"
LOGOUT_REDIRECT_URL = "staff:login"
CODEX_CABINET_SPACES = {"staff": {"prefixes": ("/staff/",), "default_module": "overview", "settings_url_name": "staff:settings"}}
from .identity import *  # noqa: E402,F403

# Notification verification may only authenticate and read eBay public keys.
EBAY_APP_ID = os.environ.get("EBAY_APP_ID", "")
EBAY_CERT_ID = os.environ.get("EBAY_CERT_ID", "")
EBAY_OAUTH_RUNAME = os.environ.get("EBAY_OAUTH_RUNAME", "")
EBAY_OAUTH_BASE_URL = os.environ.get("EBAY_OAUTH_BASE_URL", "https://shop.pinlite.dev")
EBAY_OAUTH_ENCRYPTION_KEYS = os.environ.get("EBAY_OAUTH_ENCRYPTION_KEYS", "")
EBAY_NOTIFICATION_ENDPOINT = os.environ.get("EBAY_NOTIFICATION_ENDPOINT", "")
EBAY_NOTIFICATION_VERIFICATION_TOKEN = os.environ.get("EBAY_NOTIFICATION_VERIFICATION_TOKEN", "")
