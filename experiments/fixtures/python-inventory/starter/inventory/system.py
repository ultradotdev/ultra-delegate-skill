from .audit import AuditLog
from .catalog import Catalog
from .orders import OrderService
from .refunds import RefundService
from .requests import RequestLog
from .reservations import Reservations
from .stock import Stock


class Inventory:
    """Wires the services together; they share one stock, audit log and request log."""

    def __init__(self):
        self.catalog = Catalog()
        self.stock = Stock()
        self.audit = AuditLog()
        self.requests = RequestLog()
        self.reservations = Reservations(self.stock, self.audit)
        self.orders = OrderService(self.catalog, self.stock, self.reservations, self.audit, self.requests)
        self.refunds = RefundService(self.orders, self.reservations, self.stock, self.audit, self.requests)
