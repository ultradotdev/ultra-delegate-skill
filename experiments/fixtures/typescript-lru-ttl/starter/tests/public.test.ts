import { test } from "node:test";
import assert from "node:assert/strict";
import { LruCache } from "../lru.ts";

function clock(start = 0) {
  let t = start;
  return { now: () => t, advance: (ms: number) => { t += ms; } };
}

test("stores and returns values", () => {
  const c = clock();
  const cache = new LruCache<string, number>({ maxEntries: 3, now: c.now });
  cache.set("a", 1).set("b", 2);
  assert.equal(cache.get("a"), 1);
  assert.equal(cache.get("b"), 2);
  assert.equal(cache.get("zzz"), undefined);
});

test("evicts the least recently used entry, and get counts as a use", () => {
  const c = clock();
  const evicted: Array<[string, number, string]> = [];
  const cache = new LruCache<string, number>({
    maxEntries: 2,
    now: c.now,
    onEvict: (k, v, reason) => evicted.push([k, v, reason]),
  });
  cache.set("a", 1);
  cache.set("b", 2);
  cache.get("a");
  cache.set("c", 3);
  assert.deepEqual(evicted, [["b", 2, "capacity"]]);
  assert.equal(cache.get("b"), undefined);
  assert.equal(cache.get("a"), 1);
  assert.equal(cache.get("c"), 3);
});

test("entries expire after their ttl", () => {
  const c = clock(1000);
  const cache = new LruCache<string, string>({ maxEntries: 5, now: c.now, defaultTtl: 100 });
  cache.set("a", "x");
  cache.set("b", "y", 500);
  c.advance(150);
  assert.equal(cache.get("a"), undefined);
  assert.equal(cache.get("b"), "y");
});
