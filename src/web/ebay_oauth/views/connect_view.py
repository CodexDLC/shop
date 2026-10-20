from django.middleware.csrf import get_token
from django.shortcuts import redirect, render
from django.views.decorators.debug import sensitive_variables

from ..configuration import COOKIE
from ..flow_service import FlowService
from ..rejected import OAuthRejected
from .safe_view import OAuthSafeView


class ConnectView(OAuthSafeView):
    @sensitive_variables()
    def get(self, request, token):
        try:
            invitation = FlowService().invitation(token)
        except OAuthRejected:
            return render(request, "ebay_oauth/message.html", {"message": "Der Link ist ungültig oder abgelaufen."},
                          status=400)
        get_token(request)
        return render(request, "ebay_oauth/connect.html", {"seller": invitation.expected_seller})

    @sensitive_variables()
    def post(self, request, token):
        try:
            url, browser = FlowService().start(token)
        except OAuthRejected:
            return render(request, "ebay_oauth/message.html", {"message": "Die Verbindung ist derzeit nicht möglich."},
                          status=400)
        response = redirect(url)
        response.set_cookie(COOKIE, browser, max_age=600, secure=True, httponly=True, samesite="Lax", path="/")
        return response
