import type { CartEvent, LegacyEvent, StoredEvent } from './events.ts';

/** Convert a stored event to schema version 2. Version-2 events are returned as they are. */
export function upcast(event: StoredEvent): StoredEvent {
  if (event.schemaVersion === 2) return event;
  const legacy = event.data as LegacyEvent;
  let data: CartEvent;
  switch (legacy.type) {
    case 'ItemAdded':
      data = { type: 'ItemAdded', sku: legacy.sku, quantity: legacy.qty, unitPriceCents: Math.round(legacy.price * 100) };
      break;
    case 'CouponApplied':
      data = { type: 'CouponApplied', code: legacy.code, percentOff: Math.round(legacy.discount * 100) };
      break;
    default:
      data = legacy;
  }
  return { streamId: event.streamId, version: event.version, schemaVersion: 2, data };
}

export function upcastAll(events: StoredEvent[]): StoredEvent[] {
  return events.map(upcast);
}
