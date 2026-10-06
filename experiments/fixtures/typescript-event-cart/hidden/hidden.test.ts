import { test } from 'node:test';
import assert from 'node:assert/strict';
import { CartClosedError, CartService, ValidationError } from './src/cart.ts';
import type { StoredEvent } from './src/events.ts';
import { cartTotals, InventoryHolds, rebuildHolds } from './src/projections.ts';
import { applyEvent, emptyCart, replay } from './src/reducer.ts';
import type { CartState } from './src/reducer.ts';
import { loadCart, SnapshotStore, takeSnapshot } from './src/snapshots.ts';
import { ConcurrencyError, EventStore } from './src/store.ts';
import { upcast, upcastAll } from './src/upcast.ts';

function setup(snapshotEvery = 3) {
  const store = new EventStore();
  const snapshots = new SnapshotStore();
  return { store, snapshots, carts: new CartService(store, snapshots, { snapshotEvery }) };
}

function fullReplay(store: EventStore, cartId: string): CartState {
  return replay(upcastAll(store.read(cartId)), emptyCart(cartId));
}

function ev(version: number, data: any, streamId = 'c1'): StoredEvent {
  return { streamId, version, schemaVersion: 2, data };
}

function deepFreeze<T>(value: T): T {
  if (value && typeof value === 'object') {
    for (const inner of Object.values(value)) deepFreeze(inner);
    Object.freeze(value);
  }
  return value;
}

function isConflict(streamId: string, expected: number, actual: number) {
  return (error: unknown) => {
    assert.ok(error instanceof ConcurrencyError, `expected ConcurrencyError, got ${error}`);
    assert.deepEqual([error.streamId, error.expected, error.actual], [streamId, expected, actual]);
    assert.equal(error.message, `concurrency conflict on ${streamId}: expected version ${expected}, actual ${actual}`);
    return true;
  };
}

const add = (sku: string, quantity: number, unitPriceCents: number) => ({ type: 'ItemAdded', sku, quantity, unitPriceCents }) as const;
const legacyAdd = (sku: string, qty: number, price: number) => ({ type: 'ItemAdded', sku, qty, price }) as const;

test('R1 append assigns consecutive versions and schema version 2', () => {
  const store = new EventStore();
  assert.equal(store.version('nope'), 0);
  const first = store.append('c1', [add('A', 1, 100), add('B', 2, 200)]);
  assert.deepEqual(first.map((e) => [e.streamId, e.version, e.schemaVersion, e.data.type]), [['c1', 1, 2, 'ItemAdded'], ['c1', 2, 2, 'ItemAdded']]);
  const second = store.append('c1', [{ type: 'CartCheckedOut' }], 2);
  assert.equal(second[0].version, 3);
  assert.equal(store.version('c1'), 3);
  assert.deepEqual(store.append('c2', [add('A', 1, 1)])[0].version, 1);
});

test('R2 append concurrency errors store nothing', () => {
  const store = new EventStore();
  store.append('c1', [add('A', 1, 100)]);
  assert.throws(() => store.append('c1', [add('B', 1, 100), add('C', 1, 100)], 0), isConflict('c1', 0, 1));
  assert.throws(() => store.append('c1', [add('B', 1, 100)], 2), isConflict('c1', 2, 1));
  assert.equal(store.version('c1'), 1);
  assert.equal(store.readAll().length, 1);
  store.append('c1', [add('B', 1, 100)]);
  assert.equal(store.version('c1'), 2);
});

test('R3 read, readAll and legacy imports return events as stored', () => {
  const store = new EventStore();
  store.importLegacy('old', [legacyAdd('A', 2, 1.5)]);
  store.append('new', [add('B', 1, 100)]);
  store.append('old', [add('C', 1, 100)], 1);
  const old = store.read('old');
  assert.deepEqual(old.map((e) => [e.version, e.schemaVersion]), [[1, 1], [2, 2]]);
  assert.deepEqual(old[0].data, { type: 'ItemAdded', sku: 'A', qty: 2, price: 1.5 });
  assert.deepEqual(store.read('old', 1).map((e) => e.version), [2]);
  assert.deepEqual(store.read('old', 2), []);
  assert.deepEqual(store.readAll().map((e) => [e.streamId, e.version]), [['old', 1], ['new', 1], ['old', 2]]);
});

test('R4 upcasting', () => {
  const legacy: StoredEvent[] = [
    { streamId: 's', version: 1, schemaVersion: 1, data: legacyAdd('A', 3, 19.99) },
    { streamId: 's', version: 2, schemaVersion: 1, data: legacyAdd('B', 1, 0.29) },
    { streamId: 's', version: 3, schemaVersion: 1, data: { type: 'CouponApplied', code: 'X', discount: 0.15 } },
    { streamId: 's', version: 4, schemaVersion: 1, data: { type: 'ItemRemoved', sku: 'A', quantity: 1 } },
  ];
  const before = structuredClone(legacy);
  assert.deepEqual(upcastAll(legacy), [
    { streamId: 's', version: 1, schemaVersion: 2, data: add('A', 3, 1999) },
    { streamId: 's', version: 2, schemaVersion: 2, data: add('B', 1, 29) },
    { streamId: 's', version: 3, schemaVersion: 2, data: { type: 'CouponApplied', code: 'X', percentOff: 15 } },
    { streamId: 's', version: 4, schemaVersion: 2, data: { type: 'ItemRemoved', sku: 'A', quantity: 1 } },
  ]);
  assert.deepEqual(legacy, before);
  const current = ev(5, add('C', 1, 5));
  assert.deepEqual(upcast(current), current);
});

test('R5 empty cart and versions', () => {
  assert.deepEqual(emptyCart('c9'), { cartId: 'c9', version: 0, status: 'open', lines: [], coupon: null });
  const state = applyEvent(emptyCart('c9'), ev(7, add('A', 1, 10), 'c9'));
  assert.equal(state.version, 7);
  assert.equal(state.cartId, 'c9');
});

test('R6 adding items', () => {
  const state = replay([ev(1, add('A', 1, 100)), ev(2, add('B', 2, 50)), ev(3, add('A', 4, 90)), ev(4, add('C', 1, 1))], emptyCart('c1'));
  assert.deepEqual(state.lines, [
    { sku: 'A', quantity: 5, unitPriceCents: 90 },
    { sku: 'B', quantity: 2, unitPriceCents: 50 },
    { sku: 'C', quantity: 1, unitPriceCents: 1 },
  ]);
});

test('R7 removing items', () => {
  let state = replay([ev(1, add('A', 3, 100)), ev(2, add('B', 1, 50)), ev(3, { type: 'ItemRemoved', sku: 'A', quantity: 1 })], emptyCart('c1'));
  assert.deepEqual(state.lines, [{ sku: 'A', quantity: 2, unitPriceCents: 100 }, { sku: 'B', quantity: 1, unitPriceCents: 50 }]);
  state = applyEvent(state, ev(4, { type: 'ItemRemoved', sku: 'A', quantity: 2 }));
  assert.deepEqual(state.lines, [{ sku: 'B', quantity: 1, unitPriceCents: 50 }]);
  state = applyEvent(state, ev(5, add('A', 1, 70)));
  assert.deepEqual(state.lines.map((l) => l.sku), ['B', 'A']);
  const before = structuredClone(state);
  state = applyEvent(state, ev(6, { type: 'ItemRemoved', sku: 'Z', quantity: 1 }));
  assert.deepEqual(state, { ...before, version: 6 });
});

test('R8 coupons and checkout', () => {
  const state = replay([
    ev(1, add('A', 1, 100)),
    ev(2, { type: 'CouponApplied', code: 'ONE', percentOff: 10 }),
    ev(3, { type: 'CouponApplied', code: 'TWO', percentOff: 20 }),
    ev(4, { type: 'CartCheckedOut' }),
  ], emptyCart('c1'));
  assert.deepEqual(state.coupon, { code: 'TWO', percentOff: 20 });
  assert.equal(state.status, 'checked_out');
});

test('R9 applyEvent never modifies its input', () => {
  const base = replay([ev(1, add('A', 2, 100)), ev(2, add('B', 1, 50)), ev(3, { type: 'CouponApplied', code: 'X', percentOff: 5 })], emptyCart('c1'));
  const events = [
    ev(4, add('A', 1, 120)),
    ev(4, add('C', 1, 10)),
    ev(4, { type: 'ItemRemoved', sku: 'A', quantity: 1 }),
    ev(4, { type: 'ItemRemoved', sku: 'B', quantity: 1 }),
    ev(4, { type: 'CouponApplied', code: 'Y', percentOff: 7 }),
    ev(4, { type: 'CartCheckedOut' }),
  ];
  for (const event of events) {
    const state = structuredClone(base);
    const copy = structuredClone(base);
    deepFreeze(state);
    assert.doesNotThrow(() => applyEvent(state, event), `applying ${event.data.type}`);
    assert.deepEqual(state, copy);
  }
});

test('R10 totals round half up', () => {
  const cart = (lines: [string, number, number][], percentOff?: number): CartState => ({
    cartId: 'c', version: 1, status: 'open',
    lines: lines.map(([sku, quantity, unitPriceCents]) => ({ sku, quantity, unitPriceCents })),
    coupon: percentOff ? { code: 'C', percentOff } : null,
  });
  assert.deepEqual(cartTotals(cart([['A', 1, 5]], 10)), { subtotalCents: 5, discountCents: 1, totalCents: 4, itemCount: 1 });
  assert.deepEqual(cartTotals(cart([['A', 1, 1999]], 15)), { subtotalCents: 1999, discountCents: 300, totalCents: 1699, itemCount: 1 });
  assert.deepEqual(cartTotals(cart([['A', 2, 125], ['B', 3, 1]], 10)), { subtotalCents: 253, discountCents: 25, totalCents: 228, itemCount: 5 });
  assert.deepEqual(cartTotals(cart([['A', 2, 125]])), { subtotalCents: 250, discountCents: 0, totalCents: 250, itemCount: 2 });
  assert.deepEqual(cartTotals(cart([['A', 1, 333]], 100)), { subtotalCents: 333, discountCents: 333, totalCents: 0, itemCount: 1 });
});

test('R11 one append per command, all or nothing, checks in order', () => {
  const { store, carts } = setup(100);
  const calls: number[] = [];
  const original = store.append.bind(store);
  store.append = (streamId, events, expectedVersion) => {
    calls.push(events.length);
    return original(streamId, events, expectedVersion);
  };
  const state = carts.addItems('c1', [{ sku: 'A', quantity: 1, unitPriceCents: 10 }, { sku: 'B', quantity: 2, unitPriceCents: 20 }, { sku: 'A', quantity: 1, unitPriceCents: 30 }]);
  assert.deepEqual(calls, [3]);
  assert.deepEqual(store.read('c1').map((e) => [e.version, e.data.type]), [[1, 'ItemAdded'], [2, 'ItemAdded'], [3, 'ItemAdded']]);
  assert.deepEqual(state.lines, [{ sku: 'A', quantity: 2, unitPriceCents: 30 }, { sku: 'B', quantity: 2, unitPriceCents: 20 }]);
  assert.throws(() => carts.addItems('c1', [{ sku: 'C', quantity: 1, unitPriceCents: 10 }, { sku: 'D', quantity: -1, unitPriceCents: 10 }]), ValidationError);
  assert.equal(store.version('c1'), 3);
  carts.checkout('c1');
  assert.throws(() => carts.addItem('c1', '', -1, -1), CartClosedError);
  assert.throws(() => carts.addItem('c1', '', -1, -1, 1), isConflict('c1', 1, 4));
});

test('R12 validation rules', () => {
  const { store, carts } = setup();
  const bad: [string, () => unknown][] = [
    ['empty sku', () => carts.addItem('c1', '', 1, 100)],
    ['fractional quantity', () => carts.addItem('c1', 'A', 1.5, 100)],
    ['zero quantity', () => carts.addItem('c1', 'A', 0, 100)],
    ['negative price', () => carts.addItem('c1', 'A', 1, -1)],
    ['fractional price', () => carts.addItem('c1', 'A', 1, 9.5)],
    ['no items', () => carts.addItems('c1', [])],
    ['remove missing sku', () => carts.removeItem('c1', 'Z', 1)],
    ['remove too many', () => carts.removeItem('c1', 'A', 3)],
    ['remove zero', () => carts.removeItem('c1', 'A', 0)],
    ['empty code', () => carts.applyCoupon('c1', '', 10)],
    ['percent zero', () => carts.applyCoupon('c1', 'X', 0)],
    ['percent over', () => carts.applyCoupon('c1', 'X', 101)],
    ['percent fraction', () => carts.applyCoupon('c1', 'X', 12.5)],
  ];
  carts.addItem('c1', 'A', 2, 100);
  for (const [label, call] of bad) assert.throws(call, ValidationError, label);
  assert.equal(store.version('c1'), 1);
  assert.equal(carts.applyCoupon('c1', 'ALL', 100).coupon?.percentOff, 100);
  assert.deepEqual(carts.removeItem('c1', 'A', 2).lines, []);
  assert.throws(() => carts.checkout('c1'), ValidationError);
  assert.equal(carts.addItem('c1', 'F', 1, 0).lines[0].unitPriceCents, 0);
});

test('R13 checked-out carts are closed', () => {
  const { store, carts } = setup();
  carts.addItem('c1', 'A', 2, 100);
  carts.checkout('c1');
  const attempts = [
    () => carts.addItem('c1', 'B', 1, 1),
    () => carts.addItems('c1', [{ sku: 'B', quantity: 1, unitPriceCents: 1 }]),
    () => carts.removeItem('c1', 'A', 1),
    () => carts.applyCoupon('c1', 'X', 10),
    () => carts.checkout('c1'),
  ];
  for (const attempt of attempts) assert.throws(attempt, CartClosedError);
  assert.equal(store.version('c1'), 2);
});

test('R14 expectedVersion is honoured by commands', () => {
  const { store, carts } = setup();
  carts.addItem('c1', 'A', 2, 100, 0);
  carts.addItem('c1', 'B', 1, 100, 1);
  assert.throws(() => carts.addItem('c1', 'C', 1, 100, 1), isConflict('c1', 1, 2));
  assert.throws(() => carts.removeItem('c1', 'A', 1, 0), isConflict('c1', 0, 2));
  assert.throws(() => carts.applyCoupon('c1', 'X', 10, 5), isConflict('c1', 5, 2));
  assert.throws(() => carts.checkout('c1', 1), isConflict('c1', 1, 2));
  assert.throws(() => carts.removeItem('c1', 'Z', 99, 1), isConflict('c1', 1, 2));
  assert.equal(store.version('c1'), 2);
  assert.equal(carts.checkout('c1', 2).version, 3);

  const seen: (number | undefined)[] = [];
  const original = store.append.bind(store);
  store.append = (streamId, events, expectedVersion) => {
    seen.push(expectedVersion);
    return original(streamId, events, expectedVersion);
  };
  carts.addItem('c2', 'A', 1, 100);
  carts.addItem('c2', 'A', 1, 100);
  assert.deepEqual(seen, [0, 1]);
});

test('R15 commands on legacy streams', () => {
  const legacy = setup();
  legacy.store.importLegacy('c1', [legacyAdd('A', 2, 1.5), { type: 'CouponApplied', code: 'TEN', discount: 0.1 }]);
  const modern = setup();
  modern.store.append('c1', [add('A', 2, 150), { type: 'CouponApplied', code: 'TEN', percentOff: 10 }]);
  for (const { carts } of [legacy, modern]) {
    carts.addItem('c1', 'A', 1, 150, 2);
    carts.addItem('c1', 'B', 1, 999);
    carts.removeItem('c1', 'A', 1);
  }
  const state = legacy.carts.load('c1');
  assert.deepEqual(state, modern.carts.load('c1'));
  assert.deepEqual(state.lines, [{ sku: 'A', quantity: 2, unitPriceCents: 150 }, { sku: 'B', quantity: 1, unitPriceCents: 999 }]);
  assert.deepEqual(cartTotals(state), { subtotalCents: 1299, discountCents: 130, totalCents: 1169, itemCount: 3 });
});

test('R16 snapshot policy', () => {
  const { snapshots, carts, store } = setup(2);
  carts.addItem('c1', 'A', 1, 100);
  carts.addItem('c1', 'B', 1, 100);
  carts.addItems('c1', [{ sku: 'C', quantity: 1, unitPriceCents: 1 }, { sku: 'D', quantity: 1, unitPriceCents: 1 }, { sku: 'E', quantity: 1, unitPriceCents: 1 }]);
  carts.removeItem('c1', 'E', 1);
  assert.deepEqual(snapshots.all('c1').map((s) => s.version), [2, 5, 6]);
  assert.equal(snapshots.latest('c1')?.version, 6);
  store.append('c1', [add('F', 1, 1)], 6);
  const taken = takeSnapshot(store, snapshots, 'c1');
  assert.equal(taken.version, 7);
  assert.deepEqual(snapshots.latest('c1'), taken);
  assert.equal(snapshots.latest('none'), undefined);
  const defaults = setup();
  defaults.carts.addItem('c1', 'A', 1, 1);
  defaults.carts.addItem('c1', 'A', 1, 1);
  assert.equal(defaults.snapshots.all('c1').length, 0);
  defaults.carts.addItem('c1', 'A', 1, 1);
  assert.deepEqual(defaults.snapshots.all('c1').map((s) => s.version), [3]);
});

test('R17 snapshots never change', () => {
  const { store, snapshots, carts } = setup(2);
  for (let i = 0; i < 4; i++) carts.addItem('c1', 'A', 1, 100 + i);
  carts.removeItem('c1', 'A', 1);
  carts.addItem('c1', 'B', 2, 5);
  carts.removeItem('c1', 'A', 3);
  carts.addItem('c1', 'A', 1, 7);
  const all = snapshots.all('c1');
  assert.deepEqual(all.map((s) => s.version), [2, 4, 6, 8]);
  for (const snapshot of all) {
    assert.deepEqual(snapshot, replay(upcastAll(store.read('c1')).slice(0, snapshot.version), emptyCart('c1')), `snapshot at ${snapshot.version}`);
  }
});

test('R18 loading from a snapshot equals a full replay', () => {
  const { store, snapshots, carts } = setup(2);
  carts.addItem('c1', 'A', 1, 100);
  carts.addItem('c1', 'A', 2, 100);
  carts.addItem('c1', 'A', 4, 100);
  carts.removeItem('c1', 'A', 1);
  carts.addItem('c1', 'B', 1, 1);
  assert.deepEqual(loadCart(store, snapshots, 'c1'), fullReplay(store, 'c1'));
  assert.equal(carts.load('c1').lines[0].quantity, 6);

  const legacy = setup();
  legacy.store.importLegacy('c2', [legacyAdd('A', 1, 2.5), legacyAdd('B', 1, 0.5)]);
  takeSnapshot(legacy.store, legacy.snapshots, 'c2');
  legacy.store.importLegacy('c2', [legacyAdd('A', 2, 2.75), { type: 'CouponApplied', code: 'Q', discount: 0.25 }]);
  const loaded = loadCart(legacy.store, legacy.snapshots, 'c2');
  assert.deepEqual(loaded, fullReplay(legacy.store, 'c2'));
  assert.deepEqual(loaded.lines, [{ sku: 'A', quantity: 3, unitPriceCents: 275 }, { sku: 'B', quantity: 1, unitPriceCents: 50 }]);
  assert.deepEqual(loaded.coupon, { code: 'Q', percentOff: 25 });
  assert.equal(legacy.carts.addItem('c2', 'C', 1, 1, 4).version, 5);
});

test('R19 holds across carts', () => {
  const { store, carts } = setup();
  carts.addItem('c1', 'A', 2, 1);
  carts.addItem('c1', 'B', 1, 1);
  carts.addItem('c2', 'A', 3, 1);
  carts.removeItem('c1', 'A', 1);
  carts.checkout('c2');
  const holds = rebuildHolds(store);
  assert.deepEqual([holds.held('A'), holds.committed('A'), holds.held('B'), holds.committed('B')], [1, 3, 1, 0]);
  assert.deepEqual([holds.held('Z'), holds.committed('Z')], [0, 0]);
});

test('R20 duplicate deliveries are ignored', () => {
  const holds = new InventoryHolds();
  const events = [ev(1, add('A', 2, 1)), ev(2, add('A', 3, 1)), ev(1, add('A', 5, 1), 'c2')];
  for (const event of events) holds.apply(event);
  for (const event of events) holds.apply(event);
  holds.apply(ev(1, add('A', 100, 1)));
  assert.equal(holds.held('A'), 10);
  holds.apply(ev(3, { type: 'CartCheckedOut' }));
  holds.apply(ev(2, { type: 'CartCheckedOut' }));
  assert.deepEqual([holds.held('A'), holds.committed('A')], [5, 5]);
});

test('R21 holds from legacy events', () => {
  const store = new EventStore();
  store.importLegacy('old', [legacyAdd('A', 2, 1.5), legacyAdd('B', 4, 0.5), { type: 'ItemRemoved', sku: 'B', quantity: 1 }]);
  store.append('old', [{ type: 'CartCheckedOut' }], 3);
  store.importLegacy('older', [legacyAdd('A', 1, 1.5)]);
  const holds = rebuildHolds(store);
  assert.deepEqual([holds.held('A'), holds.committed('A'), holds.committed('B'), holds.held('B')], [1, 2, 3, 0]);
  const direct = new InventoryHolds();
  direct.apply({ streamId: 'x', version: 1, schemaVersion: 1, data: legacyAdd('C', 7, 1) });
  assert.equal(direct.held('C'), 7);
});
