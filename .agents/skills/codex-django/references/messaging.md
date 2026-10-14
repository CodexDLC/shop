# Messaging, campaigns and mailbox UI

Use the canonical `codex_django.messaging` API. `codex_django.notifications` is a deprecated compatibility forwarding layer; preserve existing consumers when outside the requested change, and use messaging for new integration.

## Dispatch and workers

`BaseMessagingEngine` coordinates injected queue/cache/i18n/content-selector adapters. Register events using `email_template` or `email_rendered` and the messaging event registry. The project must import/register its handlers; installing the app is not handler discovery.

- Template mode sends a template/context contract to a renderer. A worker may use `codex_platform` Jinja2; inspect that worker before writing template syntax.
- Rendered mode carries already-rendered bodies. Do not send Django template source as if it were rendered HTML.
- `DjangoQueueAdapter` synchronous dispatch normally enqueues after transaction commit and returns no immediate job object; asynchronous enqueue is immediate, without that same on-commit behavior.
- `DjangoDirectAdapter` is an email adapter using Django mail, not a universal sender for every channel. Template mode needs an appropriate renderer.
- Default task/language settings are library defaults, not proof of the project's worker configuration or desired language. Confirm injected adapters and event spec.

`AbstractEmailSettings` with `EmailSettingsSyncMixin` provides the worker settings synchronization contract (`PROJECT_NAME:email_settings`). Sender/site identity and transport credentials have different purposes; use the relevant mixins instead of exposing all credentials in site settings context.

## Data, audience and campaigns

Abstract thread/message/reply/campaign/recipient/log models need project concrete models and relationships. Placeholder abstract relationships are not a finished project schema.

`BaseAudienceBuilder` starts from the configured recipient model. Its base `apply_filters` leaves the queryset unchanged: the project must implement consent, eligibility and tenant selection. Iteration can be chunked, but `CampaignService.build_batches` materializes its batch list. Do not describe it as an automatically streaming, scheduled or deduplicated campaign engine.

Implement the campaign dispatcher/worker integration and delivery callbacks in the project. A campaign DTO does not send mail by itself.

## Cabinet

Use `MessagingBridge`, `MessagingCabinetWorkflowService`, state DTOs and `MessagingCabinetPresenter` for mailbox, detail/reply, campaigns/composer, recipients, delivery log and settings screens. Workflow validation delegates persistence to the bridge; the project owns URL/view wiring, ORM queries, permissions and background processing.

The `conversations` helpers expose inbox-notification presentation, not a complete chat backend. The cabinet `notification_registry` supplies notification items/counts/links; it is separate from message delivery.

Source: `messaging/__init__.py`, `registry.py`, `service.py`, `adapters/`, `audience.py`, `campaigns.py`, `workers_contract.py`, `cabinet/`, `mixins/models.py`.
