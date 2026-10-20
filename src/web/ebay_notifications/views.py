import hashlib

from django.db import DatabaseError
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .configuration import challenge_configuration
from .receipt_service import ReceiptService
from .rejected import NotificationRejected
from .signature_verifier import SignatureVerifier


@method_decorator(csrf_exempt, name="dispatch")
class AccountDeletionView(View):
    http_method_names = ["get", "post"]

    def dispatch(self, request, *args, **kwargs):
        try:
            response = super().dispatch(request, *args, **kwargs)
        except NotificationRejected as error:
            response = JsonResponse({"error": {"code": error.code}}, status=error.status)
        except DatabaseError:
            response = JsonResponse({"error": {"code": "ebay.receipt_unavailable"}}, status=503)
        response["Cache-Control"] = "no-store"
        response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        return response

    def get(self, request):
        token, endpoint = challenge_configuration()
        values = request.GET.getlist("challenge_code")
        if len(values) != 1 or not 1 <= len(values[0]) <= 1024:
            raise NotificationRejected("ebay.invalid_challenge", 400)
        digest = hashlib.sha256((values[0] + token + endpoint).encode()).hexdigest()
        return JsonResponse({"challengeResponse": digest})

    def post(self, request):
        challenge_configuration()
        if request.content_type != "application/json":
            raise NotificationRejected("ebay.invalid_content_type", 415)
        try:
            length = int(request.META.get("CONTENT_LENGTH") or 0)
        except (ValueError, TypeError):
            raise NotificationRejected("ebay.invalid_length", 400) from None
        if length < 0 or length > 65536:
            raise NotificationRejected("ebay.payload_too_large", 413)
        # Read at most one byte beyond the cap; never request.body on untrusted input.
        body = request.read(65537)
        if len(body) > 65536:
            raise NotificationRejected("ebay.payload_too_large", 413)
        SignatureVerifier().verify(body, request.headers.get("X-EBAY-SIGNATURE"))
        ReceiptService().receive(body)
        return JsonResponse({"status": "received"}, status=200)
