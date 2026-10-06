"""Per-warehouse stock levels.

`hold`, `release`, `ship` and `restock` are the low-level movements used by the
reservation and refund services. They trust their callers: the allocation
planner is responsible for never holding more than is available.
"""
from .errors import UnknownWarehouse


def _check_qty(qty):
    if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
        raise ValueError(f'quantity must be a positive int, got {qty!r}')


class Stock:
    def __init__(self):
        self._warehouses = []
        self._on_hand = {}
        self._reserved = {}

    def add_warehouse(self, code):
        if code in self._warehouses:
            raise ValueError(f'duplicate warehouse {code!r}')
        self._warehouses.append(code)

    def warehouses(self):
        """Warehouse codes in priority order."""
        return list(self._warehouses)

    def _check(self, warehouse):
        if warehouse not in self._warehouses:
            raise UnknownWarehouse(warehouse)

    def receive(self, sku, warehouse, qty):
        self._check(warehouse)
        _check_qty(qty)
        self._on_hand[sku, warehouse] = self._on_hand.get((sku, warehouse), 0) + qty

    def on_hand(self, sku, warehouse):
        self._check(warehouse)
        return self._on_hand.get((sku, warehouse), 0)

    def reserved(self, sku, warehouse):
        self._check(warehouse)
        return self._reserved.get((sku, warehouse), 0)

    def available(self, sku, warehouse):
        return self.on_hand(sku, warehouse) - self.reserved(sku, warehouse)

    def total_available(self, sku):
        return sum(self.available(sku, wh) for wh in self._warehouses)

    # Movements -----------------------------------------------------------

    def hold(self, sku, warehouse, qty):
        self._check(warehouse)
        self._reserved[sku, warehouse] = self._reserved.get((sku, warehouse), 0) + qty

    def release(self, sku, warehouse, qty):
        self._check(warehouse)
        self._reserved[sku, warehouse] = self._reserved.get((sku, warehouse), 0) - qty

    def ship(self, sku, warehouse, qty):
        self._check(warehouse)
        self._on_hand[sku, warehouse] = self._on_hand.get((sku, warehouse), 0) - qty
        self._reserved[sku, warehouse] = self._reserved.get((sku, warehouse), 0) - qty

    def restock(self, sku, warehouse, qty):
        self._check(warehouse)
        self._on_hand[sku, warehouse] = self._on_hand.get((sku, warehouse), 0) + qty
