from codex_ecommerce.inventory import InventoryError


class ExpiryTransactionError(InventoryError):
    code = 'expiry_requires_autocommit'
    action = 'retry_outside_transaction'
