from django.contrib import admin

from web.cart.models import PromoCode


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'kind', 'value', 'currency', 'min_subtotal', 'is_active', 'starts_at', 'ends_at')
    list_filter = ('is_active', 'kind')
    search_fields = ('code',)
