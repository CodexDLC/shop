# Redis managers, cache and sessions

Use the library's Redis mechanisms for their specific purpose. A model settings cache, Django cache backend and session store are distinct contracts.

## Managers

`BaseDjangoRedisManager` provides project/prefix/key naming and synchronous/asynchronous Redis access. Reuse its lifecycle/context handling rather than leaving new clients open. Inspect each manager's use of `_is_disabled`: DEBUG with `CODEX_REDIS_ENABLED` false affects opt-in manager behavior; it is not a global Redis bypass.

## Django cache

`RedisCache` uses JSON serialization by default. It has no silent pickle fallback. `CacheCoder` defines conversions for supported values such as datetime, Decimal and UUID; use the installed contract for decoding/type hints. Do not pass arbitrary ORM objects and assume lossless round trips.

`clear()` operates within `KEY_PREFIX` and refuses an empty namespace. Redis failures propagate rather than silently converting the cache into memory storage. A custom `SERIALIZER` is an explicit project choice, not a compatibility repair to add automatically.

## Sessions

Set `SESSION_ENGINE = "codex_django.sessions.backends.redis"` only when the project intends Redis-backed sessions. Keys combine `PROJECT_NAME`, `CODEX_SESSION_KEY_PREFIX` (default `session`) and session key; expiry determines TTL.

The backend stores Django-encoded JSON session data. It does not provide a DB/memory fallback on Redis errors or transparent migration of older pickled sessions. Plan session compatibility separately when changing an existing deployment.

`CODEX_REDIS_ENABLED` does not disable all cache/session IO. Verify actual backend configuration and tests before attributing network access to that flag.

Source: `core/redis/managers/base.py`, `cache/backends/redis.py`, `cache/values.py`, `sessions/backends/redis.py`.
