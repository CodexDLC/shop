from django.contrib import admin


class ReadonlyProductAdmin(admin.ModelAdmin):
    """Workflow-owned content is mutated only through the locked staff editor."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
