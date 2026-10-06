"""Reservations: which warehouse holds which units for which order line."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Allocation:
    line_no: int
    sku: str
    warehouse: str
    qty: int


class Reservations:
    def __init__(self, stock, audit):
        self.stock = stock
        self.audit = audit
        self._by_order = {}

    def reserve(self, order_id, line_no, sku, plan):
        """Hold the units of one planned line and remember the allocations."""
        allocations = self._by_order.setdefault(order_id, [])
        for warehouse, qty in plan:
            self.stock.hold(sku, warehouse, qty)
            allocations.append(Allocation(line_no, sku, warehouse, qty))
            self._record('reserve', order_id, allocations[-1])

    def allocations(self, order_id):
        return list(self._by_order.get(order_id, []))

    def release(self, order_id):
        for allocation in self._by_order.get(order_id, []):
            self.stock.release(allocation.sku, allocation.warehouse, allocation.qty)
            self._record('release', order_id, allocation)

    def ship(self, order_id):
        for allocation in self._by_order.get(order_id, []):
            self.stock.ship(allocation.sku, allocation.warehouse, allocation.qty)
            self._record('ship', order_id, allocation)

    def _record(self, event, order_id, allocation):
        self.audit.record(event, order=order_id, line=allocation.line_no, sku=allocation.sku,
                          warehouse=allocation.warehouse, qty=allocation.qty)
