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
  ttl: number | undefined;
}

export class LruCache<K, V> {
  #entries = new Map<K, Entry<V>>();
  #maxEntries: number;
  #now: () => number;
  #defaultTtl: number | undefined;
  #onEvict: ((key: K, value: V, reason: EvictionReason) => void) | undefined;

  constructor(options: LruOptions<K, V>) {
    this.#maxEntries = options.maxEntries;
    this.#now = options.now;
    this.#defaultTtl = options.defaultTtl;
    this.#onEvict = options.onEvict;
  }

  #expired(entry: Entry<V>): boolean {
    return this.#now() > entry.expiresAt;
  }

  #lookup(key: K): Entry<V> | undefined {
    const entry = this.#entries.get(key);
    if (entry === undefined) return undefined;
    if (this.#expired(entry)) {
      this.#entries.delete(key);
      return undefined;
    }
    return entry;
  }

  set(key: K, value: V, ttl?: number): this {
    const lifetime = ttl ?? this.#defaultTtl;
    const expiresAt = lifetime === undefined ? Infinity : this.#now() + lifetime;
    const old = this.#entries.get(key);
    if (old !== undefined) {
      this.#onEvict?.(key, old.value, "deleted");
      this.#entries.delete(key);
    } else if (this.#entries.size >= this.#maxEntries) {
      const oldest = this.#entries.keys().next().value as K;
      this.#onEvict?.(oldest, this.#entries.get(oldest)!.value, "capacity");
      this.#entries.delete(oldest);
    }
    this.#entries.set(key, { value, expiresAt, ttl: lifetime });
    return this;
  }

  get(key: K): V | undefined {
    const entry = this.#lookup(key);
    if (entry === undefined) return undefined;
    // sliding expiry: every read keeps the entry alive a bit longer
    if (entry.ttl !== undefined) entry.expiresAt = this.#now() + entry.ttl;
    return entry.value;
  }

  has(key: K): boolean {
    return this.get(key) !== undefined;
  }

  peek(key: K): V | undefined {
    return this.#lookup(key)?.value;
  }

  delete(key: K): boolean {
    return this.#entries.delete(key);
  }

  prune(): number {
    let removed = 0;
    for (const [key, entry] of this.#entries) {
      if (this.#expired(entry)) {
        this.#onEvict?.(key, entry.value, "expired");
        this.#entries.delete(key);
        removed++;
      }
    }
    return removed;
  }

  clear(): void {
    this.#entries.clear();
  }

  keys(): K[] {
    return [...this.#entries.keys()];
  }

  get size(): number {
    return this.#entries.size;
  }
}
