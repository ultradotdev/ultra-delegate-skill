# Event-sourced shopping cart

Carts are event streams in an in-memory `EventStore` (`src/store.ts`). A cart's state is
never stored directly: it is what you get by replaying the stream through `applyEvent`
(`src/reducer.ts`). Old streams begin with events in the legacy schema version 1, which
`upcast` (`src/upcast.ts`) converts to the current schema version 2. `CartService`
(`src/cart.ts`) checks commands and appends events, snapshots (`src/snapshots.ts`) speed
up loading, and `src/projections.ts` computes totals and inventory holds.

Event payloads, schema version 2:

```
ItemAdded      { type, sku, quantity, unitPriceCents }
ItemRemoved    { type, sku, quantity }
CouponApplied  { type, code, percentOff }
CartCheckedOut { type }
```

Schema version 1 differs only in two payloads: `ItemAdded { type, sku, qty, price }` with
`price` in dollars (`19.99`), and `CouponApplied { type, code, discount }` with `discount`
as a fraction (`0.15` is 15%).

A stored event is `{ streamId, version, schemaVersion, data }`. A cart state is
`{ cartId, version, status: 'open' | 'checked_out', lines: [{ sku, quantity, unitPriceCents }], coupon: { code, percentOff } | null }`.

## Event store

R1. A stream's version is the number of events in it (0 for an empty or unknown stream). `append(streamId, events, expectedVersion?)` stores the events with versions current+1, current+2, ... and `schemaVersion` 2, and returns the stored events.
R2. If `expectedVersion` is a number other than the stream's current version, `append` throws `ConcurrencyError` with properties `streamId`, `expected` and `actual` and the message `concurrency conflict on <streamId>: expected version <expected>, actual <actual>`, and stores nothing. An undefined `expectedVersion` skips the check.
R3. `importLegacy(streamId, payloads)` appends schema-version-1 payloads without a concurrency check. `read(streamId, afterVersion = 0)` returns the stream's events with a version greater than `afterVersion`, in order, and `readAll()` returns the events of all streams in append order. Both return events exactly as stored: schema-version-1 events come back unconverted.

## Upcasting

R4. `upcast(event)` converts a schema-version-1 event to version 2: ItemAdded gets `quantity = qty` and `unitPriceCents = Math.round(price * 100)`, CouponApplied gets `percentOff = Math.round(discount * 100)`, and the other types keep their payload. The result keeps `streamId` and `version` and has `schemaVersion` 2. A version-2 event is returned unchanged. `upcast` never modifies its argument.

## Reducer

R5. `emptyCart(cartId)` is `{ cartId, version: 0, status: 'open', lines: [], coupon: null }`. `applyEvent(state, event)` takes a schema-version-2 event and returns the new state, whose `version` is the event's version.
R6. ItemAdded for a SKU already in the cart adds its quantity to that line and sets the line's unit price to the event's; for a new SKU it appends a line at the end.
R7. ItemRemoved lowers the line's quantity, and a line whose quantity drops to 0 or below is removed (adding the SKU again later appends a new line at the end). ItemRemoved for a SKU that is not in the cart changes only `version`.
R8. CouponApplied sets `coupon`, replacing any earlier one; CartCheckedOut sets `status` to `'checked_out'`.
R9. `applyEvent` is pure: it never modifies its input state or any object or array reachable from it.

## Totals

R10. `cartTotals(state)` returns `{ subtotalCents, discountCents, totalCents, itemCount }`: the subtotal is the sum of quantity × unitPriceCents; the discount is subtotal × percentOff / 100 rounded half up to a whole cent (0 without a coupon); the total is subtotal − discount; itemCount is the sum of the quantities.

## Commands

`new CartService(store, snapshots, { snapshotEvery = 3 })` offers
`addItem(cartId, sku, quantity, unitPriceCents, expectedVersion?)`,
`addItems(cartId, [{ sku, quantity, unitPriceCents }, ...], expectedVersion?)`,
`removeItem(cartId, sku, quantity, expectedVersion?)`,
`applyCoupon(cartId, code, percentOff, expectedVersion?)`, `checkout(cartId, expectedVersion?)`
and `load(cartId)`. Every command returns the cart's new state.

R11. A command loads the current state, checks it, and appends all of its events with a single `append`; a command that throws appends nothing. The checks run in this order: concurrency (R14), closed cart (R13), then the rules of R12.
R12. Each of these violations throws `ValidationError`: a sku that is not a non-empty string; a quantity that is not a positive integer; a unitPriceCents that is not a non-negative integer; `addItems` with no items (it appends one ItemAdded per item, in order); `removeItem` for a SKU not in the cart or for more than the line's quantity; `applyCoupon` with an empty code or a percentOff that is not an integer from 1 to 100; `checkout` of a cart with no lines.
R13. Every command on a checked-out cart throws `CartClosedError`.
R14. When the caller passes `expectedVersion` and it differs from the stream's current version, the command throws `ConcurrencyError` (as in R2, with `actual` the current version) before any other check. When the caller omits it, the command passes the version it loaded to `append` as `expectedVersion`.
R15. Commands behave the same on streams that begin with schema-version-1 events as on the equivalent version-2 streams.

## Snapshots

R16. When a command takes the stream from version a to version b, the service saves a snapshot of the new state if floor(b / snapshotEvery) > floor(a / snapshotEvery). `takeSnapshot(store, snapshots, cartId)` saves and returns the current state. `snapshots.latest(cartId)` returns the snapshot with the highest version and `snapshots.all(cartId)` returns all of them in the order they were saved.
R17. A saved snapshot never changes: it stays deep-equal to the replay of the first `snapshot.version` events of its stream, whatever happens afterwards.
R18. `loadCart(store, snapshots, cartId)` and `CartService.load` start from the latest snapshot and apply the later events. The result deep-equals a full replay of the upcast stream from `emptyCart`, whatever snapshots exist and whatever schema versions the events have, including schema-version-1 events after the snapshot.

## Inventory holds

R19. `InventoryHolds` consumes stored events from any number of carts. `held(sku)` is the total quantity of the SKU in carts that are still open; `committed(sku)` is the total quantity of the SKU that carts contained when they were checked out. Both are 0 for unknown SKUs.
R20. `apply(event)` ignores an event whose version is not greater than the last version it applied for that stream, so delivering events twice changes nothing.
R21. `apply` accepts events of either schema version, and `rebuildHolds(store)` applies `store.readAll()` in order; a stream recorded with schema-version-1 events produces the same holds as the equivalent version-2 events.
