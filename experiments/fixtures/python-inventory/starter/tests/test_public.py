import unittest
from decimal import Decimal

from inventory import Inventory


def setup():
    inv = Inventory()
    inv.catalog.add('MUG', 'Mug', '10.50', '0.05')
    inv.catalog.add('TEE', 'T-shirt', '19.99', '0.08')
    for code in ('EAST', 'WEST'):
        inv.stock.add_warehouse(code)
    inv.stock.receive('MUG', 'EAST', 3)
    inv.stock.receive('MUG', 'WEST', 10)
    inv.stock.receive('TEE', 'WEST', 5)
    return inv


class Public(unittest.TestCase):
    def test_place_order_splits_across_warehouses(self):
        inv = setup()
        order = inv.orders.place_order('r1', 'o1', [('MUG', 12)])
        self.assertEqual(order.status, 'reserved')
        allocations = [(a.warehouse, a.qty) for a in inv.reservations.allocations('o1')]
        self.assertEqual(allocations, [('EAST', 3), ('WEST', 9)])
        self.assertEqual(inv.stock.reserved('MUG', 'WEST'), 9)
        self.assertEqual(inv.stock.total_available('MUG'), 1)

    def test_totals_round_half_up(self):
        inv = setup()
        order = inv.orders.place_order('r1', 'o1', [('MUG', 1), ('TEE', 2)])
        mug, tee = order.lines
        self.assertEqual((mug.subtotal, mug.tax, mug.total), (Decimal('10.50'), Decimal('0.53'), Decimal('11.03')))
        self.assertEqual((tee.subtotal, tee.tax, tee.total), (Decimal('39.98'), Decimal('3.20'), Decimal('43.18')))
        self.assertEqual(order.total, Decimal('54.21'))

    def test_ship_then_cancel_rules(self):
        inv = setup()
        inv.orders.place_order('r1', 'o1', [('TEE', 2)])
        inv.orders.ship_order('r2', 'o1')
        self.assertEqual(inv.orders.get('o1').status, 'shipped')
        self.assertEqual((inv.stock.on_hand('TEE', 'WEST'), inv.stock.reserved('TEE', 'WEST')), (3, 0))

        inv.orders.place_order('r3', 'o2', [('TEE', 1)])
        inv.orders.cancel_order('r4', 'o2')
        self.assertEqual(inv.orders.get('o2').status, 'cancelled')
        self.assertEqual(inv.stock.available('TEE', 'WEST'), 3)

    def test_place_order_is_idempotent(self):
        inv = setup()
        first = inv.orders.place_order('r1', 'o1', [('TEE', 2)])
        again = inv.orders.place_order('r1', 'o1', [('TEE', 2)])
        self.assertIs(again, first)
        self.assertEqual(inv.stock.reserved('TEE', 'WEST'), 2)

    def test_audit_for_placement(self):
        inv = setup()
        inv.orders.place_order('r1', 'o1', [('MUG', 4)])
        self.assertEqual(inv.audit.entries(), [
            {'seq': 1, 'event': 'reserve', 'order': 'o1', 'line': 1, 'sku': 'MUG', 'warehouse': 'WEST', 'qty': 4},
            {'seq': 2, 'event': 'order_placed', 'order': 'o1', 'total': Decimal('44.10')},
        ])


if __name__ == '__main__':
    unittest.main()
