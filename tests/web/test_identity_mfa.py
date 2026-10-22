import time
from urllib.parse import parse_qs, urlsplit

import pytest
from allauth.account.forms import default_token_generator
from allauth.account.models import EmailAddress
from allauth.account.utils import user_pk_to_url_str
from allauth.mfa.models import Authenticator
from allauth.mfa.recovery_codes.internal.auth import RecoveryCodes
from allauth.mfa.totp.internal.auth import (
    TOTP,
    format_hotp_value,
    generate_totp_secret,
    hotp_value,
)
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse

from web.identity.mfa_adapter import ShopMFAAdapter
from web.staff.models import CabinetPreferences

pytestmark = pytest.mark.django_db
PASSWORD = "test-only-valid-long-password"


@pytest.fixture(autouse=True)
def require_staff_mfa(settings):
    settings.SHOP_STAFF_MFA_REQUIRED = True
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    settings.MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    cache.clear()
    yield
    cache.clear()


def user(*, name="owner", staff=True, verified=True):
    account = get_user_model().objects.create_user(
        username=name, email=f"{name}@example.test", password=PASSWORD,
        is_staff=staff, is_superuser=staff,
    )
    if verified:
        EmailAddress.objects.create(user=account, email=account.email, primary=True, verified=True)
    return account


def totp(account):
    return TOTP.activate(account, generate_totp_secret()).instance


def record(client, auth, *, at=None, auth_type=None):
    session = client.session
    session["account_authentication_methods"] = [{
        "method": "mfa", "id": auth.pk,
        "type": auth_type or auth.type, "at": time.time() if at is None else at,
    }]
    session.save()


def assert_redirect(response, name):
    assert response.status_code == 302
    assert urlsplit(response.url).path == reverse(name)


def test_anonymous_staff_and_admin_use_common_login(client):
    assert_redirect(client.get(reverse("staff:home")), "account_login")
    response = client.get(reverse("admin:index"))
    assert_redirect(response, "admin:login")
    assert_redirect(client.get(response.url), "account_login")


@pytest.mark.parametrize("verified_row", [False, True])
def test_unverified_staff_must_verify_email_before_enrollment(client, verified_row):
    account = user(verified=False)
    if verified_row:
        EmailAddress.objects.create(user=account, email=account.email, verified=False)
    client.force_login(account)
    assert_redirect(client.get(reverse("staff:home")), "account_email")


def test_verified_staff_without_device_redirects_to_enrollment(client):
    client.force_login(user())
    response = client.get(reverse("staff:home"))
    assert_redirect(response, "mfa_activate_totp")
    assert parse_qs(urlsplit(response.url).query)["next"] == [reverse("staff:home")]


def test_password_only_session_requires_mfa_in_staff_and_admin(client):
    account = user()
    totp(account)
    client.force_login(account)
    for endpoint in ("staff:home", "admin:index", "admin:login"):
        assert_redirect(client.get(reverse(endpoint)), "mfa_reauthenticate")


@pytest.mark.parametrize("kind", ["totp", "recovery_codes"])
def test_current_owned_mfa_record_grants_staff_and_admin(client, kind):
    account = user()
    auth = totp(account)
    if kind == "recovery_codes":
        auth = RecoveryCodes.activate(account).instance
    client.force_login(account)
    record(client, auth)
    assert client.get(reverse("staff:home")).status_code == 200
    assert client.get(reverse("admin:index")).status_code == 200


@pytest.mark.parametrize("invalid", ["foreign", "deleted", "expired", "future", "wrong_type"])
def test_invalid_mfa_records_cannot_authorize_staff(client, settings, invalid):
    account = user()
    auth = totp(account)
    client.force_login(account)
    if invalid == "foreign":
        auth = totp(user(name="other"))
    record(client, auth,
           at=(time.time() - settings.SHOP_STAFF_MFA_MAX_AGE - 5 if invalid == "expired"
               else time.time() + 60 if invalid == "future" else None),
           auth_type="recovery_codes" if invalid == "wrong_type" else None)
    if invalid == "deleted":
        auth.delete()
        totp(account)
    assert_redirect(client.get(reverse("staff:home")), "mfa_reauthenticate")


def test_post_without_mfa_never_changes_staff_settings(client):
    account = user()
    totp(account)
    client.force_login(account)
    response = client.post(reverse("staff:settings"), {"links": []})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "auth.mfa_required"
    assert not CabinetPreferences.objects.exists()


def test_staff_promotion_does_not_reuse_customer_password_session(client):
    account = user(staff=False)
    client.force_login(account)
    account.is_staff = True
    account.save(update_fields=["is_staff"])
    assert_redirect(client.get(reverse("staff:home")), "mfa_activate_totp")


def test_authenticator_secret_is_encrypted_and_roundtrips():
    account = user()
    secret = generate_totp_secret()
    auth = TOTP.activate(account, secret).instance
    auth.refresh_from_db()
    assert secret not in str(auth.data)
    assert ShopMFAAdapter().decrypt(auth.data["secret"]) == secret


def test_staff_can_deactivate_own_authenticator_via_allauth(client):
    account = user()
    auth = totp(account)
    client.force_login(account)
    record(client, auth)
    assert ShopMFAAdapter().can_delete_authenticator(auth)
    response = client.post(reverse("mfa_deactivate_totp"))
    assert response.status_code == 302
    assert not Authenticator.objects.filter(pk=auth.pk).exists()


def test_real_recovery_code_is_accepted_only_once():
    account = user()
    totp(account)
    recovery = RecoveryCodes.activate(account)
    code = recovery.get_unused_codes()[0]
    assert recovery.validate_code(code)
    assert not RecoveryCodes(Authenticator.objects.get(pk=recovery.instance.pk)).validate_code(code)


def test_password_login_requires_real_mfa_code_before_staff_access(client):
    account = user()
    auth = totp(account)
    response = client.post(reverse("account_login"), {
        "login": account.email, "password": PASSWORD,
        "next": reverse("staff:home"),
    })
    assert_redirect(response, "mfa_authenticate")
    assert "_auth_user_id" not in client.session
    secret = ShopMFAAdapter().decrypt(auth.data["secret"])
    code = format_hotp_value(hotp_value(secret, int(time.time()) // 30))
    response = client.post(reverse("mfa_authenticate"), {"code": code})
    assert response.status_code == 302
    assert client.session["_auth_user_id"] == str(account.pk)
    assert client.get(reverse("staff:home")).status_code == 200


def test_real_password_reset_keeps_authenticator_and_requires_mfa_on_next_login(client):
    account = user()
    auth = totp(account)
    token = default_token_generator.make_token(account)
    reset_url = reverse("account_reset_password_from_key", kwargs={
        "uidb36": user_pk_to_url_str(account), "key": token,
    })
    response = client.get(reset_url)
    assert response.status_code == 302
    changed_password = "another-test-only-long-password"
    response = client.post(response.url, {
        "password1": changed_password, "password2": changed_password,
    })
    assert response.status_code == 302
    account.refresh_from_db()
    assert account.check_password(changed_password)
    assert Authenticator.objects.filter(pk=auth.pk, user=account).exists()
    assert "_auth_user_id" not in client.session
    response = client.post(reverse("account_login"), {
        "login": account.email, "password": changed_password,
    })
    assert_redirect(response, "mfa_authenticate")


def test_customer_cannot_gain_staff_access_even_with_valid_mfa(client):
    account = user(staff=False)
    auth = totp(account)
    client.force_login(account)
    record(client, auth)
    assert client.get(reverse("staff:home")).status_code == 403


def test_enrollment_creates_encrypted_device_and_requires_explicit_mfa_reauthentication(client):
    account = user()
    client.force_login(account)
    session = client.session
    session["account_authentication_methods"] = [{"method": "password", "at": time.time()}]
    session.save()
    response = client.get(reverse("mfa_activate_totp"))
    assert response.status_code == 200
    secret = client.session["mfa.totp.secret"]
    code = format_hotp_value(hotp_value(secret, int(time.time()) // 30))
    response = client.post(reverse("mfa_activate_totp"), {"code": code})
    assert response.status_code == 302
    auth = Authenticator.objects.get(user=account, type=Authenticator.Type.TOTP)
    assert auth.data["secret"] != secret
    assert Authenticator.objects.filter(user=account, type=Authenticator.Type.RECOVERY_CODES).exists()
    assert_redirect(client.get(reverse("staff:home")), "mfa_reauthenticate")


def test_direct_enrollment_post_cannot_bypass_missing_verified_email(client):
    account = user(verified=False)
    client.force_login(account)
    session = client.session
    session["account_authentication_methods"] = [{"method": "password", "at": time.time()}]
    session.save()
    response = client.get(reverse("mfa_activate_totp"))
    assert response.status_code == 200
    secret = client.session["mfa.totp.secret"]
    code = format_hotp_value(hotp_value(secret, int(time.time()) // 30))
    response = client.post(reverse("mfa_activate_totp"), {"code": code})
    assert response.status_code == 200
    assert response.context["form"].errors.as_data()["code"][0].code == "unverified_email"
    assert not Authenticator.objects.filter(user=account).exists()


def test_default_mfa_policy_is_voluntary():
    from web.config.settings.identity import SHOP_STAFF_MFA_REQUIRED
    assert SHOP_STAFF_MFA_REQUIRED is False


@pytest.mark.parametrize('endpoint', ['staff:home', 'admin:index'])
def test_optional_mfa_does_not_require_enrollment_for_staff(client, settings, endpoint):
    settings.SHOP_STAFF_MFA_REQUIRED = False
    account = user()
    client.force_login(account)
    response = client.get(reverse(endpoint))
    assert response.status_code == 200
    assert not Authenticator.objects.filter(user=account).exists()
