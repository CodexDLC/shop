import logging

from django.http import HttpResponse
from django.views import View
from django.views.decorators.debug import sensitive_variables

logger = logging.getLogger(__name__)


class OAuthSafeView(View):
    """OAuth request URLs contain secrets: never send unexpected errors to a traceback reporter."""

    @sensitive_variables()
    def dispatch(self, request, *args, **kwargs):
        request.sensitive_post_parameters = "__ALL__"
        try:
            return super().dispatch(request, *args, **kwargs)
        except Exception:
            # Stable operational event only. No exc_info, request, URL, provider data or locals.
            logger.error("ebay_oauth.unexpected_error")
            return HttpResponse("Die Verbindung ist derzeit nicht möglich. Bitte später erneut versuchen.",
                                status=500, content_type="text/plain; charset=utf-8")
