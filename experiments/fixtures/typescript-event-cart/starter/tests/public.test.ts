import { test } from 'node:test';
import assert from 'node:assert/strict';
import { CartClosedError, CartService, ValidationError } from '../src/cart.ts';
import { cartTotals } from '../src/projections.ts';
import { SnapshotStore } from '../src/snapshots.ts';
import { ConcurrencyError, EventStore } from '../src/store.ts';

function service() {
  const store = new EventStore();
  return { store, carts: new CartService(store, new SnapshotStore()) };
}

test('store assigns versions and enforces expectedVersion', () => {
  const store = new EventStore();
  const stored = store.append('c1', [{ type: 'ItemAdded', sku: 'A', quantity: 1, unitPriceCents: 100 }], 0);
  assert.deepEqual(stored.map((e) => [e.version, e.schemaVersion]), [[1, 2]]);
  assert.equal(store.version('c1'), 1);
  assert.throws(() => store.append('c1', [{ type: 'CartCheckedOut' }], 0), (error: unknown) => {
    assert.ok(error instanceof ConcurrencyError);
    assert.equal(error.message, 'concurrency conflict on c1: expected version 0, actual 1');
    return true;
  });
  assert.equal(store.version('c1'), 1);
});

test('adding the same sku twice adds up the quantity', () => {
  const { carts } = service();
  carts.addItem('c1', 'A', 1, 250);
  carts.addItem('c1', 'B', 1, 999);
  const state = carts.addItem('c1', 'A', 2, 300);
  assert.deepEqual(state.lines, [
    { sku: 'A', quantity: 3, unitPriceCents: 300 },
    { sku: 'B', quantity: 1, unitPriceCents: 999 },
  ]);
  assert.equal(state.version, 3);
});

test('totals with a coupon', () => {
  const { carts } = service();
  carts.addItem('c1', 'A', 3, 1999);
  const state = carts.applyCoupon('c1', 'SAVE15', 15);
  assert.deepEqual(cartTotals(state), { subtotalCents: 5997, discountCents: 900, totalCents: 5097, itemCount: 3 });
});

test('validation and checkout', () => {
  const { store, carts } = service();
  assert.throws(() => carts.addItem('c1', 'A', 0, 100), ValidationError);
  assert.throws(() => carts.checkout('c1'), ValidationError);
  assert.equal(store.version('c1'), 0);
  carts.addItem('c1', 'A', 1, 100);
  assert.equal(carts.checkout('c1').status, 'checked_out');
  assert.throws(() => carts.addItem('c1', 'B', 1, 100), CartClosedError);
});
