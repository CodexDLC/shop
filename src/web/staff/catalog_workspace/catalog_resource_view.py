from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.urls import reverse

from web.localization.translation import translate_text
from web.staff.views.staff_page_view import StaffPageView

from .presentation import resource_label
from .registry import RESOURCES
from .selectors import resource_queryset


class CatalogResourceView(StaffPageView):
    cabinet_module = "catalog"
    template_name = "staff/catalog_workspace/list.html"
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
        query = self.request.GET.get("q", "").strip()[:200]
        page = Paginator(resource_queryset(self.resource, query), 30).get_page(self.request.GET.get("page"))
        rows = []
        for obj in page:
            if self.resource in ("reviews", "photos"):
                label = f"{obj.product.brand.name} · {obj.product.model_name}"
                secondary = (
                    f"{obj.rating}/5 · {translate_text(f'staff.workspace_catalog.status.{obj.status}')}"
                    if self.resource == "reviews" else obj.color_code
                )
            elif self.resource == "size_guides":
                label, secondary = resource_label(self.resource, obj), obj.category.name if obj.category_id else "—"
            else:
                label = resource_label(self.resource, obj)
                secondary = obj.slug
            route = f"staff:{singular}_detail"
            rows.append({"object": obj, "label": label, "secondary": secondary,
                         "url": reverse(route, kwargs={"pk": obj.pk})})
        params = self.request.GET.copy()
        params.pop("page", None)
        context.update(
            resource=self.resource, title_key=f"staff.workspace_catalog.{self.resource}",
            page_obj=page, rows=rows, search_query=query, page_query=params.urlencode(),
            add_url=(reverse(f"staff:{singular}_add") if fields
                     and self.resource not in ("categories", "tags")
                     and self.request.user.has_perm(f"catalog.add_{model._meta.model_name}") else ""),
        )
        return context
