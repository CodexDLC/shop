class InventoryError(ValueError):
    """Stable domain error code; transport adapters provide localized messages."""

    code = "inventory_error"
    action = "review_input"

    def __init__(self):
        super().__init__(self.code)
