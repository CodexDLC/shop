"""Public, request-scoped shop identity; no settings or actor details."""

from django.utils.functional import SimpleLazyObject

from web.shop.identity import get_store_identity


def store_identity(request):
    return {"shop_identity": SimpleLazyObject(lambda: get_store_identity(request))}
