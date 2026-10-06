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
      const lines = [...state.lines];
      const existing = lines.find((line) => line.sku === data.sku);
      if (existing) {
        existing.quantity = data.quantity;
        existing.unitPriceCents = data.unitPriceCents;
      } else {
        lines.push({ sku: data.sku, quantity: data.quantity, unitPriceCents: data.unitPriceCents });
      }
      return { ...state, version, lines };
    }
    case 'ItemRemoved': {
      const lines = [...state.lines];
      const index = lines.findIndex((line) => line.sku === data.sku);
      if (index === -1) return { ...state, version };
      lines[index].quantity -= data.quantity;
      if (lines[index].quantity <= 0) lines.splice(index, 1);
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
