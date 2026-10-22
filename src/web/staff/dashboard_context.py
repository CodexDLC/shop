from django.db.models import Count, Q
from django.urls import reverse

from web.catalog.models import Product
from web.orders.models import Order
from web.support.models import ContactTicket


def dashboard_context(user):
    cards = []
    recent = []
    if user.has_perm("catalog.view_product"):
        counts = Product.objects.aggregate(
            products=Count("pk"), drafts=Count("pk", filter=Q(is_active=False) & ~Q(editorial_state="review")),
            review=Count("pk", filter=Q(is_active=False, editorial_state="review")),
        )
        for key, state in (("products", ""), ("drafts", "draft"), ("review", "review")):
            cards.append({"label": f"staff.workspace.overview.{key}", "count": counts[key],
                          "url": reverse("staff:products") + (f"?state={state}" if state else "")})
        recent = Product.objects.select_related("brand").order_by("-pk")[:5]
    if user.has_perm("orders.view_order"):
        cards.append({"label": "staff.workspace.overview.orders", "count": Order.objects.filter(is_test=True).count(),
                      "url": reverse("staff:orders")})
    if user.has_perm("support.view_contactticket"):
        cards.append({"label": "staff.workspace.overview.support",
                      "count": ContactTicket.objects.filter(resolved=False).count(),
                      "url": reverse("staff:support")})
    return {"workspace_cards": cards, "workspace_recent_products": recent}
