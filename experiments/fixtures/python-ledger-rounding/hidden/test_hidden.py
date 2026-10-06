import unittest
from decimal import Decimal

from ledger import CurrencyError, Ledger, add, allocate, invoice, money, scale


def strs(items):
    return [str(m) for m in items]


class Hidden(unittest.TestCase):
    def test_R1_unknown_currency(self):
        for code in ("usd", "XYZ", ""):
            with self.subTest(code=code), self.assertRaises(CurrencyError):
                money("1", code)
        with self.assertRaises(CurrencyError):
            Ledger("Usd")

    def test_R2_amount_grammar(self):
        self.assertEqual(str(money("-3", "USD")), "USD -3.00")
        self.assertEqual(str(money("007.10", "USD")), "USD 7.10")
        for text in (" 1", "1 ", "+1", "1e3", "NaN", "Infinity", "1.", ".5", "1,000", "١", "", "--1", "1.2.3"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                money(text, "USD")
        for value in (1.5, 2, Decimal("1.00")):
            with self.subTest(value=value), self.assertRaises(TypeError):
                money(value, "USD")

    def test_R3_exact_minor_units(self):
        for text, code in (("1.005", "USD"), ("100.5", "JPY"), ("0.0001", "KWD"), ("2.999", "EUR")):
            with self.subTest(text=text, code=code), self.assertRaises(ValueError):
                money(text, code)
        self.assertEqual(money("1.500", "USD").amount.as_tuple().exponent, -2)
        self.assertEqual(str(money("1.500", "USD")), "USD 1.50")
        self.assertEqual(str(money("12.000", "JPY")), "JPY 12")
        self.assertEqual(str(money("1.5", "KWD")), "KWD 1.500")

    def test_R4_no_negative_zero(self):
        z = money("-0.00", "USD")
        self.assertFalse(z.amount.is_signed())
        self.assertEqual(str(z), "USD 0.00")
        self.assertEqual(str(money("-0", "JPY")), "JPY 0")
        tiny = scale(money("1.00", "USD"), "-0.001")
        self.assertEqual(str(tiny), "USD 0.00")
        self.assertFalse(tiny.amount.is_signed())
        parts = allocate(money("-0.01", "USD"), [1, 1])
        self.assertEqual(strs(parts), ["USD -0.01", "USD 0.00"])
        self.assertFalse(parts[1].amount.is_signed())

    def test_R5_format(self):
        self.assertEqual(str(money("-12.3", "USD")), "USD -12.30")
        self.assertEqual(str(money("1000", "JPY")), "JPY 1000")
        self.assertEqual(str(money("0.25", "KWD")), "KWD 0.250")
        self.assertEqual(str(money("1234567.89", "USD")), "USD 1234567.89")
        self.assertEqual(str(money("0", "KWD")), "KWD 0.000")
        self.assertEqual(str(scale(money("100", "JPY"), "100")), "JPY 10000")

    def test_R6_add(self):
        self.assertEqual(str(add(money("0.10", "EUR"), money("0.20", "EUR"))), "EUR 0.30")
        self.assertEqual(str(add(money("1.001", "KWD"), money("-2", "KWD"))), "KWD -0.999")
        with self.assertRaises(CurrencyError):
            add(money("1", "JPY"), money("1", "USD"))

    def test_R7_scale_half_even(self):
        cases = [
            ("0.25", "USD", "0.1", "USD 0.02"),
            ("0.35", "USD", "0.1", "USD 0.04"),
            ("-0.25", "USD", "0.1", "USD -0.02"),
            ("25", "JPY", "0.1", "JPY 2"),
            ("35", "JPY", "0.1", "JPY 4"),
            ("1.000", "KWD", "0.0025", "KWD 0.002"),
            ("1.000", "KWD", "0.0035", "KWD 0.004"),
            ("19.99", "USD", "3", "USD 59.97"),
            ("10.00", "USD", "0.333333", "USD 3.33"),
        ]
        for amount, code, factor, expected in cases:
            with self.subTest(amount=amount, factor=factor):
                self.assertEqual(str(scale(money(amount, code), factor)), expected)
        for factor in ("1e-1", "abc", "", " 2", ".5"):
            with self.subTest(factor=factor), self.assertRaises(ValueError):
                scale(money("1", "USD"), factor)
        with self.assertRaises(TypeError):
            scale(money("1", "USD"), 0.5)

    def test_R8_invoice_tax_on_subtotal(self):
        subtotal, tax, total = invoice([money("0.25", "USD")] * 3, "0.1")
        self.assertEqual(strs([subtotal, tax, total]), ["USD 0.75", "USD 0.08", "USD 0.83"])
        subtotal, tax, total = invoice([money("0.05", "USD"), money("0.10", "USD")], "0.25")
        self.assertEqual(strs([subtotal, tax, total]), ["USD 0.15", "USD 0.04", "USD 0.19"])
        subtotal, tax, total = invoice([money("30", "JPY"), money("20", "JPY")], "0.05")
        self.assertEqual(strs([subtotal, tax, total]), ["JPY 50", "JPY 2", "JPY 52"])
        with self.assertRaises(ValueError):
            invoice([], "0.1")
        with self.assertRaises(CurrencyError):
            invoice([money("1", "USD"), money("1", "EUR")], "0.1")

    def test_R9_allocate_sums_and_validates(self):
        for amount, code, weights in (("100.00", "USD", [1, 2, 3, 4]), ("1", "JPY", [5, 5, 5]),
                                      ("10.000", "KWD", [7, 11, 13]), ("-99.99", "EUR", [1, 1, 1, 1, 1, 1, 1])):
            with self.subTest(amount=amount, weights=weights):
                m = money(amount, code)
                parts = allocate(m, weights)
                self.assertEqual(len(parts), len(weights))
                self.assertTrue(all(p.currency == code for p in parts))
                self.assertEqual(sum((p.amount for p in parts), Decimal(0)), m.amount)
        for weights in ([], [0, 0], [1, -1], [-2]):
            with self.subTest(weights=weights), self.assertRaises(ValueError):
                allocate(money("1.00", "USD"), weights)

    def test_R10_largest_remainder(self):
        self.assertEqual(strs(allocate(money("0.07", "USD"), [3, 5, 2])), ["USD 0.02", "USD 0.04", "USD 0.01"])
        self.assertEqual(strs(allocate(money("10", "JPY"), [1, 1, 1])), ["JPY 4", "JPY 3", "JPY 3"])
        self.assertEqual(strs(allocate(money("2", "JPY"), [1, 0, 1, 1])), ["JPY 1", "JPY 0", "JPY 1", "JPY 0"])
        self.assertEqual(strs(allocate(money("100", "JPY"), [1, 2, 4])), ["JPY 14", "JPY 29", "JPY 57"])
        self.assertEqual(strs(allocate(money("1.000", "KWD"), [1, 1, 1])), ["KWD 0.334", "KWD 0.333", "KWD 0.333"])
        self.assertEqual(strs(allocate(money("0.05", "USD"), [0, 1, 0])), ["USD 0.00", "USD 0.05", "USD 0.00"])

    def test_R11_negative_allocation(self):
        self.assertEqual(strs(allocate(money("-0.07", "USD"), [3, 5, 2])), ["USD -0.02", "USD -0.04", "USD -0.01"])
        self.assertEqual(strs(allocate(money("-10", "JPY"), [1, 1, 1])), ["JPY -4", "JPY -3", "JPY -3"])
        self.assertEqual(strs(allocate(money("-100", "JPY"), [1, 2, 4])), ["JPY -14", "JPY -29", "JPY -57"])

    def test_R12_ledger_balance(self):
        self.assertEqual(str(Ledger("JPY").balance()), "JPY 0")
        self.assertEqual(str(Ledger("USD").balance()), "USD 0.00")
        self.assertEqual(str(Ledger("KWD").balance()), "KWD 0.000")
        ledger = Ledger("EUR")
        ledger.post(money("0.10", "EUR"))
        ledger.post(money("0.20", "EUR"))
        ledger.post(money("-0.30", "EUR"))
        self.assertEqual(str(ledger.balance()), "EUR 0.00")

    def test_R13_post_rejects_mixed_currency_atomically(self):
        ledger = Ledger("USD")
        ledger.post(money("5.00", "USD"))
        with self.assertRaises(CurrencyError):
            ledger.post(money("1", "JPY"))
        self.assertEqual(str(ledger.balance()), "USD 5.00")
        with self.assertRaises(CurrencyError):
            ledger.post_many([money("1.00", "USD"), money("2.00", "USD"), money("3.00", "EUR")])
        self.assertEqual(str(ledger.balance()), "USD 5.00")
        ledger.post_many([money("1.00", "USD"), money("2.00", "USD")])
        self.assertEqual(str(ledger.balance()), "USD 8.00")

    def test_R14_split(self):
        ledger = Ledger("USD")
        ledger.post_many([money("0.04", "USD"), money("0.03", "USD")])
        self.assertEqual(strs(ledger.split([3, 5, 2])), ["USD 0.02", "USD 0.04", "USD 0.01"])
        self.assertEqual(str(ledger.balance()), "USD 0.07")
        ledger.post(money("-0.14", "USD"))
        self.assertEqual(strs(ledger.split([3, 5, 2])), ["USD -0.02", "USD -0.04", "USD -0.01"])


if __name__ == "__main__":
    unittest.main()
