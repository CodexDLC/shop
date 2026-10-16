from django.urls import path
from django.views.generic import RedirectView

from web.catalog.product_detail_view import ProductDetailView
from web.catalog.variant_preview_view import VariantPreviewView
from web.catalog.views import CatalogPageView

app_name = "catalog"
urlpatterns = [
    path("produkt/<slug:slug>/variante/", VariantPreviewView.as_view(), name="variant_preview"),
    path("katalog/", CatalogPageView.as_view(template_name="catalog/list.html"), name="list"),
    path("katalog/leer/", CatalogPageView.as_view(template_name="catalog/empty.html"), name="empty"),
    path("katalog/mobil/", CatalogPageView.as_view(template_name="catalog/mobile.html"), name="mobile"),
    path("katalog/suche/", CatalogPageView.as_view(template_name="catalog/search.html"), name="search"),
    path("katalog/suche/leer/", CatalogPageView.as_view(template_name="catalog/search_empty.html"), name="search_empty"),
    path("produkt/demo/", RedirectView.as_view(pattern_name="catalog:detail", permanent=False),
         {"slug": "manstore-m2223"}, name="product"),
    path("produkt/<slug:slug>/", ProductDetailView.as_view(), name="detail"),
]
