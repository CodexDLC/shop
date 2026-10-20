from django.urls import path
from django.views.generic import RedirectView

from web.customer.views import (
    CustomerPageView,
    DefaultAddressView,
    DeleteAddressView,
    SaveAddressView,
    SaveProfileView,
)
from web.customer.views.customer_order_detail_view import CustomerOrderDetailView
from web.customer.views.customer_orders_view import CustomerOrdersView
from web.identity.customer_overview_view import CustomerOverviewView

app_name = "customer"
urlpatterns = [
    path("konto/anmelden/", RedirectView.as_view(pattern_name="account_login", query_string=True), name="login"),
    path("konto/anmelden/mobil/", RedirectView.as_view(pattern_name="account_login", query_string=True), name="login_mobile"),
    path("konto/registrieren/", RedirectView.as_view(pattern_name="account_signup", query_string=True), name="register"),
    path("konto/registrieren/mobil/", RedirectView.as_view(pattern_name="account_signup", query_string=True), name="register_mobile"),
    path("konto/passwort/", RedirectView.as_view(pattern_name="account_reset_password"), name="password_reset"),
    path("konto/", CustomerOverviewView.as_view(), name="overview"),
    path("konto/mobil/", RedirectView.as_view(pattern_name="customer:overview"), name="mobile"),
    path("konto/bestellungen/", CustomerOrdersView.as_view(), name="orders"),
    path("konto/bestellungen/demo/", CustomerOrderDetailView.as_view(), name="order_detail"),
    path("konto/bestellungen/<uuid:reference>/", CustomerOrderDetailView.as_view(), name="order_receipt"),
    path("konto/profil/speichern/", SaveProfileView.as_view(), name="save_profile"),
    path("konto/adressen/neu/", SaveAddressView.as_view(), name="address_create"),
    path("konto/adressen/<int:pk>/speichern/", SaveAddressView.as_view(), name="address_update"),
    path("konto/adressen/<int:pk>/entfernen/", DeleteAddressView.as_view(), name="address_delete"),
    path("konto/adressen/<int:pk>/standard/", DefaultAddressView.as_view(), name="address_default"),
    path("konto/profil/", CustomerPageView.as_view(template_name="customer/profile.html"), name="profile"),
]
