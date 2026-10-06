"""Money amounts with per-currency minor units, rounding and allocation."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

MINOR_UNITS = {"JPY": 0, "USD": 2, "EUR": 2, "KWD": 3}


class CurrencyError(ValueError):
    """Unknown currency code, or amounts in different currencies."""


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    def __str__(self) -> str:
        return f"{self.currency} {self.amount}"


def _exponent(currency: str) -> Decimal:
    return Decimal(1).scaleb(-MINOR_UNITS[currency])


def _round(value: Decimal, currency: str) -> Decimal:
    return value.quantize(_exponent(currency), rounding=ROUND_HALF_UP)


def money(amount: str, currency: str) -> Money:
    value = Decimal(amount)
    return Money(_round(value, currency), currency)


def add(a: Money, b: Money) -> Money:
    if a.currency != b.currency:
        raise CurrencyError(f"cannot add {a.currency} and {b.currency}")
    return Money(a.amount + b.amount, a.currency)


def scale(m: Money, factor: str) -> Money:
    return Money(_round(m.amount * Decimal(factor), m.currency), m.currency)


def invoice(lines: list[Money], tax_rate: str) -> tuple[Money, Money, Money]:
    currency = lines[0].currency
    subtotal = Money(Decimal(0), currency)
    tax = Money(Decimal(0), currency)
    for line in lines:
        subtotal = add(subtotal, line)
        tax = add(tax, scale(line, tax_rate))
    return subtotal, tax, add(subtotal, tax)


def allocate(m: Money, weights: list[int]) -> list[Money]:
    if not weights:
        raise ValueError("no weights")
    places = MINOR_UNITS[m.currency]
    units = int(m.amount.scaleb(places))
    total_weight = sum(weights)
    shares = [units * w // total_weight for w in weights]
    # whatever is left over goes to the last party
    shares[-1] += units - sum(shares)
    return [Money(Decimal(s).scaleb(-places), m.currency) for s in shares]


class Ledger:
    def __init__(self, currency: str):
        self.currency = currency
        self._entries: list[Money] = []

    def post(self, m: Money) -> None:
        if m.currency != self.currency:
            raise CurrencyError(f"ledger is {self.currency}, got {m.currency}")
        self._entries.append(m)

    def post_many(self, items: list[Money]) -> None:
        for m in items:
            self.post(m)

    def balance(self) -> Money:
        total = Money(Decimal(0), self.currency)
        for m in self._entries:
            total = add(total, m)
        return total

    def split(self, weights: list[int]) -> list[Money]:
        return allocate(self.balance(), weights)
