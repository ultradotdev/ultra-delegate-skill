import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Latest } from './task.ts';

function pending<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: Error) => void;
  const promise = new Promise<T>((a, b) => { resolve = a; reject = b; });
  return { promise, resolve, reject };
}

test('R1 public API and synchronous loading flag', async () => {
  const x = new Latest<string>();
  assert.equal(x.value, undefined);
  assert.equal(x.loading, false);
  const a = pending<string>();
  let calls = 0;
  const p = x.load(() => { calls++; return a.promise; });
  assert.ok(p instanceof Promise);
  assert.equal(x.loading, true);
  assert.equal(calls, 1);
  a.resolve('done');
  assert.equal(await p, undefined);
  assert.equal(calls, 1);
});

test('R2 current load sets value and clears loading', async () => {
  const x = new Latest<number>();
  await x.load(() => Promise.resolve(4));
  assert.equal(x.value, 4);
  assert.equal(x.loading, false);
  await x.load(() => Promise.resolve(5));
  assert.equal(x.value, 5);
  assert.equal(x.loading, false);
});

test('R3 old result cannot overwrite new', async () => {
  const x = new Latest<number>();
  const a = pending<number>(), b = pending<number>();
  const one = x.load(() => a.promise), two = x.load(() => b.promise);
  b.resolve(2); await two;
  a.resolve(1); await one;
  assert.equal(x.value, 2);
  assert.equal(x.loading, false);
});

test('R3 superseded result arriving first is ignored', async () => {
  const x = new Latest<number>();
  const a = pending<number>(), b = pending<number>();
  const one = x.load(() => a.promise), two = x.load(() => b.promise);
  a.resolve(1); await one;
  assert.equal(x.value, undefined);
  b.resolve(2); await two;
  assert.equal(x.value, 2);
});

test('R4 old finish cannot clear loading', async () => {
  const x = new Latest<number>();
  const a = pending<number>(), b = pending<number>();
  const one = x.load(() => a.promise), two = x.load(() => b.promise);
  a.resolve(1); await one;
  assert.equal(x.loading, true);
  b.resolve(2); await two;
  assert.equal(x.loading, false);
});

test('R4 old rejection cannot clear loading', async () => {
  // R5: the superseded load's promise rejects with its own error
  const x = new Latest<number>();
  const a = pending<number>(), b = pending<number>();
  const one = x.load(() => a.promise), two = x.load(() => b.promise);
  const oldError = new Error('old');
  a.reject(oldError);
  await assert.rejects(one, (e) => e === oldError);
  assert.equal(x.loading, true);
  b.resolve(3); await two;
  assert.equal(x.value, 3);
  assert.equal(x.loading, false);
});

test('R5 new rejection propagates and clears loading', async () => {
  const x = new Latest<number>();
  await assert.rejects(x.load(() => Promise.reject(new Error('failed'))), /failed/);
  assert.equal(x.loading, false);
});

test('R5 rejection keeps the previous value', async () => {
  const x = new Latest<number>();
  await x.load(() => Promise.resolve(7));
  const error = new Error('boom');
  await assert.rejects(x.load(() => Promise.reject(error)), (e) => e === error);
  assert.equal(x.value, 7);
  assert.equal(x.loading, false);
});
