"""Bounded session data, segregated by the current authentication principal."""
MAX_PRODUCTS = 50


def wishlist_key(request):
    return f"wishlist_user_{request.user.pk}" if request.user.is_authenticated else "wishlist_guest"


def product_ids(request):
    values = request.session.get(wishlist_key(request), [])
    if not isinstance(values, list):
        return []
    return list(dict.fromkeys(value for value in values[:MAX_PRODUCTS]
                              if type(value) is int and 0 < value <= 2147483647))


def save_ids(request, values):
    request.session[wishlist_key(request)] = list(dict.fromkeys(values))[:MAX_PRODUCTS]
