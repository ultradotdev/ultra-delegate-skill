import unittest
from decimal import Decimal

from inventory import Inventory
from inventory.errors import (IdempotencyConflict, InsufficientStock, InvalidState, RefundError,
                              UnknownSku, UnknownWarehouse)


def make(warehouses=('A', 'B', 'C'), stock=(), products=(('W', '10.00', '0'),)):
    inv = Inventory()
    for sku, price, rate in products:
        inv.catalog.add(sku, sku.lower(), price, rate)
    for code in warehouses:
        inv.stock.add_warehouse(code)
    for sku, wh, qty in stock:
        inv.stock.receive(sku, wh, qty)
    return inv


def allocs(inv, order_id):
    return [(a.line_no, a.warehouse, a.qty) for a in inv.reservations.allocations(order_id)]


def levels(inv, sku):
    return {wh: (inv.stock.on_hand(sku, wh), inv.stock.reserved(sku, wh)) for wh in inv.stock.warehouses()}


class Stock(unittest.TestCase):
    def test_R1_priority_and_unknown_warehouse(self):
        inv = make(warehouses=('Z', 'A', 'M'))
        self.assertEqual(inv.stock.warehouses(), ['Z', 'A', 'M'])
        with self.assertRaises(ValueError):
            inv.stock.add_warehouse('A')
        for call in (lambda: inv.stock.receive('W', 'Q', 1), lambda: inv.stock.on_hand('W', 'Q'),
                     lambda: inv.stock.reserved('W', 'Q'), lambda: inv.stock.available('W', 'Q')):
            with self.assertRaises(UnknownWarehouse):
                call()
        # Priority follows insertion, not name: Z is first.
        inv.stock.receive('W', 'M', 5)
        inv.stock.receive('W', 'Z', 5)
        inv.orders.place_order('r1', 'o1', [('W', 2)])
        self.assertEqual(allocs(inv, 'o1'), [(1, 'Z', 2)])

    def test_R2_available(self):
        inv = make(stock=[('W', 'A', 4), ('W', 'B', 6)])
        inv.orders.place_order('r1', 'o1', [('W', 5)])
        self.assertEqual(inv.stock.available('W', 'B'), 1)
        self.assertEqual(inv.stock.available('W', 'A'), 4)
        self.assertEqual(inv.stock.total_available('W'), 5)

    def test_R3_reserved_never_exceeds_on_hand(self):
        inv = make(stock=[('W', 'A', 5)])
        with self.assertRaises(InsufficientStock):
            inv.orders.place_order('r1', 'o1', [('W', 4), ('W', 3)])
        self.assertEqual(levels(inv, 'W')['A'], (5, 0))
        inv.orders.place_order('r2', 'o2', [('W', 3), ('W', 2)])
        inv.orders.cancel_order('r3', 'o2')
        with self.assertRaises(InvalidState):
            inv.orders.cancel_order('r4', 'o2')
        for wh, (on_hand, reserved) in levels(inv, 'W').items():
            self.assertTrue(0 <= reserved <= on_hand, (wh, on_hand, reserved))


class Money(unittest.TestCase):
    def test_R4_half_up_to_cents(self):
        inv = make(products=[('P', '0.25', '0.10'), ('Q', '2.665', '0')], stock=[('P', 'A', 9), ('Q', 'A', 9)])
        order = inv.orders.place_order('r1', 'o1', [('P', 1), ('Q', 1)])
        p, q = order.lines
        self.assertEqual(p.tax, Decimal('0.03'))
        self.assertEqual(q.unit_price, Decimal('2.67'))
        for value in (p.subtotal, p.tax, p.total, q.total, order.total):
            self.assertIsInstance(value, Decimal)
            self.assertEqual(value.as_tuple().exponent, -2)

    def test_R5_line_and_order_totals(self):
        inv = make(products=[('P', '3.35', '0.15'), ('Q', '1.10', '0.0725')],
                   stock=[('P', 'A', 9), ('Q', 'A', 9)])
        order = inv.orders.place_order('r1', 'o1', [('P', 3), ('Q', 5)])
        p, q = order.lines
        self.assertEqual((p.subtotal, p.tax, p.total), (Decimal('10.05'), Decimal('1.51'), Decimal('11.56')))
        self.assertEqual((q.subtotal, q.tax, q.total), (Decimal('5.50'), Decimal('0.40'), Decimal('5.90')))
        self.assertEqual(order.total, Decimal('17.46'))


class Placing(unittest.TestCase):
    def test_R6_validation(self):
        inv = make(stock=[('W', 'A', 5)])
        for lines in ([], [('W', 0)], [('W', -1)], [('W', 1.0)], [('W', True)]):
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                inv.orders.place_order('rv', 'ov', lines)
        with self.assertRaises(UnknownSku):
            inv.orders.place_order('ru', 'ou', [('W', 1), ('NOPE', 1)])
        order = inv.orders.place_order('r1', 'o1', [('W', 1), ('W', 2)])
        self.assertEqual([line.line_no for line in order.lines], [1, 2])
        with self.assertRaises(InvalidState):
            inv.orders.place_order('r2', 'o1', [('W', 1)])
        self.assertEqual(levels(inv, 'W')['A'], (5, 3))

    def test_R7_lines_see_earlier_lines(self):
        inv = make(stock=[('W', 'A', 5), ('W', 'B', 5)])
        inv.orders.place_order('r1', 'o1', [('W', 4), ('W', 3)])
        self.assertEqual(allocs(inv, 'o1'), [(1, 'A', 4), (2, 'B', 3)])
        self.assertEqual(levels(inv, 'W'), {'A': (5, 4), 'B': (5, 3), 'C': (0, 0)})

    def test_R7_three_lines_same_sku(self):
        inv = make(stock=[('W', 'A', 3), ('W', 'B', 2), ('W', 'C', 4)])
        inv.orders.place_order('r1', 'o1', [('W', 2), ('W', 4), ('W', 3)])
        self.assertEqual(allocs(inv, 'o1'), [(1, 'A', 2), (2, 'C', 4), (3, 'A', 1), (3, 'B', 2)])

    def test_R8_fewest_warehouses_then_priority(self):
        inv = make(stock=[('W', 'A', 3), ('W', 'B', 3), ('W', 'C', 5)])
        inv.orders.place_order('r1', 'o1', [('W', 8)])
        self.assertEqual(allocs(inv, 'o1'), [(1, 'A', 3), (1, 'C', 5)])

        inv = make(warehouses=('A', 'B', 'C', 'D'), stock=[('W', 'A', 2), ('W', 'B', 5), ('W', 'C', 5), ('W', 'D', 9)])
        inv.orders.place_order('r1', 'o1', [('W', 5)])
        self.assertEqual(allocs(inv, 'o1'), [(1, 'B', 5)])
        inv.orders.place_order('r2', 'o2', [('W', 10)])
        self.assertEqual(allocs(inv, 'o2'), [(1, 'A', 2), (1, 'D', 8)])

    def test_R8_empty_warehouses_skipped(self):
        inv = make(stock=[('W', 'B', 2), ('W', 'C', 3)])
        inv.orders.place_order('r1', 'o1', [('W', 4)])
        self.assertEqual(allocs(inv, 'o1'), [(1, 'B', 2), (1, 'C', 2)])

    def test_R9_all_or_nothing(self):
        inv = make(products=[('W', '1.00', '0'), ('V', '1.00', '0')], stock=[('W', 'A', 5), ('V', 'A', 1)])
        before = inv.audit.entries()
        with self.assertRaises(InsufficientStock):
            inv.orders.place_order('r1', 'o1', [('W', 2), ('V', 2)])
        with self.assertRaises(InsufficientStock):
            inv.orders.place_order('r2', 'o2', [('W', 4), ('W', 2)])
        self.assertEqual(levels(inv, 'W')['A'], (5, 0))
        self.assertEqual(inv.audit.entries(), before)
        self.assertEqual(inv.reservations.allocations('o1'), [])
        with self.assertRaises(InvalidState):
            inv.orders.get('o2')
        inv.stock.receive('V', 'B', 1)
        order = inv.orders.place_order('r1', 'o1', [('W', 2), ('V', 2)])
        self.assertEqual(order.status, 'reserved')

    def test_R10_reserving(self):
        inv = make(stock=[('W', 'A', 1), ('W', 'B', 6)])
        order = inv.orders.place_order('r1', 'o1', [('W', 6)])
        self.assertEqual(order.status, 'reserved')
        self.assertEqual(levels(inv, 'W'), {'A': (1, 0), 'B': (6, 6), 'C': (0, 0)})


class ShipCancel(unittest.TestCase):
    def test_R11_ship(self):
        inv = make(stock=[('W', 'A', 2), ('W', 'B', 3)])
        inv.orders.place_order('r1', 'o1', [('W', 4)])
        inv.orders.ship_order('r2', 'o1')
        self.assertEqual(inv.orders.get('o1').status, 'shipped')
        self.assertEqual(levels(inv, 'W'), {'A': (0, 0), 'B': (1, 0), 'C': (0, 0)})
        with self.assertRaises(InvalidState):
            inv.orders.ship_order('r3', 'o1')
        for call in (lambda: inv.orders.get('nope'), lambda: inv.orders.ship_order('r4', 'nope'),
                     lambda: inv.orders.cancel_order('r5', 'nope'), lambda: inv.refunds.refund('r6', 'nope', 1, 1)):
            with self.assertRaises(InvalidState):
                call()
        inv.orders.place_order('r7', 'o2', [('W', 1)])
        inv.orders.cancel_order('r8', 'o2')
        with self.assertRaises(InvalidState):
            inv.orders.ship_order('r9', 'o2')

    def test_R12_cancel_exactly_once(self):
        inv = make(stock=[('W', 'A', 2), ('W', 'B', 3)])
        inv.orders.place_order('r1', 'o1', [('W', 4)])
        inv.orders.cancel_order('r2', 'o1')
        self.assertEqual(levels(inv, 'W')['B'], (3, 0))
        entries = inv.audit.entries()
        with self.assertRaises(InvalidState):
            inv.orders.cancel_order('r3', 'o1')
        self.assertEqual(levels(inv, 'W'), {'A': (2, 0), 'B': (3, 0), 'C': (0, 0)})
        self.assertEqual(inv.stock.total_available('W'), 5)
        self.assertEqual(inv.audit.entries(), entries)
        inv.orders.place_order('r4', 'o2', [('W', 1)])
        inv.orders.ship_order('r5', 'o2')
        with self.assertRaises(InvalidState):
            inv.orders.cancel_order('r6', 'o2')
        self.assertEqual(inv.orders.get('o2').status, 'shipped')


def shipped(inv, lines, order_id='o1'):
    inv.orders.place_order('place-' + order_id, order_id, lines)
    inv.orders.ship_order('ship-' + order_id, order_id)
    return inv.orders.get(order_id)


class Refunds(unittest.TestCase):
    def test_R13_refund_validation(self):
        inv = make(stock=[('W', 'A', 9)])
        inv.orders.place_order('r1', 'o1', [('W', 2)])
        with self.assertRaises(InvalidState):
            inv.refunds.refund('r2', 'o1', 1, 1)
        inv.orders.ship_order('r3', 'o1')
        for line_no, qty in ((2, 1), (1, 0), (1, -1), (1, 3), (1, 1.0)):
            with self.subTest(line_no=line_no, qty=qty), self.assertRaises(RefundError):
                inv.refunds.refund(f'bad-{line_no}-{qty}', 'o1', line_no, qty)
        inv.refunds.refund('r4', 'o1', 1, 2)
        with self.assertRaises(RefundError):
            inv.refunds.refund('r5', 'o1', 1, 1)

    def test_R14_restock_where_shipped_from(self):
        inv = make(stock=[('W', 'B', 2), ('W', 'C', 3)])
        shipped(inv, [('W', 5)])
        inv.refunds.refund('r1', 'o1', 1, 4)
        self.assertEqual({wh: on for wh, (on, _) in levels(inv, 'W').items()}, {'A': 0, 'B': 1, 'C': 3})
        inv.refunds.refund('r2', 'o1', 1, 1)
        self.assertEqual({wh: on for wh, (on, _) in levels(inv, 'W').items()}, {'A': 0, 'B': 2, 'C': 3})

    def test_R14_restock_per_line(self):
        inv = make(stock=[('W', 'A', 2), ('W', 'B', 4)])
        shipped(inv, [('W', 1), ('W', 4)])  # line 1 from A, line 2 from B
        inv.refunds.refund('r1', 'o1', 2, 1)
        inv.refunds.refund('r2', 'o1', 1, 1)
        self.assertEqual({wh: on for wh, (on, _) in levels(inv, 'W').items()}, {'A': 2, 'B': 1, 'C': 0})

    def test_R15_refund_amounts(self):
        inv = make(stock=[('W', 'A', 9)])
        shipped(inv, [('W', 3)])
        self.assertEqual(inv.orders.get('o1').total, Decimal('30.00'))
        amounts = [inv.refunds.refund(f'r{i}', 'o1', 1, 1) for i in range(3)]
        self.assertEqual(amounts, [Decimal('10.00')] * 3)

        inv = make(products=[('P', '3.33', '0.001')], stock=[('P', 'A', 9)])
        shipped(inv, [('P', 3)])
        line = inv.orders.get('o1').lines[0]
        self.assertEqual(line.total, Decimal('10.00'))
        amounts = [inv.refunds.refund(f'r{i}', 'o1', 1, 1) for i in range(3)]
        self.assertEqual(amounts, [Decimal('3.33'), Decimal('3.33'), Decimal('3.34')])
        self.assertEqual(sum(amounts), line.total)

    def test_R15_half_up_and_remainder(self):
        inv = make(products=[('P', '0.50', '0.25')], stock=[('P', 'A', 9)])
        shipped(inv, [('P', 4)])
        self.assertEqual(inv.orders.get('o1').lines[0].total, Decimal('2.50'))
        self.assertEqual(inv.refunds.refund('r1', 'o1', 1, 1), Decimal('0.63'))
        self.assertEqual(inv.refunds.refund('r2', 'o1', 1, 3), Decimal('1.87'))
        self.assertEqual(inv.orders.get('o1').refunded_total, Decimal('2.50'))

    def test_R16_refund_totals(self):
        inv = make(products=[('W', '10.00', '0'), ('V', '4.00', '0.25')], stock=[('W', 'A', 9), ('V', 'A', 9)])
        order = shipped(inv, [('W', 2), ('V', 1)])
        inv.refunds.refund('r1', 'o1', 1, 1)
        inv.refunds.refund('r2', 'o1', 2, 1)
        w, v = order.lines
        self.assertEqual((w.refunded_qty, w.refunded_amount), (1, Decimal('10.00')))
        self.assertEqual((v.refunded_qty, v.refunded_amount), (1, Decimal('5.00')))
        self.assertEqual(order.refunded_total, Decimal('15.00'))
        self.assertEqual(order.status, 'shipped')


class Idempotency(unittest.TestCase):
    def test_R17_replays_have_no_effect(self):
        inv = make(stock=[('W', 'A', 2), ('W', 'B', 3)])
        order = inv.orders.place_order('p', 'o1', [('W', 4)])
        self.assertIs(inv.orders.ship_order('s', 'o1'), order)
        entries = inv.audit.entries()
        self.assertIs(inv.orders.place_order('p', 'o1', [('W', 4)]), order)
        self.assertIs(inv.orders.ship_order('s', 'o1'), order)
        self.assertEqual(levels(inv, 'W'), {'A': (0, 0), 'B': (1, 0), 'C': (0, 0)})
        self.assertEqual(inv.audit.entries(), entries)

        amount = inv.refunds.refund('f', 'o1', 1, 3)
        entries = inv.audit.entries()
        self.assertEqual(inv.refunds.refund('f', 'o1', 1, 3), amount)
        self.assertEqual(inv.audit.entries(), entries)
        self.assertEqual(order.lines[0].refunded_qty, 3)
        self.assertEqual(inv.stock.on_hand('W', 'A') + inv.stock.on_hand('W', 'B'), 4)

    def test_R17_cancel_replay(self):
        inv = make(stock=[('W', 'A', 5)])
        order = inv.orders.place_order('p', 'o1', [('W', 4)])
        self.assertIs(inv.orders.cancel_order('c', 'o1'), order)
        entries = inv.audit.entries()
        self.assertIs(inv.orders.cancel_order('c', 'o1'), order)
        self.assertEqual(levels(inv, 'W')['A'], (5, 0))
        self.assertEqual(inv.audit.entries(), entries)

    def test_R17_last_refund_replay_keeps_amount(self):
        inv = make(products=[('P', '3.33', '0.001')], stock=[('P', 'A', 9)])
        shipped(inv, [('P', 3)])
        inv.refunds.refund('f1', 'o1', 1, 2)
        last = inv.refunds.refund('f2', 'o1', 1, 1)
        self.assertEqual(inv.refunds.refund('f2', 'o1', 1, 1), last)
        self.assertEqual(inv.refunds.refund('f1', 'o1', 1, 2), Decimal('6.67'))

    def test_R18_conflicts(self):
        inv = make(stock=[('W', 'A', 5)])
        inv.orders.place_order('p', 'o1', [('W', 2)])
        entries = inv.audit.entries()
        with self.assertRaises(IdempotencyConflict):
            inv.orders.place_order('p', 'o1', [('W', 3)])
        with self.assertRaises(IdempotencyConflict):
            inv.orders.place_order('p', 'o2', [('W', 2)])
        with self.assertRaises(IdempotencyConflict):
            inv.orders.cancel_order('p', 'o1')
        with self.assertRaises(IdempotencyConflict):
            inv.orders.ship_order('p', 'o1')
        self.assertEqual(inv.orders.get('o1').status, 'reserved')
        self.assertEqual(levels(inv, 'W')['A'], (5, 2))
        inv.orders.ship_order('s', 'o1')
        inv.refunds.refund('f', 'o1', 1, 1)
        with self.assertRaises(IdempotencyConflict):
            inv.refunds.refund('f', 'o1', 1, 2)
        with self.assertRaises(IdempotencyConflict):
            inv.refunds.refund('s', 'o1', 1, 1)
        self.assertEqual(inv.orders.get('o1').lines[0].refunded_qty, 1)
        self.assertEqual(len(inv.audit.entries()), len(entries) + 4)

    def test_R19_errors_are_not_remembered(self):
        inv = make(stock=[('W', 'A', 1)])
        with self.assertRaises(InsufficientStock):
            inv.orders.place_order('p', 'o1', [('W', 3)])
        inv.stock.receive('W', 'B', 2)
        self.assertEqual(inv.orders.place_order('p', 'o1', [('W', 3)]).status, 'reserved')
        with self.assertRaises(InvalidState):
            inv.refunds.refund('f', 'o1', 1, 1)
        with self.assertRaises(InvalidState):
            inv.orders.cancel_order('c', 'missing')
        inv.orders.ship_order('s', 'o1')
        self.assertEqual(inv.refunds.refund('f', 'o1', 1, 3), Decimal('30.00'))
        inv.orders.place_order('p2', 'o2', [('W', 1)])
        self.assertEqual(inv.orders.cancel_order('c', 'o2').status, 'cancelled')


class Audit(unittest.TestCase):
    def test_R20_sequence_numbers(self):
        inv = make(stock=[('W', 'A', 2), ('W', 'B', 3)])
        inv.orders.place_order('p', 'o1', [('W', 4)])
        inv.orders.ship_order('s', 'o1')
        inv.refunds.refund('f', 'o1', 1, 4)
        entries = inv.audit.entries()
        self.assertEqual([e['seq'] for e in entries], list(range(1, len(entries) + 1)))
        entries[0]['event'] = 'tampered'
        self.assertEqual(inv.audit.entries()[0]['event'], 'reserve')

    def test_R21_placement_entries(self):
        inv = make(products=[('W', '10.00', '0'), ('V', '1.00', '0')],
                   stock=[('W', 'A', 2), ('W', 'B', 3), ('V', 'C', 1)])
        inv.orders.place_order('p', 'o1', [('V', 1), ('W', 4)])
        self.assertEqual(inv.audit.entries(), [
            {'seq': 1, 'event': 'reserve', 'order': 'o1', 'line': 1, 'sku': 'V', 'warehouse': 'C', 'qty': 1},
            {'seq': 2, 'event': 'reserve', 'order': 'o1', 'line': 2, 'sku': 'W', 'warehouse': 'A', 'qty': 2},
            {'seq': 3, 'event': 'reserve', 'order': 'o1', 'line': 2, 'sku': 'W', 'warehouse': 'B', 'qty': 2},
            {'seq': 4, 'event': 'order_placed', 'order': 'o1', 'total': Decimal('41.00')},
        ])

    def test_R22_ship_and_cancel_entries(self):
        inv = make(stock=[('W', 'A', 2), ('W', 'B', 3)])
        inv.orders.place_order('p1', 'o1', [('W', 4)])
        inv.orders.ship_order('s1', 'o1')
        inv.orders.place_order('p2', 'o2', [('W', 1)])
        inv.orders.cancel_order('c2', 'o2')
        events = [{k: v for k, v in e.items() if k != 'seq'} for e in inv.audit.entries()[3:]]
        self.assertEqual(events, [
            {'event': 'ship', 'order': 'o1', 'line': 1, 'sku': 'W', 'warehouse': 'A', 'qty': 2},
            {'event': 'ship', 'order': 'o1', 'line': 1, 'sku': 'W', 'warehouse': 'B', 'qty': 2},
            {'event': 'order_shipped', 'order': 'o1'},
            {'event': 'reserve', 'order': 'o2', 'line': 1, 'sku': 'W', 'warehouse': 'B', 'qty': 1},
            {'event': 'order_placed', 'order': 'o2', 'total': Decimal('10.00')},
            {'event': 'release', 'order': 'o2', 'line': 1, 'sku': 'W', 'warehouse': 'B', 'qty': 1},
            {'event': 'order_cancelled', 'order': 'o2'},
        ])

    def test_R23_refund_entries(self):
        inv = make(stock=[('W', 'B', 2), ('W', 'C', 3)])
        shipped(inv, [('W', 5)])
        start = len(inv.audit.entries())
        inv.refunds.refund('f1', 'o1', 1, 4)
        inv.refunds.refund('f2', 'o1', 1, 1)
        events = [{k: v for k, v in e.items() if k != 'seq'} for e in inv.audit.entries()[start:]]
        self.assertEqual(events, [
            {'event': 'restock', 'order': 'o1', 'line': 1, 'sku': 'W', 'warehouse': 'C', 'qty': 3},
            {'event': 'restock', 'order': 'o1', 'line': 1, 'sku': 'W', 'warehouse': 'B', 'qty': 1},
            {'event': 'refund', 'order': 'o1', 'line': 1, 'qty': 4, 'amount': Decimal('40.00')},
            {'event': 'restock', 'order': 'o1', 'line': 1, 'sku': 'W', 'warehouse': 'B', 'qty': 1},
            {'event': 'refund', 'order': 'o1', 'line': 1, 'qty': 1, 'amount': Decimal('10.00')},
        ])

    def test_R24_failures_and_replays_record_nothing(self):
        inv = make(stock=[('W', 'A', 3)])
        inv.orders.place_order('p', 'o1', [('W', 2)])
        inv.orders.place_order('p2', 'o2', [('W', 1)])
        inv.orders.cancel_order('c2', 'o2')
        count = len(inv.audit.entries())
        attempts = [
            lambda: inv.orders.place_order('x1', 'o3', [('W', 1), ('W', 5)]),
            lambda: inv.orders.place_order('x2', 'o3', [('W', 1), ('NOPE', 1)]),
            lambda: inv.orders.cancel_order('x3', 'o2'),
            lambda: inv.refunds.refund('x4', 'o1', 1, 1),
            lambda: inv.orders.place_order('p', 'o1', [('W', 2)]),
            lambda: inv.orders.cancel_order('c2', 'o2'),
        ]
        for attempt in attempts:
            try:
                attempt()
            except Exception:
                pass
        self.assertEqual(len(inv.audit.entries()), count)


if __name__ == '__main__':
    unittest.main()
