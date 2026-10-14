# Components and interaction contracts

Import generic DTOs from `codex_django.cabinet`. Inspect `cabinet/types/components.py` and the corresponding template together before constructing context.

| Need | Reuse |
| --- | --- |
| Responsive list/table | `DataTableData`, `TableColumn`, `TableAction`, `TableFilter`; `cabinet/components/data_table.html` |
| Calendar layout | `CalendarGridData`, `CalendarSlot` |
| Card collection | `CardGridData`, `CardItem` |
| Compact list | `ListViewData`, `ListRow` |
| Two-panel screen | `SplitPanelData` |
| Modal sections | `ModalContentData`, section DTOs, `ModalPresenter` / `present_modal_state` |

For example, a project selector supplies already-authorized rows; a view places this DTO under `table`:

```python
from codex_django.cabinet import DataTableData, TableColumn

table = DataTableData(
    columns=[TableColumn(key="name", label="Name", bold=True)],
    rows=[{"name": "Example"}],
)
```

```django
{% include "cabinet/components/data_table.html" with table=table %}
```

## Behavior that needs project wiring

- Table rows are mappings. The current table renders desktop rows and mobile cards; search is a normal GET request with configurable action/parameter. Actions are regular links. Do not assume row actions automatically open a modal.
- `sortable` metadata does not implement sorting or pagination, and the current template does not render sort controls or pagination links. An ORM ordering/pagination implementation still needs corresponding project controls or a reusable template extension. Filter metadata currently renders disabled filter placeholders; do not disguise them as working controls.
- Calendar rows/columns and slot positions are computed server-side; indices are zero-based. Supply action URLs and valid positions, rather than implementing a competing booking engine in JavaScript.
- Modal form DTOs render fields; they are not Django `ModelForm` validation or persistence. Validate posted data in the project workflow/view.
- `cabinet/includes/_modal_base.html` listens for `open-modal` with `detail.url` and optional size, loads into `#modal-body`, and supports `close-modal`. Staff shell includes it; client integration must supply required markup/assets explicitly.
- Booking-specific UI states and presentation belong to the booking contracts; do not create a duplicate generic DTO family for the same feature.

## Extending the UI

Use existing templates and tokens first. Decide whether a change is a reusable component capability or project composition. Library CSS should use semantic `--cab-*` tokens; project static/template overrides hold brand decisions. Avoid copying the entire base shell for one visual change.

For a changed interaction verify the normal page and HTMX path, mobile layout, empty/error/loading states that actually apply, and keyboard/focus behavior. The presence of Bootstrap or a modal template is not evidence that every accessibility state is complete.

Source: `cabinet/types/`, `cabinet/presenters/`, `cabinet/templates/cabinet/components/`, `cabinet/templates/cabinet/includes/_modal_base.html`, `cabinet/static/cabinet/js/app/`, `cabinet/static/cabinet/css/cab_tokens.css`.
