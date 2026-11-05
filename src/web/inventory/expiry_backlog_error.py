from codex_ecommerce.inventory import InventoryError


class ExpiryBacklogError(InventoryError):
    code = 'expiry_backlog'
    action = 'retry_cleanup'
