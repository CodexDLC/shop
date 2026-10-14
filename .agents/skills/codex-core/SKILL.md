---
name: codex-core
description: Use when integrating codex-core DTOs, PII masking, settings, common helpers, logging, or developer tools in a Python consumer project.
---

# codex-core consumer guide

This skill is distributed by the installed `codex-core` package. Check the installed package version and source/docstrings for version-specific behavior before changing a consumer. Keep application rules in the consuming project's own guidance; this directory and its manifest are installer-managed.

Read only the reference for the task:

- [Integration and version discovery](references/integration.md) when locating installed source or refreshing this skill.
- [DTOs and PII](references/dto-pii.md) for immutable transfer objects and log representation.
- [Settings](references/settings.md) for environment-backed settings and Redis URLs.
- [Common and logging](references/common-logging.md) for normalization, context, and optional Loguru setup.
- [Developer tools](references/developer-tools.md) for quality gates, static compilation, and project trees.

Public modules live under `codex_core.core`, `codex_core.settings`, `codex_core.common`, and `codex_core.dev`. The package requires Python 3.12 or newer. Do not treat DTO masking as a general serialization or secret-storage boundary: it applies to the DTO string representation.
