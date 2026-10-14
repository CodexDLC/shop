# Tracking and runnable examples

## Tracking

The tracking app registers cabinet navigation and a dashboard provider. It also has concrete page-view models and migrations; plan its installation accordingly.

`CODEX_TRACKING` is the current configuration, with legacy `CABINET_TRACKING` inputs still normalized. Check `tracking/settings.py` for exact options before overriding. Redis tracking, anonymous tracking, redirects and skipped prefixes have distinct controls.

Middleware records eligible GET responses after the view (successful/redirect statuses according to configuration), catches tracking errors and returns the response. This does not prove zero latency: the tracking operations are still synchronous on that path.

Redis accumulates counters/unique sets; `flush_page_views` writes snapshots for longer-term queries. The management command does not schedule itself. Configure project scheduling and Redis/DB availability. `TrackingSelector` combines stored snapshots and current counters; avoid counting both independently in a parallel reporting implementation.

The tracking cabinet view enforces staff access. Do not generalize that protection to all other cabinet views.

## Showcase

Use `showcase` templates and mock DTOs to learn component composition and generate local examples. Views guarded by `debug_only` return forbidden outside DEBUG. Do not remove the guard to deploy mock operational screens.

Showcase demonstrates UI contracts, not production repositories, worker connections, permissions or real customer data. For a real feature, replace the mock data boundary through project selectors/bridges and retain reusable library templates where appropriate.

Source: `tracking/apps.py`, `tracking/middleware.py`, `tracking/management/commands/flush_page_views.py`, `tracking/selector.py`, `tracking/views.py`, `showcase/mock.py`, `showcase/views.py`, `showcase/templates/`.
