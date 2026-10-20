import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from .configuration import SCOPES, configuration
from .models import AuthorizationFlow, Invitation, SellerConnection
from .provider_client import ProviderClient
from .rejected import OAuthRejected


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class FlowService:
    def invitation(self, token):
        if not isinstance(token, str) or len(token) != 64:
            raise OAuthRejected
        invite = Invitation.objects.filter(token_hash=digest(token), used_at=None,
                                           expires_at__gt=timezone.now()).first()
        if invite is None:
            raise OAuthRejected
        return invite

    @sensitive_variables()
    def start(self, token):
        _, runame, _ = configuration()
        invite = self.invitation(token)
        state, browser = secrets.token_urlsafe(48), secrets.token_urlsafe(48)
        AuthorizationFlow.objects.create(invitation=invite, state_hash=digest(state),
                                         browser_hash=digest(browser),
                                         expires_at=timezone.now() + timedelta(minutes=10))
        query = urlencode({"client_id": settings.EBAY_APP_ID, "response_type": "code",
                           "redirect_uri": runame, "scope": " ".join(SCOPES), "state": state})
        return "https://auth.ebay.com/oauth2/authorize?" + query, browser

    @sensitive_variables()
    def finish(self, state, browser, code):
        if not all(isinstance(value, str) and 1 <= len(value) <= limit
                   for value, limit in ((state, 128), (browser, 128), (code, 16384))):
            raise OAuthRejected
        now = timezone.now()
        # Atomic conditional update consumes state before any external request, including on failures.
        with transaction.atomic():
            flow = AuthorizationFlow.objects.select_for_update().filter(state_hash=digest(state)).first()
            if flow is None or not secrets.compare_digest(flow.browser_hash, digest(browser)):
                raise OAuthRejected
            if not AuthorizationFlow.objects.filter(pk=flow.pk, used_at=None, expires_at__gt=now).update(
                used_at=now
            ):
                raise OAuthRejected
        _, _, cipher = configuration()
        client = ProviderClient()
        tokens = client.exchange(code)
        seller = client.seller(tokens["access_token"])
        with transaction.atomic():
            invite = Invitation.objects.select_for_update().get(pk=flow.invitation_id)
            if invite.used_at is not None or invite.expires_at <= timezone.now():
                raise OAuthRejected
            if seller.casefold() != invite.expected_seller.casefold():
                raise OAuthRejected
            SellerConnection.objects.update_or_create(seller=invite.expected_seller.casefold(), defaults={
                "encrypted_access_token": cipher.encrypt(tokens["access_token"].encode()).decode(),
                "encrypted_refresh_token": cipher.encrypt(tokens["refresh_token"].encode()).decode(),
                "access_expires_at": now + timedelta(seconds=tokens["expires_in"]),
                "refresh_expires_at": now + timedelta(seconds=tokens["refresh_token_expires_in"]),
                "scopes": list(SCOPES),
            })
            invite.used_at = timezone.now()
            invite.save(update_fields=["used_at"])
