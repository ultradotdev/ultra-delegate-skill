# Warehouse inventory and orders

The `inventory` package tracks stock across warehouses, reserves it for orders,
ships, cancels and refunds orders, and keeps an audit log. Everything is reached
through `inventory.Inventory`:

```python
inv = Inventory()
inv.catalog.add(sku, name, unit_price, tax_rate)        # prices and rates as str or Decimal
inv.stock.add_warehouse(code)
inv.stock.receive(sku, warehouse, qty)
inv.stock.on_hand(sku, warehouse)    inv.stock.reserved(sku, warehouse)
inv.stock.available(sku, warehouse)  inv.stock.total_available(sku)
inv.orders.place_order(request_id, order_id, [(sku, qty), ...])  # -> Order
inv.orders.ship_order(request_id, order_id)                      # -> Order
inv.orders.cancel_order(request_id, order_id)                    # -> Order
inv.orders.get(order_id)                                         # -> Order
inv.reservations.allocations(order_id)   # -> [Allocation(line_no, sku, warehouse, qty), ...]
inv.refunds.refund(request_id, order_id, line_no, qty)           # -> Decimal amount
inv.audit.entries()                                              # -> list[dict]
```

`Order` has `order_id`, `status` (`"reserved"`, `"shipped"` or `"cancelled"`), `lines`
(a list of `Line`), `total` and `refunded_total`. `Line` has `line_no`, `sku`, `qty`,
`unit_price`, `subtotal`, `tax`, `total`, `refunded_qty` and `refunded_amount`.
Exceptions live in `inventory.errors` and all derive from `InventoryError`.

## Stock

R1. Warehouse priority is the order in which warehouses were added with `add_warehouse`; adding a code twice raises `ValueError`. An unknown warehouse code passed to `receive`, `on_hand`, `reserved` or `available` raises `UnknownWarehouse`.
R2. `available(sku, wh)` is `on_hand - reserved` for that warehouse, and `total_available(sku)` is the sum of `available` over all warehouses.
R3. At all times, for every SKU and warehouse, `0 <= reserved <= on_hand`.

## Money

R4. Every money value (unit prices given to `catalog.add`, subtotals, taxes, totals and refund amounts) is a `Decimal` rounded to cents with `ROUND_HALF_UP` (never a float, never banker's rounding).
R5. For each line: `subtotal = round(unit_price * qty)`, `tax = round(subtotal * tax_rate)`, `total = subtotal + tax`. The order total is the sum of its line totals.

## Placing orders

R6. `place_order` requires at least one line and a positive `int` quantity on every line, where a `bool` does not count as an `int` (`ValueError` otherwise); an unknown SKU raises `UnknownSku`; an order id that is already in use raises `InvalidState`. Lines are numbered from 1 in the given order.
R7. Each line is allocated separately, in line order, against the stock still available after the allocations of the earlier lines of the same order. The same SKU may appear on several lines of one order.
R8. A line of quantity Q is allocated from the smallest number of warehouses whose combined available stock covers Q; among such sets, the one whose priority positions, sorted ascending, are lexicographically smallest wins. Within the chosen set, warehouses are used in priority order and each gives all of its available stock, except the last, which gives the remainder. A warehouse with no available stock is never used. `allocations(order_id)` lists allocations in line order, then in this order.
R9. Placement is all-or-nothing: if any line cannot be allocated, `InsufficientStock` is raised (and likewise for the errors in R6), and no reservation, order, audit entry or remembered request is left behind.
R10. A placed order has status `"reserved"` and each of its allocations raises `reserved` for that SKU and warehouse by the allocated quantity.

## Shipping and cancelling

R11. `ship_order` on a reserved order lowers both `on_hand` and `reserved` by each allocation and sets the status to `"shipped"`. Shipping an order that is not reserved raises `InvalidState`. `get`, ship, cancel and refund raise `InvalidState` for an unknown order id.
R12. `cancel_order` on a reserved order releases each allocation exactly once and sets the status to `"cancelled"`. Cancelling an order that is already cancelled or shipped raises `InvalidState` and changes nothing.

## Refunds

R13. Only shipped orders can be refunded (`InvalidState` otherwise). An unknown line number, a quantity that is not a positive `int`, or a quantity that would take the line's refunded quantity above its `qty` raises `RefundError`.
R14. Refunded units go back into `on_hand` of the warehouses the line shipped from: walk the line's allocations in reverse allocation order, putting into each warehouse at most the units shipped from it for that line minus the units already put back there by earlier refunds of the same line.
R15. The refund amount is `round(line.total * qty / line.qty)`, except that a refund which brings the line's refunded quantity up to its full `qty` returns `line.total` minus the amounts already refunded for that line, so the refunds of a line always add up to exactly its total.
R16. A refund increases the line's `refunded_qty` and `refunded_amount`; the order's `refunded_total` is the sum of its lines' `refunded_amount`. The order status stays `"shipped"`.

## Idempotency

R17. Every mutating call (`place_order`, `ship_order`, `cancel_order`, `refund`) takes a `request_id`; one id space is shared by all four. Repeating a request id with the same operation and the same arguments returns the result of the first call (the same `Order` object, or the same refund amount) and has no other effect: no stock change, no audit entry and no error, even if the order has changed state since.
R18. Reusing a request id with a different operation or different arguments raises `IdempotencyConflict` and changes nothing.
R19. A call that raised an error is not remembered: retrying the same request id later runs the operation afresh.

## Audit log

R20. `audit.entries()` returns the entries in the order they were recorded. Each entry is a dict with `seq` (1, 2, 3, ... without gaps), `event`, and the fields listed below, and nothing else.
R21. `place_order` records one `reserve` entry per allocation (fields `order`, `line`, `sku`, `warehouse`, `qty`) in the order of R8, then one `order_placed` entry (`order`, `total`).
R22. `ship_order` records one `ship` entry per allocation, in the same order and with the same fields as `reserve`, then `order_shipped` (`order`). `cancel_order` does the same with `release` entries followed by `order_cancelled` (`order`).
R23. `refund` records one `restock` entry per warehouse that received units (`order`, `line`, `sku`, `warehouse`, `qty`), in the order of R14, then one `refund` entry (`order`, `line`, `qty`, `amount`).
R24. A call that raises, or that is answered from an earlier request (R17), records nothing.
