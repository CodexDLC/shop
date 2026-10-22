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
        topbar=TopbarEntry(group="services", label=label("staff.workspace.group.shop"), icon="bi-box", url=reverse_lazy("staff:products"), order=20),
        sidebar=[SidebarItem(label=label("staff.nav.products"), url=reverse_lazy("staff:products"), icon="bi-box", order=10,
                             permissions=("catalog.view_product",)), *[
            SidebarItem(label=label(f"staff.workspace.nav.{name}"), url=reverse_lazy(f"staff:{name}"),
                        icon=icon, order=order, permissions=(permission,))
            for name, icon, order, permission in (
                ("brands", "bi-bookmark", 20, "catalog.view_brand"),
                ("categories", "bi-diagram-3", 30, "catalog.view_category"),
                ("materials", "bi-layers", 40, "catalog.view_material"),
                ("properties", "bi-list-check", 50, "catalog.view_productproperty"),
                ("tags", "bi-tags", 60, "catalog.view_tag"),
                ("size_guides", "bi-rulers", 70, "catalog.view_sizeguide"),
                ("reviews", "bi-chat-square-text", 80, "catalog.view_productreview"),
                ("photos", "bi-images", 90, "catalog.view_productimage"),
            )]],
        settings_url=reverse_lazy("staff:catalog_settings"))
declare("management", space="staff",
        topbar=TopbarEntry(group="admin", label=label("staff.workspace.group.management"), icon="bi-gear", url=reverse_lazy("staff:settings"), order=10),
        sidebar=[SidebarItem(label=label("staff.nav.quick_access"), url=reverse_lazy("staff:settings"), icon="bi-lightning", order=10,
                             permissions=("staff.change_cabinetpreferences",)), *[
            SidebarItem(label=label(f"staff.workspace.nav.{name}"), url=reverse_lazy(f"staff:{name}"),
                        icon=icon, order=order, permissions=(permission,))
            for name, icon, order, permission in (
                ("promos", "bi-percent", 20, "cart.view_promocode"),
                ("payments", "bi-credit-card", 30, "payments.view_paymentattempt"),
                ("seo_overview", "bi-search", 45, "seo.view_seopage"),
                ("team", "bi-person-badge", 60, "auth.view_user"),
                ("audit", "bi-clock-history", 80, "staff.view_staffauditevent"),
            )], *[
            SidebarItem(label=label(f"staff.workspace.nav.{name}"),
                        url=reverse_lazy("staff:workspace_preview", kwargs={"section": name}),
                        icon=icon, order=order, permissions=(("shop.change_storeidentity" if name == "store_settings" else "staff.change_cabinetpreferences"),))
            for name, icon, order in (
                ("analytics", "bi-bar-chart", 40), ("content", "bi-layout-text-window", 50),
                ("integrations", "bi-plug", 70), ("store_settings", "bi-sliders", 90),
            )]])

declare("operations", space="staff",
        topbar=TopbarEntry(group="services", label=label("staff.workspace.group.operations"),
                          icon="bi-inboxes", url=reverse_lazy("staff:orders"), order=30),
        sidebar=[SidebarItem(label=label(f"staff.workspace.nav.{name}"),
                             url=reverse_lazy(f"staff:{name}"), icon=icon, order=order,
                             permissions=(permission,))
                 for name, icon, order, permission in (
                     ("orders", "bi-receipt", 10, "orders.view_order"),
                     ("customers", "bi-people", 20, "auth.view_user"),
                     ("support", "bi-chat-left-text", 30, "support.view_contactticket"),
                     ("stock", "bi-boxes", 40, "catalog.view_productvariant"),
                 )] + [SidebarItem(label=label(f"staff.workspace.nav.{name}"),
                                      url=reverse_lazy("staff:workspace_preview", kwargs={"section": name}),
                                      icon=icon, order=order, permissions=("orders.view_order",))
                       for name, icon, order in (("shipping", "bi-truck", 50), ("returns", "bi-arrow-return-left", 60))],
        settings_url=reverse_lazy("staff:workspace_preview", kwargs={"section": "operations_settings"}))
