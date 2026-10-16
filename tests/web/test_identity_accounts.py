import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db
PASSWORD = "Long-Unique-Example-Password!928"


@pytest.fixture(autouse=True)
def clear_auth_cache():
    cache.clear()


def account(*, verified=True):
    user = get_user_model().objects.create_user(username="customer-auth", email="customer@example.test", password=PASSWORD)
    EmailAddress.objects.create(user=user, email=user.email, verified=verified, primary=True)
    return user


def test_login_uses_real_site_template_and_csrf(client):
    response = client.get(reverse("account_login"))
    assert response.status_code == 200
    html = response.content.decode()
    assert 'data-real-auth="true"' in html
    assert 'name="csrfmiddlewaretoken"' in html
    assert 'name="login"' in html
    assert "triggerSubmitValidation" not in html
    assert "AtelierKuratierung2025" not in html
    assert "no-store" in response["Cache-Control"]
    assert response["Referrer-Policy"] == "same-origin"
    assert Client(enforce_csrf_checks=True).post(reverse("account_login"), {}).status_code == 403


def test_verified_customer_login_and_own_overview(client):
    user = account()
    response = client.post(reverse("account_login"), {"login": user.email, "password": PASSWORD})
    assert response.status_code == 302
    assert response.url == reverse("customer:overview")
    response = client.get(response.url)
    assert user.email in response.content.decode()
    assert reverse("staff:home") not in response.content.decode()
    assert reverse("mfa_index") in response.content.decode()


def test_unverified_email_does_not_authenticate(client):
    user = account(verified=False)
    response = client.post(reverse("account_login"), {"login": user.email, "password": PASSWORD})
    assert response.status_code == 302
    assert "_auth_user_id" not in client.session
    assert mail.outbox


def test_registration_never_grants_staff_or_implicitly_confirms_email(client):
    response = client.post(reverse("account_signup"), {
        "email": "new@example.test", "password1": PASSWORD, "password2": PASSWORD,
        "is_staff": "true", "is_superuser": "true",
    })
    assert response.status_code == 302
    user = get_user_model().objects.get(email="new@example.test")
    assert not user.is_staff and not user.is_superuser
    assert not EmailAddress.objects.get(user=user).verified
    assert "_auth_user_id" not in client.session
    assert mail.outbox


def test_external_next_is_rejected_and_customer_cannot_enter_staff(client):
    user = account()
    response = client.post(reverse("account_login"), {
        "login": user.email, "password": PASSWORD, "next": "//example.invalid/",
    })
    assert response.status_code == 302
    assert response.url == reverse("customer:overview")
    assert client.get(reverse("staff:home")).status_code == 403


def test_password_reset_does_not_disclose_account_existence(client):
    user = account()
    actual = client.post(reverse("account_reset_password"), {"email": user.email})
    absent = client.post(reverse("account_reset_password"), {"email": "absent@example.test"})
    assert actual.status_code == absent.status_code == 302
    assert actual.url == absent.url
    assert "_auth_user_id" not in client.session


def test_legacy_entries_redirect_to_common_login(client):
    for name in ("staff:login", "customer:login", "customer:login_mobile"):
        response = client.get(reverse(name))
        assert response.status_code == 302
        assert response.url == reverse("account_login")


def test_login_rate_limit_is_active(client, settings):
    settings.ACCOUNT_RATE_LIMITS = {"login": "2/m/ip"}
    results = [client.post(reverse("account_login"), {"login": "unknown@example.test", "password": PASSWORD})
               for _ in range(3)]
    assert results[-1].status_code == 429


def test_dev_access_log_redacts_auth_tokens():
    import logging

    from web.identity.auth_log_filter import AuthLogFilter

    record = logging.LogRecord("django.server", logging.INFO, "", 0, "%s %s", (
        "GET /ru/accounts/password/reset/key/private-token/?next=/konto/ HTTP/1.1", 200,
    ), None)
    assert AuthLogFilter().filter(record)
    assert "private-token" not in record.getMessage()
    assert "/ru/accounts/[redacted]" in record.getMessage()
