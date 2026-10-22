import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.translation import override
from test_staff_operations import order_record, staff_user

from web.orders.models import OrderLine
from web.payments.models import PaymentAttempt
from web.staff.operations.selectors import record_detail

pytestmark = pytest.mark.django_db


def test_order_has_dedicated_snapshot_layout_and_private_requisites(client):
    order = order_record()
    client.force_login(staff_user("orders.view_order"))
    response = client.get(reverse("staff:order_detail", kwargs={"pk": order.pk}))
    assert "staff/operations/order_detail.html" in [t.name for t in response.templates]
    html = response.content.decode()
    assert 'class="order-workspace"' in html
    assert 'id="order-reference"' in html and 'data-copy-target="order-reference"' in html
    assert 'data-order-coupon' not in html
    assert '<script>bad()' not in html and '&lt;script&gt;bad()&lt;/script&gt;' in html
    assert '19,95 €' in html
    assert 'secret-checkout' not in html and 'secret-session' not in html
    assert 'Private street' not in html
    assert not response.context['order_detail']['show_updated']
    assert html.count('<li><time datetime=') == 1


@pytest.mark.parametrize(("language", "station", "country"), [
    ("de", "DHL Packstation 123", "Deutschland"),
    ("ru", "Постамат DHL 123", "Германия"),
])
def test_postal_addresses_are_allowlisted_and_packstation_is_readable(client, language, station, country):
    order = order_record()
    order.address = {"first_name": "Max", "last_name": "<Buyer>", "shipping_type": "packstation",
                     "packstation_number": "123", "post_number": "12345678", "postal_code": "10115",
                     "city": "Berlin", "country": "DE", "unexpected_secret": "DO-NOT-PRINT"}
    order.billing_address = {"first_name": "Max", "last_name": "Buyer", "street": "Main 1",
                             "postal_code": "10115", "city": "Berlin", "country": "DE"}
    order.save()
    client.force_login(staff_user("orders.view_order", "customer.view_customeraddress"))
    with override(language):
        url = reverse("staff:order_detail", kwargs={"pk": order.pk})
        html = client.get(url, HTTP_ACCEPT_LANGUAGE=language).content.decode()
    assert station in html and country in html and '10115 Berlin' in html and '&lt;Buyer&gt;' in html
    assert '12345678' in html and 'Main 1' in html
    assert 'DO-NOT-PRINT' not in html
    assert html.count('data-address-card') == 2


def test_payment_history_requires_permission_and_does_not_expose_provider(client):
    order = order_record()
    attempt = PaymentAttempt.objects.create(order=order, method="card", amount="19.95", status="failed",
                                             provider_reference="PRIVATE-PROVIDER")
    client.force_login(staff_user("orders.view_order"))
    url = reverse("staff:order_detail", kwargs={"pk": order.pk})
    assert 'data-payment-attempt' not in client.get(url).content.decode()
    user = client.session['_auth_user_id']
    get_user_model().objects.get(pk=user).user_permissions.add(
        Permission.objects.get(content_type__app_label="payments", codename="view_paymentattempt"))
    response = client.get(url)
    html = response.content.decode()
    assert 'data-payment-attempt' in html and 'PRIVATE-PROVIDER' not in html
    assert response.context['order_detail']['payments'][0]['created_at'] == attempt.created_at


def test_order_detail_query_budget_does_not_grow_with_lines_and_attempts():
    order = order_record()
    user = staff_user("orders.view_order", "payments.view_paymentattempt")
    user.has_perm("payments.view_paymentattempt")
    from web.staff.operations.order_presentation import order_context
    with CaptureQueriesContext(connection) as first:
        order_context(record_detail("orders", order.pk, user), user)
    OrderLine.objects.bulk_create([OrderLine(order=order, sku=f"EXTRA-{i}", product_name="Snapshot",
                                            unit_amount="1.00") for i in range(10)])
    PaymentAttempt.objects.bulk_create([PaymentAttempt(order=order, method="card", amount="1.00")
                                        for i in range(10)])
    with CaptureQueriesContext(connection) as later:
        data = order_context(record_detail("orders", order.pk, user), user)
    assert len(data['lines']) == 11 and len(data['payments']) == 10
    assert len(first) == len(later) == 3


@pytest.mark.parametrize("photo", ["https://[invalid", "javascript:alert(1)", "//untrusted/image.jpg"])
def test_invalid_snapshot_photos_do_not_break_or_execute_in_order(client, photo):
    order = order_record()
    order.lines.update(photo_url=photo)
    client.force_login(staff_user("orders.view_order"))
    response = client.get(reverse("staff:order_detail", kwargs={"pk": order.pk}))
    assert response.status_code == 200
    assert response.context['order_detail']['lines'][0]['photo_url'] == ''


def test_snapshot_photo_and_coupon_display_without_catalogue_dependency(client):
    order = order_record()
    order.lines.update(photo_url="https://images.example.test/snapshot.jpg")
    order.coupon_code = "SAVED10"
    order.save()
    client.force_login(staff_user("orders.view_order", "customer.view_customeraddress"))
    html = client.get(reverse("staff:order_detail", kwargs={"pk": order.pk})).content.decode()
    assert 'src="https://images.example.test/snapshot.jpg"' in html
    assert 'data-order-coupon' in html and 'SAVED10' in html
    assert 'Postnummer' not in html

