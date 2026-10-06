# lru.ts: LRU cache with per-entry TTL

`LruCache<K, V>` in `lru.ts` is a least-recently-used cache with optional
per-entry expiry. Time comes only from the injected `now()` function (milliseconds);
the cache never uses real timers or `Date`. Node 24 with native TypeScript type
stripping, no npm packages.

```ts
type EvictionReason = "capacity" | "expired" | "deleted";

new LruCache<K, V>({
  maxEntries: number,
  now: () => number,
  defaultTtl?: number,
  onEvict?: (key: K, value: V, reason: EvictionReason) => void,
});
```

Methods: `set(key, value, ttl?)`, `get(key)`, `has(key)`, `peek(key)`,
`delete(key)`, `prune()`, `clear()`, `keys()`, and the `size` getter.

An entry is **live** while it has not expired, and **expired** from the moment
R3 says so. "Most recently used" is abbreviated MRU and "least recently used" LRU.

## Requirements

R1. The constructor throws `RangeError` unless `maxEntries` is a positive integer, and unless `defaultTtl` is either `undefined` or a positive finite number. `set` throws `RangeError` for a `ttl` argument that is not `undefined` or a positive finite number, and then leaves the cache unchanged.

R2. `set(key, value, ttl?)` stores the entry as the MRU entry and returns the cache. The entry expires at `now() + ttl`, or `now() + defaultTtl` when `ttl` is omitted; with neither, it never expires.

R3. An entry is expired when `now() >= expiresAt`: at exactly its expiry time it is already gone.

R4. `get(key)` returns the value of a live entry and makes it the MRU entry, but does not extend its expiry. It returns `undefined` for a missing key.

R5. `has(key)` and `peek(key)` report presence and return the value of a live entry without changing recency.

R6. When `get`, `has`, `peek`, `set` or `delete` finds that the requested key's entry has expired, it removes that entry and calls `onEvict(key, value, "expired")`, then behaves as if the key were missing. Other entries are not touched.

R7. `set` on a live existing key replaces the value, recomputes the expiry from the current `now()` with the new `ttl` argument (or `defaultTtl`), and makes it MRU. Replacing is not an eviction: `onEvict` is not called and nothing else is evicted.

R8. When `set` inserts a new key while the cache holds `maxEntries` entries (expired ones included), it first removes every expired entry, calling `onEvict(..., "expired")` for each in LRU-to-MRU order. Only if the cache is still full does it evict the LRU live entry with reason `"capacity"`. The cache never holds more than `maxEntries` entries.

R9. `delete(key)` on a live entry removes it, calls `onEvict(key, value, "deleted")` and returns `true`. On a missing key it returns `false` without calling `onEvict`. On an expired entry it follows R6 (reason `"expired"`) and returns `false`.

R10. `size` is the number of live entries. Reading it never calls `onEvict` and never changes recency.

R11. `keys()` returns the keys of the live entries ordered from MRU to LRU, without changing recency or calling `onEvict`.

R12. `prune()` removes every expired entry, calling `onEvict(..., "expired")` for each in LRU-to-MRU order, and returns how many it removed.

R13. `clear()` removes every entry, calling `onEvict` for each one in LRU-to-MRU order: reason `"expired"` for expired entries and `"deleted"` for live ones.

R14. `onEvict` is called only after the entry has been removed: inside the callback, `size` and `keys()` already exclude it.
