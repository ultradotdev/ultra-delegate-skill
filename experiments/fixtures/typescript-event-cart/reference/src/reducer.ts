import type { CartEvent, StoredEvent } from './events.ts';

export type CartLine = { sku: string; quantity: number; unitPriceCents: number };
export type Coupon = { code: string; percentOff: number };
export type CartState = {
  cartId: string;
  version: number;
  status: 'open' | 'checked_out';
  lines: CartLine[];
  coupon: Coupon | null;
};

export function emptyCart(cartId: string): CartState {
  return { cartId, version: 0, status: 'open', lines: [], coupon: null };
}

export function applyEvent(state: CartState, event: StoredEvent): CartState {
  if (event.schemaVersion !== 2) {
    throw new Error(`cannot apply a schema version ${event.schemaVersion} event; upcast it first`);
  }
  const data = event.data as CartEvent;
  const version = event.version;
  switch (data.type) {
    case 'ItemAdded': {
      // Never touch the old line objects: snapshots may share them.
      const exists = state.lines.some((line) => line.sku === data.sku);
      const lines = exists
        ? state.lines.map((line) =>
            line.sku === data.sku
              ? { sku: line.sku, quantity: line.quantity + data.quantity, unitPriceCents: data.unitPriceCents }
              : line,
          )
        : [...state.lines, { sku: data.sku, quantity: data.quantity, unitPriceCents: data.unitPriceCents }];
      return { ...state, version, lines };
    }
    case 'ItemRemoved': {
      const lines = state.lines
        .map((line) => (line.sku === data.sku ? { ...line, quantity: line.quantity - data.quantity } : line))
        .filter((line) => line.quantity > 0);
      return { ...state, version, lines };
    }
    case 'CouponApplied':
      return { ...state, version, coupon: { code: data.code, percentOff: data.percentOff } };
    case 'CartCheckedOut':
      return { ...state, version, status: 'checked_out' };
  }
}

/** Apply schema-version-2 events in order, starting from `from`. */
export function replay(events: StoredEvent[], from: CartState): CartState {
  return events.reduce(applyEvent, from);
}
