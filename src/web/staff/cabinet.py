from codex_django.cabinet import SidebarItem, TopbarEntry, configure_space, declare
from django.urls import reverse_lazy
from django.utils.functional import lazy

from web.localization import translate_text

label = lazy(translate_text, str)
configure_space("staff", label="Männermasche", icon="bi-shop")
declare("overview", space="staff",
        topbar=TopbarEntry(group="services", label=label("staff.nav.overview"), icon="bi-grid", url=reverse_lazy("staff:home"), order=10),
        sidebar=[SidebarItem(label=label("staff.nav.overview"), url=reverse_lazy("staff:home"), icon="bi-grid", order=10)])
declare("catalog", space="staff",
        topbar=TopbarEntry(group="services", label=label("staff.nav.catalog"), icon="bi-box", url=reverse_lazy("staff:products"), order=20),
        sidebar=[SidebarItem(label=label("staff.nav.products"), url=reverse_lazy("staff:products"), icon="bi-box", order=10,
                             permissions=("catalog.view_product",))],
        settings_url=reverse_lazy("staff:catalog_settings"))
declare("management", space="staff",
        topbar=TopbarEntry(group="admin", label=label("staff.nav.settings"), icon="bi-gear", url=reverse_lazy("staff:settings"), order=10),
        sidebar=[SidebarItem(label=label("staff.nav.quick_access"), url=reverse_lazy("staff:settings"), icon="bi-lightning", order=10,
                             permissions=("staff.change_cabinetpreferences",))])
