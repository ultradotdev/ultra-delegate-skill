class InventoryError(Exception):
    """Base class for every error raised by the inventory package."""


class UnknownSku(InventoryError):
    pass


class UnknownWarehouse(InventoryError):
    pass


class InsufficientStock(InventoryError):
    pass


class InvalidState(InventoryError):
    pass


class IdempotencyConflict(InventoryError):
    pass


class RefundError(InventoryError):
    pass
