from django.db.models import Count, Q

from .registry import record_model


def records(kind, query="", status=""):
    """Bounded presentation queries; no side effects and no external providers."""
    queryset = record_model(kind).objects.all()
    if kind == "orders":
        queryset = queryset.annotate(item_count=Count("lines"))
        if query:
            # Searching order/customer identifiers must not reveal customer PII.
            queryset = queryset.filter(Q(reference__icontains=query) | Q(lines__sku__icontains=query)).distinct()
        if status:
            queryset = queryset.filter(status=status)
    elif kind in ("customers", "team"):
        queryset = queryset.filter(is_staff=(kind == "team"))
        if query:
            queryset = queryset.filter(Q(username__icontains=query) | Q(email__icontains=query)
                                       | Q(first_name__icontains=query) | Q(last_name__icontains=query))
        if status:
            queryset = queryset.filter(is_active=(status == "active"))
    elif kind == "support":
        if query:
            queryset = queryset.filter(Q(topic__icontains=query) | Q(message__icontains=query)
                                       | Q(name__icontains=query) | Q(email__icontains=query))
        if status:
            queryset = queryset.filter(resolved=(status == "resolved"))
    elif kind == "stock":
        queryset = queryset.select_related("product", "product__brand")
        if query:
            queryset = queryset.filter(Q(sku__icontains=query) | Q(product__model_name__icontains=query))
        if status:
            queryset = queryset.filter(is_active=(status == "active"))
    elif kind == "payments":
        queryset = queryset.select_related("order")
        if query:
            queryset = queryset.filter(Q(operation_id__icontains=query) | Q(order__reference__icontains=query))
        if status:
            queryset = queryset.filter(status=status)
    elif kind == "promos":
        if query:
            queryset = queryset.filter(code__icontains=query)
        if status:
            queryset = queryset.filter(is_active=(status == "active"))
    elif kind == "audit":
        queryset = queryset.select_related("actor")
        if query:
            queryset = queryset.filter(Q(action__icontains=query) | Q(object_type__icontains=query)
                                       | Q(object_id__icontains=query))
    return queryset.order_by("-pk")


def record_detail(kind, pk, user):
    queryset = records(kind)
    if kind == "orders":
        queryset = queryset.prefetch_related("lines")
        if user.has_perm("payments.view_paymentattempt"):
            queryset = queryset.prefetch_related("payment_attempts")
        if user.has_perm("auth.view_user"):
            queryset = queryset.select_related("user")
    elif kind == "customers" and user.has_perm("customer.view_customeraddress"):
        queryset = queryset.prefetch_related("customer_addresses")
    elif kind == "payments" and user.has_perm("payments.view_refundattempt"):
        queryset = queryset.prefetch_related("refund_attempts")
    elif kind == "team" and user.has_perm("auth.view_group"):
        queryset = queryset.prefetch_related("groups")
    return queryset.get(pk=pk)
