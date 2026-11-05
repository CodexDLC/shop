"""Persist synthetic source facts locally. No network, routes or dispatch.

Snapshots are absolute on_hand observations fenced by both source sequence and
the local revision observed when that snapshot was requested. A local movement
invalidates the fence. Immutable completed sales can arrive out of order; each
external ID acts once and shortage remains a durable manual-review decision.
"""
from datetime import UTC, timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, OperationalError, transaction

from codex_ecommerce.inventory import (
    IdempotencyConflictError,
    InsufficientStockError,
    InventoryInvariantError,
    OperationContext,
    OperationKind,
    adjust_stock,
    commit_reservation,
    reserve_stock,
)
from codex_ecommerce.inventory.validation import aware_datetime
from web.catalog.models import ProductVariant
from web.staff.models import StaffAuditEvent

from .access import require_actor
from .expiry_service import opportunistic_cleanup, require_no_due_locked
from .fake_source_fact import FakeSourceFact
from .models import (
    ExternalInventoryConflict,
    ExternalInventoryReceipt,
    InventoryMovement,
    ReservationLine,
    StockBalance,
)
from .operation_store import MAX_INT, fingerprint, unique_constraint
from .reservation_persistence import persist_reservation_result
from .snapshots import balance_snapshot
from .write_access import service_write


def _previous(fact, payload_fingerprint, actor, now):
    receipt = ExternalInventoryReceipt.objects.filter(external_id=fact.external_id).first()
    if receipt is None:
        return None
    if receipt.fingerprint != payload_fingerprint:
        # Raise outside the transaction so the conflict fact itself survives.
        with transaction.atomic(), service_write():
            ExternalInventoryConflict.objects.get_or_create(receipt=receipt, attempted_fingerprint=payload_fingerprint,
                defaults=dict(actor=actor, observed_at=now))
        return False
    return receipt.snapshot()


def ingest_fake_fact(*, actor, fact, now):
    actor = require_actor(actor, 'ingest_fake_inventory')
    if getattr(settings, 'SHOP_CHECKOUT_STOCK_MODE', None) != 'inventory_test':
        raise PermissionDenied
    if not isinstance(fact, FakeSourceFact):
        raise InventoryInvariantError()
    aware_datetime(now)
    now = now.astimezone(UTC)
    payload = dict(external_id=fact.external_id, variant_id=fact.variant_id, kind=fact.kind,
        quantity=fact.quantity, source_revision=fact.source_revision, expected_stock_revision=fact.expected_stock_revision)
    payload_fingerprint = fingerprint(payload)
    previous = _previous(fact, payload_fingerprint, actor, now)
    if previous is False:
        raise IdempotencyConflictError()
    if previous is not None:
        return previous
    # Main-action authorization above permits bounded internal maintenance,
    # not the global expire endpoint. Each expiry commits independently before
    # the stock command, exactly as staff/checkout preflight does. A backlog
    # cannot turn stale HELD counters into a permanent shortage receipt.
    opportunistic_cleanup(actor=actor, variant_id=fact.variant_id, now=now)
    for attempt in range(2):
        try:
            with transaction.atomic(), service_write():
                variant = ProductVariant.objects.select_for_update().filter(pk=fact.variant_id).first()
                balance = StockBalance.objects.select_for_update().filter(variant_id=fact.variant_id,
                    location_id='main').first()
                previous = _previous(fact, payload_fingerprint, actor, now)
                if previous is not None:
                    result = previous
                else:
                    if variant is None:
                        raise InventoryInvariantError()
                    require_no_due_locked(variant_id=fact.variant_id, now=now)
                    before = balance_snapshot(balance)
                    result = _apply(actor, fact, now, variant, balance, before, payload_fingerprint)
            if result is False:
                raise IdempotencyConflictError()
            return result
        except IntegrityError as error:
            # Different targets with the same global external ID can race.
            # Only a committed receipt with this ID explains this collision;
            # its fingerprint decides replay/conflict on the second attempt.
            if (attempt or unique_constraint(error) != 'inventory_fake_external_id'
                    or not ExternalInventoryReceipt.objects.filter(external_id=fact.external_id).exists()):
                raise
        except OperationalError as error:
            if attempt or getattr(error.__cause__, 'sqlstate', None) not in {'40001', '40P01'}:
                raise
    raise AssertionError('Unreachable synthetic source attempt state')


def _apply(actor, fact, now, variant, balance, before, payload_fingerprint):
    status, code, after = 'needs_attention', 'stock_not_configured', before
    reservation_id = None
    if before is not None:
        if not variant.is_active:
            code = 'inactive_variant'
        elif before.revision >= MAX_INT - 1:
            code = 'revision_limit'
        else:
            latest = ExternalInventoryReceipt.objects.filter(variant_id=variant.pk).order_by(
                '-source_revision').values_list('source_revision', flat=True).first() or 0
            if fact.kind == 'snapshot' and fact.source_revision <= latest:
                status, code = 'stale_snapshot', 'source_revision_changed'
            elif fact.kind == 'snapshot' and fact.expected_stock_revision != before.revision:
                status, code = 'stale_snapshot', 'local_revision_changed'
            elif fact.kind == 'snapshot' and fact.quantity < before.reserved:
                code = 'below_local_reservations'
            else:
                try:
                    if fact.kind == 'snapshot':
                        context = OperationContext(f'{fact.variant_id}:{fact.external_id}', 'fake_external', 'synthetic',
                            'Synthetic source contract test', before.revision)
                        after = adjust_stock(before, fact.quantity, context)
                    else:
                        after, reservation_id = _commit_synthetic_sale(actor, fact, now, balance, before)
                except InsufficientStockError:
                    code = 'insufficient_available'
                else:
                    status, code = 'applied', 'applied'
                    if fact.kind == 'snapshot':
                        balance.on_hand, balance.revision = after.on_hand, after.revision
                        balance.save(update_fields=['on_hand', 'revision'])
                        movement = InventoryMovement.objects.create(variant_id=variant.pk, location_id='main',
                            kind='external_snapshot', source=context.source, owner=context.owner,
                            operation_key=context.operation_key, fingerprint=payload_fingerprint, quantity=fact.quantity,
                            expected_revision=before.revision, reason=context.reason, actor=actor,
                            before_on_hand=before.on_hand, before_reserved=before.reserved,
                            after_on_hand=after.on_hand, after_reserved=after.reserved,
                            delta_on_hand=after.on_hand - before.on_hand, delta_reserved=0, revision=after.revision)
                        StaffAuditEvent.objects.create(actor=actor, action='inventory.external_snapshot',
                            object_type=movement._meta.label_lower, object_id=str(movement.pk))
    receipt = ExternalInventoryReceipt.objects.create(external_id=fact.external_id, variant=variant,
        kind=fact.kind, quantity=fact.quantity, source_revision=fact.source_revision,
        expected_stock_revision=fact.expected_stock_revision, fingerprint=payload_fingerprint,
        status=status, code=code, actor=actor, observed_at=now,
        result_on_hand=after.on_hand if after else None, result_reserved=after.reserved if after else None,
        result_revision=after.revision if after else None, reservation_id=reservation_id)
    return receipt.snapshot()


def _commit_synthetic_sale(actor, fact, now, balance, before):
    reference = 'fake:' + fingerprint(dict(external_id=fact.external_id, variant_id=fact.variant_id))
    prefix = f'{fact.variant_id}:{fact.external_id}'
    context = OperationContext(prefix + ':reserve', 'fake_external', 'synthetic',
        'Synthetic completed sale contract test', before.revision)
    held = reserve_stock(before, reference, fact.quantity, context, now=now, expires_at=now + timedelta(seconds=1))
    line = ReservationLine(reference=reference, variant_id=fact.variant_id, location_id='main', original=fact.quantity)
    persist_reservation_result(actor=actor, kind=OperationKind.RESERVE, context=context, balance=balance,
        line=line, result=held, before_stock=before, before_line=None, quantity=fact.quantity, now=now)
    context = OperationContext(prefix + ':commit', 'fake_external', 'synthetic',
        'Synthetic completed sale contract test', held.stock.revision)
    committed = commit_reservation(held.stock, held.reservation, context, expected_reservation_revision=1, now=now)
    persist_reservation_result(actor=actor, kind=OperationKind.COMMIT, context=context, balance=balance,
        line=line, result=committed, before_stock=held.stock, before_line=held.reservation, quantity=0, now=now)
    return committed.stock, reference
