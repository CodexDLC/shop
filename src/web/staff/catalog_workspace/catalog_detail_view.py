from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.urls import reverse

from web.staff.views.staff_page_view import StaffPageView

from .presentation import resource_card, resource_label
from .registry import RESOURCES
from .selectors import resource_queryset


class CatalogDetailView(StaffPageView):
    cabinet_module = "catalog"
    template_name = "staff/catalog_workspace/detail.html"
    resource = None
    http_method_names = ["get", "head", "options"]

    def dispatch(self, request, *args, **kwargs):
        model = RESOURCES[self.resource][0]
        if request.user.is_authenticated and not request.user.has_perm(f"catalog.view_{model._meta.model_name}"):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        model, singular, fields = RESOURCES[self.resource]
        obj = get_object_or_404(resource_queryset(self.resource), pk=self.kwargs["pk"])
        products = []
        if self.request.user.has_perm("catalog.view_product"):
            if self.resource in ("reviews", "photos"):
                products = [obj.product]
            elif self.resource not in ("size_guides",):
                products = obj.products.select_related("brand").order_by("pk")[:30]
        if self.resource == "size_guides":
            context["guide_rows"] = obj.rows.all()
        card = resource_card(self.resource, obj)
        context.update(
            object=obj, object_label=resource_label(self.resource, obj),
            resource=self.resource, title_key=f"staff.workspace_catalog.{self.resource}",
            values=card["values"], technical=card["technical"], photo_url=card["photo"], products=products, back_url=reverse(f"staff:{self.resource}"),
            edit_url=(reverse(f"staff:{singular}_edit", kwargs={"pk": obj.pk})
                      if fields and self.request.user.has_perm(f"catalog.change_{model._meta.model_name}") else ""),
        )
        return context
