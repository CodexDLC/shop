import json
from datetime import timedelta
from io import StringIO
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from cryptography.fernet import Fernet
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client
from django.utils import timezone

from web.ebay_oauth.configuration import COOKIE, PREFIX, SCOPES, configuration
from web.ebay_oauth.flow_service import FlowService, digest
from web.ebay_oauth.models import AuthorizationFlow, Invitation, SellerConnection
from web.ebay_oauth.provider_client import ProviderClient
from web.ebay_oauth.rejected import OAuthRejected

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def configured(settings, monkeypatch):
    settings.EBAY_APP_ID = "test-app"
    settings.EBAY_CERT_ID = "test-secret"
    settings.EBAY_OAUTH_BASE_URL = "https://shop.pinlite.dev"
    settings.EBAY_OAUTH_RUNAME = "test-runame"
    settings.EBAY_OAUTH_ENCRYPTION_KEYS = Fernet.generate_key().decode()
    monkeypatch.setattr("http.client.HTTPSConnection", Mock(side_effect=AssertionError("offline tests")))


@pytest.fixture
def invitation():
    token = "a" * 64
    invite = Invitation.objects.create(token_hash=digest(token), expected_seller="sonne_fuer_alle",
                                       expires_at=timezone.now() + timedelta(hours=24))
    return token, invite


@pytest.fixture
def provider(monkeypatch):
    exchange = Mock(return_value={"access_token": "private-access", "refresh_token": "private-refresh",
                                  "expires_in": 7200, "refresh_token_expires_in": 86400})
    seller = Mock(return_value="sonne_fuer_alle")
    monkeypatch.setattr(ProviderClient, "exchange", exchange)
    monkeypatch.setattr(ProviderClient, "seller", seller)
    return exchange, seller


def started(invitation):
    url, browser = FlowService().start(invitation[0])
    return parse_qs(urlsplit(url).query)["state"][0], browser


def test_success_encrypts_and_consumes(invitation, provider):
    state, browser = started(invitation)
    FlowService().finish(state, browser, "private-code")
    connection = SellerConnection.objects.get()
    assert connection.seller == "sonne_fuer_alle"
    assert connection.encrypted_access_token != "private-access"
    _, _, cipher = configuration()
    assert cipher.decrypt(connection.encrypted_access_token.encode()) == b"private-access"
    assert cipher.decrypt(connection.encrypted_refresh_token.encode()) == b"private-refresh"
    assert set(connection.scopes) == set(SCOPES)
    invitation[1].refresh_from_db()
    assert invitation[1].used_at
    assert AuthorizationFlow.objects.get().used_at
    with pytest.raises(OAuthRejected):
        FlowService().finish(state, browser, "private-code")
    assert provider[0].call_count == 1
    with pytest.raises(OAuthRejected):
        FlowService().start(invitation[0])


@pytest.mark.parametrize("browser", [None, "wrong", ""])
def test_missing_or_mismatching_browser_denied(invitation, provider, browser):
    state, _ = started(invitation)
    with pytest.raises(OAuthRejected):
        FlowService().finish(state, browser, "code")
    provider[0].assert_not_called()
    assert not SellerConnection.objects.exists()


def test_state_expiration_and_unknown_state(invitation, provider):
    state, browser = started(invitation)
    AuthorizationFlow.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    for value in (state, "unknown"):
        with pytest.raises(OAuthRejected):
            FlowService().finish(value, browser, "code")
    provider[0].assert_not_called()


def test_wrong_seller_discards_tokens_and_invite_can_retry(invitation, provider):
    provider[1].return_value = "prime_8088"
    state, browser = started(invitation)
    with pytest.raises(OAuthRejected):
        FlowService().finish(state, browser, "code")
    assert not SellerConnection.objects.exists()
    invitation[1].refresh_from_db()
    assert invitation[1].used_at is None
    assert AuthorizationFlow.objects.get().used_at is not None
    FlowService().start(invitation[0])


def test_failed_exchange_consumes_state(invitation, provider):
    provider[0].side_effect = OAuthRejected
    state, browser = started(invitation)
    with pytest.raises(OAuthRejected):
        FlowService().finish(state, browser, "code")
    provider[0].side_effect = None
    with pytest.raises(OAuthRejected):
        FlowService().finish(state, browser, "code")
    assert provider[0].call_count == 1


def test_invite_used_during_external_call_fails_closed(invitation, provider):
    state, browser = started(invitation)
    provider[1].side_effect = lambda _: (Invitation.objects.filter(pk=invitation[1].pk).update(
        used_at=timezone.now()) and "sonne_fuer_alle")
    with pytest.raises(OAuthRejected):
        FlowService().finish(state, browser, "code")
    assert not SellerConnection.objects.exists()


def test_invitation_expired(invitation):
    Invitation.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    with pytest.raises(OAuthRejected):
        FlowService().start(invitation[0])
    assert not AuthorizationFlow.objects.exists()


def test_get_has_no_oauth_effect_and_csrf_required(invitation):
    client = Client(enforce_csrf_checks=True)
    path = PREFIX + "connect/" + invitation[0] + "/"
    page = client.get(path)
    assert page.status_code == 200
    assert not AuthorizationFlow.objects.exists()
    assert "sonne_fuer_alle" in page.content.decode()
    assert client.post(path).status_code == 403
    response = client.post(path, {"csrfmiddlewaretoken": client.cookies["csrftoken"].value})
    assert response.status_code == 302
    parsed = urlsplit(response["Location"])
    assert parsed.scheme == "https" and parsed.netloc == "auth.ebay.com"
    assert set(parse_qs(parsed.query)["scope"][0].split()) == set(SCOPES)
    cookie = response.cookies[COOKIE]
    assert cookie["secure"] and cookie["httponly"] and cookie["samesite"] == "Lax"
    assert response["Cache-Control"] == "no-store, private"
    assert response["X-Robots-Tag"].startswith("noindex")


def test_callback_redirect_has_no_secrets(invitation, provider):
    state, browser = started(invitation)
    client = Client()
    client.cookies[COOKIE] = browser
    response = client.get(PREFIX + "callback/", {"state": state, "code": "private-code"})
    assert response.status_code == 302
    assert response["Location"] == PREFIX + "result/?status=connected"
    assert COOKIE in response.cookies and response.cookies[COOKIE]["max-age"] == 0
    assert b"private" not in response.content
    assert response["Cache-Control"] == "no-store, private"


@pytest.mark.parametrize("query", ["error=access_denied", "state=a&code=b&code=c", "state=a&code=b&state=c"])
def test_invalid_callback_no_exchange(query, provider):
    response = Client().get(PREFIX + "callback/?" + query)
    assert response["Location"] == PREFIX + "result/?status=failed"
    provider[0].assert_not_called()


@pytest.mark.parametrize("method,path,headers", [
    ("POST", "/ws/api.dll", {"X-EBAY-API-CALL-NAME": "GetUser"}),
    ("DELETE", "/ws/api.dll", {"X-EBAY-API-CALL-NAME": "GetUser"}),
    ("POST", "/ws/api.dll", {"X-EBAY-API-CALL-NAME": "ReviseInventoryStatus"}),
    ("POST", "https://evil.example/token", {}),
    ("POST", "/sell/inventory/v1/inventory_item", {}),
    ("GET", "/identity/v1/oauth2/token", {}),
])
def test_transport_rejects_before_connection(method, path, headers):
    import http.client
    with pytest.raises(OAuthRejected):
        ProviderClient()._request(method, path, "", headers)
    http.client.HTTPSConnection.assert_not_called()


@pytest.mark.parametrize("change", [
    {"refresh_token": ""}, {"scope": "https://api.ebay.com/oauth/api_scope/sell.inventory"},
    {"expires_in": -1}, {"refresh_token_expires_in": True}, {"token_type": "evil"},
])
def test_token_payload_validation(monkeypatch, change):
    payload = {"access_token": "access", "refresh_token": "refresh", "expires_in": 7200,
               "refresh_token_expires_in": 86400, "scope": " ".join(SCOPES)}
    payload.update(change)
    monkeypatch.setattr(ProviderClient, "_request", lambda *args: json.dumps(payload).encode())
    with pytest.raises(OAuthRejected):
        ProviderClient().exchange("code")


def test_provider_fixed_paths_and_getuser(monkeypatch):
    calls = []
    def request(self, method, path, body, headers):
        calls.append((method, path, headers))
        if path == "/identity/v1/oauth2/token":
            return json.dumps({"access_token": "access", "refresh_token": "refresh", "expires_in": 7200,
                               "refresh_token_expires_in": 86400, "token_type": "User Access Token"}).encode()
        return b'<GetUserResponse xmlns="urn:ebay:apis:eBLBaseComponents"><Ack>Success</Ack><User><UserID>sonne_fuer_alle</UserID></User></GetUserResponse>'
    monkeypatch.setattr(ProviderClient, "_request", request)
    client = ProviderClient()
    assert client.exchange("code")["access_token"] == "access"
    assert client.seller("access") == "sonne_fuer_alle"
    assert [item[1] for item in calls] == ["/identity/v1/oauth2/token", "/ws/api.dll"]
    assert calls[1][2]["X-EBAY-API-CALL-NAME"] == "GetUser"


def test_invitation_command_private_file_and_no_stdout_token(tmp_path):
    target = tmp_path / "invitation.txt"
    output = StringIO()
    call_command("create_ebay_oauth_invite", seller="sonne_fuer_alle", output=str(target), stdout=output)
    link = target.read_text().strip()
    assert link.startswith("https://shop.pinlite.dev" + PREFIX + "connect/")
    token = link.rstrip("/").split("/")[-1]
    assert len(token) == 64 and Invitation.objects.get().token_hash == digest(token)
    assert token not in output.getvalue()
    assert token not in Invitation.objects.get().token_hash
    with pytest.raises(CommandError):
        call_command("create_ebay_oauth_invite", seller="sonne_fuer_alle", output=str(target))
    assert Invitation.objects.count() == 1


def test_invalid_configuration_blocks_invite(settings, tmp_path):
    settings.EBAY_OAUTH_BASE_URL = "http://shop.pinlite.dev"
    with pytest.raises(CommandError):
        call_command("create_ebay_oauth_invite", seller="sonne_fuer_alle", output=str(tmp_path / "x"))
    assert Invitation.objects.count() == 0


def test_unexpected_callback_error_is_generic(invitation, monkeypatch, caplog):
    state, browser = started(invitation)
    monkeypatch.setattr(FlowService, "finish", Mock(side_effect=RuntimeError("secret-code-private")))
    client = Client()
    client.cookies[COOKIE] = browser
    response = client.get(PREFIX + "callback/", {"state": state, "code": "secret-code-private"})
    assert response.status_code == 500
    assert b"secret-code-private" not in response.content
    assert "secret-code-private" not in caplog.text
    assert "ebay_oauth.unexpected_error" in caplog.text
    assert response["Cache-Control"] == "no-store, private"


def test_cleanup_removes_expired_attempts_and_preserves_connections(invitation, provider):
    state, browser = started(invitation)
    FlowService().finish(state, browser, "code")
    Invitation.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    call_command("cleanup_ebay_oauth", stdout=StringIO())
    assert not Invitation.objects.exists()
    assert not AuthorizationFlow.objects.exists()
    assert SellerConnection.objects.count() == 1


@pytest.mark.parametrize("status,body", [(302, b""), (500, b"secret-provider-error"), (200, b"x" * 262145)], ids=["redirect", "upstream-error", "oversized"])
def test_transport_response_bounds_and_redaction(monkeypatch, status, body):
    response = Mock(status=status)
    response.read.return_value = body
    connection = Mock()
    connection.getresponse.return_value = response
    constructor = Mock(return_value=connection)
    monkeypatch.setattr("http.client.HTTPSConnection", constructor)
    with pytest.raises(OAuthRejected) as caught:
        ProviderClient().exchange("private-code")
    assert str(caught.value) == ""
    constructor.assert_called_once_with("api.ebay.com", timeout=10)
    response.read.assert_called_once_with(262145)
    connection.close.assert_called_once()
