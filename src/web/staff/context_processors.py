from codex_django.cabinet import cabinet_registry
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
    module = resolved.module if resolved.module in {"catalog", "operations", "management"} else "catalog"
    def allowed(item):
        return not item.permissions or any(user.has_perm(p) for p in item.permissions)
    can_catalog = user.has_perm("catalog.view_product")
    can_settings = (user.has_perm("staff.change_cabinetpreferences") or user.has_perm("shop.change_storeidentity")
                    or user.has_perm("seo.view_seopage"))
    selected = CabinetPreferences.objects.filter(pk=1).values_list("quick_access_keys", flat=True).first() or []
    entries = [entry for entry in resolved.topbar_entries
               if (entry.group != "admin" or can_settings)
               and (str(entry.url) != reverse("staff:products") or can_catalog)]
    entries.sort(key=lambda entry: (entry.group == "admin", entry.order))
    global_settings = reverse("staff:workspace_preview", kwargs={"section": "store_settings"})
    sidebar = [item for item in cabinet_registry.get_sidebar("staff", module)
               if allowed(item) and str(item.url) != global_settings]
    matching = [str(item.url) for item in sidebar if request.path.startswith(str(item.url))]
    active_url = max(matching, key=len, default="")
    groups = []
    for group_module, key in (("catalog", "shop"), ("operations", "operations"), ("management", "management")):
        available = sorted((item for item in cabinet_registry.get_sidebar("staff", group_module) if allowed(item)),
                           key=lambda item: item.order)
        if available:
            first = next((item for item in available if str(item.url) != reverse("staff:settings")), available[0])
            groups.append({"key": key, "label_key": f"staff.workspace.group.{key}",
                           "url": str(first.url), "active": module == group_module})
    return {
        "staff_primary_groups": groups, "staff_workspace_group": module,
        "cabinet_sidebar": sorted(sidebar, key=lambda item: item.order),
        "staff_sidebar_rows": [{"item": item, "active": str(item.url) == active_url}
                               for item in sorted(sidebar, key=lambda item: item.order)],
        "cabinet_topbar_entries": entries, "cabinet_nav": [], "cabinet_topbar_actions": [],
        "cabinet_quick_access": get_enabled_staff_quick_access(selected, user),
        "cabinet_active_module": resolved.module, "cabinet_active_topbar": resolved.active_topbar,
        "cabinet_branding": resolved.branding, "cabinet_space": "staff",
        "cabinet_settings_url": (
            reverse("staff:catalog_settings") if module == "catalog" and can_catalog else
            reverse("staff:workspace_preview", kwargs={"section": "operations_settings"})
            if module == "operations" and user.has_perm("orders.view_order") else None
        ),
        "staff_global_settings_url": global_settings if user.has_perm("shop.change_storeidentity") else None,
        "cabinet_site_url": reverse("shop:home"), "cabinet_client_switch_url": reverse("customer:overview"),
        "cabinet_logout_url": reverse("staff:logout_confirm"), "notification_items": [],
    }
