"""Narrow TEST checkout adapter: no caller-supplied actor or inventory scope."""
from time import monotonic

from codex_ecommerce.inventory import InventoryInvariantError, OperationContext, OperationKind, reserve_stock

from .expiry_backlog_error import ExpiryBacklogError
from .expiry_service import BATCH_TIME_LIMIT, SKU_BATCH_SIZE, _due, _expire_one, _require_autocommit
from .models import ReservationLine
from .reservation_persistence import persist_reservation_result
from .snapshots import balance_snapshot


def preflight_checkout(*, variant_ids, now):
    if len(variant_ids) > 50 or any(type(value) is not int or value <= 0 for value in variant_ids):
        raise InventoryInvariantError()
    query = _due(now).filter(variant_id__in=variant_ids, location_id='main')
    if not query.exists():
        return
    _require_autocommit()
    deadline = monotonic() + BATCH_TIME_LIMIT
    targets = list(query.values_list('variant_id', 'reference')[:100])
    attempted = {}
    for variant_id, reference in targets:
        if monotonic() >= deadline:
            break
        count = attempted.get(variant_id, 0)
        if count >= SKU_BATCH_SIZE:
            continue
        attempted[variant_id] = count + 1
        _expire_one(actor=None, variant_id=variant_id, reference=reference, now=now)
    if query.exists():
        raise ExpiryBacklogError()


def reserve_order_line(*, order, order_line, balance, expires_at, now):
    if (not order.pk or not order.is_test or order.stock_mode != 'inventory_test'
            or not order_line.pk or order_line.order_id != order.pk
            or balance is None or balance.location_id != 'main'):
        raise InventoryInvariantError()
    reference = f'orderline:{order.reference.hex}:{order_line.pk}'
    before = balance_snapshot(balance)
    context = OperationContext(f'reserve:{order_line.pk}', 'checkout_test', str(order.reference),
        'TEST checkout reservation', before.revision)
    result = reserve_stock(before, reference, order_line.quantity, context, expires_at=expires_at, now=now)
    line = ReservationLine(reference=reference, variant_id=balance.variant_id, location_id='main',
        original=result.reservation.original, order_line=order_line)
    return persist_reservation_result(actor=None, kind=OperationKind.RESERVE, context=context,
        balance=balance, line=line, result=result, before_stock=before, before_line=None,
        quantity=order_line.quantity, now=now)


def recheck_due_checkout(*, variant_ids, now):
    if _due(now).filter(variant_id__in=variant_ids, location_id='main').exists():
        raise ExpiryBacklogError()
