from django.urls import path

from web.orders.confirmation_view import OrderConfirmationView
from web.orders.views import OrderPageView

app_name = "orders"
urlpatterns = [
    path("bestellung/adresse/", OrderPageView.as_view(template_name="orders/address.html"), name="address"),
    path("bestellung/adresse/fehler/", OrderPageView.as_view(template_name="orders/address_errors.html"), name="address_errors"),
    path("bestellung/bestaetigung/", OrderConfirmationView.as_view(), name="confirmation"),
]
