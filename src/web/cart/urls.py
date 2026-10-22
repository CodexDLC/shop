from django.urls import path

from web.cart import actions, coupon_actions
from web.cart.views import CartPageView

app_name = "cart"
urlpatterns = [
    path("warenkorb/gutschein/", coupon_actions.apply, name="coupon_apply"),
    path("warenkorb/gutschein/entfernen/", coupon_actions.remove, name="coupon_remove"),
    path("warenkorb/hinzufuegen/", actions.add, name="add"),
    path("warenkorb/aendern/", actions.update, name="update"),
    path("warenkorb/entfernen/", actions.remove, name="remove"),
    path("warenkorb/", CartPageView.as_view(template_name="cart/detail.html"), name="detail"),
    path("warenkorb/leer/", CartPageView.as_view(template_name="cart/empty.html"), name="empty"),
]
