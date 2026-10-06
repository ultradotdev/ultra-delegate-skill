"""Money amounts with per-currency minor units, rounding and allocation."""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

MINOR_UNITS = {"JPY": 0, "USD": 2, "EUR": 2, "KWD": 3}

_DECIMAL = re.compile(r"-?[0-9]+(?:\.[0-9]+)?", re.ASCII)


class CurrencyError(ValueError):
    """Unknown currency code, or amounts in different currencies."""


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    def __str__(self) -> str:
        return f"{self.currency} {self.amount:f}"


def _minor(currency: str) -> int:
    if not isinstance(currency, str) or currency not in MINOR_UNITS:
        raise CurrencyError(f"unknown currency: {currency!r}")
    return MINOR_UNITS[currency]


def _exponent(currency: str) -> Decimal:
    return Decimal(1).scaleb(-_minor(currency))


def _make(value: Decimal, currency: str) -> Money:
    """Round half-even to the currency's minor units; never store a negative zero."""
    q = value.quantize(_exponent(currency), rounding=ROUND_HALF_EVEN)
    if q.is_zero():
        q = abs(q)
    return Money(q, currency)


def _parse_decimal(text) -> Decimal:
    if not isinstance(text, str):
        raise TypeError(f"expected str, got {type(text).__name__}")
    if not _DECIMAL.fullmatch(text):
        raise ValueError(f"invalid decimal: {text!r}")
    return Decimal(text)


def money(amount: str, currency: str) -> Money:
    exponent = _exponent(currency)
    value = _parse_decimal(amount)
    if value.quantize(exponent) != value:
        raise ValueError(f"{amount!r} has more precision than {currency} allows")
    return _make(value, currency)


def _same_currency(items) -> str:
    currencies = {m.currency for m in items}
    if len(currencies) > 1:
        raise CurrencyError(f"mixed currencies: {sorted(currencies)}")
    return currencies.pop()


def add(a: Money, b: Money) -> Money:
    currency = _same_currency([a, b])
    return _make(a.amount + b.amount, currency)


def scale(m: Money, factor: str) -> Money:
    return _make(m.amount * _parse_decimal(factor), m.currency)


def invoice(lines: list[Money], tax_rate: str) -> tuple[Money, Money, Money]:
    if not lines:
        raise ValueError("an invoice needs at least one line")
    currency = _same_currency(lines)
    subtotal = _make(sum((m.amount for m in lines), Decimal(0)), currency)
    tax = scale(subtotal, tax_rate)
    return subtotal, tax, add(subtotal, tax)


def allocate(m: Money, weights: list[int]) -> list[Money]:
    if (not isinstance(weights, list) or not weights
            or any(type(w) is not int or w < 0 for w in weights) or sum(weights) == 0):
        raise ValueError("weights must be a non-empty list of non-negative ints with a positive sum")
    places = MINOR_UNITS[m.currency]
    units = int(abs(m.amount).scaleb(places))
    total_weight = sum(weights)
    shares, remainders = [], []
    for w in weights:
        q, r = divmod(units * w, total_weight)
        shares.append(q)
        remainders.append(r)
    leftover = units - sum(shares)
    for i in sorted(range(len(weights)), key=lambda i: (-remainders[i], i))[:leftover]:
        shares[i] += 1
    sign = -1 if m.amount < 0 else 1
    return [_make(Decimal(sign * s).scaleb(-places), m.currency) for s in shares]


class Ledger:
    def __init__(self, currency: str):
        _minor(currency)
        self.currency = currency
        self._entries: list[Money] = []

    def _check(self, m: Money) -> None:
        if m.currency != self.currency:
            raise CurrencyError(f"ledger is {self.currency}, got {m.currency}")

    def post(self, m: Money) -> None:
        self._check(m)
        self._entries.append(m)

    def post_many(self, items: list[Money]) -> None:
        items = list(items)
        for m in items:
            self._check(m)
        self._entries.extend(items)

    def balance(self) -> Money:
        return _make(sum((m.amount for m in self._entries), Decimal(0)), self.currency)

    def split(self, weights: list[int]) -> list[Money]:
        return allocate(self.balance(), weights)
