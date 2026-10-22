from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from web.catalog.models import (
    Brand,
    Category,
    Product,
    ProductInformation,
    ProductReview,
    SizeGuide,
    SizeGuideRow,
)
from web.catalog.product_information_context import product_information_context

pytestmark = pytest.mark.django_db


@pytest.fixture
def product():
    return Product.objects.create(
        slug="sample", model_name="Sample", brand=Brand.objects.create(slug="brand", name="Brand"),
        category=Category.objects.create(slug="briefs", name_key="category.briefs"),
    )


def guide_for(product, **kwargs):
    return SizeGuide.objects.create(brand_id=product.brand_id, title="Maker sizes", **kwargs)


def test_missing_information_is_empty(product):
    context = product_information_context(product)
    assert context["product_information"] == dict.fromkeys(
        ["description", "composition", "care", "fit", "origin", "certification"], "",
    )
    assert context["information_language"] is None
    assert context["size_guide"] is None
    assert context["review_summary"] == {"count": 0, "average": None}
    assert context["product_reviews"] == []


def test_information_language_and_product_isolation(product):
    ProductInformation.objects.create(product=product, language_code="de", description="Deutsch")
    ProductInformation.objects.create(product=product, language_code="en", description="English")
    assert product_information_context(product, "en")["product_information"]["description"] == "English"
    fallback = product_information_context(product, "ru")
    assert fallback["product_information"]["description"] == "Deutsch"
    assert fallback["information_language"] == "de"
    ProductInformation.objects.create(product=product, language_code="en-gb", description="British")
    assert product_information_context(product, "en-gb")["product_information"]["description"] == "British"
    other = Product.objects.create(
        slug="other", model_name="Other", brand_id=product.brand_id, category_id=product.category_id,
    )
    assert product_information_context(other)["product_information"]["description"] == ""
    with pytest.raises(IntegrityError), transaction.atomic():
        ProductInformation.objects.create(product=product, description="Duplicate")


def test_published_specific_guide_precedes_general_and_conversion(product):
    general = guide_for(product, is_published=True, source_label="Maker")
    specific = guide_for(product, category_id=product.category_id, is_published=True, source_label="Maker")
    SizeGuideRow.objects.create(guide=specific, size="M", waist_min_cm="76.2", waist_max_cm="81.28")
    context = product_information_context(product)
    assert context["size_guide"]["rows"] == [{
        "size": "M", "waist_cm": "76.2–81.28", "waist_inch": "30.0–32.0",
        "hip_cm": "", "hip_inch": "",
    }]
    specific.is_published = False
    specific.save()
    assert product_information_context(product)["size_guide"]["title"] == general.title
    general.is_published = False
    general.save()
    wrong_category = Category.objects.create(slug="other", name_key="other")
    guide_for(product, category=wrong_category, is_published=True, source_label="Maker")
    other_brand = Brand.objects.create(slug="other", name="Other")
    SizeGuide.objects.create(brand=other_brand, title="Other", is_published=True, source_label="Maker")
    assert product_information_context(product)["size_guide"] is None


def test_guide_publication_and_uniqueness(product):
    with pytest.raises(ValidationError):
        SizeGuide(brand_id=product.brand_id, title="Unsourced", is_published=True).full_clean()
    with pytest.raises(IntegrityError), transaction.atomic():
        guide_for(product, is_published=True)
    guide_for(product)
    with pytest.raises(IntegrityError), transaction.atomic():
        guide_for(product)
    guide = guide_for(product, category_id=product.category_id)
    with pytest.raises(IntegrityError), transaction.atomic():
        guide_for(product, category_id=product.category_id)
    row = {"guide": guide, "size": "M", "hip_min_cm": "80", "hip_max_cm": "90"}
    SizeGuideRow.objects.create(**row)
    with pytest.raises(IntegrityError), transaction.atomic():
        SizeGuideRow.objects.create(**row)


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,test", "//example.test", "https://["])
def test_unsafe_source_url_never_reaches_context(product, url):
    guide_for(product, source_url=url, is_published=True)
    assert product_information_context(product)["size_guide"]["source_url"] == ""


@pytest.mark.parametrize("values", [
    {}, {"waist_min_cm": "50"}, {"waist_min_cm": "60", "waist_max_cm": "50"},
    {"hip_min_cm": "0", "hip_max_cm": "50"},
    {"waist_min_cm": "50", "waist_max_cm": "60", "hip_max_cm": "90"},
])
def test_invalid_measurements_rejected_by_validation_and_database(product, values):
    guide = guide_for(product)
    with pytest.raises(ValidationError):
        SizeGuideRow(guide=guide, size="M", **values).full_clean()
    with pytest.raises(IntegrityError), transaction.atomic():
        SizeGuideRow.objects.create(guide=guide, size="M", **values)


def test_review_moderation_summary_limit_and_constraints(product):
    for rating in [1, 5]:
        ProductReview.objects.create(product=product, rating=rating, author_display="Hidden")
    ProductReview.objects.create(product=product, rating=1, status="rejected")
    for index in range(12):
        ProductReview.objects.create(
            product=product, rating=4, status="approved", author_display=f"Reader {index}", body="<b>Plain</b>",
        )
    context = product_information_context(product)
    assert context["review_summary"] == {"count": 12, "average": 4.0}
    assert len(context["product_reviews"]) == 10
    assert context["product_reviews"][0]["author_display"] == "Reader 11"
    assert context["product_reviews"][0]["body"] == "<b>Plain</b>"
    for rating in [0, 6]:
        with pytest.raises(ValidationError):
            ProductReview(product=product, rating=rating).full_clean()
        with pytest.raises(IntegrityError), transaction.atomic():
            ProductReview.objects.create(product=product, rating=rating)
    with pytest.raises(ValidationError):
        ProductReview(product=product, rating=3, body="x" * 3001).full_clean()
    with pytest.raises(IntegrityError), transaction.atomic():
        ProductReview.objects.create(product=product, rating=3, status="unknown")


@pytest.mark.parametrize("row_count", [1, 20])
def test_context_query_count_is_bounded(product, django_assert_num_queries, row_count):
    guide = guide_for(product, is_published=True, source_label="Maker")
    for index in range(row_count):
        SizeGuideRow.objects.create(
            guide=guide, size=str(index), waist_min_cm=Decimal("50"), waist_max_cm=Decimal("60"),
        )
        ProductReview.objects.create(product=product, rating=3, status="approved")
    with django_assert_num_queries(5):
        result = product_information_context(product, "en")
    assert len(result["size_guide"]["rows"]) == row_count
