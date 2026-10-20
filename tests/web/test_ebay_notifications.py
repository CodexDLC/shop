import base64
import hashlib
import json
from unittest.mock import Mock

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.core.cache import cache
from django.db import DatabaseError
from django.test import Client, RequestFactory

from web.ebay_notifications.models import DeletionReceipt
from web.ebay_notifications.public_key_client import PublicKeyClient
from web.ebay_notifications.rejected import NotificationRejected
from web.ebay_notifications.views import AccountDeletionView

pytestmark = pytest.mark.django_db
ENDPOINT = "https://shop.pinlite.dev/integrations/ebay/account-deletion/"
TOKEN = "test-only-notification-token-0123456789"
PATH = "/integrations/ebay/account-deletion/"


@pytest.fixture(autouse=True)
def configuration(settings, monkeypatch):
    settings.EBAY_NOTIFICATION_ENDPOINT = ENDPOINT
    settings.EBAY_NOTIFICATION_VERIFICATION_TOKEN = TOKEN
    settings.EBAY_APP_ID = "test-app"
    settings.EBAY_CERT_ID = "test-secret"
    cache.clear()
    # Every test is offline, even if an implementation accidentally reaches the network.
    monkeypatch.setattr("http.client.HTTPSConnection", Mock(side_effect=AssertionError("network forbidden")))


@pytest.fixture
def signing_key(monkeypatch):
    private = ec.generate_private_key(ec.SECP256R1())
    pem = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    monkeypatch.setattr(PublicKeyClient, "get", lambda self, kid: {
        "algorithm": "ECDSA", "digest": "SHA1", "key": pem,
    })
    return private


def payload():
    return {
        "metadata": {"topic": "MARKETPLACE_ACCOUNT_DELETION", "schemaVersion": "1.0"},
        "notification": {
            "notificationId": "test-notification-001", "eventDate": "2026-10-16T10:00:00Z",
            "publishDate": "2026-10-16T10:00:01Z", "publishAttemptCount": 1,
            "data": {"userId": "test-immutable-user", "username": "private-user", "eiasToken": "private-token"},
        },
    }


def signature(private, body, **changes):
    envelope = {"alg": "ECDSA", "digest": "SHA1", "kid": "test-key",
                "signature": base64.b64encode(private.sign(body, ec.ECDSA(hashes.SHA1()))).decode()}
    envelope.update(changes)
    return base64.b64encode(json.dumps(envelope).encode()).decode()


def post(private, value=None, *, body=None, header=None):
    body = body if body is not None else json.dumps(value or payload(), separators=(",", ":")).encode()
    request = RequestFactory().post(
        PATH, data=body, content_type="application/json",
        HTTP_X_EBAY_SIGNATURE=header if header is not None else signature(private, body),
    )
    return AccountDeletionView.as_view()(request)


def test_challenge_uses_exact_configured_endpoint_not_request_host():
    request = RequestFactory().get(PATH, {"challenge_code": "abc"}, HTTP_HOST="attacker.invalid")
    response = AccountDeletionView.as_view()(request)
    assert response.status_code == 200
    assert json.loads(response.content) == {
        "challengeResponse": hashlib.sha256(("abc" + TOKEN + ENDPOINT).encode()).hexdigest()
    }
    assert response["X-Robots-Tag"] == "noindex, nofollow, noarchive"


@pytest.mark.parametrize("query", ["", "?challenge_code=", "?challenge_code=a&challenge_code=b",
                                  "?challenge_code=" + "a" * 1025])
def test_invalid_challenge(query):
    response = AccountDeletionView.as_view()(RequestFactory().get(PATH + query))
    assert response.status_code == 400


def test_challenge_does_not_need_app_credentials(settings):
    settings.EBAY_APP_ID = settings.EBAY_CERT_ID = ""
    assert AccountDeletionView.as_view()(RequestFactory().get(PATH, {"challenge_code": "a"})).status_code == 200


def test_missing_verification_configuration_fails_closed(settings):
    settings.EBAY_NOTIFICATION_VERIFICATION_TOKEN = ""
    assert AccountDeletionView.as_view()(RequestFactory().get(PATH, {"challenge_code": "a"})).status_code == 503


@pytest.mark.parametrize("token", [None, "a" * 31, "a" * 81, "not-allowed+" * 4])
def test_invalid_token_configuration_fails_closed(settings, token):
    settings.EBAY_NOTIFICATION_VERIFICATION_TOKEN = token
    assert AccountDeletionView.as_view()(RequestFactory().get(PATH, {"challenge_code": "a"})).status_code == 503


def test_valid_signed_receipt_is_durable_metadata_only(signing_key):
    response = post(signing_key)
    assert response.status_code == 200
    receipt = DeletionReceipt.objects.get()
    assert receipt.status == "review_required"
    assert receipt.notification_id == "test-notification-001"
    serialized = repr(DeletionReceipt.objects.values().get())
    for value in ("test-immutable-user", "private-user", "private-token"):
        assert value not in serialized
    assert len(receipt.user_fingerprint) == 64


def test_unsigned_request_rejected_before_key_fetch(monkeypatch):
    fetch = Mock(side_effect=AssertionError("must not fetch"))
    monkeypatch.setattr(PublicKeyClient, "get", fetch)
    request = RequestFactory().post(PATH, data=b"{}", content_type="application/json")
    assert AccountDeletionView.as_view()(request).status_code == 412
    fetch.assert_not_called()
    assert not DeletionReceipt.objects.exists()


@pytest.mark.parametrize("header", ["!notbase64", base64.b64encode(b"[]").decode(),
                                   base64.b64encode(b"{}").decode(), "a" * 8193])
def test_malformed_signature_rejected(signing_key, header):
    assert post(signing_key, header=header).status_code == 412


@pytest.mark.parametrize("change", [{"alg": "RSA"}, {"digest": "SHA256"}, {"kid": "../secrets"}])
def test_unsupported_algorithms_and_unsafe_key_ids_rejected(signing_key, change):
    body = json.dumps(payload()).encode()
    assert post(signing_key, body=body, header=signature(signing_key, body, **change)).status_code == 412


def test_raw_body_tamper_rejected(signing_key):
    body = json.dumps(payload()).encode()
    header = signature(signing_key, body)
    assert post(signing_key, body=body + b" ", header=header).status_code == 412
    assert not DeletionReceipt.objects.exists()


def test_duplicate_is_idempotent_but_conflicting_id_rejected(signing_key):
    assert post(signing_key).status_code == 200
    assert post(signing_key).status_code == 200
    changed = payload()
    changed["notification"]["publishAttemptCount"] = 2
    changed["notification"]["publishDate"] = "2026-10-16T10:02:01Z"
    assert post(signing_key, changed).status_code == 200
    changed["notification"]["data"]["userId"] = "different-person"
    assert post(signing_key, changed).status_code == 409
    assert DeletionReceipt.objects.count() == 1


def test_unexpected_topic_not_acknowledged(signing_key):
    value = payload()
    value["metadata"]["topic"] = "UNEXPECTED_TOPIC"
    assert post(signing_key, value).status_code == 400
    assert not DeletionReceipt.objects.exists()


def test_oversized_body_not_read_or_acknowledged():
    request = RequestFactory().post(PATH, data=b"x" * 65537, content_type="application/json")
    request.read = Mock(side_effect=AssertionError("body must not be read"))
    assert AccountDeletionView.as_view()(request).status_code == 413


def test_key_unavailable_returns_retryable_failure(signing_key, monkeypatch):
    monkeypatch.setattr(PublicKeyClient, "get", Mock(
        side_effect=NotificationRejected("ebay.verification_unavailable", 503)
    ))
    assert post(signing_key).status_code == 503
    assert not DeletionReceipt.objects.exists()


def test_db_failure_returns_retryable_failure(signing_key, monkeypatch):
    monkeypatch.setattr(DeletionReceipt.objects, "get_or_create", Mock(side_effect=DatabaseError))
    assert post(signing_key).status_code == 503


def test_public_key_client_fixed_origin_auth_and_one_hour_cache(monkeypatch):
    transport = Mock(side_effect=[{"access_token": "test-token", "expires_in": 7200},
                                  {"key": "test-pem", "algorithm": "ECDSA", "digest": "SHA1"}])
    monkeypatch.setattr(PublicKeyClient, "_request", transport)
    client = PublicKeyClient()
    assert client.get("key-01") == client.get("key-01")
    assert transport.call_count == 2
    assert transport.call_args_list[0].args[0:2] == ("POST", "/identity/v1/oauth2/token")
    assert transport.call_args_list[1].args[0:2] == ("GET", "/commerce/notification/v1/public_key/key-01")


def test_missing_credentials_fail_closed(settings):
    settings.EBAY_CERT_ID = ""
    with pytest.raises(NotificationRejected) as error:
        PublicKeyClient().get("key-01")
    assert error.value.status == 503


def test_key_fetch_does_not_follow_redirects(monkeypatch):
    response = Mock(status=302)
    response.read.return_value = b"{}"
    connection = Mock()
    connection.getresponse.return_value = response
    constructor = Mock(return_value=connection)
    monkeypatch.setattr("http.client.HTTPSConnection", constructor)
    with pytest.raises(NotificationRejected) as error:
        PublicKeyClient()._request("GET", "/commerce/notification/v1/public_key/key-01", {})
    assert error.value.status == 503
    constructor.assert_called_once()
    assert constructor.call_args.args == ("api.ebay.com",)
    assert constructor.call_args.kwargs["timeout"] == 5
    connection.request.assert_called_once()
    connection.close.assert_called_once()


@pytest.mark.parametrize("method,path", [
    ("POST", "/sell/inventory/v1/inventory_item"),
    ("DELETE", "/commerce/notification/v1/public_key/key-01"),
    ("GET", "/identity/v1/oauth2/token"),
    ("GET", "/commerce/notification/v1/public_key/../different"),
    ("GET", "https://other.example/commerce/notification/v1/public_key/key-01"),
])
def test_outbound_mutation_or_unapproved_path_never_opens_connection(monkeypatch, method, path):
    constructor = Mock(side_effect=AssertionError("network forbidden"))
    monkeypatch.setattr("http.client.HTTPSConnection", constructor)
    with pytest.raises(NotificationRejected) as error:
        PublicKeyClient()._request(method, path, {})
    assert error.value.code == "ebay.read_only_violation"
    constructor.assert_not_called()


def test_wired_endpoint_is_csrf_exempt_and_public():
    response = Client(enforce_csrf_checks=True).post(PATH, data=b"{}", content_type="application/json")
    assert response.status_code == 412  # Signature gate, not session login or CSRF.


def test_official_ebay_sdk_signed_fixture(monkeypatch):
    # eBay event-notification-nodejs-sdk/test/test.json VALID (Apache-2.0).
    # Public, synthetic SDK fixture; no real credentials or customer information.
    header = (
        "eyJhbGciOiJlY2RzYSIsImtpZCI6Ijk5MzYyNjFhLTdkN2ItNDYyMS1hMGYxLTk2Y2NiNDI4YWY0OSIs"
        "InNpZ25hdHVyZSI6Ik1FWUNJUUNmeGZJV3V4bVdjSUJRSjljNS9YN2lHREpxczJSQ0dzQkVhQWppbnly"
        "cmZBSWhBSVY2d0djVGlCdVY1S0pVaWYyaG9reXJMK1E5c3NIa2FkK214Mm5FRTI1dyIsImRpZ2VzdCI6"
        "IlNIQTEifQ=="
    )
    pem = (
        "-----BEGIN PUBLIC KEY-----MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEZhhxXKtR+TOvtDbgTPCk"
        "Sof02qgBB7IsYOyf76ilExJ/upAa/vKIKheOoCyOpcLmi4t0b4uepb7LLjmMr90FUg==-----END PUBLIC KEY-----"
    )
    monkeypatch.setattr(PublicKeyClient, "get", lambda self, kid: {
        "key": pem, "algorithm": "ECDSA", "digest": "SHA1",
    })
    value = {
        "metadata": {"topic": "MARKETPLACE_ACCOUNT_DELETION", "schemaVersion": "1.0", "deprecated": False},
        "notification": {
            "notificationId": "49feeaeb-4982-42d9-a377-9645b8479411_33f7e043-fed8-442b-9d44-791923bd9a6d",
            "eventDate": "2021-03-19T20:43:59.462Z", "publishDate": "2021-03-19T20:43:59.679Z",
            "publishAttemptCount": 1,
            "data": {"username": "test_user", "userId": "ma8vp1jySJC",
                     "eiasToken": "nY+sHZ2PrBmdj6wVnY+sEZ2PrA2dj6wJnY+gAZGEpwmdj6x9nY+seQ=="},
        },
    }
    response = post(None, value, header=header)
    assert response.status_code == 200
    assert DeletionReceipt.objects.get().status == "review_required"
