from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExpirySummary:
    scanned: int
    expired: int
    skipped: int
    has_more: bool
