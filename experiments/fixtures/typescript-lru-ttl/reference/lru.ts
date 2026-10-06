export type EvictionReason = "capacity" | "expired" | "deleted";

export interface LruOptions<K, V> {
  maxEntries: number;
  now: () => number;
  defaultTtl?: number;
  onEvict?: (key: K, value: V, reason: EvictionReason) => void;
}

interface Entry<V> {
  value: V;
  expiresAt: number;
}

function checkTtl(ttl: number | undefined, name: string): void {
  if (ttl !== undefined && !(typeof ttl === "number" && Number.isFinite(ttl) && ttl > 0)) {
    throw new RangeError(`${name} must be a positive finite number`);
  }
}

export class LruCache<K, V> {
  // Map iteration order is insertion order: the first entry is the LRU one.
  #entries = new Map<K, Entry<V>>();
  #maxEntries: number;
  #now: () => number;
  #defaultTtl: number | undefined;
  #onEvict: ((key: K, value: V, reason: EvictionReason) => void) | undefined;

  constructor(options: LruOptions<K, V>) {
    if (!Number.isInteger(options.maxEntries) || options.maxEntries < 1) {
      throw new RangeError("maxEntries must be a positive integer");
    }
    checkTtl(options.defaultTtl, "defaultTtl");
    this.#maxEntries = options.maxEntries;
    this.#now = options.now;
    this.#defaultTtl = options.defaultTtl;
    this.#onEvict = options.onEvict;
  }

  #expired(entry: Entry<V>, now: number): boolean {
    return now >= entry.expiresAt;
  }

  #remove(key: K, entry: Entry<V>, reason: EvictionReason): void {
    this.#entries.delete(key);
    this.#onEvict?.(key, entry.value, reason);
  }

  /** The live entry for key, after evicting it if it has expired. */
  #live(key: K): Entry<V> | undefined {
    const entry = this.#entries.get(key);
    if (entry === undefined) return undefined;
    if (this.#expired(entry, this.#now())) {
      this.#remove(key, entry, "expired");
      return undefined;
    }
    return entry;
  }

  #removeExpired(): number {
    const now = this.#now();
    const expired = [...this.#entries].filter(([, entry]) => this.#expired(entry, now));
    for (const [key, entry] of expired) this.#remove(key, entry, "expired");
    return expired.length;
  }

  set(key: K, value: V, ttl?: number): this {
    checkTtl(ttl, "ttl");
    const existing = this.#live(key);
    if (existing !== undefined) {
      this.#entries.delete(key);
    } else if (this.#entries.size >= this.#maxEntries) {
      this.#removeExpired();
      while (this.#entries.size >= this.#maxEntries) {
        const [lruKey, lruEntry] = this.#entries.entries().next().value!;
        this.#remove(lruKey, lruEntry, "capacity");
      }
    }
    const lifetime = ttl ?? this.#defaultTtl;
    const expiresAt = lifetime === undefined ? Infinity : this.#now() + lifetime;
    this.#entries.set(key, { value, expiresAt });
    return this;
  }

  get(key: K): V | undefined {
    const entry = this.#live(key);
    if (entry === undefined) return undefined;
    this.#entries.delete(key);
    this.#entries.set(key, entry);
    return entry.value;
  }

  has(key: K): boolean {
    return this.#live(key) !== undefined;
  }

  peek(key: K): V | undefined {
    return this.#live(key)?.value;
  }

  delete(key: K): boolean {
    const entry = this.#live(key);
    if (entry === undefined) return false;
    this.#remove(key, entry, "deleted");
    return true;
  }

  prune(): number {
    return this.#removeExpired();
  }

  clear(): void {
    const now = this.#now();
    for (const [key, entry] of [...this.#entries]) {
      this.#remove(key, entry, this.#expired(entry, now) ? "expired" : "deleted");
    }
  }

  keys(): K[] {
    const now = this.#now();
    const live: K[] = [];
    for (const [key, entry] of this.#entries) {
      if (!this.#expired(entry, now)) live.push(key);
    }
    return live.reverse();
  }

  get size(): number {
    const now = this.#now();
    let count = 0;
    for (const entry of this.#entries.values()) {
      if (!this.#expired(entry, now)) count++;
    }
    return count;
  }
}
