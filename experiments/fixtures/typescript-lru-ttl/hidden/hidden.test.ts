import { test } from "node:test";
import assert from "node:assert/strict";
import { LruCache } from "./lru.ts";
import type { EvictionReason } from "./lru.ts";

type Log = Array<[string, number, EvictionReason]>;

function setup(maxEntries: number, defaultTtl?: number) {
  let t = 0;
  const log: Log = [];
  const cache = new LruCache<string, number>({
    maxEntries,
    defaultTtl,
    now: () => t,
    onEvict: (k, v, reason) => log.push([k, v, reason]),
  });
  return { cache, log, at: (ms: number) => { t = ms; } };
}

test("R1 rejects invalid maxEntries, defaultTtl and ttl", () => {
  const now = () => 0;
  for (const maxEntries of [0, -1, 1.5, NaN, Infinity]) {
    assert.throws(() => new LruCache({ maxEntries, now }), RangeError, `maxEntries ${maxEntries}`);
  }
  for (const defaultTtl of [0, -5, NaN, Infinity]) {
    assert.throws(() => new LruCache({ maxEntries: 1, now, defaultTtl }), RangeError, `defaultTtl ${defaultTtl}`);
  }
  assert.doesNotThrow(() => new LruCache({ maxEntries: 1, now, defaultTtl: undefined }));
  const { cache, log } = setup(2);
  cache.set("a", 1);
  for (const ttl of [0, -1, NaN, Infinity]) {
    assert.throws(() => cache.set("a", 2, ttl), RangeError, `ttl ${ttl}`);
    assert.throws(() => cache.set("b", 2, ttl), RangeError, `ttl ${ttl}`);
  }
  assert.equal(cache.peek("a"), 1);
  assert.equal(cache.has("b"), false);
  assert.equal(cache.size, 1);
  assert.deepEqual(log, []);
});

test("R2 set returns the cache and uses ttl, then defaultTtl, then no expiry", () => {
  const { cache, at } = setup(5, 100);
  assert.equal(cache.set("a", 1), cache);
  cache.set("b", 2, 300);
  at(250);
  assert.equal(cache.peek("a"), undefined);
  assert.equal(cache.peek("b"), 2);
  const forever = setup(5);
  forever.cache.set("x", 9);
  forever.at(1e12);
  assert.equal(forever.cache.get("x"), 9);
});

test("R3 an entry is gone at exactly its expiry time", () => {
  const one = setup(5);
  one.cache.set("a", 1, 100);
  one.at(99);
  assert.equal(one.cache.get("a"), 1);
  one.at(100);
  assert.equal(one.cache.get("a"), undefined);
  const two = setup(5, 50);
  two.at(10);
  two.cache.set("a", 1);
  two.at(60);
  assert.equal(two.cache.size, 0);
  assert.equal(two.cache.has("a"), false);
});

test("R4 get makes an entry MRU but does not extend its expiry", () => {
  const { cache, log, at } = setup(5, 100);
  cache.set("a", 1);
  at(60);
  assert.equal(cache.get("a"), 1);
  at(99);
  assert.equal(cache.get("a"), 1);
  at(100);
  assert.equal(cache.get("a"), undefined);
  assert.deepEqual(log, [["a", 1, "expired"]]);

  const lru = setup(3);
  lru.cache.set("a", 1).set("b", 2).set("c", 3);
  lru.cache.get("a");
  lru.cache.get("b");
  lru.cache.set("d", 4);
  assert.deepEqual(lru.log, [["c", 3, "capacity"]]);
  assert.equal(lru.cache.get("missing"), undefined);
});

test("R5 has and peek do not change recency", () => {
  const { cache, log } = setup(2);
  cache.set("a", 1).set("b", 2);
  assert.equal(cache.has("a"), true);
  assert.equal(cache.peek("a"), 1);
  assert.equal(cache.has("zzz"), false);
  assert.equal(cache.peek("zzz"), undefined);
  cache.set("c", 3);
  assert.deepEqual(log, [["a", 1, "capacity"]]);
});

test("R6 lookups that find an expired entry evict it as expired, once", () => {
  const { cache, log, at } = setup(10);
  cache.set("g", 1, 10).set("h", 2, 10).set("p", 3, 10).set("d", 4, 10).set("s", 5, 10).set("other", 6, 10);
  at(10);
  assert.equal(cache.get("g"), undefined);
  assert.equal(cache.get("g"), undefined);
  assert.equal(cache.has("h"), false);
  assert.equal(cache.peek("p"), undefined);
  assert.equal(cache.delete("d"), false);
  cache.set("s", 50);
  assert.deepEqual(log, [["g", 1, "expired"], ["h", 2, "expired"], ["p", 3, "expired"], ["d", 4, "expired"], ["s", 5, "expired"]]);
  assert.equal(cache.get("s"), 50);
  assert.deepEqual(cache.keys(), ["s"]);
});

test("R7 replacing a live key resets its expiry and recency without eviction", () => {
  const { cache, log, at } = setup(2, 100);
  cache.set("a", 1).set("b", 2);
  at(80);
  cache.set("a", 10);
  at(150);
  assert.equal(cache.peek("a"), 10);
  assert.equal(cache.peek("b"), undefined);
  at(180);
  assert.equal(cache.peek("a"), undefined);
  assert.deepEqual(log, [["b", 2, "expired"], ["a", 10, "expired"]]);

  const r = setup(2);
  r.cache.set("a", 1).set("b", 2);
  r.cache.set("a", 3, 50);
  r.cache.set("c", 4);
  assert.deepEqual(r.log, [["b", 2, "capacity"]]);
  r.at(49);
  assert.equal(r.cache.get("a"), 3);
  r.at(50);
  assert.equal(r.cache.get("a"), undefined);
});

test("R8 a full cache drops expired entries before evicting for capacity", () => {
  const one = setup(2);
  one.cache.set("a", 1).set("b", 2, 10);
  one.at(10);
  one.cache.set("c", 3);
  assert.deepEqual(one.log, [["b", 2, "expired"]]);
  assert.deepEqual(one.cache.keys(), ["c", "a"]);

  const two = setup(3);
  two.cache.set("a", 1, 5).set("b", 2).set("c", 3, 5);
  two.at(5);
  two.cache.set("d", 4);
  assert.deepEqual(two.log, [["a", 1, "expired"], ["c", 3, "expired"]]);
  assert.equal(two.cache.size, 2);

  const three = setup(2);
  three.cache.set("a", 1).set("b", 2, 100);
  three.at(50);
  three.cache.set("c", 3);
  assert.deepEqual(three.log, [["a", 1, "capacity"]]);
  for (let i = 0; i < 10; i++) three.cache.set(`k${i}`, i);
  assert.equal(three.cache.size, 2);
  assert.deepEqual(three.cache.keys(), ["k9", "k8"]);
});

test("R9 delete reports deleted for live entries and nothing for missing ones", () => {
  const { cache, log, at } = setup(5);
  cache.set("a", 1).set("b", 2).set("c", 3, 10);
  assert.equal(cache.delete("a"), true);
  assert.equal(cache.delete("a"), false);
  assert.equal(cache.delete("nope"), false);
  assert.equal(cache.has("a"), false);
  assert.equal(cache.size, 2);
  at(10);
  assert.equal(cache.delete("c"), false);
  assert.deepEqual(log, [["a", 1, "deleted"], ["c", 3, "expired"]]);
});

test("R10 size counts live entries only and has no side effects", () => {
  const { cache, log, at } = setup(5);
  cache.set("a", 1, 10).set("b", 2, 20).set("c", 3);
  assert.equal(cache.size, 3);
  at(10);
  assert.equal(cache.size, 2);
  at(20);
  assert.equal(cache.size, 1);
  assert.deepEqual(log, []);
  assert.equal(cache.prune(), 2);
});

test("R11 keys lists live keys from MRU to LRU without side effects", () => {
  const { cache, log, at } = setup(3);
  cache.set("a", 1).set("b", 2, 10).set("c", 3);
  cache.get("a");
  assert.deepEqual(cache.keys(), ["a", "c", "b"]);
  at(10);
  assert.deepEqual(cache.keys(), ["a", "c"]);
  assert.deepEqual(log, []);
  const plain = setup(2);
  plain.cache.set("x", 1).set("y", 2);
  plain.cache.keys();
  plain.cache.set("z", 3);
  assert.deepEqual(plain.log, [["x", 1, "capacity"]]);
});

test("R12 prune removes expired entries in LRU-to-MRU order and counts them", () => {
  const { cache, log, at } = setup(5);
  cache.set("a", 1, 5).set("b", 2).set("c", 3, 3).set("d", 4, 5);
  cache.get("c");
  at(5);
  assert.equal(cache.prune(), 3);
  assert.deepEqual(log, [["a", 1, "expired"], ["d", 4, "expired"], ["c", 3, "expired"]]);
  assert.equal(cache.prune(), 0);
  assert.deepEqual(cache.keys(), ["b"]);
});

test("R13 clear reports every entry in LRU-to-MRU order with the right reason", () => {
  const { cache, log, at } = setup(5);
  cache.set("a", 1, 5).set("b", 2).set("c", 3, 5);
  cache.get("a");
  at(5);
  cache.clear();
  assert.deepEqual(log, [["b", 2, "deleted"], ["c", 3, "expired"], ["a", 1, "expired"]]);
  assert.equal(cache.size, 0);
  assert.deepEqual(cache.keys(), []);
  cache.clear();
  assert.equal(log.length, 3);
});

test("R14 onEvict runs after the entry is removed", () => {
  let t = 0;
  const seen: Array<[string, EvictionReason, number, string[]]> = [];
  const cache: LruCache<string, number> = new LruCache<string, number>({
    maxEntries: 2,
    now: () => t,
    onEvict: (k, _v, reason) => seen.push([k, reason, cache.size, cache.keys()]),
  });
  cache.set("a", 1).set("b", 2);
  cache.set("c", 3);
  cache.delete("b");
  cache.set("d", 4, 10);
  t = 10;
  cache.get("d");
  cache.set("e", 5);
  cache.clear();
  assert.deepEqual(seen, [
    ["a", "capacity", 1, ["b"]],
    ["b", "deleted", 1, ["c"]],
    ["d", "expired", 1, ["c"]],
    ["c", "deleted", 1, ["e"]],
    ["e", "deleted", 0, []],
  ]);
});
