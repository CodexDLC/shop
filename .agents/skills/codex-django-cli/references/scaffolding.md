# Scaffolding workflows

`codex-django init myproject` creates a repository with a Django project under `src/myproject`. Use `codex-django init --help` for the current flag set. Useful options include `--code`, `--i18n --languages en,ru`, `--with-booking`, `--with-notifications`, `--with-messaging`, `--with-public-booking`, and `--with-sw`.

The selection is resolved by `codex_django_cli.commands.install.resolve_install_selection`. Booking adds its core and cabinet integration; public booking implies booking; booking and messaging imply cabinet. Conversations and Unfold admin are selected by default unless disabled. The generated repository's dependencies and migrations remain a separate setup step.

For an existing project, run `codex-django menu` from its repository root and select **Extend existing Django project**. The menu detects modules by generated file markers and offers a compare copy under `_scaffold_compare` for inspecting changes. Do not treat marker detection as a complete health check. Compare the resulting files and run the generated project's tests and Django checks.

`codex-django deploy` generates deployment files. The menu also offers repository config and pre-commit generation. These operations write project files; review targets and preserve local modifications before using overwrite options.
