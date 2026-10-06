import { test } from 'node:test';
import assert from 'node:assert/strict';
import { applyBatch as f } from './solution.ts';

const frozenState = () => Object.freeze([Object.freeze({ id: 'a', count: 1 }), Object.freeze({ id: 'b', count: 2 })]);

// Each invalid operation follows a valid put; the call must throw and leave state untouched (R14).
const rejectsOp = (op: unknown) => {
  const s = [{ id: 'a', count: 1 }];
  assert.throws(() => f(s, [{ type: 'put', id: 'a', count: 7 }, op]), TypeError);
  assert.deepEqual(s, [{ id: 'a', count: 1 }]);
};

test('R1 operations must be an array', () => {
  for (const bad of [null, {}, 'x', 4, undefined]) assert.throws(() => f([], bad), TypeError);
});

test('R2 operations must be plain objects', () => {
  for (const op of [null, [], new Date(), 'put', 3]) rejectsOp(op);
});

test('R3 exact keys per type', () => {
  for (const op of [{}, { type: 'remove', id: 'a', count: 1 }, { type: 'put', id: 'a', count: 1, extra: 1 },
    { type: 'put', id: 'a' }, { type: 'add', id: 'a', count: 1 }, { id: 'a', count: 1 }]) rejectsOp(op);
});

test('R4 id is a nonempty string', () => {
  for (const op of [{ type: 'put', id: '', count: 2 }, { type: 'remove', id: '' }, { type: 'put', id: 5, count: 2 }]) rejectsOp(op);
});

test('R5 put count', () => {
  for (const count of [true, '2', NaN, 2 ** 53, -1, 1.5]) rejectsOp({ type: 'put', id: 'a', count });
  assert.deepEqual(f([], [{ type: 'put', id: 'z', count: 0 }]), [{ id: 'z', count: 0 }]);
});

test('R6 sequential application', () => {
  // R7 R9 R10 R11 R12: mixed frozen batch
  const ops = Object.freeze([
    Object.freeze({ type: 'put', id: 'a', count: 3 }),
    Object.freeze({ type: 'remove', id: 'a' }),
    Object.freeze({ type: 'put', id: 'a', count: 4 }),
    Object.freeze({ type: 'put', id: '__proto__', count: 0 }),
    Object.freeze({ type: 'remove', id: 'missing' }),
  ]);
  assert.deepEqual(f(frozenState(), ops), [{ id: 'b', count: 2 }, { id: 'a', count: 4 }, { id: '__proto__', count: 0 }]);
  assert.deepEqual(f([], [{ type: 'put', id: 'x', count: 1 }, { type: 'put', id: 'x', count: 2 }]), [{ id: 'x', count: 2 }]);
});

test('R7 put replaces in place', () => {
  assert.deepEqual(
    f([{ id: 'a', count: 1 }, { id: 'b', count: 2 }, { id: 'c', count: 3 }], [{ type: 'put', id: 'b', count: 9 }]),
    [{ id: 'a', count: 1 }, { id: 'b', count: 9 }, { id: 'c', count: 3 }],
  );
});

test('R8 put appends new ids', () => {
  assert.deepEqual(f([{ id: 'a', count: 1 }], [{ type: 'put', id: 'b', count: 2 }]), [{ id: 'a', count: 1 }, { id: 'b', count: 2 }]);
});

test('R9 remove', () => {
  assert.deepEqual(f([{ id: 'a', count: 1 }, { id: 'b', count: 2 }], [{ type: 'remove', id: 'a' }]), [{ id: 'b', count: 2 }]);
  assert.deepEqual(f([{ id: 'a', count: 1 }], [{ type: 'remove', id: 'missing' }]), [{ id: 'a', count: 1 }]);
});

test('R10 removed then put appends at end', () => {
  assert.deepEqual(
    f([{ id: 'a', count: 1 }, { id: 'b', count: 2 }], [{ type: 'remove', id: 'a' }, { type: 'put', id: 'a', count: 5 }]),
    [{ id: 'b', count: 2 }, { id: 'a', count: 5 }],
  );
});

test('R11 literal ids', () => {
  assert.deepEqual(
    f([{ id: 'constructor', count: 1 }], [{ type: 'put', id: 'constructor', count: Number.MAX_SAFE_INTEGER }]),
    [{ id: 'constructor', count: Number.MAX_SAFE_INTEGER }],
  );
  assert.deepEqual(f([], [{ type: 'put', id: '__proto__', count: 1 }, { type: 'put', id: 'toString', count: 2 }]),
    [{ id: '__proto__', count: 1 }, { id: 'toString', count: 2 }]);
  assert.deepEqual(f([{ id: 'hasOwnProperty', count: 1 }], [{ type: 'remove', id: 'hasOwnProperty' }]), []);
});

test('R12 no mutation, new array', () => {
  const state = frozenState();
  const ops = Object.freeze([Object.freeze({ type: 'put', id: 'b', count: 5 }), Object.freeze({ type: 'put', id: 'c', count: 6 })]);
  const result = f(state, ops);
  assert.deepEqual(result, [{ id: 'a', count: 1 }, { id: 'b', count: 5 }, { id: 'c', count: 6 }]);
  assert.notEqual(result, state);
  assert.deepEqual(state, [{ id: 'a', count: 1 }, { id: 'b', count: 2 }]);
});

test('R13 independent item objects', () => {
  const state = frozenState();
  const result = f(state, []);
  assert.notEqual(result, state);
  assert.notEqual(result[0], state[0]);
  result[0].count = 9;
  assert.equal(state[0].count, 1);
});

test('R14 no partial application', () => {
  for (const op of [null, [], {}, new Date(), { type: 'put', id: 'a', count: true }, { type: 'put', id: 'a', count: '2' },
    { type: 'put', id: 'a', count: NaN }, { type: 'put', id: 'a', count: 2 ** 53 }, { type: 'put', id: '', count: 2 },
    { type: 'put', id: 'a', count: -1 }, { type: 'remove', id: 'a', count: 1 }, { type: 'put', id: 'a', count: 1, extra: 1 }]) {
    rejectsOp(op);
  }
});
