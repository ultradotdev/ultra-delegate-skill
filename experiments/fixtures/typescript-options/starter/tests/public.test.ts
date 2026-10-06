import { test } from 'node:test';
import assert from 'node:assert/strict';
import { normalizeOptions } from '../solution.ts';

test('defaults', () => {
  assert.deepEqual(normalizeOptions({}), { limit: 20, offset: 0, label: '' });
});

test('explicit values', () => {
  assert.deepEqual(normalizeOptions({ limit: 5, offset: 10, label: 'x' }), { limit: 5, offset: 10, label: 'x' });
});

test('limit above 100 is rejected', () => {
  assert.throws(() => normalizeOptions({ limit: 101 }), TypeError);
});
