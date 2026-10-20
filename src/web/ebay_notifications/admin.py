from django.contrib import admin

from .models import DeletionReceipt


@admin.register(DeletionReceipt)
class DeletionReceiptAdmin(admin.ModelAdmin):
    list_display = ("notification_id", "received_at", "status")
    list_filter = ("status",)
    readonly_fields = tuple(field.name for field in DeletionReceipt._meta.fields)
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
