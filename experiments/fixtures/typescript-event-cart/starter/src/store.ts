import type { CartEvent, LegacyEvent, StoredEvent } from './events.ts';

export class ConcurrencyError extends Error {
  streamId: string;
  expected: number;
  actual: number;

  constructor(streamId: string, expected: number, actual: number) {
    super(`concurrency conflict on ${streamId}: expected version ${expected}, actual ${actual}`);
    this.name = 'ConcurrencyError';
    this.streamId = streamId;
    this.expected = expected;
    this.actual = actual;
  }
}

function freeze<T>(value: T): T {
  if (value && typeof value === 'object') {
    for (const inner of Object.values(value)) freeze(inner);
    Object.freeze(value);
  }
  return value;
}

/** In-memory event store. Stored events are frozen and returned exactly as stored. */
export class EventStore {
  #streams = new Map<string, StoredEvent[]>();
  #log: StoredEvent[] = [];

  version(streamId: string): number {
    return this.#streams.get(streamId)?.length ?? 0;
  }

  append(streamId: string, events: CartEvent[], expectedVersion?: number): StoredEvent[] {
    const current = this.version(streamId);
    if (expectedVersion !== undefined && expectedVersion !== current) {
      throw new ConcurrencyError(streamId, expectedVersion, current);
    }
    return this.#write(streamId, events.map((data) => ({ schemaVersion: 2 as const, data })));
  }

  /** Append legacy (schema version 1) payloads, as a data migration would. */
  importLegacy(streamId: string, events: LegacyEvent[]): StoredEvent[] {
    return this.#write(streamId, events.map((data) => ({ schemaVersion: 1 as const, data })));
  }

  read(streamId: string, afterVersion = 0): StoredEvent[] {
    return (this.#streams.get(streamId) ?? []).filter((event) => event.version > afterVersion);
  }

  readAll(): StoredEvent[] {
    return [...this.#log];
  }

  #write(streamId: string, items: { schemaVersion: 1 | 2; data: CartEvent | LegacyEvent }[]): StoredEvent[] {
    const stream = this.#streams.get(streamId) ?? [];
    const stored = items.map((item, index) =>
      freeze({ streamId, version: stream.length + index + 1, schemaVersion: item.schemaVersion, data: structuredClone(item.data) }),
    );
    stream.push(...stored);
    this.#streams.set(streamId, stream);
    this.#log.push(...stored);
    return stored;
  }
}
