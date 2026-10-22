from django.db.models import Count, F, Q
from django.http import Http404
from django.utils.translation import override

from web.catalog.models import Product
from web.catalog.presentation import product_presentation
from web.catalog.product_information_context import product_information_context
from web.seo.models import SeoPage, SeoRule
from web.seo.origin import public_origin
from web.seo.public import apply_published_body
from web.seo.structured_data import product_schema
from web.seo.workspace import get_page


def workspace_summary(language):
    pages = SeoPage.objects.filter(language=language)
    counts = pages.aggregate(drafts=Count("pk", filter=~Q(draft=F("published"))),
                             published=Count("pk", filter=~Q(published={})))
    counts["rules"] = SeoRule.objects.filter(language=language).exclude(draft=F("published")).count()
    recent = []
    for row in pages.order_by("-updated_at", "-pk").values("kind", "key")[:5]:
        try:
            recent.append(get_page(row["kind"], row["key"], language))
        except Http404:
            # A removed catalog target has no editable page; never recreate it during GET.
            continue
    return counts, recent


def page_schema(page, language):
    if page["kind"] != "product" or not public_origin():
        return ""
    product = Product.objects.select_related("brand", "category").prefetch_related(
        "variants", "images", "tags").get(slug=page["key"])
    with override(language):
        context = {"product": product_presentation(product, code="seo"),
                   "manufacturer_article": product.manufacturer_article,
                   **product_information_context(product, language)}
        apply_published_body(context, page["published"], "product", page["key"], language)
        return product_schema(context, public_origin() + page["path"])
