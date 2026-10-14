# Redis service

`codex_platform.redis_service.RedisService` accepts an existing `redis.asyncio.Redis` client. Its `.hash`, `.string`, `.list`, `.set`, `.zset`, `.json`, `.json_module`, and `.pipeline` attributes are separate operation objects. `.json` stores JSON as a plain Redis string; `.json_module` requires the server-side RedisJSON module.

The fragment below runs inside an async function and assumes a reachable Redis server:

```python
from redis.asyncio import Redis
from codex_platform.redis_service import RedisService

client = Redis(host="localhost", port=6379)
service = RedisService(client)
await service.hash.set_json("u:42", "profile", {"name": "Ada"})
profile = await service.hash.get_json("u:42", "profile")
await client.aclose()
```

For a smaller composition, instantiate operations from `codex_platform.redis_service.operations` directly. `BaseRedisKey` and `resolve_key` live in `codex_platform.redis_service.keys`; define application-specific key templates in the consumer. Inspect method signatures in the installed package before changing data formats or TTL behavior.
