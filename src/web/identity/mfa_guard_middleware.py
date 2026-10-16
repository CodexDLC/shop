from urllib.parse import urlencode

from allauth.mfa.models import Authenticator
from django.conf import settings
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin

from web.identity.policy import has_recent_mfa, has_verified_email, is_staff_user
from web.localization import translate_text


class MFAGuardMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        if not match or not set(match.namespaces).intersection({"staff", "admin"}):
            return None
        if not settings.SHOP_STAFF_MFA_REQUIRED or not is_staff_user(request.user):
            return None
        if match.url_name in {"logout", "logout_confirm"}:
            return None
        if not has_verified_email(request.user):
            target = reverse("account_email")
        elif not Authenticator.objects.filter(user=request.user, type=Authenticator.Type.TOTP).exists():
            target = reverse("mfa_activate_totp")
        elif not has_recent_mfa(request):
            target = reverse("mfa_reauthenticate")
        else:
            return None
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            return JsonResponse({"error": {"code": "auth.mfa_required",
                "message": translate_text("auth.mfa_required"), "url": target}}, status=403)
        return HttpResponseRedirect(target + "?" + urlencode({"next": request.get_full_path()}))
