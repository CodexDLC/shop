from django.contrib import admin

from .models import ContactTicket


@admin.register(ContactTicket)
class ContactTicketAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "topic", "resolved")
    list_filter = ("resolved", "topic")
    readonly_fields = ("created_at", "user", "name", "email", "topic", "message")
    fields = ("created_at", "user", "name", "email", "topic", "message", "resolved")

    def has_add_permission(self, request):
        return False
