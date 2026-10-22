"""Existing page identities; these selectors never mutate catalog records."""
from urllib.parse import parse_qs, urlencode, urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import CharField, Exists, F, OuterRef, Q, Value
from django.db.models.functions import Coalesce, NullIf
from django.http import Http404
from django.urls import reverse
from django.utils.translation import override

from web.catalog.descriptions import legacy_description
from web.catalog.models import Brand, Category, Product, ProductInformation, ProductVariant
from web.localization import translate_text

from .search_results import SearchResults

KINDS = ("product", "category", "brand", "static")
STATIC_PAGES = {
    "shop:home": "seo.home.title", "catalog:list": "catalog.listing.title",
    "catalog:brands": "catalog.brands.title", "support:help": "seo.help.title",
    "support:impressum": "legal.impressum.title", "support:datenschutz": "legal.datenschutz.title",
    "support:agb": "legal.agb.title", "support:widerruf": "legal.widerruf.title",
    "support:versand_zahlung": "legal.versand.title",
}
BODY_STATIC = {"shop:home", "catalog:list", "catalog:brands", "support:help", "support:contact"}


def validate_identity(kind, language):
    if kind not in KINDS or language not in ("de", "ru"):
        raise ValidationError("Unsupported SEO page type or content language.")


def target_path(kind, key):
    if kind == "product":
        return reverse("catalog:detail", kwargs={"slug": key})
    if kind in ("category", "brand"):
        return reverse("catalog:list") + "?" + urlencode({kind: key})
    return reverse(key)


def target_data(kind, key, language="de"):
    validate_identity(kind, language)
    with override(language):
        brand = category = body = ""
        body_supplies_description = False
        if kind == "product":
            item = Product.objects.select_related("brand", "category").filter(slug=key).first()
            if not item:
                raise Http404
            name, brand, category = item.model_name, item.brand.name, item.category.name
            information = ProductInformation.objects.filter(product=item, language_code=language).first()
            if not information and language != "de":
                information = ProductInformation.objects.filter(product=item, language_code="de").first()
            body = (information.description if information else "") or legacy_description(item)
            body_supplies_description = True
            title, description = f"{brand} {name}", body or f"{brand} {name}"
        elif kind == "category":
            item = Category.objects.filter(slug=key).first()
            if not item:
                raise Http404
            name = category = item.name
            body = item.description
            title, description = item.seo_title or name, item.seo_description or body or name
            body_supplies_description = not item.seo_description
        elif kind == "brand":
            item = Brand.objects.filter(slug=key).first()
            if not item:
                raise Http404
            name = brand = item.name
            title = description = name
        else:
            if key not in STATIC_PAGES:
                raise Http404
            name = translate_text(STATIC_PAGES[key])
            # Legal documents keep their factual body under the legal-document owner.
            if name.startswith("["):
                name = key.split(":")[-1].replace("_", " ").capitalize()
            title = name
            description = translate_text("seo." + key.replace(":", ".") + ".description")
            if description.startswith("["):
                description = name
        return {"kind": kind, "key": key, "language": language, "label": name,
                "path": target_path(kind, key), "body_allowed": kind != "static" or key in BODY_STATIC,
                "body_supplies_description": body_supplies_description,
                "variables": {"name": name, "brand": brand, "category": category, "site": settings.SEO_SITE_NAME},
                "automatic": {"title": title, "description": description, "body": body}}


def search_pages(query="", kind="", language="de", page=1):
    if kind and kind not in KINDS or language not in ("de", "ru"):
        raise ValidationError("Unsupported SEO page type or content language.")
    query = str(query).strip()[:160]
    # Accept a pasted URL without using its host or exposing its query in SEO output.
    if "/" in query:
        try:
            parsed = urlsplit(query)
        except ValueError:
            return Paginator([], 20).get_page(page)
        filters = parse_qs(parsed.query)
        query = next(iter(filters.get("category", []) or filters.get("brand", [])), "") or parsed.path.rstrip("/").split("/")[-1]
    with override(language):
        static = [{"kind": "static", "key": key, "label": translate_text(label)}
                    for key, label in STATIC_PAGES.items()
                    if not query or query.casefold() in (key + " " + translate_text(label) + " " + reverse(key)).casefold()]
    if kind == "static":
        result = Paginator(static, 20).get_page(page)
        with override(language):
            result.object_list = [{**row, "path": target_path(row["kind"], row["key"])} for row in result.object_list]
        return result
    kinds = (kind,) if kind else ("product", "category", "brand")
    sets = []
    for current in kinds:
        model = {"product": Product, "category": Category, "brand": Brand}[current]
        label = {"product": "model_name", "category": "name_de", "brand": "name"}[current]
        rows = model.objects.order_by()
        if query:
            condition = Q(slug__icontains=query) | Q(**{label + "__icontains": query})
            if current == "category":
                condition |= Q(name_ru__icontains=query) | Q(name_key__icontains=query)
            if current == "product":
                rows = rows.alias(sku_matches=Exists(ProductVariant.objects.filter(product_id=OuterRef("pk"), sku__icontains=query)))
                condition |= Q(sku_matches=True) | Q(brand__name__icontains=query)
            rows = rows.filter(condition)
        label_expression = F(label)
        if current == "category":
            names = ["name_ru", "name_de", "name_key", "slug"] if language == "ru" else ["name_de", "name_key", "slug"]
            label_expression = Coalesce(*(NullIf(F(field), Value("")) for field in names), output_field=CharField())
        sets.append(rows.annotate(kind=Value(current, output_field=CharField()), key=F("slug"), label=label_expression).values("kind", "key", "label"))
    rows = sets[0].union(*sets[1:]).order_by("label", "key") if len(sets) > 1 else sets[0].order_by("label", "key")
    result = Paginator(SearchResults(static, rows) if not kind else rows, 20).get_page(page)
    with override(language):
        formatted = []
        for row in result.object_list:
            label = row["label"] or row["key"]
            translated = translate_text(label) if row["kind"] == "category" else label
            formatted.append({**row, "label": translated if not translated.startswith("[") else label,
                              "path": target_path(row["kind"], row["key"])})
        result.object_list = formatted
    return result
