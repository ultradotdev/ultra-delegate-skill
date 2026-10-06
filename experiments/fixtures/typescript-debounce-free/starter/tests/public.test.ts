import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildQuery } from '../query.ts';

test('sorted and encoded', () => {
  assert.equal(buildQuery({ q: 'x y', page: 2 }), 'page=2&q=x%20y');
});

test('null and undefined are omitted', () => {
  assert.equal(buildQuery({ a: null, b: undefined, c: 'x' }), 'c=x');
});
