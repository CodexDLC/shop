"""Resolve published overlays once per HTML page; no per-card queries."""
from django.conf import settings

from web.localization import translate_text

from .models import SeoPage, SeoRule
from .policy import PUBLIC_ROUTES, PagePolicy
from .targets import BODY_STATIC
from .workspace import apply_rule


def apply_published_body(context, published, kind, key, language):
    if published.get("body") and (kind != "static" or key in BODY_STATIC):
        context["seo_visible_body"] = published["body"]
        if kind == "product":
            context["product_information"] = {**context.get("product_information", {}), "description": published["body"]}
            # The overlay translates the description alone. Material/fit facts
            # retain the source-row language, which may still be a fallback.
            context["description_language"] = language


def apply_public_overlay(request, context, *, status=200):
    match = getattr(request, "resolver_match", None)
    route = match.view_name if match else ""
    if route not in PUBLIC_ROUTES or status != 200:
        return
    kind, key = "static", route
    product = context.get("product", {})
    category = context.get("selected_category")
    variables = {"name": "", "brand": "", "category": "", "site": settings.SEO_SITE_NAME}
    if route == "catalog:detail" and product:
        kind, key = "product", product["slug"]
        variables.update(name=product["name"], brand=product["brand"], category=context.get("seo_category_name", ""))
    elif route == "catalog:list" and category:
        kind, key = "category", category.slug
        variables.update(name=category.name, category=category.name)
    elif route == "catalog:list":
        brand = context.get("selected_brand")
        if brand:
            kind, key = "brand", brand.slug
            variables.update(name=brand.name, brand=brand.name)
    language = getattr(request, "LANGUAGE_CODE", "de").split("-")[0]
    if language not in ("de", "ru"):
        return
    identity = (kind, key, language)
    cache = getattr(request, "_seo_overlays", None)
    if cache is None:
        cache = request._seo_overlays = {}
    if identity not in cache:
        cache[identity] = (
            SeoPage.objects.filter(kind=kind, key=key, language=language).values_list("published", flat=True).first() or {},
            SeoRule.objects.filter(kind=kind, language=language).values_list("published", flat=True).first() or {},
        )
    published, rule = cache[identity]
    apply_published_body(context, published, kind, key, language)
    from .metadata import page_metadata

    baseline = page_metadata(request, context)
    # Store raw metadata so normal final escaping/truncation/page-number behavior remains centralized.
    title = baseline["title"].removesuffix(" | " + settings.SEO_SITE_NAME)
    policy = PagePolicy(request, context)
    if policy.page > 1:
        title = title.removesuffix(" · " + translate_text("seo.page", page=policy.page))
    if kind == "brand":
        title = variables["name"]
        baseline["description"] = variables["name"]
    variables["name"] = variables["name"] or title
    body = (context.get("product_information", {}).get("description", "") if kind == "product"
            else category.description if kind == "category" else "")
    automatic = apply_rule({"title": title, "description": baseline["description"], "body": body}, variables, rule)
    context["seo_overrides"] = {field: published.get(field) or automatic[field] for field in ("title", "description")}
