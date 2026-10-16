from django.urls import path
from django.views.generic import RedirectView

from web.customer.views import (
    CustomerPageView,
    DefaultAddressView,
    DeleteAddressView,
    SaveAddressView,
    SaveProfileView,
)
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
    path("konto/bestellungen/", CustomerPageView.as_view(template_name="customer/orders.html"), name="orders"),
    path("konto/bestellungen/demo/", CustomerPageView.as_view(template_name="customer/order_detail.html"), name="order_detail"),
    path("konto/profil/speichern/", SaveProfileView.as_view(), name="save_profile"),
    path("konto/adressen/neu/", SaveAddressView.as_view(), name="address_create"),
    path("konto/adressen/<int:pk>/speichern/", SaveAddressView.as_view(), name="address_update"),
    path("konto/adressen/<int:pk>/entfernen/", DeleteAddressView.as_view(), name="address_delete"),
    path("konto/adressen/<int:pk>/standard/", DefaultAddressView.as_view(), name="address_default"),
    path("konto/profil/", CustomerPageView.as_view(template_name="customer/profile.html"), name="profile"),
]
