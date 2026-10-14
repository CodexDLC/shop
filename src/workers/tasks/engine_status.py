"""Diagnostic task with no external side effects."""

from typing import Any


async def engine_status(ctx: dict[str, Any]) -> dict[str, Any]:
    return ctx["engine"].status().model_dump(mode="json")
