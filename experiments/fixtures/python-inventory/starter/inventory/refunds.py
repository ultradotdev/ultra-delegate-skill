from .errors import InvalidState, RefundError
from .money import to_money


class RefundService:
    def __init__(self, orders, reservations, stock, audit, requests):
        self.orders = orders
        self.reservations = reservations
        self.stock = stock
        self.audit = audit
        self.requests = requests

    def refund(self, request_id, order_id, line_no, qty):
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

        # Returned goods go back to the primary warehouse.
        warehouse = self.stock.warehouses()[0]
        self.stock.restock(line.sku, warehouse, qty)
        self.audit.record('restock', order=order_id, line=line_no, sku=line.sku,
                          warehouse=warehouse, qty=qty)

        line.refunded_qty += qty
        line.refunded_amount += amount
        self.audit.record('refund', order=order_id, line=line_no, qty=qty, amount=amount)
        return amount
