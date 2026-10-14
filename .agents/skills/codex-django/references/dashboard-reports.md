# Dashboard providers and reports

## Dashboard

Use `DashboardSelector` and the existing dashboard adapters/providers rather than building a second widget registry. Providers receive a request and return context; adapters structure metric/table/list widget data. Read the installed selector's merge behavior when multiple providers contribute the same key: later context can overwrite earlier values.

`DashboardSelector.extend(cache_key=..., cache_ttl=...)` can cache provider results. **The cache key is provider-wide, not automatically scoped to the user or tenant.** For request-specific data use `cache_ttl=0` or implement correctly scoped caching in the provider. Never put private request-dependent output under one shared key. Use the selector's invalidation methods when the cached data changes.

The project owns aggregation, queryset scoping, permissions, and concrete widget URLs. A provider returning zero or an empty list should remain renderable.

Example registration in the project's discovered `cabinet.py` (the project implements `orders_summary_for` and consumes `orders_summary` in its dashboard widget template):

```python
from codex_django.cabinet.selector.dashboard import DashboardSelector
from .selectors import orders_summary_for


@DashboardSelector.extend(cache_key="orders_summary", cache_ttl=0)
def orders_summary(request):
    return {"orders_summary": orders_summary_for(request.user)}
```

## Report pages

Public cabinet exports include `ReportPageData`, `ReportChartData`, `ChartDatasetData`, `ChartAxisData`, `ReportTableData`, summary cards/tabs, and `resolve_report_period`. Supply these DTOs to the report templates rather than assembling a second chart serialization format.

The library renders Chart.js-oriented data. It does not infer the correct business aggregation, implement an export handler just because an export URL exists, or enforce project data access. Verify date/time boundaries and access in the project selector/view.

Source: `cabinet/selector/dashboard.py` (selector and adapters), `cabinet/reports/`, `cabinet/templates/cabinet/`.
