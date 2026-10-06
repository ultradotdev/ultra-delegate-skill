import type { CartEvent } from './events.ts';
import { replay } from './reducer.ts';
import type { CartState } from './reducer.ts';
import { loadCart } from './snapshots.ts';
import type { SnapshotStore } from './snapshots.ts';
import type { EventStore } from './store.ts';

export class ValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ValidationError';
  }
}

export class CartClosedError extends Error {
  constructor(cartId: string) {
    super(`cart ${cartId} is checked out`);
    this.name = 'CartClosedError';
  }
}

export type NewItem = { sku: string; quantity: number; unitPriceCents: number };

function check(condition: boolean, message: string): void {
  if (!condition) throw new ValidationError(message);
}

function checkItem(item: NewItem): void {
  check(typeof item.sku === 'string' && item.sku.length > 0, 'sku must be a non-empty string');
  check(Number.isInteger(item.quantity) && item.quantity > 0, 'quantity must be a positive integer');
  check(Number.isInteger(item.unitPriceCents) && item.unitPriceCents >= 0, 'unitPriceCents must be a non-negative integer');
}

export class CartService {
  store: EventStore;
  snapshots: SnapshotStore;
  snapshotEvery: number;

  constructor(store: EventStore, snapshots: SnapshotStore, options: { snapshotEvery?: number } = {}) {
    this.store = store;
    this.snapshots = snapshots;
    this.snapshotEvery = options.snapshotEvery ?? 3;
  }

  load(cartId: string): CartState {
    return loadCart(this.store, this.snapshots, cartId);
  }

  addItem(cartId: string, sku: string, quantity: number, unitPriceCents: number, expectedVersion?: number): CartState {
    return this.addItems(cartId, [{ sku, quantity, unitPriceCents }], expectedVersion);
  }

  addItems(cartId: string, items: NewItem[], expectedVersion?: number): CartState {
    return this.#execute(cartId, expectedVersion, () => {
      check(Array.isArray(items) && items.length > 0, 'addItems needs at least one item');
      items.forEach(checkItem);
      return items.map((item) => ({ type: 'ItemAdded', sku: item.sku, quantity: item.quantity, unitPriceCents: item.unitPriceCents }));
    });
  }

  removeItem(cartId: string, sku: string, quantity: number, expectedVersion?: number): CartState {
    return this.#execute(cartId, expectedVersion, (state) => {
      check(Number.isInteger(quantity) && quantity > 0, 'quantity must be a positive integer');
      const line = state.lines.find((candidate) => candidate.sku === sku);
      check(line !== undefined, `${sku} is not in the cart`);
      check(quantity <= line!.quantity, `cannot remove ${quantity} of ${line!.quantity} ${sku}`);
      return [{ type: 'ItemRemoved', sku, quantity }];
    });
  }

  applyCoupon(cartId: string, code: string, percentOff: number, expectedVersion?: number): CartState {
    return this.#execute(cartId, expectedVersion, () => {
      check(typeof code === 'string' && code.length > 0, 'coupon code must be a non-empty string');
      check(Number.isInteger(percentOff) && percentOff >= 1 && percentOff <= 100, 'percentOff must be an integer from 1 to 100');
      return [{ type: 'CouponApplied', code, percentOff }];
    });
  }

  checkout(cartId: string, expectedVersion?: number): CartState {
    return this.#execute(cartId, expectedVersion, (state) => {
      check(state.lines.length > 0, 'cannot check out an empty cart');
      return [{ type: 'CartCheckedOut' }];
    });
  }

  #execute(cartId: string, expectedVersion: number | undefined, decide: (state: CartState) => CartEvent[]): CartState {
    const state = this.load(cartId);
    if (state.status === 'checked_out') throw new CartClosedError(cartId);
    const events = decide(state);
    const stored = this.store.append(cartId, events, state.version);
    const next = replay(stored, state);
    if (Math.floor(next.version / this.snapshotEvery) > Math.floor(state.version / this.snapshotEvery)) {
      this.snapshots.save(next);
    }
    return next;
  }
}
