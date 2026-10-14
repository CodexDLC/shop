# Settings, models, fixtures and action tokens

## Compose concrete project models

Use `AbstractSiteSettings` and the relevant contact/geo/social/marketing/technical mixins; add `SiteEmailIdentityMixin` when the project needs sender identity. Set `CODEX_SITE_SETTINGS_MODEL` to the concrete model label. Keep project migrations and admin registration in the project.

`AbstractUserProfile` supplies user-profile primitives; project subclasses own extra fields and integration with the selected user model. Credential mixins provide fields for provider configuration. A Stripe/Google/Twilio-related mixin is not a complete provider client or payment flow.

Inspect settings serialization before exposing it. The model's `to_dict()` serializes concrete fields broadly; neither `SettingsProxy` nor a context processor is a secret-redaction policy. Keep sensitive provider data out of public template context.

Settings lifecycle synchronization uses Redis and can be skipped in DEBUG unless `CODEX_REDIS_ENABLED` enables it. Check the concrete sync mixin rather than assuming every save persists every cache.

For the cabinet's settings service and access boundary read [cabinet-shell](cabinet-shell.md). The project service owns editable sections, permissions and save behavior.

## Content fixtures

Reuse the existing command bases in `system/management/base_commands.py`: `BaseUpdateAllContentCommand`, `BaseHashProtectedCommand`, `JsonFixtureUpsertCommand`, and `SingletonFixtureUpdateCommand`. Configure the model, lookup and fixture contract rather than adding another importer with divergent hash logic.

Hash protection skips unchanged fixture content; it is not validation of arbitrary fixtures or permission to overwrite production data. Verify the command's update and deletion semantics for the intended project use.

## Action tokens

`JsonActionTokenRedisManager` creates random URL-safe tokens and stores JSON data with TTL; sync/async create/get/delete are separate operations. Override payload validation for the concrete action. A get followed by delete is **not atomic single-use consumption**. For sensitive single-use actions provide an atomic operation at the appropriate storage boundary.

In disabled DEBUG mode a token can be generated without persistence, so a later lookup returns no stored payload. Test the configured environment, not just the returned token string.

Source: `system/mixins/`, `system/management/base_commands.py`, `system/redis/managers/tokens.py`.
