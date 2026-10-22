from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse

from web.catalog.models import Category, Product
from web.localization import translate_text
from web.staff.audit import record_staff_action
from web.staff.views.staff_page_view import StaffPageView

from .category_form import CategoryForm
from .category_tree import branch_ids, category_rows, check_category_state, issue_category_state


class CategoryEditView(PermissionRequiredMixin, StaffPageView):
    cabinet_module = "catalog"
    template_name = "staff/categories/form.html"
    http_method_names = ["get", "post", "head", "options"]

    def get_permission_required(self):
        action = "change" if self.kwargs.get("pk") else "add"
        return (f"catalog.{action}_category", "catalog.view_category")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        categories = category_rows()
        category = kwargs.get("category")
        if category is None and self.kwargs.get("pk"):
            category = get_object_or_404(Category, pk=self.kwargs["pk"])
        branch = branch_ids(categories, category.pk) if category else set()
        context.update(category=category,
                       form=kwargs.get("form") or CategoryForm(instance=category, categories=categories),
                       original_state=issue_category_state(categories, category.pk if category else None),
                       published_count=sum(row.published_count for row in categories if row.pk in branch))
        return context

    def post(self, request, *args, **kwargs):
        category = None
        saved = False
        uploaded_name = None
        try:
            with transaction.atomic():
                # Serialize every structural edit, including two concurrent reparent operations.
                categories = list(Category.objects.select_for_update().order_by("pk"))
                if kwargs.get("pk"):
                    category = next((row for row in categories if row.pk == kwargs["pk"]), None)
                    if category is None:
                        get_object_or_404(Category, pk=kwargs["pk"])
                previous = (category.parent_id, category.is_visible, category.section) if category else None
                valid_state = check_category_state(request.POST.get("original_state", ""), categories,
                                                   category.pk if category else None)
                branch = branch_ids(categories, category.pk) if category else set()
                form = CategoryForm(request.POST, request.FILES, instance=category, categories=categories)
                valid = form.is_valid()
                if not valid_state:
                    form.add_error(None, translate_text("staff.workspace_catalog.stale"))
                    valid = False
                if valid and previous != (form.instance.parent_id, form.instance.is_visible, form.instance.section):
                    # Product state is never altered here; the additional permission protects exposure changes.
                    linked = list(Product.objects.select_for_update().filter(category_id__in=branch).order_by("pk"))
                    if any(product.is_active for product in linked):
                        if not request.user.has_perm("catalog.publish_product"):
                            form.add_error(None, translate_text("staff.categories.publish_permission"))
                            valid = False
                        if not form.cleaned_data.get("confirm_visibility"):
                            form.add_error("confirm_visibility", translate_text("staff.categories.confirm_required"))
                            valid = False
                if valid:
                    category = form.save(commit=False)
                    if not category.name_key:
                        category.name_key = f"catalog.category.{category.slug}"
                    if form.cleaned_data.get("remove_image"):
                        category.image = ""
                    if form.cleaned_data.get("upload"):
                        upload = form.cleaned_data["upload"]
                        category.image.save(upload.name, upload, save=False)
                        uploaded_name = category.image.name
                    category.save()
                    record_staff_action(request, "reference.category.saved", category)
                    saved = True
        except IntegrityError:
            if uploaded_name:
                Category._meta.get_field("image").storage.delete(uploaded_name)
            form.add_error(None, translate_text("staff.workspace_catalog.conflict"))
        except Exception:
            if uploaded_name:
                Category._meta.get_field("image").storage.delete(uploaded_name)
            raise
        if saved:
            messages.success(request, translate_text("staff.workspace_catalog.saved"))
            return HttpResponseRedirect(reverse("staff:category_detail", kwargs={"pk": category.pk}))
        persisted_category = Category.objects.filter(pk=kwargs.get("pk")).first() if kwargs.get("pk") else None
        return self.render_to_response(self.get_context_data(category=persisted_category, form=form), status=400)
