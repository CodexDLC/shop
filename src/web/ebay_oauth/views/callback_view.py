from django.db import DatabaseError
from django.shortcuts import redirect
from django.views.decorators.debug import sensitive_variables

from ..configuration import COOKIE, PREFIX
from ..flow_service import FlowService
from ..rejected import OAuthRejected
from .safe_view import OAuthSafeView


class CallbackView(OAuthSafeView):
    @sensitive_variables()
    def get(self, request):
        success = False
        if (len(request.GET.getlist("state")) == 1 and len(request.GET.getlist("code")) == 1
                and "error" not in request.GET):
            try:
                FlowService().finish(request.GET["state"], request.COOKIES.get(COOKIE), request.GET["code"])
                success = True
            except (OAuthRejected, DatabaseError):
                pass
        # No provider values or secrets survive the redirect, including in error messages.
        response = redirect(PREFIX + "result/?status=" + ("connected" if success else "failed"))
        response.delete_cookie(COOKIE, path="/", samesite="Lax")
        return response
