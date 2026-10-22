"""Detail-only, bounded queries for editorial information, manufacturer sizes and reviews."""
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import urlsplit

from django.db.models import Avg, Case, Count, IntegerField, Q, Value, When
from django.utils.translation import get_language

from .descriptions import legacy_description
from .models import ProductInformation, ProductReview, SizeGuide

INFORMATION_FIELDS = ("description", "composition", "care", "fit", "origin", "certification")


def _measurement(minimum, maximum, *, inches=False):
    if minimum is None:
        return ""
    if inches:
        minimum = (minimum / Decimal("2.54")).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        maximum = (maximum / Decimal("2.54")).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        left, right = str(minimum), str(maximum)
    else:
        left, right = format(minimum.normalize(), "f"), format(maximum.normalize(), "f")
    return left if minimum == maximum else f"{left}–{right}"


def _source_url(url):
    try:
        parsed = urlsplit(url)
        return url if parsed.scheme.lower() in {"http", "https"} and parsed.netloc else ""
    except ValueError:
        return ""


def product_information_context(product, language_code=None):
    language = (language_code or get_language() or "de").lower()
    information = (
        ProductInformation.objects.filter(product_id=product.pk, language_code__in=[language, "de"])
        .order_by(Case(When(language_code=language, then=Value(0)), default=Value(1), output_field=IntegerField()))
        .first()
    )
    guide = (
        SizeGuide.objects.filter(brand_id=product.brand_id, is_published=True)
        .filter(Q(category_id=product.category_id) | Q(category__isnull=True))
        .order_by(Case(When(category_id=product.category_id, then=Value(0)), default=Value(1),
                       output_field=IntegerField()))
        .first()
    )
    size_guide = None
    if guide is not None:
        size_guide = {
            "title": guide.title, "source_label": guide.source_label, "source_url": _source_url(guide.source_url),
            "instructions": guide.instructions,
            "rows": [{
                "size": row.size,
                "waist_cm": _measurement(row.waist_min_cm, row.waist_max_cm),
                "waist_inch": _measurement(row.waist_min_cm, row.waist_max_cm, inches=True),
                "hip_cm": _measurement(row.hip_min_cm, row.hip_max_cm),
                "hip_inch": _measurement(row.hip_min_cm, row.hip_max_cm, inches=True),
            } for row in guide.rows.all()],
        }
    reviews = ProductReview.objects.filter(product_id=product.pk, status="approved")
    information_fields = {field: getattr(information, field, "") for field in INFORMATION_FIELDS}
    if not information_fields['description'].strip():
        information_fields['description'] = legacy_description(product)
    return {
        "product_information": information_fields,
        "information_language": information.language_code if information is not None else None,
        "description_language": information.language_code if information is not None else None,
        "size_guide": size_guide,
        "review_summary": reviews.aggregate(count=Count("pk"), average=Avg("rating")),
        "product_reviews": list(reviews.values("author_display", "body", "rating", "created_at")[:10]),
    }
