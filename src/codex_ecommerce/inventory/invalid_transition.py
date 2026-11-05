from .inventory_error import InventoryError


class InvalidTransitionError(InventoryError):
    code = "invalid_transition"
    action = "review_reservation"
