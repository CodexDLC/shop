from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect
from django.views import View

from web.catalog.models import Product
from web.localization import translate_text

from .session import MAX_PRODUCTS, product_ids, save_ids


class WishlistMutationView(View):
    http_method_names = ["post"]
    remove = False

    def post(self, request):
        raw = request.POST.get("product_id", "")
        if not raw.isascii() or not raw.isdecimal() or len(raw) > 10:
            return HttpResponseBadRequest(translate_text("wishlist.error.product"))
        product_id = int(raw)
        if not 0 < product_id <= 2147483647:
            return HttpResponseBadRequest(translate_text("wishlist.error.product"))
        values = product_ids(request)
        if self.remove:
            values = [value for value in values if value != product_id]
        else:
            if not Product.objects.filter(pk=product_id, is_active=True,
                                          variants__is_active=True, variants__currency="EUR").exists():
                return HttpResponseBadRequest(translate_text("wishlist.error.product"))
            if product_id not in values:
                if len(values) >= MAX_PRODUCTS:
                    return HttpResponseBadRequest(translate_text("wishlist.error.limit"))
                values.append(product_id)
        save_ids(request, values)
        if request.headers.get("Accept") == "application/json":
            return JsonResponse({"count": len(values), "saved": product_id in values})
        return redirect("wishlist:detail")
