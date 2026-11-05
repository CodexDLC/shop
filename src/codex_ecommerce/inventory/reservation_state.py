from enum import StrEnum


class ReservationState(StrEnum):
    HELD = "held"
    COMMITTED = "committed"
    CLOSED = "closed"
