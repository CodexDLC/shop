"""Read-only main-warehouse projections. Endpoint authorization precedes queries.

Correlated aggregates avoid line/ledger multiplication and keep reconciliation
within one database statement, so concurrent committed writes cannot produce a
false mismatch by interleaving separate balance/ledger reads.
"""
from django.core.paginator import Paginator
from django.db.models import BigIntegerField, Count, F, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce

from web.catalog.models import ProductVariant
from web.inventory.models import InventoryMovement, ReservationLine, StockBalance


def variants(*, query='', status='', threshold=None, balance=True):
    rows = ProductVariant.objects.select_related('product', 'product__brand').order_by('sku', 'pk')
    if query:
        rows = rows.filter(Q(sku__icontains=query) | Q(product__model_name__icontains=query)
            | Q(color_code__icontains=query) | Q(size__icontains=query))
    if balance:
        stock = StockBalance.objects.filter(variant_id=OuterRef('pk'), location_id='main')
        rows = rows.annotate(**{f'stock_{name}': Subquery(stock.values(name)[:1])
            for name in ('on_hand', 'reserved', 'revision')})
        rows = rows.annotate(stock_available=F('stock_on_hand') - F('stock_reserved'))
        if status == 'missing':
            rows = rows.filter(stock_on_hand__isnull=True)
        elif status == 'unavailable':
            rows = rows.filter(stock_available=0)
        elif status == 'reserved':
            rows = rows.filter(stock_reserved__gt=0)
        elif status == 'low' and threshold is not None:
            rows = rows.filter(stock_available__lte=threshold)
    return rows


def history_rows(variant_id):
    return InventoryMovement.objects.filter(variant_id=variant_id, location_id='main').select_related(
        'actor', 'variant').order_by('-pk')


def reservation_rows(variant_id):
    return ReservationLine.objects.filter(variant_id=variant_id, location_id='main').select_related(
        'variant').order_by('-created_at', 'reference')


def bounded_page(rows, number):
    try:
        number = max(1, min(int(number or 1), 401))
    except (ValueError, TypeError):
        number = 1
    return Paginator(rows, 25).get_page(number)


def reconciliation(variant_id):
    movements = InventoryMovement.objects.filter(variant_id=OuterRef('pk'), location_id='main')
    lines = ReservationLine.objects.filter(variant_id=OuterRef('pk'), location_id='main')
    expressions = {'line_reserved': (lines, Sum('remaining_reserved')), 'line_count': (lines, Count('pk')),
        'ledger_on_hand': (movements, Sum('delta_on_hand')),
        'ledger_reserved': (movements, Sum('delta_reserved')), 'ledger_count': (movements, Count('pk'))}
    annotations = {name: Coalesce(Subquery(rows.order_by().values('variant_id').annotate(total=aggregate)
        .values('total')[:1]), 0, output_field=BigIntegerField()) for name, (rows, aggregate) in expressions.items()}
    for name in ('on_hand', 'reserved', 'revision'):
        annotations['last_' + name] = Subquery(movements.order_by('-pk').values(
            'revision' if name == 'revision' else 'after_' + name)[:1])
        stock = StockBalance.objects.filter(variant_id=OuterRef('pk'), location_id='main')
        annotations[name] = Subquery(stock.values(name)[:1])
    row = ProductVariant.objects.filter(pk=variant_id).annotate(**annotations).values(*annotations).get()
    if row['on_hand'] is None:
        row.update(missing=True, matches=row['ledger_count'] == 0 and row['line_count'] == 0)
        return row
    row['matches'] = (row['on_hand'] == row['ledger_on_hand'] == row['last_on_hand']
        and row['reserved'] == row['line_reserved'] == row['ledger_reserved'] == row['last_reserved']
        and row['revision'] == row['ledger_count'] == row['last_revision'])
    return row
