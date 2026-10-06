"""Choose the warehouses a line is allocated from (SPEC R8)."""
from itertools import combinations

from .errors import InsufficientStock


def plan(stock, sku, qty, planned=None):
    """Return [(warehouse, qty), ...] covering `qty` units of `sku`.

    `planned` maps (sku, warehouse) to units already promised to earlier lines
    that are not yet held in stock; they count as unavailable.

    Raises InsufficientStock when all warehouses together cannot cover it.
    """
    planned = planned or {}
    candidates = []
    for warehouse in stock.warehouses():
        available = stock.available(sku, warehouse) - planned.get((sku, warehouse), 0)
        if available > 0:
            candidates.append((warehouse, available))
    total = sum(available for _, available in candidates)
    if total < qty:
        raise InsufficientStock(f'{sku}: wanted {qty}, only {total} available')
    # combinations() keeps priority order, so the first covering set of each
    # size is the lexicographically smallest one.
    for size in range(1, len(candidates) + 1):
        for chosen in combinations(candidates, size):
            if sum(available for _, available in chosen) >= qty:
                result, remaining = [], qty
                for warehouse, available in chosen:
                    take = min(available, remaining)
                    result.append((warehouse, take))
                    remaining -= take
                return result
    raise AssertionError('unreachable')
