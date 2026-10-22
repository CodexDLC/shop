from .readonly_product_admin import ReadonlyProductAdmin


class CategoryAdmin(ReadonlyProductAdmin):
    change_form_template = "admin/catalog/category/change_form.html"
