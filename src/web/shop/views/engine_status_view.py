from django.http import JsonResponse
from django.views import View

from codex_ecommerce import Engine


class EngineStatusView(View):
    """Liveness and proof of the shared engine API; no dependency/network probe."""

    def get(self, request):
        return JsonResponse(Engine().status().model_dump(mode="json"))
