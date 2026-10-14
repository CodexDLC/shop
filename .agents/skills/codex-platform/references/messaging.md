# Messaging

For new integrations, import from `codex_platform.messaging`. The older `codex_platform.notifications` path is a deprecated compatibility surface. Messaging owns framework-independent DTOs, channel contracts, delivery adapters, templates, threading helpers, and worker task-name constants. The host application owns persistence, recipient selection, and channel configuration.

This example exercises the fallback chain in memory without sending a real message:

```python
import asyncio
from codex_platform.messaging import (
    BaseDeliveryOrchestrator,
    NotificationRecipient,
    RenderedNotificationDTO,
)

class MemoryChannel:
    def is_available(self) -> bool:
        return True

    async def send(self, to, subject, html_content, text_content, headers=None) -> bool:
        return to == "customer@example.test" and subject == "Order received"

async def main() -> None:
    payload = RenderedNotificationDTO(
        notification_id="order-42",
        recipient=NotificationRecipient(email="customer@example.test"),
        subject="Order received",
        html_content="<p>Thank you</p>",
    )
    delivered = await BaseDeliveryOrchestrator([MemoryChannel()]).deliver(payload)
    assert delivered

asyncio.run(main())
```

Each channel implements `is_available()` and async `send(...) -> bool`. The orchestrator tries available channels in order and stops on the first success. For queue delivery, inspect `ArqNotificationAdapter` and the matching `workers_contract` task constants in the installed version; producer and worker must agree on payload schema. For email threading, use `ThreadHeadersDTO` and helpers in `codex_platform.messaging.threading`.
