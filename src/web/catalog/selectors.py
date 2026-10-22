from django.db.models import Avg, Count, Exists, F, OuterRef, Prefetch, Q, Subquery

from .category_visibility import descendant_category_ids, visible_category_ids
from .models import Product, ProductReview, ProductVariant


def storefront_products():
    """Lazy queryset: callers must bound the page before evaluation (four SQL queries)."""
    return Product.objects.filter(is_active=True, category_id__in=visible_category_ids()).select_related("brand", "category").prefetch_related(
        Prefetch("variants", queryset=ProductVariant.objects.filter(is_active=True)), "images", "tags"
    )


def catalog_products(*, query="", category="", brand="", tag="", limit=24, offset=0):
    """Bounded, lazy catalogue page; slug filters combine with a literal text search.

    Search covers model name, brand name, tag slugs and active variant SKUs.
    Translation keys are identifiers rather than searchable customer-facing text.
    Empty criteria are ignored; unknown slugs return an empty page. Sold-out active
    variants remain visible, but inactive variants cannot match or be presented.
    Related data costs four queries for a nonempty page, regardless of page size.
    """
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer between 1 and 100")
    if type(offset) is not int or offset < 0:
        raise ValueError("offset must be a nonnegative integer")

    products = storefront_products()
    if category.strip():
        products = products.filter(category_id__in=descendant_category_ids([category.strip()]))
    if brand.strip():
        products = products.filter(brand__slug=brand.strip())
    if tag.strip():
        tag_match = Product.tags.through.objects.filter(
            product_id=OuterRef("pk"), tag__slug=tag.strip(),
        )
        products = products.filter(Exists(tag_match))

    term = query.strip()
    if term:
        matching_skus = ProductVariant.objects.filter(
            product_id=OuterRef("pk"), is_active=True, sku__icontains=term,
        )
        matching_tags = Product.tags.through.objects.filter(
            product_id=OuterRef("pk"), tag__slug__icontains=term,
        )
        products = products.filter(
            Q(model_name__icontains=term) | Q(brand__name__icontains=term)
            | Q(Exists(matching_skus)) | Q(Exists(matching_tags))
        )
    return products.order_by("pk")[offset:offset + limit]


def gallery_for_color(product, color_code):
    """Use the prefetched relation; no per-size duplication or filtered-manager query."""
    images = list(product.images.all())
    return [image for image in images if image.color_code == color_code] or [
        image for image in images if not image.color_code
    ]


def listing_variant_conditions(criteria):
    """All variant constraints must be evaluated together, on one active EUR SKU."""
    conditions = Q(is_active=True, currency="EUR")
    for field, model_field in (("color", "color_code"), ("size", "size")):
        if criteria.filters.get(field):
            conditions &= Q(**{f"{model_field}__in": criteria.filters[field]})
    for field, lookup in (("min_price", "price__gte"), ("max_price", "price__lte")):
        if field in criteria.filters:
            conditions &= Q(**{lookup: criteria.filters[field]})
    if criteria.filters.get("in_stock"):
        conditions &= Q(demo_quantity__gt=0)
    if criteria.filters.get("sale"):
        conditions &= Q(is_on_sale=True)
    return conditions


def listing_products(criteria):
    """Unsliced queryset for count/pagination; no join multiplication or N+1."""
    matching = ProductVariant.objects.filter(
        listing_variant_conditions(criteria), product_id=OuterRef("pk"),
    )
    products = Product.objects.filter(is_active=True, category_id__in=visible_category_ids()).filter(Exists(matching))
    if criteria.filters.get("section"):
        products = products.filter(category__section=criteria.filters["section"])
    if criteria.filters.get("new"):
        from django.utils import timezone

        products = products.filter(new_until__gte=timezone.localdate())
    if criteria.filters.get("category"):
        products = products.filter(category_id__in=descendant_category_ids(criteria.filters["category"]))
    for field in ("brand",):
        if criteria.filters.get(field):
            products = products.filter(**{f"{field}__slug__in": criteria.filters[field]})
    if criteria.filters.get("tag"):
        products = products.filter(Exists(Product.tags.through.objects.filter(
            product_id=OuterRef("pk"), tag__slug__in=criteria.filters["tag"],
        )))
    for field, relation, related_field in (
        ("material", "materials", "material"), ("property", "properties", "productproperty"),
    ):
        if criteria.filters.get(field):
            through = getattr(Product, relation).through
            products = products.filter(Exists(through.objects.filter(
                product_id=OuterRef("pk"), **{f"{related_field}__slug__in": criteria.filters[field]},
            )))
    if criteria.query:
        sku_match = ProductVariant.objects.filter(
            product_id=OuterRef("pk"), is_active=True, currency="EUR", sku__icontains=criteria.query,
        )
        tag_match = Product.tags.through.objects.filter(
            product_id=OuterRef("pk"), tag__slug__icontains=criteria.query,
        )
        products = products.filter(
            Q(model_name__icontains=criteria.query) | Q(brand__name__icontains=criteria.query)
            | Q(Exists(sku_match)) | Q(Exists(tag_match))
        )
    # The displayed SKU and sorting price share the same matching-variant subquery.
    matching = matching.order_by("price", "pk")
    products = products.annotate(
        listing_sku=Subquery(matching.values("sku")[:1]),
        listing_price=Subquery(matching.values("price")[:1]),
    )
    if criteria.sort == "rating":
        approved = ProductReview.objects.filter(
            product_id=OuterRef("pk"), status="approved",
        ).order_by().values("product_id").annotate(average=Avg("rating"), count=Count("pk"))
        products = products.alias(
            approved_rating=Subquery(approved.values("average")[:1]),
            approved_review_count=Subquery(approved.values("count")[:1]),
        )
    orders = {
        "name": ("model_name", "pk"),
        "price_asc": ("listing_price", "pk"),
        "price_desc": ("-listing_price", "pk"),
        "newest": (F("published_at").desc(nulls_last=True), "model_name", "pk"),
        "rating": (F("approved_rating").desc(nulls_last=True),
                   F("approved_review_count").desc(nulls_last=True), "model_name", "pk"),
    }
    return products.select_related("brand", "category").prefetch_related(
        Prefetch("variants", queryset=ProductVariant.objects.filter(is_active=True, currency="EUR")),
        "images", "tags",
    ).order_by(*orders[criteria.sort])


def listing_facets():
    """Seven bounded facet queries across visible base products; no gallery/card loading."""
    from .models import Brand, Category, Material, ProductProperty, Tag

    active_variant = ProductVariant.objects.filter(
        product_id=OuterRef("pk"), is_active=True, currency="EUR",
    )
    visible = Product.objects.filter(is_active=True, category_id__in=visible_category_ids()).filter(Exists(active_variant)).order_by().values("pk")
    variants = ProductVariant.objects.filter(product_id__in=visible, is_active=True, currency="EUR")
    # Cap values server-side. Selection URLs keep filters even outside the facet window.
    return {
        "brands": list(Brand.objects.filter(products__pk__in=visible).order_by("name", "slug")
                       .values_list("slug", "name").distinct()[:200]),
        "categories": [(row.slug, row.name) for row in Category.objects.filter(
            products__pk__in=visible).order_by("position", "slug").distinct()[:200]],
        "tags": list(Tag.objects.filter(products__pk__in=visible).order_by("slug")
                     .values_list("slug", "label_key").distinct()[:200]),
        "materials": list(Material.objects.filter(products__pk__in=visible).order_by("name", "slug")
                          .values_list("slug", "name").distinct()[:200]),
        "properties": list(ProductProperty.objects.filter(products__pk__in=visible).order_by("name", "slug")
                           .values_list("slug", "name").distinct()[:200]),
        "colors": list(variants.order_by("color_code", "color_name_key")
                       .values_list("color_code", "color_name_key", "color_hex").distinct()[:200]),
        "sizes": list(variants.order_by("size").values_list("size", flat=True).distinct()[:200]),
    }
