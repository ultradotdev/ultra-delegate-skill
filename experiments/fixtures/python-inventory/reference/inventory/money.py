"""Money helpers. Every amount in the package is a Decimal rounded to cents."""
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal('0.01')
ZERO = Decimal('0.00')


def to_money(value):
    """Round a str, int or Decimal amount to cents."""
    if isinstance(value, float):
        raise TypeError('use str or Decimal for money, not float')
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)
