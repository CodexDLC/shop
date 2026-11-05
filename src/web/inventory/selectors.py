from codex_ecommerce.inventory import InventoryInvariantError

from .access import require_actor
from .models import (
    ExternalInventoryReceipt,
    InventoryChangeEvent,
    InventoryMovement,
    ReservationLine,
    StockBalance,
)
from .references import require_reference
from .snapshots import balance_snapshot, reservation_snapshot


def _page(limit, offset):
    if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or not 0 <= offset <= 10000:
        raise InventoryInvariantError()


def _variant_id(variant_id):
    if type(variant_id) is not int or variant_id <= 0:
        raise InventoryInvariantError()


def stock(*, actor, variant_id, location_id='main'):
    require_actor(actor, 'view_stockbalance')
    _variant_id(variant_id)
    if location_id != 'main':
        raise InventoryInvariantError()
    return balance_snapshot(StockBalance.objects.filter(variant_id=variant_id, location_id=location_id).first())


def balances(*, actor, limit=50, offset=0):
    require_actor(actor, 'view_stockbalance')
    _page(limit, offset)
    return list(StockBalance.objects.select_related('variant').order_by('variant_id')[offset:offset + limit])


def history(*, actor, variant_id=None, location_id='main', limit=50, offset=0):
    require_actor(actor, 'view_inventorymovement')
    _page(limit, offset)
    if location_id != 'main':
        raise InventoryInvariantError()
    rows = InventoryMovement.objects.select_related('variant').filter(location_id=location_id)
    if variant_id is not None:
        _variant_id(variant_id)
        rows = rows.filter(variant_id=variant_id)
    return list(rows[offset:offset + limit])


def reservation(*, actor, reservation_id):
    require_actor(actor, 'view_reservationline')
    require_reference(reservation_id)
    return reservation_snapshot(ReservationLine.objects.filter(reference=reservation_id).first())


def reservations(*, actor, variant_id=None, location_id='main', limit=50, offset=0):
    require_actor(actor, 'view_reservationline')
    _page(limit, offset)
    if location_id != 'main':
        raise InventoryInvariantError()
    rows = ReservationLine.objects.select_related('variant').filter(location_id=location_id)
    if variant_id is not None:
        _variant_id(variant_id)
        rows = rows.filter(variant_id=variant_id)
    return list(rows[offset:offset + limit])


def change_events(*, actor, after_id=0, limit=50):
    """Display pagination only, never a delivery checkpoint.

    Database sequence order is not transaction commit order: concurrent reads
    may skip a lower uncommitted ID. All facts remain in the journal; a future
    dispatcher needs explicit acknowledgement/claim state before draining it.
    """
    require_actor(actor, 'view_inventorychangeevent')
    _page(limit, 0)
    if type(after_id) is not int or not 0 <= after_id <= 9223372036854775807:
        raise InventoryInvariantError()
    return tuple(row.snapshot() for row in InventoryChangeEvent.objects.filter(pk__gt=after_id).order_by('pk')[:limit])


def fake_receipts(*, actor, after_id=0, limit=50):
    """Bounded local display of synthetic outcomes, not a delivery cursor."""
    require_actor(actor, 'view_externalinventoryreceipt')
    _page(limit, 0)
    if type(after_id) is not int or not 0 <= after_id <= 9223372036854775807:
        raise InventoryInvariantError()
    return tuple(row.snapshot() for row in ExternalInventoryReceipt.objects.filter(pk__gt=after_id).order_by('pk')[:limit])
