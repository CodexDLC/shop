from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from codex_ecommerce.cart import CartError
from web.cart.session_cart import change_cart
from web.cart.views import CartPageView


def _change(request, **options):
    try:
        change_cart(request, request.POST.get("sku"), request.POST.get("quantity", "1"), **options)
    except CartError as exc:
        view = CartPageView()
        view.setup(request)
        return view.render_to_response(view.get_context_data(cart_error=str(exc)), status=400)
    return redirect("orders:address" if request.POST.get("next") == "checkout" else "cart:detail")


@require_POST
def add(request):
    return _change(request, add=True)


@require_POST
def update(request):
    return _change(request)


@require_POST
def remove(request):
    return _change(request, remove=True)
