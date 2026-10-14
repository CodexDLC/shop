---
name: codex-django
description: "Use codex-django in a consuming Django project: integrate or extend its cabinet, resources, booking, messaging, settings, Redis, and tracking mechanisms. Consult this skill when working with codex_django APIs or deciding whether an existing library mechanism fits a project task."
---

# Use codex-django

Find the existing library mechanism before implementing a parallel one. This skill describes the installed library; the consuming project's instructions supply its business rules, access policy, branding, and deployment choices.

## Route the task

Read only the relevant references, then inspect the named API where the task needs exact fields or behavior:

| Task | Reference |
| --- | --- |
| Add the library, locate installed sources, choose app configuration | [integration](references/integration.md) |
| Cabinet shell, spaces, navigation, access, page templates | [cabinet shell](references/cabinet-shell.md) |
| Tables, cards, calendars, forms, modals, theme extension | [cabinet components](references/cabinet-components.md) |
| Model-backed resource lists/forms or smart-create workflow | [cabinet resources](references/cabinet-resources.md) |
| Dashboard providers, charts, report pages | [dashboard and reports](references/dashboard-reports.md) |
| Site settings, abstract models, credentials, fixture import, action tokens | [system](references/system.md) |
| Model mixins, SEO, translation, sitemap | [core and localization](references/core-seo-i18n.md) |
| Redis managers, cache serialization, sessions | [Redis](references/redis.md) |
| Availability, booking persistence, booking cabinet integration | [booking](references/booking.md) |
| Email dispatch, campaign/mailbox cabinet, worker integration | [messaging](references/messaging.md) |
| Page-view analytics or runnable UI examples | [tracking and showcase](references/tracking-showcase.md) |

Paths in references are relative to the installed `codex_django` package unless explicitly described as project files. They are source locators, not additional files that must all be read. Do not assume the source checkout, test suite, or full documentation is installed alongside the wheel.

## Ownership and extension

- The library owns reusable contracts, templates, components, adapters, and workflow primitives. The project owns concrete models/migrations, URL wiring, permissions and tenant boundaries, data selection, external workers, and brand assets.
- Preserve Django Templates, HTMX, Alpine, and the existing CSS system. An email worker's Jinja2 renderer does not change the UI template stack. Do not introduce React/Vue or a separate dashboard framework to use this library.
- Prefer public exports and supplied bridges/providers over copying internals. Implement a project adapter when the seam exists. If the library genuinely lacks a reusable capability, identify that gap explicitly before extending the library.
- A hidden menu item, `staff` space, or disabled button is not endpoint authorization. Verify server-side access and data scoping for each project integration.
- Keep this installed skill library-managed. Put project-specific additions in a separate project skill; update the canonical skill in the library when its API changes. Do not embed a customer's rules or branding here.

## Work from the installed contract

1. Locate the project's current integration and installed library version. Read the one or two references that match the task.
2. Check the relevant exported signature and template context before using it; do not infer implemented behavior from a DTO field name or a mock page.
3. Connect the project's models, selectors, services and views through the documented seam. Reuse component DTOs and templates where they fit.
4. Verify the changed behavior at its boundary: access/data scoping and mutation validation for server work; full-page and HTMX responses plus visible states for UI work. Use project tests and browser tooling already available.

If source and these instructions disagree, treat installed code as evidence, state the mismatch, and avoid inventing a compatibility shim. Updating the Python package and refreshing the project skill are separate operations.
