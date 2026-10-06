# ledger.py: money amounts, rounding and allocation

`ledger.py` models money as a frozen `Money(amount: Decimal, currency: str)` value.
`MINOR_UNITS` maps each supported currency code to its number of minor-unit
(fractional) digits: `JPY` 0, `USD` 2, `EUR` 2, `KWD` 3. `CurrencyError` is a
subclass of `ValueError`. Use only the standard library.

Public API: `money(amount, currency)`, `str(Money)`, `add(a, b)`,
`scale(m, factor)`, `invoice(lines, tax_rate)`, `allocate(m, weights)` and the
`Ledger` class (`Ledger(currency)`, `post(m)`, `post_many(items)`, `balance()`,
`split(weights)`).

## Requirements

R1. A currency code must be a key of `MINOR_UNITS`, compared case-sensitively (`"usd"` is unknown). An unknown code raises `CurrencyError` wherever a currency is accepted (`money`, `Ledger`).

R2. `money(amount, currency)` takes `amount` as a `str`; any other type raises `TypeError`. The string must match an optional leading `-`, one or more ASCII digits, then optionally `.` followed by one or more ASCII digits. Anything else (whitespace, `+`, exponents such as `1e3`, `NaN`, `Infinity`, `1.`, `.5`, thousands separators, non-ASCII digits) raises `ValueError`.

R3. The value must be exactly representable in the currency's minor units: `"1.005"` USD and `"100.5"` JPY raise `ValueError` (never round silently), while trailing zeros are fine (`"1.500"` USD is 1.50). The stored `amount` always has exactly the currency's number of fractional digits (`money("1.5", "USD").amount` is `Decimal("1.50")`).

R4. Zero is never negative: every `Money` produced by any function in this module (including `money("-0.00", "USD")`, rounding results and allocation parts) stores a non-negative zero, so it prints as `USD 0.00`, never `USD -0.00`.

R5. `str(m)` is `"<CODE> <amount>"`: a leading `-` for negative amounts, exactly the currency's number of fractional digits (no decimal point for JPY), no thousands separators and no exponent notation. Examples: `USD -12.30`, `JPY 1000`, `KWD 0.250`, `USD 1234567.89`.

R6. `add(a, b)` returns the exact sum when both have the same currency, and raises `CurrencyError` otherwise.

R7. `scale(m, factor)` multiplies by `factor`, a `str` in the R2 grammar except that it may have any number of fractional digits (non-`str` raises `TypeError`, a bad string raises `ValueError`). The exact product is rounded once to the currency's minor units using round-half-even (banker's rounding): `USD 0.25 × "0.1"` is `USD 0.02`, `USD 0.35 × "0.1"` is `USD 0.04`, `USD -0.25 × "0.1"` is `USD -0.02`.

R8. `invoice(lines, tax_rate)` returns `(subtotal, tax, total)`. `lines` must be non-empty (`ValueError`) and all in one currency (`CurrencyError`). `subtotal` is the exact sum of the lines. `tax` is computed once on the subtotal, as `scale(subtotal, tax_rate)`, not per line. `total = subtotal + tax`. Example: three lines of `USD 0.25` at `"0.1"` give subtotal `USD 0.75`, tax `USD 0.08`, total `USD 0.83`.

R9. `allocate(m, weights)` splits `m` into one part per weight, in the same order and currency, and the parts always sum exactly to `m`. `weights` must be a non-empty list of integers, each `>= 0`, with a positive sum; otherwise `ValueError`.

R10. Allocation works in whole minor units. With `U` the amount in minor units, `W` the sum of the weights and `w` a party's weight, each party first gets `floor(U * w / W)` units. The units left over are then handed out one at a time to the parties with the largest remainder `(U * w) mod W`, ties going to the lower index; no party gets more than one extra unit. Examples: `USD 0.07` over `[3, 5, 2]` is `[0.02, 0.04, 0.01]`; `JPY 10` over `[1, 1, 1]` is `[4, 3, 3]`; `JPY 2` over `[1, 0, 1, 1]` is `[1, 0, 1, 0]`.

R11. A negative amount is allocated by allocating its absolute value under R10 and negating every part, so `allocate(-x, w)` is the part-by-part negation of `allocate(x, w)`. Example: `USD -0.07` over `[3, 5, 2]` is `[-0.02, -0.04, -0.01]`.

R12. `Ledger(currency)` validates the currency (R1). `balance()` is the exact sum of everything posted, and a zero `Money` in the ledger's currency when nothing has been posted (`JPY 0`, `USD 0.00`).

R13. `post(m)` adds one amount; `post_many(items)` adds several. An item in a different currency raises `CurrencyError`, and `post_many` is all-or-nothing: if any item is rejected, none of the items are posted and the balance is unchanged.

R14. `split(weights)` returns `allocate(balance(), weights)` and does not change the ledger.
