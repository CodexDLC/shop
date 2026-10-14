---
name: codex-platform
description: Use for consumer code using codex-platform Redis, Streams, ARQ workers, or messaging APIs.
---

# codex-platform consumer guide

Check the installed `codex-platform` version and the relevant public module before changing an integration. This skill is shipped with the library; its installed copy and `.manifest.json` are managed by `python -m codex_platform.agent_skills`. Keep application-specific keys, handlers, business rules, and adapters in project-owned code or skills.

For the current environment, `python -c "from importlib.metadata import version; import codex_platform; print(version('codex-platform'), codex_platform.__file__)"` identifies the installed version and source location. Check that source when signatures matter.

Read only the reference for the task:

- Redis operations and key definitions: [references/redis.md](references/redis.md)
- Redis Streams handlers and runtime: [references/streams.md](references/streams.md)
- ARQ workers and tasks: [references/arq.md](references/arq.md)
- Notification delivery and threading: [references/messaging.md](references/messaging.md)

The four components have separate optional dependencies. Install the relevant extra before using one: `[redis]`, `[streams]`, `[arq]`, or `[notifications]`. `codex_platform.notifications` remains a deprecated compatibility surface; use `codex_platform.messaging` for new work.
