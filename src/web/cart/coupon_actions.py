from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from codex_ecommerce.cart import CartError
from web.cart.promotions import coupon_key, normalize_code, promotion_quote
from web.cart.session_cart import quote
from web.cart.views import CartPageView


@require_POST
def apply(request):
    try:
        code = normalize_code(request.POST.get('code'))
        cart = quote(request, ignore_coupon=True)
        if not cart['can_checkout']:
            raise CartError(cart['errors'][0] if cart['errors'] else 'commerce.error.unavailable')
        promotion_quote(code, cart['subtotal'])
    except CartError as exc:
        view = CartPageView()
        view.setup(request)
        return view.render_to_response(view.get_context_data(coupon_error=str(exc)), status=400)
    request.session[coupon_key(request)] = code
    return redirect('cart:detail')


@require_POST
def remove(request):
    request.session.pop(coupon_key(request), None)
    return redirect('cart:detail')
