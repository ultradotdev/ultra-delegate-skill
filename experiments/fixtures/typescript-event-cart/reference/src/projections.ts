import type { CartEvent, StoredEvent } from './events.ts';
import type { CartState } from './reducer.ts';
import type { EventStore } from './store.ts';
import { upcast } from './upcast.ts';

export type Totals = { subtotalCents: number; discountCents: number; totalCents: number; itemCount: number };

export function cartTotals(state: CartState): Totals {
  const subtotalCents = state.lines.reduce((sum, line) => sum + line.quantity * line.unitPriceCents, 0);
  const percentOff = state.coupon?.percentOff ?? 0;
  const discountCents = Math.round((subtotalCents * percentOff) / 100);
  const itemCount = state.lines.reduce((sum, line) => sum + line.quantity, 0);
  return { subtotalCents, discountCents, totalCents: subtotalCents - discountCents, itemCount };
}

function bump(map: Map<string, number>, key: string, delta: number): void {
  map.set(key, (map.get(key) ?? 0) + delta);
}

/** Stock held by open carts and committed by checked-out carts, across all carts. */
export class InventoryHolds {
  #carts = new Map<string, Map<string, number>>();
  #held = new Map<string, number>();
  #committed = new Map<string, number>();
  #applied = new Map<string, number>();

  apply(stored: StoredEvent): void {
    const event = upcast(stored);
    if (event.version <= (this.#applied.get(event.streamId) ?? 0)) return;
    this.#applied.set(event.streamId, event.version);
    const data = event.data as CartEvent;
    const cart = this.#carts.get(event.streamId) ?? new Map<string, number>();
    this.#carts.set(event.streamId, cart);
    switch (data.type) {
      case 'ItemAdded':
        bump(cart, data.sku, data.quantity);
        bump(this.#held, data.sku, data.quantity);
        break;
      case 'ItemRemoved': {
        const removed = Math.min(data.quantity, cart.get(data.sku) ?? 0);
        bump(cart, data.sku, -removed);
        bump(this.#held, data.sku, -removed);
        break;
      }
      case 'CartCheckedOut':
        for (const [sku, quantity] of cart) {
          bump(this.#held, sku, -quantity);
          bump(this.#committed, sku, quantity);
        }
        cart.clear();
        break;
      case 'CouponApplied':
        break;
    }
  }

  held(sku: string): number {
    return this.#held.get(sku) ?? 0;
  }

  committed(sku: string): number {
    return this.#committed.get(sku) ?? 0;
  }
}

export function rebuildHolds(store: EventStore): InventoryHolds {
  const holds = new InventoryHolds();
  for (const event of store.readAll()) holds.apply(event);
  return holds;
}
