# Redis Streams

`StreamRuntime` wires a producer, consumer, dispatcher, and processor for one stream. Define handlers with `StreamRouter.on()` and include the router before starting the runtime.

This integration fragment runs inside an async application lifecycle; `redis_client` is an app-owned `redis.asyncio.Redis` instance:

```python
from codex_platform.streams import StreamRouter, StreamRuntime, StreamRuntimeConfig

router = StreamRouter()

@router.on("order.paid", group="orders")
async def handle_paid(payload: dict) -> None:
    print(payload["order_id"])

runtime = StreamRuntime(redis_client, StreamRuntimeConfig("events:orders", "workers", "worker-1"))
runtime.include_router(router)
await runtime.start()
# On application shutdown: await runtime.stop()
```

`enabled_groups` filters logical handler groups; `consumer_group` controls Redis delivery. A partial runtime must use an explicit consumer group other than the default `monolith`. Use distinct consumer names per worker. `StreamProducer` provides publish and request/reply methods; inspect its installed signatures and timeout behavior before coupling two services.
