"""Application entry point shared by web and background adapters."""

from .status import EngineStatus


class Engine:
    """Foundation API; external writes are not implemented or enabled."""

    def status(self) -> EngineStatus:
        return EngineStatus()
