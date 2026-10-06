import unittest
from decimal import Decimal

from ledger import CurrencyError, Ledger, add, allocate, money


class Public(unittest.TestCase):
    def test_parse_and_format(self):
        self.assertEqual(str(money("12.5", "USD")), "USD 12.50")
        self.assertEqual(str(money("1000", "JPY")), "JPY 1000")
        self.assertEqual(money("0.25", "KWD").amount, Decimal("0.250"))

    def test_add(self):
        self.assertEqual(str(add(money("1.10", "USD"), money("2.25", "USD"))), "USD 3.35")
        with self.assertRaises(CurrencyError):
            add(money("1", "USD"), money("1", "EUR"))

    def test_allocate_evenly(self):
        parts = allocate(money("100.00", "USD"), [1, 1, 1])
        self.assertEqual([str(p) for p in parts], ["USD 33.34", "USD 33.33", "USD 33.33"])

    def test_ledger_balance(self):
        ledger = Ledger("USD")
        ledger.post(money("10.00", "USD"))
        ledger.post(money("-2.50", "USD"))
        self.assertEqual(str(ledger.balance()), "USD 7.50")


if __name__ == "__main__":
    unittest.main()
