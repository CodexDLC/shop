from django.db.models import Q

from .registry import RESOURCES


def resource_queryset(resource, query=""):
    model, _, _ = RESOURCES[resource]
    queryset = model.objects.order_by("pk")
    if resource == "size_guides":
        queryset = queryset.select_related("brand", "category")
        search_fields = ["title", "brand__name"]
    elif resource in ("reviews", "photos"):
        queryset = queryset.select_related("product", "product__brand")
        search_fields = ["product__model_name", "product__brand__name"]
        if resource == "reviews":
            search_fields += ["body", "author_display"]
            queryset = queryset.order_by("-created_at", "-pk")
    else:
        search_fields = ["slug", "name"] if resource in ("brands", "materials", "properties") else ["slug"]
    if query:
        condition = Q()
        for field in search_fields:
            condition |= Q(**{f"{field}__icontains": query})
        queryset = queryset.filter(condition)
    return queryset
