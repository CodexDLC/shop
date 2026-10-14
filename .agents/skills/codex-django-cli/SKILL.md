---
name: codex-django-cli
description: Use the installed codex-django-cli to initialize or extend a Django project, generate repository or deployment files, or inspect its blueprints. Activate for CLI scaffolding work; use the separate codex-django skill for runtime library APIs.
---

# Use codex-django-cli

This skill describes the installed `codex-django-cli` package. Check its version with `python -m pip show codex-django-cli`, and use `python -c "import codex_django_cli; print(codex_django_cli.__file__)"` to locate the installed sources. A source checkout, tests, and full documentation may be absent from a wheel.

Read [scaffolding](references/scaffolding.md) for project creation, module dependencies, and extension. Read [blueprints](references/blueprints.md) when changing generated output or integrating a generated project. Read [delivery](references/delivery.md) when updating this managed skill.

The CLI generates project files. The separate `codex-django` package supplies runtime APIs. Generated code must be checked against the installed runtime version; a blueprint filename or optional flag does not prove the runtime dependency is installed. Keep project-specific permissions, models, deployment choices, and business rules in project-owned guidance.

For a new project, run `codex-django init <name>` or `codex-django menu`. Inspect generated files before applying local edits. For an existing project, use the menu's extension and compare-copy flows. A normal scaffold skips existing files; overwrite mode replaces them, so preserve edits first.
