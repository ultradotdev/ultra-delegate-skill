// Event payloads. Schema version 2 is current; version 1 is the legacy format
// still found at the start of old streams (see upcast.ts).

export type ItemAdded = { type: 'ItemAdded'; sku: string; quantity: number; unitPriceCents: number };
export type ItemRemoved = { type: 'ItemRemoved'; sku: string; quantity: number };
export type CouponApplied = { type: 'CouponApplied'; code: string; percentOff: number };
export type CartCheckedOut = { type: 'CartCheckedOut' };
export type CartEvent = ItemAdded | ItemRemoved | CouponApplied | CartCheckedOut;

/** Legacy ItemAdded: `price` is in dollars, e.g. 19.99. */
export type ItemAddedV1 = { type: 'ItemAdded'; sku: string; qty: number; price: number };
/** Legacy CouponApplied: `discount` is a fraction, e.g. 0.15 for 15%. */
export type CouponAppliedV1 = { type: 'CouponApplied'; code: string; discount: number };
export type LegacyEvent = ItemAddedV1 | ItemRemoved | CouponAppliedV1 | CartCheckedOut;

export type StoredEvent = {
  streamId: string;
  /** 1-based position of the event within its stream. */
  version: number;
  schemaVersion: 1 | 2;
  data: CartEvent | LegacyEvent;
};
