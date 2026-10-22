from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect

from web.catalog.models import Product, ProductImage
from web.localization.translation import translate_text
from web.staff.audit import record_staff_action
from web.staff.forms.product_photo_form import ProductPhotoForm
from web.staff.photo_editing import delete_photo, save_photo
from web.staff.product_editing import check_state, issue_state, mark_changed, require_editable
from web.staff.views.staff_page_view import StaffPageView


class ProductPhotosView(PermissionRequiredMixin, StaffPageView):
    permission_required = ("catalog.view_product", "catalog.view_productimage")
    template_name = "staff/product_photos.html"
    cabinet_module = "catalog"
    http_method_names = ["get", "post", "head", "options"]

    def render_editor(self, product, *, form=None, image=None, error="", status=200):
        colors = list(product.variants.order_by("color_code").values_list("color_code", flat=True).distinct())
        rows = [{"image": item, "form": form if image and item.pk == image.pk else ProductPhotoForm(
            product=product, image=item, color_codes=colors)} for item in product.images.all()]
        token = self.request.POST.get("original_state", "") if status == 409 else issue_state(product)
        response = self.render_to_response(self.get_context_data(
            product=product, photo_rows=rows, new_form=form if image is None and form else ProductPhotoForm(
                product=product, color_codes=colors, initial={"position": 0}), original_state=token,
            photo_error=error), status=status)
        response["Cache-Control"] = "no-store, private"
        response["X-Robots-Tag"] = "noindex, nofollow"
        return response

    def get(self, request, *args, **kwargs):
        return self.render_editor(get_object_or_404(Product, pk=kwargs["pk"]))

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        permission = {"create": "add_productimage", "update": "change_productimage",
                      "delete": "delete_productimage"}.get(action)
        if not permission or not request.user.has_perms(("catalog.change_product", f"catalog.{permission}")):
            raise PermissionDenied
        created_files = []
        form = image = None
        try:
            with transaction.atomic():
                product = get_object_or_404(Product.objects.select_for_update(), pk=kwargs["pk"])
                require_editable(product)
                if action != "create":
                    try:
                        image_id = int(request.POST.get("image_id", ""))
                    except (ValueError, TypeError):
                        raise Http404 from None
                    image = get_object_or_404(ProductImage, product=product, pk=image_id)
                if not check_state(product, request.POST.get("original_state", "")):
                    return self.render_editor(product, error=translate_text("staff.photos.stale"), status=409)
                if action == "delete":
                    delete_photo(image)
                else:
                    form = ProductPhotoForm(request.POST, request.FILES, product=product, image=image)
                    if not form.is_valid():
                        return self.render_editor(product, form=form, image=image, status=400)
                    save_photo(product, image, form.cleaned_data, created_files)
                mark_changed(product)
                record_staff_action(request, f"photos.{action}", product)
            messages.success(request, translate_text("staff.photos.saved"))
            return redirect("staff:product_photos", pk=product.pk)
        except (IntegrityError, ValidationError) as error:
            if isinstance(error, ValidationError):
                message = "; ".join(error.messages)
                status = 400
            else:
                message = translate_text("staff.photos.conflict")
                status = 409
            return self.render_editor(product, form=form, image=image, error=message, status=status)
        finally:
            # On rollback the database has no references to these freshly generated names.
            # Existing originals are never removed when replacing/deleting a DB relationship.
            for storage, name in created_files:
                if not ProductImage.objects.filter(file=name).exists():
                    storage.delete(name)
