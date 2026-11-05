from .inventory_error import InventoryError


class ReservationExpiredError(InventoryError):
    code = "reservation_expired"
    action = "review_reservation"
