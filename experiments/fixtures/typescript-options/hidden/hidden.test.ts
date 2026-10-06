import { test } from 'node:test';
import assert from 'node:assert/strict';
import { normalizeOptions as f } from './solution.ts';

const rejects = (values: unknown[]) => {
  for (const value of values) assert.throws(() => f(value), TypeError);
};

test('R1 plain objects only', () => {
  rejects([null, [], 3, 'x', undefined, true, new Date(), Object.create({ limit: 2 }), new (class Opts {})()]);
  assert.deepEqual(f(Object.assign(Object.create(null), { limit: 7 })), { limit: 7, offset: 0, label: '' });
});

test('R2 unknown own keys', () => {
  rejects([{ unexpected: 1 }, JSON.parse('{"__proto__":{}}'), { constructor: 1 }, { limit: 1, extra: undefined }]);
});

test('R3 defaults', () => {
  assert.deepEqual(f({}), { limit: 20, offset: 0, label: '' });
  assert.deepEqual(f(Object.assign(Object.create(null), { limit: undefined })), { limit: 20, offset: 0, label: '' });
  assert.deepEqual(f({ limit: undefined, offset: undefined, label: undefined }), { limit: 20, offset: 0, label: '' });
});

test('R4 inherited values are ignored', () => {
  // R1: an object inheriting limit from another prototype is rejected outright
  rejects([Object.create({ limit: 2 })]);
  const proto = Object.prototype as Record<string, unknown>;
  let result: unknown;
  proto.limit = 5;
  proto.label = 'inherited';
  try {
    result = f({ offset: 3 });
  } finally {
    delete proto.limit;
    delete proto.label;
  }
  assert.deepEqual(result, { limit: 20, offset: 3, label: '' });
});

test('R5 limit range', () => {
  assert.deepEqual(f({ limit: 1, offset: 0, label: '雪' }), { limit: 1, offset: 0, label: '雪' });
  assert.equal(f({ limit: 100 }).limit, 100);
  rejects([{ limit: 0 }, { limit: NaN }, { limit: Infinity }, { limit: 1.5 }, { limit: 101 }, { limit: -1 }]);
});

test('R6 offset range', () => {
  assert.equal(f({ offset: Number.MAX_SAFE_INTEGER }).offset, Number.MAX_SAFE_INTEGER);
  rejects([{ offset: -1 }, { offset: 2 ** 53 }, { offset: 0.5 }, { offset: Infinity }]);
});

test('R7 label length in UTF-16 code units', () => {
  assert.equal(f({ label: 'a'.repeat(40) }).label, 'a'.repeat(40));
  assert.equal(f({ label: '😀'.repeat(20) }).label, '😀'.repeat(20));
  rejects([{ label: '😀'.repeat(21) }, { label: 'a'.repeat(41) }]);
});

test('R8 no coercion', () => {
  rejects([{ limit: '2' }, { offset: '0' }, { label: null }, { label: 5 }, { limit: true }, { offset: null }, { limit: null }]);
});

test('R9 fresh result, no mutation', () => {
  const x = Object.freeze({ limit: 100, offset: Number.MAX_SAFE_INTEGER, label: 'a'.repeat(40) });
  const result = f(x);
  assert.deepEqual(result, x);
  assert.notEqual(result, x);
  assert.deepEqual(Object.keys(f({ label: 'z' })).sort(), ['label', 'limit', 'offset']);
  const y = { limit: 3 };
  f(y);
  assert.deepEqual(y, { limit: 3 });
});
