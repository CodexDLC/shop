from django.urls import path

from .catalog_detail_view import CatalogDetailView
from .catalog_reference_edit_view import CatalogReferenceEditView
from .catalog_resource_view import CatalogResourceView
from .category_detail_view import CategoryDetailView
from .category_edit_view import CategoryEditView
from .category_list_view import CategoryListView
from .registry import RESOURCES

urlpatterns = [
    path("catalog/categories/", CategoryListView.as_view(), name="categories"),
    path("catalog/categories/new/", CategoryEditView.as_view(), name="category_add"),
    path("catalog/categories/<int:pk>/", CategoryDetailView.as_view(), name="category_detail"),
    path("catalog/categories/<int:pk>/edit/", CategoryEditView.as_view(), name="category_edit"),
    path("catalog/categories/<int:pk>/preview/", CategoryDetailView.as_view(preview=True), name="category_preview"),
]
for resource, (_, singular, fields) in RESOURCES.items():
    if resource == "categories":
        continue
    segment = resource.replace("_", "-")
    urlpatterns += [
        path(f"catalog/{segment}/", CatalogResourceView.as_view(resource=resource), name=resource),
        path(f"catalog/{segment}/<int:pk>/", CatalogDetailView.as_view(resource=resource), name=f"{singular}_detail"),
    ]
    if fields:
        urlpatterns.append(path(
            f"catalog/{segment}/<int:pk>/edit/", CatalogReferenceEditView.as_view(resource=resource),
            name=f"{singular}_edit",
        ))
        if resource not in ("categories", "tags"):
            urlpatterns.append(path(
                f"catalog/{segment}/new/", CatalogReferenceEditView.as_view(resource=resource), name=f"{singular}_add",
            ))
