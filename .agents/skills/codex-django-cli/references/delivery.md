# Managed skill lifecycle

The source for this skill is packaged in `codex_django_cli.agent_skills.resources`. Install it into a consuming project with:

```bash
codex-django skills install --project /path/to/project
codex-django skills status --project /path/to/project
```

After upgrading the Python package, run `codex-django skills update` with the same `--project` argument. To remove only installer-owned content, run `codex-django skills delete`. `python -m codex_django_cli.agent_skills` is an equivalent entrypoint. The installer records the package version and SHA-256 hashes in `.agents/skills/codex-django-cli/.manifest.json` and adds a marked instruction to the project's `AGENTS.md`.

The installed skill and manifest are managed outputs. Put project-specific additions in a separate project skill. If a managed file was locally edited, update and delete refuse to overwrite it; save those changes elsewhere and restore the managed copy before retrying. Unrelated files in the skill directory and unrelated `AGENTS.md` text are left in place.
