from django.urls import path

from web.cart import actions
from web.cart.views import CartPageView

app_name = "cart"
urlpatterns = [
    path("warenkorb/hinzufuegen/", actions.add, name="add"),
    path("warenkorb/aendern/", actions.update, name="update"),
    path("warenkorb/entfernen/", actions.remove, name="remove"),
    path("warenkorb/", CartPageView.as_view(template_name="cart/detail.html"), name="detail"),
    path("warenkorb/leer/", CartPageView.as_view(template_name="cart/empty.html"), name="empty"),
]
