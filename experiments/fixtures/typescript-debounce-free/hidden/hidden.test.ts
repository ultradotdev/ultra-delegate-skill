import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildQuery } from './query.ts';

test('R1 joining and empty result', () => {
  assert.equal(buildQuery({}), '');
  assert.equal(buildQuery({ a: null, b: [] }), '');
  assert.equal(buildQuery({ a: '1', b: '2', c: '3' }), 'a=1&b=2&c=3');
  assert.equal(buildQuery({ only: 'x' }), 'only=x');
});

test('R2 key order by code unit', () => {
  assert.equal(buildQuery({ b: 1, a: 1, B: 1, _: 1 }), 'B=1&_=1&a=1&b=1');
  assert.equal(buildQuery({ '9': 'x', '10': 'y', '2': 'z' }), '10=y&2=z&9=x');
  const inherited = Object.create({ hidden: 'no' });
  inherited.shown = 'yes';
  assert.equal(buildQuery(inherited), 'shown=yes');
});

test('R3 encodeURIComponent for keys and values', () => {
  assert.equal(buildQuery({ 'a b': 'c&d=e', 'ключ': 'é' }), 'a%20b=c%26d%3De&%D0%BA%D0%BB%D1%8E%D1%87=%C3%A9');
  assert.equal(buildQuery({ path: '/x?y#z', plus: '1+1' }), 'path=%2Fx%3Fy%23z&plus=1%2B1');
  assert.equal(buildQuery({ list: ['a&b', 'é'] }), 'list=a%26b&list=%C3%A9');
});

test('R4 scalar conversion including falsy values', () => {
  assert.equal(buildQuery({ n: 0, f: false, t: true, x: -1.5 }), 'f=false&n=0&t=true&x=-1.5');
  assert.equal(buildQuery({ big: 1e21, small: 0.1 }), 'big=1e%2B21&small=0.1');
});

test('R5 null and undefined omitted', () => {
  assert.equal(buildQuery({ a: undefined, b: null, c: 'x', d: 0 }), 'c=x&d=0');
});

test('R6 arrays repeat the key', () => {
  assert.equal(buildQuery({ tag: ['a b', 1, false], e: [] }), 'tag=a%20b&tag=1&tag=false');
  assert.equal(buildQuery({ z: ['2', '1'], a: 'x' }), 'a=x&z=2&z=1');
  assert.equal(buildQuery({ zero: [0, ''] }), 'zero=0&zero=');
});

test('R7 non-finite numbers throw RangeError', () => {
  for (const params of [{ a: NaN }, { a: Infinity }, { a: -Infinity }, { a: [1, Infinity] }, { ok: 'x', a: [NaN] }]) {
    assert.throws(() => buildQuery(params), RangeError);
  }
});

test('R8 empty string value', () => {
  assert.equal(buildQuery({ a: '' }), 'a=');
  assert.equal(buildQuery({ a: [''] }), 'a=');
  assert.equal(buildQuery({ b: '', a: 'x' }), 'a=x&b=');
});
