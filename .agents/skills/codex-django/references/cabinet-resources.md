# Model-backed cabinet resources

Use this layer for a registered model's list, create/edit forms, and optional smart-create flow. It is not a complete admin replacement or an automatic tenant-safe CRUD API.

Public exports from `codex_django.cabinet`: `CabinetResource`, `CabinetResourceField`, `CabinetResourceListColumn`, `cabinet_resource_registry`, `build_resource_form_class`, and smart-create contracts. Define a resource around the project's concrete model and register it once during app integration.

`CabinetResource` describes key, model, section, labels, list columns/selector, search, form fields, create/edit flags, language settings, permissions, and smart handler. Read `cabinet/resources/contracts.py` for the installed signature. Registry validation checks names/model fields and duplicate keys; declared virtual fields are permitted.

Example in an installed project app's `cabinet.py`, assuming its `Category` model has a `name` field and project access policy permits the generic model-permission views:

```python
from codex_django.cabinet import (
    CabinetResource,
    CabinetResourceListColumn,
    cabinet_resource_registry,
)
from .models import Category

cabinet_resource_registry.register(
    CabinetResource(
        key="catalog_categories",
        model=Category,
        section="catalog",
        title="Categories",
        list_columns=[CabinetResourceListColumn("name", searchable=True)],
        form_fields=["name"],
    )
)
```

With library routes included in the project's `cabinet` namespace, reverse `cabinet:resource_list` using `resource_key="catalog_categories"`. Register navigation separately through `declare`; resource registration does not choose the project's menu composition.

## Lists and forms

- Default selection reads the model's default manager, then searches declared searchable columns in Python. This is not automatic database pagination or a scalable query planner.
- Supply `list_selector(request, resource)` for project data selection; a custom selector owns its filtering behavior. Return the supported row structures checked in `selectors.py`.
- Forms are built from declared model fields. Virtual fields become form values, but normal model saving does not persist them; give them an explicit project workflow.
- Readonly fields are disabled. `richtext`, `html`, `markdown`, and `json` widgets currently use textareas, not complete editor integrations.
- Current generic views bind POST without FILES. Do not promise working uploads by merely declaring a file field.

## Access boundaries

Generic views require login and model view/add/change permissions by default. Resource action permission overrides exist; an empty permission intentionally allows the action after login, so do not use it as a harmless default.

**A scoped list selector does not scope edit-object lookup.** Multi-tenant or owner-only projects must enforce object restrictions in their view/service integration. UI create/edit flags are not a substitute for endpoint checks. Check server validation directly when a project needs these restrictions.

There is no generic resource delete endpoint to wire by assumption. Reuse only routes actually present in `cabinet/urls.py`.

## Smart create

Implement `SmartCreateHandlerProtocol` in the project: create a preview job, obtain status by draft/user, and publish edited data. Use `SmartCreateJobRef`, `SmartCreateStatus`, and language states to match template polling/status expectations.

The project owns the AI provider, queue, draft storage/ownership, validation, and final persistence. The library supplies the contract and cabinet flow; registering `smart_handler` does not provision an AI worker.

Source: `cabinet/resources/{contracts,registry,forms,selectors}.py`, `cabinet/views/resources.py`, `cabinet/templates/cabinet/resources/`, `cabinet/urls.py`.
