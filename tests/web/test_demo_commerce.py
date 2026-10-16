from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from web.cart.demo import get_cart_demo_context
from web.cart.models import Cart, CartLine
from web.orders.demo import get_order_demo_context
from web.orders.models import Order, OrderLine
from web.payments.demo import get_payment_demo_context
from web.payments.models import PaymentAttempt, RefundAttempt


@pytest.mark.django_db
def test_cart_rejects_duplicate_sku_and_zero_quantity():
    cart = Cart.objects.create()
    CartLine.objects.create(cart=cart, sku="DEMO-1", quantity=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        CartLine.objects.create(cart=cart, sku="DEMO-1", quantity=2)
    with pytest.raises(IntegrityError), transaction.atomic():
        CartLine.objects.create(cart=cart, sku="DEMO-2", quantity=0)


@pytest.mark.django_db
def test_order_keeps_snapshot_and_rejects_negative_money():
    order = Order.objects.create(total_amount=Decimal("49.95"))
    line = OrderLine.objects.create(
        order=order, sku="DEMO-1", product_name="Purchase-time model", quantity=1,
        unit_amount=Decimal("49.95"), colour_name="Black", size_name="M",
    )
    line.refresh_from_db()
    assert line.unit_amount == Decimal("49.95")
    assert line.product_name == "Purchase-time model"
    with pytest.raises(IntegrityError), transaction.atomic():
        Order.objects.create(total_amount=Decimal("-0.01"))


@pytest.mark.django_db
def test_payment_operation_identity_and_live_mode_rejected():
    order = Order.objects.create(total_amount=Decimal("49.95"))
    payment = PaymentAttempt.objects.create(order=order, amount=order.total_amount, method="paypal")
    assert payment.provider == "stripe"
    assert payment.mode == "demo"
    with pytest.raises(IntegrityError), transaction.atomic():
        PaymentAttempt.objects.create(
            order=order, amount=order.total_amount, method="paypal", operation_id=payment.operation_id,
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        PaymentAttempt.objects.create(order=order, amount=order.total_amount, method="card", mode="live")
    with pytest.raises(IntegrityError), transaction.atomic():
        RefundAttempt.objects.create(payment=payment, amount=Decimal("0.00"))
    assert payment.refund_attempts.count() == 0


@pytest.mark.django_db
def test_demo_contexts_are_read_only_and_fresh(django_assert_num_queries, monkeypatch):
    def forbidden_network(*args, **kwargs):
        raise AssertionError("Demo presentation must not call network")

    monkeypatch.setattr("socket.create_connection", forbidden_network)
    with django_assert_num_queries(0):
        cart = get_cart_demo_context()
        order = get_order_demo_context()
        payment = get_payment_demo_context()
        cart["cart"]["lines"].clear()
        assert get_cart_demo_context()["cart"]["lines"]
    assert order["order"]["tracking_number"] is None
    assert payment["payment"]["mode"] == "demo"
    assert payment["payment"]["can_charge"] is False
    assert payment["payment"]["can_refund"] is False
    assert Order.objects.count() == PaymentAttempt.objects.count() == Cart.objects.count() == 0
