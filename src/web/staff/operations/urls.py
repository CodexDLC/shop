from django.urls import path

from .promo_edit_view import PromoEditView
from .record_detail_view import RecordDetailView
from .record_list_view import RecordListView
from .registry import detail_route
from .support_status_view import SupportStatusView

urlpatterns = [
    path("promos/new/", PromoEditView.as_view(), name="promo_add"),
    path("promos/<int:pk>/edit/", PromoEditView.as_view(), name="promo_edit"),
    path("support/<int:pk>/status/", SupportStatusView.as_view(), name="support_status"),
]
for kind in ("orders", "customers", "support", "stock", "payments", "promos", "audit", "team"):
    module = "operations" if kind in ("orders", "customers", "support", "stock") else "management"
    urlpatterns.extend([
        path(f"{kind}/", RecordListView.as_view(kind=kind, cabinet_module=module), name=kind),
        path(f"{kind}/<int:pk>/", RecordDetailView.as_view(kind=kind, cabinet_module=module),
             name=detail_route(kind)),
    ])
