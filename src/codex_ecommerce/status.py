"""Immutable, transport-safe engine diagnostic result."""

from typing import Literal

from codex_core.core import BaseDTO


class EngineStatus(BaseDTO):
    phase: Literal["foundation"] = "foundation"
    payments_enabled: Literal[False] = False
    ebay_write_enabled: Literal[False] = False
