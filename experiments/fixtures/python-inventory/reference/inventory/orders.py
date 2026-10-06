from dataclasses import dataclass, field
from decimal import Decimal

from . import allocation
from .errors import InvalidState
from .money import ZERO, to_money
from .requests import MISSING


@dataclass
class Line:
    line_no: int
    sku: str
    qty: int
    unit_price: Decimal
    subtotal: Decimal
    tax: Decimal
    total: Decimal
    refunded_qty: int = 0
    refunded_amount: Decimal = ZERO


@dataclass
class Order:
    order_id: str
    lines: list = field(default_factory=list)
    total: Decimal = ZERO
    status: str = 'reserved'

    @property
    def refunded_total(self):
        return sum((line.refunded_amount for line in self.lines), ZERO)

    def line(self, line_no):
        for line in self.lines:
            if line.line_no == line_no:
                return line
        return None


def _check_qty(qty):
    if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
        raise ValueError(f'quantity must be a positive int, got {qty!r}')


class OrderService:
    def __init__(self, catalog, stock, reservations, audit, requests):
        self.catalog = catalog
        self.stock = stock
        self.reservations = reservations
        self.audit = audit
        self.requests = requests
        self._orders = {}

    def get(self, order_id):
        try:
            return self._orders[order_id]
        except KeyError:
            raise InvalidState(f'unknown order {order_id!r}') from None

    def place_order(self, request_id, order_id, lines):
        args = (order_id, tuple((sku, qty) for sku, qty in lines))
        previous = self.requests.replay(request_id, 'place_order', args)
        if previous is not MISSING:
            return previous
        if order_id in self._orders:
            raise InvalidState(f'order {order_id!r} already exists')
        if not lines:
            raise ValueError('an order needs at least one line')

        priced = [self._price(line_no, sku, qty) for line_no, (sku, qty) in enumerate(lines, start=1)]
        # Plan every line before touching stock so a failure leaves nothing behind.
        # Each plan sees the units already planned for earlier lines of this order.
        planned, plans = {}, []
        for line in priced:
            plan = allocation.plan(self.stock, line.sku, line.qty, planned)
            for warehouse, qty in plan:
                planned[line.sku, warehouse] = planned.get((line.sku, warehouse), 0) + qty
            plans.append(plan)
        for line, plan in zip(priced, plans):
            self.reservations.reserve(order_id, line.line_no, line.sku, plan)

        order = Order(order_id, priced, sum((line.total for line in priced), ZERO))
        self._orders[order_id] = order
        self.audit.record('order_placed', order=order_id, total=order.total)
        self.requests.remember(request_id, 'place_order', args, order)
        return order

    def _price(self, line_no, sku, qty):
        _check_qty(qty)
        product = self.catalog.get(sku)
        subtotal = to_money(product.unit_price * qty)
        tax = to_money(subtotal * product.tax_rate)
        return Line(line_no, sku, qty, product.unit_price, subtotal, tax, subtotal + tax)

    def ship_order(self, request_id, order_id):
        args = (order_id,)
        previous = self.requests.replay(request_id, 'ship_order', args)
        if previous is not MISSING:
            return previous
        order = self.get(order_id)
        if order.status != 'reserved':
            raise InvalidState(f'order {order_id!r} is {order.status}')
        self.reservations.ship(order_id)
        order.status = 'shipped'
        self.audit.record('order_shipped', order=order_id)
        self.requests.remember(request_id, 'ship_order', args, order)
        return order

    def cancel_order(self, request_id, order_id):
        args = (order_id,)
        previous = self.requests.replay(request_id, 'cancel_order', args)
        if previous is not MISSING:
            return previous
        order = self.get(order_id)
        if order.status != 'reserved':
            raise InvalidState(f'order {order_id!r} is {order.status}')
        self.reservations.release(order_id)
        order.status = 'cancelled'
        self.audit.record('order_cancelled', order=order_id)
        self.requests.remember(request_id, 'cancel_order', args, order)
        return order
