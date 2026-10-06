import { test } from 'node:test';
import assert from 'node:assert/strict';
import { applyBatch } from '../solution.ts';

test('put replaces and appends', () => {
  assert.deepEqual(
    applyBatch([{ id: 'a', count: 1 }], [{ type: 'put', id: 'a', count: 2 }, { type: 'put', id: 'b', count: 3 }]),
    [{ id: 'a', count: 2 }, { id: 'b', count: 3 }],
  );
});

test('remove deletes', () => {
  assert.deepEqual(applyBatch([{ id: 'a', count: 1 }, { id: 'b', count: 2 }], [{ type: 'remove', id: 'a' }]), [{ id: 'b', count: 2 }]);
});

test('state is not mutated', () => {
  const state = [{ id: 'a', count: 1 }];
  applyBatch(state, [{ type: 'put', id: 'a', count: 5 }, { type: 'put', id: 'c', count: 1 }]);
  assert.deepEqual(state, [{ id: 'a', count: 1 }]);
});
