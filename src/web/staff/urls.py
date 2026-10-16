from django.contrib.auth.views import LogoutView
from django.urls import path
from django.views.generic import RedirectView

from .views.catalog_settings_view import CatalogSettingsView
from .views.dashboard_view import DashboardView
from .views.logout_confirm_view import LogoutConfirmView
from .views.product_edit_view import ProductEditView
from .views.product_list_view import ProductListView
from .views.quick_access_view import QuickAccessView
from .views.variant_matrix_view import VariantMatrixView

app_name = "staff"
urlpatterns = [
    path("", DashboardView.as_view(), name="home"),
    path("login/", RedirectView.as_view(pattern_name="account_login", query_string=True), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("logout/confirm/", LogoutConfirmView.as_view(), name="logout_confirm"),
    path("catalog/", ProductListView.as_view(), name="products"),
    path("catalog/new/", ProductEditView.as_view(), name="product_add"),
    path("catalog/<int:pk>/", ProductEditView.as_view(), name="product_edit"),
    path("catalog/<int:pk>/variants/", VariantMatrixView.as_view(), name="variants"),
    path("catalog/settings/", CatalogSettingsView.as_view(), name="catalog_settings"),
    path("settings/", QuickAccessView.as_view(), name="settings"),
]
