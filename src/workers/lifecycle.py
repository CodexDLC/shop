"""Initialize independent services without filesystem or network side effects."""

from typing import Any

from codex_ecommerce import Engine


async def worker_startup(ctx: dict[str, Any]) -> None:
    ctx["engine"] = Engine()


async def worker_shutdown(ctx: dict[str, Any]) -> None:
    ctx.pop("engine", None)
