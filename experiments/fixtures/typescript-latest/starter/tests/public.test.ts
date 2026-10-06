import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Latest } from '../task.ts';

function pending<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((a) => { resolve = a; });
  return { promise, resolve };
}

test('single load sets value', async () => {
  const x = new Latest<number>();
  await x.load(() => Promise.resolve(4));
  assert.equal(x.value, 4);
  assert.equal(x.loading, false);
});

test('an older load finishing late does not overwrite the newer value', async () => {
  const x = new Latest<number>();
  const a = pending<number>(), b = pending<number>();
  const one = x.load(() => a.promise), two = x.load(() => b.promise);
  b.resolve(2); await two;
  a.resolve(1); await one;
  assert.equal(x.value, 2);
});
