from django.urls import path

from .indexing_view import SeoIndexingView
from .overview_view import SeoOverviewView
from .page_view import SeoPageView
from .pages_view import SeoPagesView
from .rules_view import SeoRulesView

urlpatterns = [
    path("", SeoOverviewView.as_view(), name="seo_overview"),
    path("pages/", SeoPagesView.as_view(), name="seo_pages"),
    path("pages/<str:kind>/<path:key>/", SeoPageView.as_view(), name="seo_page"),
    path("rules/", SeoRulesView.as_view(), name="seo_rules"),
    path("indexing/", SeoIndexingView.as_view(), name="seo_indexing"),
]
