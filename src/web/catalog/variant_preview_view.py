from django.http import JsonResponse
from django.views import View

from codex_ecommerce.catalog import CatalogSelectionError
from web.catalog.adapters import CatalogVariantSelection
from web.catalog.models import Product
from web.localization import translate_text


class VariantPreviewView(View):
    """Local demo read model, never a checkout or inventory reservation API."""

    http_method_names = ["get", "head", "options"]

    def get(self, request, slug):
        color = request.GET.get("color", "")
        size = request.GET.get("size", "")
        if not color or not size or len(color) > 40 or len(size) > 20:
            return self.error("catalog.selection_required", 400)
        try:
            result = CatalogVariantSelection().select(product_slug=slug, color=color, size=size)
        except Product.DoesNotExist:
            return self.error("catalog.product_not_found", 404)
        except CatalogSelectionError as exc:
            status = 404 if exc.code == "catalog.variant_not_found" else 409
            return self.error(exc.code, status)
        response = JsonResponse({
            "mode": "demo",
            "checkout_enabled": False,
            "variant": {
                "sku": result.variant.sku, "color": result.variant.color,
                "size": result.variant.size, "price": str(result.variant.price),
                "currency": result.variant.currency, "active": result.variant.active,
                "demo_available": result.purchase_allowed,
            },
            "gallery": {"color": result.gallery.color, "images": list(result.gallery.images)},
        })
        response["Cache-Control"] = "no-store"
        response["X-Robots-Tag"] = "noindex"
        return response

    def error(self, code, status):
        response = JsonResponse({
            "mode": "demo", "checkout_enabled": False,
            "error": {"code": code, "message": translate_text(f"{code}.message")},
        }, status=status)
        response["Cache-Control"] = "no-store"
        response["X-Robots-Tag"] = "noindex"
        return response
