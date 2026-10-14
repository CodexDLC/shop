# Core models, SEO and localization

Reuse existing abstract/mixin behavior for timestamps, active flags, ordering, UUIDs, slugs and SEO. Inspect `core/` exports and model mixins before combining bases: the project still owns concrete models and migrations.

`SoftDeleteMixin.soft_delete()` marks a flag and saves. It does not automatically change every manager's filtering or override every deletion path. Apply project query and deletion policy explicitly.

## Settings and static content context

Use the supplied `site_settings` and `static_content` context processors where needed. Site settings are exposed via `SettingsProxy`; static translations use `AbstractStaticTranslation` with `CODEX_STATIC_TRANSLATION_MODEL`. Do not create a parallel global content cache without first checking these mechanisms.

## SEO

`AbstractStaticPageSeo` is in the system layer. `core.seo.selectors.get_static_page_seo` reads it using `CODEX_STATIC_PAGE_SEO_MODEL`, key-field and cache-timeout settings. The SEO context processor maps the resolved URL name to SEO content. Align project route names and fixture keys; do not assume a page path is its lookup key.

`BaseSitemap` and `StaticPagesSitemap` support the canonical-domain/static-page conventions and language alternates. Check `CANONICAL_DOMAIN`, `SITEMAP_STATIC_PAGES`, `SITEMAP_LOOKUP_NAMESPACES`, and LANGUAGES. Their HTTPS canonical policy should agree with deployment.

## Translation

Reuse `discover_locale_paths`, the `codex_i18n` template library's `translate_url`, and `codex_makemessages` rather than hand-maintaining competing locale discovery. The management command requires the relevant app to be installed. Project URL configuration still controls translated routes.

Do not treat Django UI translation and messaging worker template rendering as one engine; see [messaging](messaging.md).

Source: `core/`, `core/seo/`, `core/templatetags/`, `core/management/`, `system/`.
