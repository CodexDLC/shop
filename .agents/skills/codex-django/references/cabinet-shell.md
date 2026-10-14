# Cabinet shell, spaces and authorization

## Register a project feature

`codex_django.cabinet` exports `declare`, `configure_space`, `cabinet_registry`, `TopbarEntry`, `SidebarItem`, and `Shortcut`. `CabinetConfig.ready()` discovers `cabinet.py` in installed Django apps. Put feature registration there; avoid a second navigation registry.

For new declarations use the space/module API: `declare(module, space=..., topbar=..., sidebar=..., shortcuts=...)`. `configure_space` supplies space metadata. Existing `CabinetSection` declarations still exist; inspect the current project before converting them.

`CabinetModuleMixin` sets request space/module/navigation context. `CabinetTemplateView` combines it with Django's `TemplateView`. **Neither grants or enforces authentication by itself.** Compose the appropriate access mixin before the template view:

```python
from codex_django.cabinet import CabinetTemplateView, StaffRequiredMixin


class OrdersView(StaffRequiredMixin, CabinetTemplateView):
    template_name = "orders/index.html"
    cabinet_space = "staff"
    cabinet_module = "orders"
```

Check the installed mixin's attribute names when adapting an existing view. Staff access is active staff or superuser; `OwnerRequiredMixin` is active superuser. Client views need the project's authentication and object/tenant policy. Navigation permission filtering does not protect a view.

## Wire URLs and context

- Context processor: `codex_django.cabinet.context_processors.cabinet`.
- Include `codex_django.cabinet.urls` with the namespace expected by project templates. The URL module has no `app_name`; the consuming project owns namespace wiring.
- `CabinetRuntimeResolver` uses explicit request context before route/path inference. `CODEX_CABINET_SPACES` configures spaces; default staff/client prefixes are `/cabinet/` and `/cabinet/my/`. Do not hardcode these into reusable components.
- The library dashboard only requires login. Site settings' default service accepts authenticated users. Override project access deliberately; a staff-looking URL does not supply staff protection.
- `CODEX_CABINET_SITE_SETTINGS_SERVICE` selects the project settings service by dotted path.

## Templates and assets

Extend `cabinet/base_cabinet.html` for staff or `cabinet/base_client.html` for client pages. The main block is **`cabinet_content`**:

```django
{% extends "cabinet/base_cabinet.html" %}
{% block cabinet_content %}
  <h1>Orders</h1>
{% endblock %}
```

For partial navigation inspect `cabinet/base_htmx.html`, the `#cab-content` target, and OOB title update `#cab-title`. Keep normal full-page navigation usable. Do not render the entire shell into a fragment target.

Staff and client shells have different assets: staff includes chart/tooltip support and the modal container; client does not automatically include all of them. Confirm required assets/container before reusing a staff-only interaction in a client page.

Theme via `--cab-*` semantic tokens and the optional project static file `cabinet/css/app_cabinet.css`. The client shell can map cabinet tokens to `--site-*`. Keep customer colors, fonts and logos in the project. A block inside an included template is not automatically an overridable block of its parent's inheritance chain.

Source: `cabinet/apps.py`, `registry.py`, `mixins.py`, `runtime.py`, `context_processors.py`, `urls.py`, `templates/cabinet/`.
