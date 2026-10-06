from .errors import InvalidState, RefundError
from .money import to_money
from .requests import MISSING


class RefundService:
    def __init__(self, orders, reservations, stock, audit, requests):
        self.orders = orders
        self.reservations = reservations
        self.stock = stock
        self.audit = audit
        self.requests = requests
        self._returned = {}  # (order_id, line_no, warehouse) -> units put back so far

    def refund(self, request_id, order_id, line_no, qty):
        args = (order_id, line_no, qty)
        previous = self.requests.replay(request_id, 'refund', args)
        if previous is not MISSING:
            return previous
        order = self.orders.get(order_id)
        if order.status != 'shipped':
            raise InvalidState(f'order {order_id!r} is {order.status}, not shipped')
        line = order.line(line_no)
        if line is None:
            raise RefundError(f'order {order_id!r} has no line {line_no!r}')
        if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
            raise RefundError(f'refund quantity must be a positive int, got {qty!r}')
        if line.refunded_qty + qty > line.qty:
            raise RefundError(f'line {line_no} has only {line.qty - line.refunded_qty} refundable units')

        if line.refunded_qty + qty == line.qty:
            amount = line.total - line.refunded_amount
        else:
            amount = to_money(line.total * qty / line.qty)

        # Returned goods go back where they shipped from, last allocation first.
        shipped = [a for a in self.reservations.allocations(order_id) if a.line_no == line_no]
        remaining = qty
        for allocation in reversed(shipped):
            key = (order_id, line_no, allocation.warehouse)
            take = min(allocation.qty - self._returned.get(key, 0), remaining)
            if take <= 0:
                continue
            self.stock.restock(line.sku, allocation.warehouse, take)
            self._returned[key] = self._returned.get(key, 0) + take
            self.audit.record('restock', order=order_id, line=line_no, sku=line.sku,
                              warehouse=allocation.warehouse, qty=take)
            remaining -= take
            if remaining == 0:
                break

        line.refunded_qty += qty
        line.refunded_amount += amount
        self.audit.record('refund', order=order_id, line=line_no, qty=qty, amount=amount)
        self.requests.remember(request_id, 'refund', args, amount)
        return amount
