from codex_django.cabinet.quick_access import get_enabled_staff_quick_access
from codex_django.cabinet.runtime import CabinetRuntimeResolver
from django.urls import reverse

from web.staff.models import CabinetPreferences


def staff_cabinet(request):
    """Read-only shell adapter using library registry; never create settings on GET."""
    user = request.user
    if not getattr(request, "cabinet_space", None) == "staff" or not user.is_authenticated:
        return {}
    resolved = CabinetRuntimeResolver().get_context(request)
    def allowed(item):
        return not item.permissions or any(user.has_perm(p) for p in item.permissions)
    can_catalog = user.has_perm("catalog.view_product")
    can_settings = user.has_perm("staff.change_cabinetpreferences")
    selected = CabinetPreferences.objects.filter(pk=1).values_list("quick_access_keys", flat=True).first() or []
    entries = [entry for entry in resolved.topbar_entries
               if (entry.group != "admin" or can_settings)
               and (str(entry.url) != reverse("staff:products") or can_catalog)]
    entries.sort(key=lambda entry: (entry.group == "admin", entry.order))
    return {
        "cabinet_sidebar": [item for item in resolved.sidebar if allowed(item)],
        "cabinet_topbar_entries": entries, "cabinet_nav": [], "cabinet_topbar_actions": [],
        "cabinet_quick_access": get_enabled_staff_quick_access(selected, user),
        "cabinet_active_module": resolved.module, "cabinet_active_topbar": resolved.active_topbar,
        "cabinet_branding": resolved.branding, "cabinet_space": "staff",
        "cabinet_settings_url": reverse("staff:catalog_settings") if resolved.module == "catalog" and can_catalog else None,
        "staff_global_settings_url": reverse("staff:settings") if can_settings else None,
        "cabinet_site_url": reverse("shop:home"), "cabinet_client_switch_url": None,
        "cabinet_logout_url": reverse("staff:logout_confirm"), "notification_items": [],
    }
