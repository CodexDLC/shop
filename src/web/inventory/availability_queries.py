"""Attach one scalar main-warehouse snapshot without extra queries or relation fan-out."""
from django.db.models import BigIntegerField, F, OuterRef, Subquery, Value

from .checkout_policy import stock_mode
from .models import StockBalance


def with_availability(variants):
    mode = stock_mode()
    if mode == 'demo':
        quantity = F('demo_quantity')
    else:
        balance = StockBalance.objects.filter(variant_id=OuterRef('pk'), location_id='main')
        # NULL is intentionally preserved: unconfigured differs from configured zero.
        quantity = Subquery(balance.annotate(available=F('on_hand') - F('reserved'))
                            .values('available')[:1], output_field=BigIntegerField())
    return variants.annotate(availability_quantity=quantity, availability_mode=Value(mode))
