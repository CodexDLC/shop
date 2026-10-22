from django.contrib.auth.views import LogoutView
from django.urls import include, path
from django.views.generic import RedirectView

from .views.catalog_settings_view import CatalogSettingsView
from .views.dashboard_view import DashboardView
from .views.logout_confirm_view import LogoutConfirmView
from .views.product_edit_view import ProductEditView
from .views.product_information_view import ProductInformationView
from .views.product_list_view import ProductListView
from .views.product_preview_view import ProductPreviewView
from .views.product_publication_view import ProductPublicationView
from .views.product_variant_preview_view import ProductVariantPreviewView
from .views.quick_access_view import QuickAccessView
from .views.store_identity_view import StoreIdentityView
from .views.variant_matrix_view import VariantMatrixView
from .views.workspace_preview_view import WorkspacePreviewView

app_name = "staff"
urlpatterns = [
    path("seo/", include("web.staff.seo_workspace.urls")),
    path("workspace/store_settings/", StoreIdentityView.as_view(), {"section": "store_settings"}, name="workspace_preview"),
    path('workspace/<slug:section>/', WorkspacePreviewView.as_view(), name='workspace_preview'),
    path('', include('web.staff.operations.urls')),
    path('', include('web.staff.catalog_workspace.urls')),
    path('', include('web.staff.media_urls')),
    path("", DashboardView.as_view(), name="home"),
    path("login/", RedirectView.as_view(pattern_name="account_login", query_string=True), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("logout/confirm/", LogoutConfirmView.as_view(), name="logout_confirm"),
    path("catalog/", ProductListView.as_view(), name="products"),
    path("catalog/new/", ProductEditView.as_view(), name="product_add"),
    path("catalog/<int:pk>/", ProductEditView.as_view(), name="product_edit"),
    path("catalog/<int:pk>/variants/", VariantMatrixView.as_view(), name="variants"),
    path('catalog/<int:pk>/information/', ProductInformationView.as_view(), name='product_information'),
    path('catalog/<int:pk>/publication/', ProductPublicationView.as_view(), name='product_publication'),
    path('catalog/<int:pk>/preview/', ProductPreviewView.as_view(), name='product_preview'),
    path('catalog/<int:pk>/preview/variant/', ProductVariantPreviewView.as_view(), name='product_variant_preview'),
    path("catalog/settings/", CatalogSettingsView.as_view(), name="catalog_settings"),
    path("settings/", QuickAccessView.as_view(), name="settings"),
]
