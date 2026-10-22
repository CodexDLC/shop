import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from web.cart.models import PromoCode
from web.catalog.models import Brand, Category, Product, ProductVariant
from web.customer.models import CustomerAddress
from web.orders.models import Order, OrderLine
from web.payments.models import PaymentAttempt, RefundAttempt
from web.staff.models import StaffAuditEvent
from web.staff.operations.presentation import table_row
from web.staff.operations.registry import detail_route, record_permission
from web.staff.operations.selectors import records
from web.support.models import ContactTicket

pytestmark = pytest.mark.django_db
KINDS = ("orders", "customers", "support", "stock", "payments", "promos", "audit", "team")


def staff_user(*permissions, owner=False):
    user = get_user_model().objects.create_user(username="operator", is_staff=True, is_superuser=owner)
    for name in permissions:
        app, codename = name.split(".")
        user.user_permissions.add(Permission.objects.get(content_type__app_label=app, codename=codename))
    return user


def order_record():
    customer = get_user_model().objects.create_user(username="buyer", email="private-buyer@example.test")
    order = Order.objects.create(total_amount="19.95", user=customer, checkout_token="secret-checkout",
                                 session_owner="secret-session", address={"street": "Private street 7",
                                 "unexpected_secret": "secret-snapshot"})
    OrderLine.objects.create(order=order, sku="REAL-SKU", product_name="<script>bad()</script>",
                             quantity=1, unit_amount="19.95")
    return order


@pytest.mark.parametrize("kind", KINDS)
def test_record_pages_require_staff_and_each_model_permission(client, kind):
    url = reverse(f"staff:{kind}")
    detail = reverse(f"staff:{detail_route(kind)}", kwargs={"pk": 999})
    assert client.get(url).status_code == 302
    customer = get_user_model().objects.create_user(username="not-staff")
    client.force_login(customer)
    assert client.get(url).status_code == 403
    user = staff_user()
    client.force_login(user)
    assert client.get(url).status_code == 403
    assert client.get(detail).status_code == 403
    app, codename = record_permission(kind).split(".")
    user.user_permissions.add(Permission.objects.get(content_type__app_label=app, codename=codename))
    assert client.get(url).status_code == 200
    assert client.get(detail).status_code == 404
    assert client.post(url, {}).status_code == 405


def test_orders_show_real_lines_escape_and_scope_personal_information(client):
    order = order_record()
    user = staff_user("orders.view_order")
    client.force_login(user)
    detail = reverse("staff:order_detail", kwargs={"pk": order.pk})
    html = client.get(detail).content.decode()
    assert "REAL-SKU" in html and "&lt;script&gt;bad()&lt;/script&gt;" in html
    assert "<script>bad()" not in html
    for private in ("secret-checkout", "secret-session", "private-buyer", "Private street", "secret-snapshot"):
        assert private not in html
    for app, codename in (("auth", "view_user"), ("customer", "view_customeraddress")):
        user.user_permissions.add(Permission.objects.get(content_type__app_label=app, codename=codename))
    html = client.get(detail).content.decode()
    assert "private-buyer@example.test" in html and "Private street 7" in html
    assert "secret-snapshot" not in html
    assert "secret-checkout" not in html and "secret-session" not in html


def test_customer_addresses_need_separate_model_permission(client):
    order = order_record()
    CustomerAddress.objects.create(user=order.user, kind="standard", recipient="Private recipient",
                                   street_address="Private address", postal_code="10115", city="Berlin")
    user = staff_user("auth.view_user")
    client.force_login(user)
    detail = reverse("staff:customer_detail", kwargs={"pk": order.user_id})
    assert "Private recipient" not in client.get(detail).content.decode()
    user.user_permissions.add(Permission.objects.get(content_type__app_label="customer", codename="view_customeraddress"))
    assert "Private recipient" in client.get(detail).content.decode()
    # A staff account is never silently classified as a customer.
    assert client.get(reverse("staff:customer_detail", kwargs={"pk": user.pk})).status_code == 404


def test_payment_refunds_need_separate_permission_and_provider_reference_never_renders(client):
    order = order_record()
    payment = PaymentAttempt.objects.create(order=order, amount="19.95", method="card",
                                            provider_reference="secret-provider")
    refund = RefundAttempt.objects.create(payment=payment, amount="5.00", provider_reference="secret-refund")
    user = staff_user("payments.view_paymentattempt")
    client.force_login(user)
    detail = reverse("staff:payment_detail", kwargs={"pk": payment.pk})
    html = client.get(detail).content.decode()
    assert str(payment.operation_id) in html
    assert str(refund.operation_id) not in html and "secret-provider" not in html
    user.user_permissions.add(Permission.objects.get(content_type__app_label="payments", codename="view_refundattempt"))
    html = client.get(detail).content.decode()
    assert str(refund.operation_id) in html and "5,00 €" in html
    assert "secret-refund" not in html and "secret-provider" not in html


def test_real_support_stock_promos_audit_and_team_details(client):
    user = staff_user(owner=True)
    client.force_login(user)
    ticket = ContactTicket.objects.create(name="Actual buyer", email="actual@example.test", topic="versand",
                                          message="<img src=x onerror=bad()>Delivery question")
    brand = Brand.objects.create(slug="actual-brand", name="Actual Brand")
    category = Category.objects.create(slug="actual-category", name_key="category.actual")
    product = Product.objects.create(slug="actual-product", model_name="Actual Product", brand=brand, category=category)
    variant = ProductVariant.objects.create(product=product, sku="ACTUAL-STOCK", color_code="black",
                                             color_name_key="colour.black", size="M", price="20.00", demo_quantity=7)
    promo = PromoCode.objects.create(code="ACTUAL10", kind="percent", value="10.00")
    event = StaffAuditEvent.objects.create(actor=user, action="product.edit", object_type="Product", object_id=str(product.pk))
    for kind, obj, expected in (("support", ticket, "Delivery question"), ("stock", variant, "ACTUAL-STOCK"),
                                ("promos", promo, "ACTUAL10"), ("audit", event, "product.edit"),
                                ("team", user, "operator")):
        response = client.get(reverse(f"staff:{detail_route(kind)}", kwargs={"pk": obj.pk}))
        assert response.status_code == 200
        assert expected in response.content.decode()
        assert client.post(reverse(f"staff:{detail_route(kind)}", kwargs={"pk": obj.pk}), {}).status_code == 405
    html = client.get(reverse("staff:support_detail", kwargs={"pk": ticket.pk})).content.decode()
    assert "<img src=x" not in html and "&lt;img" in html
    assert ProductVariant.objects.get(pk=variant.pk).demo_quantity == 7
    assert not PromoCode.objects.get(pk=promo.pk).is_active


def test_pagination_filters_real_data_and_search_survives_navigation(client):
    user = staff_user("support.view_contactticket")
    client.force_login(user)
    ContactTicket.objects.bulk_create([ContactTicket(name="Buyer", email="buyer@example.test", topic="versand",
                                                     message=f"Parcel {i}") for i in range(27)])
    ContactTicket.objects.create(name="Other", email="other@example.test", topic="zahlung", message="Other", resolved=True)
    response = client.get(reverse("staff:support"), {"q": "Parcel", "status": "open"})
    assert response.context["page_obj"].paginator.count == 27
    assert len(response.context["rows"]) == 25
    assert "q=Parcel&amp;status=open&amp;page=2" in response.content.decode()
    response = client.get(reverse("staff:support"), {"q": "Parcel", "status": "open", "page": "2"})
    assert len(response.context["rows"]) == 2
    assert client.get(reverse("staff:support"), {"q": "nothing"}).context["page_obj"].paginator.count == 0


def test_order_list_selector_query_count_does_not_grow_with_lines():
    order = order_record()
    with CaptureQueriesContext(connection) as first:
        initial = list(records("orders")[:25])
        assert initial[0].item_count == 1
    OrderLine.objects.bulk_create([OrderLine(order=order, sku=f"SKU-{i}", product_name="Item", unit_amount="1.00")
                                   for i in range(10)])
    with CaptureQueriesContext(connection) as later:
        larger = list(records("orders")[:25])
        assert larger[0].item_count == 11
    assert len(first) == len(later) == 1


def test_stock_list_projects_multiple_products_and_brands_in_one_query():
    brand = Brand.objects.create(slug="budget-brand", name="Budget Brand")
    category = Category.objects.create(slug="budget-category", name_key="category.budget")
    product = Product.objects.create(slug="budget-first", model_name="First", brand=brand, category=category)
    ProductVariant.objects.create(product=product, sku="BUDGET-FIRST", color_code="black",
                                   color_name_key="colour.black", size="M", price="20.00")
    with CaptureQueriesContext(connection) as first:
        assert len([table_row("stock", obj) for obj in records("stock")[:25]]) == 1
    for index in range(10):
        product = Product.objects.create(slug=f"budget-{index}", model_name=f"Product {index}",
                                          brand=brand, category=category)
        ProductVariant.objects.create(product=product, sku=f"BUDGET-{index}", color_code="black",
                                       color_name_key="colour.black", size="M", price="20.00")
    with CaptureQueriesContext(connection) as later:
        assert len([table_row("stock", obj) for obj in records("stock")[:25]]) == 11
    assert len(first) == len(later) == 1
