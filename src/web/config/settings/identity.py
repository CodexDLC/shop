import os

AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend", "allauth.account.auth_backends.AuthenticationBackend"]
ACCOUNT_ADAPTER = "web.identity.account_adapter.ShopAccountAdapter"
ACCOUNT_LOGIN_METHODS = {"email", "username"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGIN_ON_PASSWORD_RESET = False
ACCOUNT_LOGOUT_ON_PASSWORD_CHANGE = True
ACCOUNT_RATE_LIMITS = {"login": "20/m/ip", "login_failed": "10/m/ip,5/5m/key", "reset_password": "10/m/ip,3/10m/key"}
ACCOUNT_REAUTHENTICATION_TIMEOUT = 300
ACCOUNT_SESSION_REMEMBER = False
ACCOUNT_EMAIL_SUBJECT_PREFIX = "[Männermasche] "
MFA_ADAPTER = "web.identity.mfa_adapter.ShopMFAAdapter"
MFA_SUPPORTED_TYPES = ["totp", "recovery_codes"]
MFA_FORMS = {"activate_totp": "web.identity.activation_form.VerifiedTOTPActivationForm"}
MFA_TOTP_ISSUER = "Männermasche"
MFA_TRUST_ENABLED = False
MFA_RECOVERY_CODES_SHOW_ONCE = True
MFA_ALLOW_UNVERIFIED_EMAIL = False
MFA_TOTP_INSECURE_BYPASS_CODE = ""
SHOP_STAFF_MFA_REQUIRED = True
SHOP_STAFF_MFA_MAX_AGE = 8 * 60 * 60
SHOP_MFA_ENCRYPTION_KEYS = [key.strip() for key in os.environ.get("SHOP_MFA_ENCRYPTION_KEYS", "").split(",") if key.strip()]
LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "customer:overview"
LOGOUT_REDIRECT_URL = "account_login"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_AGE = 8 * 60 * 60
CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache",
                       "LOCATION": os.environ.get("REDIS_URL", "redis://127.0.0.1:5544/0"), "KEY_PREFIX": "inet-mag-auth"}}
LOGGING = {
    "version": 1, "disable_existing_loggers": False,
    "filters": {"auth_redaction": {"()": "web.identity.auth_log_filter.AuthLogFilter"}},
    "handlers": {"auth_console": {"class": "logging.StreamHandler", "filters": ["auth_redaction"]}},
    "loggers": {
        "django.server": {"handlers": ["auth_console"], "level": "INFO", "propagate": False},
        "django.request": {"handlers": ["auth_console"], "level": "WARNING", "propagate": False},
        "django.security.csrf": {"handlers": ["auth_console"], "level": "WARNING", "propagate": False},
    },
}
