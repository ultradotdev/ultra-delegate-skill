import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  compareVersions, DependencyCycleError, install, InvalidRangeError, InvalidVersionError, NoMatchingVersionError,
  PeerDependencyError, Registry, satisfies, VersionConflictError,
} from './src/index.ts';

type Manifest = { d?: Record<string, string>; p?: Record<string, string> };

function registry(packages: Record<string, Record<string, Manifest>>, reverse = false): Registry {
  const entries: [string, string, Manifest][] = [];
  for (const [name, versions] of Object.entries(packages)) {
    for (const [version, manifest] of Object.entries(versions)) entries.push([name, version, manifest]);
  }
  if (reverse) entries.reverse();
  const result = new Registry();
  for (const [name, version, { d, p }] of entries) result.publish(name, version, { dependencies: d, peerDependencies: p });
  return result;
}

function fails(call: () => unknown, type: Function, message: string): void {
  assert.throws(call, (error: unknown) => {
    assert.ok(error instanceof type, `expected ${type.name}, got ${error}`);
    assert.equal((error as Error).message, message);
    return true;
  });
}

function check(range: string, yes: string[], no: string[]): void {
  for (const version of yes) assert.equal(satisfies(version, range), true, `${version} should satisfy ${range}`);
  for (const version of no) assert.equal(satisfies(version, range), false, `${version} should not satisfy ${range}`);
}

test('R1 versions', () => {
  for (const bad of ['1.2', 'v1.2.3', '01.2.3', '1.02.3', '1.2.3-beta', '1.2.3.4', '', 'a.b.c']) {
    assert.throws(() => new Registry().publish('x', bad), InvalidVersionError, bad);
  }
  new Registry().publish('x', '0.0.0');
  assert.ok(compareVersions('1.10.0', '1.9.0') > 0);
  assert.ok(compareVersions('2.0.0', '10.0.0') < 0);
  assert.ok(compareVersions('1.2.10', '1.2.9') > 0);
  assert.equal(compareVersions('3.4.5', '3.4.5'), 0);
});

test('R2 alternatives, comparator sets and whitespace', () => {
  check('>=1.2.0 <1.4.0 || >=2.0.0 <2.1.0 || 5.0.0', ['1.2.0', '1.3.9', '2.0.5', '5.0.0'], ['1.4.0', '1.1.9', '2.1.0', '5.0.1']);
  check('  >= 1.2.0   <  1.4.0 ', ['1.2.0', '1.3.0'], ['1.4.0']);
  check('', ['0.0.0', '99.1.2'], []);
  check('   ', ['3.0.0'], []);
  check('^1.0.0 || ~0.1.0', ['1.9.0', '0.1.5'], ['0.2.0', '2.0.0']);
});

test('R3 partials and x-ranges', () => {
  for (const range of ['1', '1.x', '1.x.x', '1.X', '1.*', '=1']) check(range, ['1.0.0', '1.9.9'], ['0.9.9', '2.0.0']);
  for (const range of ['1.2', '1.2.x', '1.2.*']) check(range, ['1.2.0', '1.2.9'], ['1.1.9', '1.3.0']);
  for (const range of ['1.2.3', '=1.2.3', '= 1.2.3']) check(range, ['1.2.3'], ['1.2.4', '1.2.2']);
  for (const range of ['*', 'x', 'X', 'x.x.x']) check(range, ['0.0.0', '7.3.1'], []);
});

test('R4 caret ranges', () => {
  check('^1.2.3', ['1.2.3', '1.9.0'], ['1.2.2', '2.0.0']);
  check('^0.2.3', ['0.2.3', '0.2.9'], ['0.2.2', '0.3.0', '1.0.0']);
  check('^0.0.3', ['0.0.3'], ['0.0.2', '0.0.4', '0.1.0']);
  check('^1.2', ['1.2.0', '1.9.9'], ['1.1.9', '2.0.0']);
  check('^0.2', ['0.2.0', '0.2.7'], ['0.1.9', '0.3.0']);
  check('^0.0', ['0.0.0', '0.0.9'], ['0.1.0']);
  check('^0.0.x', ['0.0.5'], ['0.1.0']);
  check('^1', ['1.0.0', '1.5.0'], ['0.9.0', '2.0.0']);
  check('^0', ['0.0.0', '0.9.9'], ['1.0.0']);
  check('^0.x', ['0.5.0'], ['1.0.0']);
  check('^*', ['0.0.0', '4.0.0'], []);
});

test('R5 tilde ranges', () => {
  check('~1.2.3', ['1.2.3', '1.2.9'], ['1.2.2', '1.3.0']);
  check('~1.2', ['1.2.0', '1.2.9'], ['1.1.9', '1.3.0']);
  check('~1', ['1.0.0', '1.9.9'], ['0.9.9', '2.0.0']);
  check('~0.0.1', ['0.0.1', '0.0.9'], ['0.0.0', '0.1.0']);
  check('~*', ['0.0.0', '3.0.0'], []);
});

test('R6 comparison operators', () => {
  check('>=1.2', ['1.2.0', '3.0.0'], ['1.1.9']);
  check('<1.2', ['1.1.9'], ['1.2.0']);
  check('>1.2', ['1.3.0'], ['1.2.9']);
  check('<=1.2', ['1.2.9'], ['1.3.0']);
  check('>1', ['2.0.0'], ['1.9.9']);
  check('<=1', ['1.9.9'], ['2.0.0']);
  check('>1.2.3', ['1.2.4'], ['1.2.3']);
  check('<=1.2.3', ['1.2.3'], ['1.2.4']);
  check('<1.2.x', ['1.1.9'], ['1.2.0']);
  check('> 1.x', ['2.0.0'], ['1.9.9']);
});

test('R7 invalid ranges', () => {
  const bad = ['^', '>=', '>=*', '<x', '1.2.3.4', '01.2', '1.x.3', '1.2.3-beta', '1.0.0 - 2.0.0', 'abc', '1 ||', '|| 1',
    '>=1.0.0<2.0.0', '^^1', '>= >= 1.0.0', '1..2'];
  for (const range of bad) fails(() => satisfies('1.0.0', range), InvalidRangeError, `invalid range: "${range}"`);
  fails(() => install(new Registry(), { a: '1.x.3' }), InvalidRangeError, 'invalid range: "1.x.3"');
  fails(() => new Registry().publish('a', '1.0.0', { peerDependencies: { b: 'latest' } }), InvalidRangeError, 'invalid range: "latest"');
  fails(() => new Registry().publish('a', '1.0.0', { dependencies: { b: '>=*' } }), InvalidRangeError, 'invalid range: ">=*"');
});

test('R8 registry', () => {
  const reg = new Registry();
  for (const version of ['1.10.0', '1.2.0', '10.0.0', '1.9.0', '0.9.0', '2.0.0', '1.2.10', '1.2.9']) reg.publish('p', version);
  assert.deepEqual(reg.versions('p'), ['0.9.0', '1.2.0', '1.2.9', '1.2.10', '1.9.0', '1.10.0', '2.0.0', '10.0.0']);
  assert.deepEqual(reg.versions('unknown'), []);
  assert.throws(() => reg.publish('p', '1.9.0'), Error);
  assert.equal(reg.versions('p').length, 8);
});

test('R9 breadth-first queue and peers ignored for selection', () => {
  // a asks for e directly; b only reaches e through c, one level deeper.
  const reg = registry({
    a: { '1.0.0': { d: { e: '^1.0.0' } } },
    b: { '1.0.0': { d: { c: '1' } } },
    c: { '1.0.0': { d: { e: '1.0.x' } } },
    e: { '1.0.5': {}, '1.5.0': {} },
  });
  fails(() => install(reg, { b: '1', a: '1' }), VersionConflictError, 'e@1.5.0 does not satisfy 1.0.x required by c@1.0.0');

  const peers = registry({ plugin: { '1.0.0': { p: { host: '1.x' } } }, host: { '1.0.0': {}, '2.0.0': {} } });
  fails(() => install(peers, { plugin: '1' }), PeerDependencyError, 'plugin@1.0.0 requires peer host@1.x, but host is not installed');
  const result = install(registry({ a: { '1.0.0': { d: { b: '1' } } }, b: { '1.0.0': { d: { c: '*' } } }, c: { '3.0.0': {} }, z: { '1.0.0': {} } }), { a: '1' });
  assert.deepEqual(result.versions, { a: '1.0.0', b: '1.0.0', c: '3.0.0' });
});

test('R10 highest version satisfying all requests so far', () => {
  const reg = registry({
    a: { '1.0.0': { d: { c: '^1.0.0' } } },
    b: { '1.0.0': { d: { c: '<1.3.0' } } },
    c: { '1.0.0': {}, '1.2.9': {}, '1.3.0': {}, '2.0.0': {} },
  });
  assert.equal(install(reg, { a: '1', b: '1' }).versions.c, '1.2.9');
  const shuffled = registry({ lib: { '1.2.0': {}, '1.10.0': {}, '1.9.0': {}, '2.0.0': {} } });
  assert.deepEqual(install(shuffled, { lib: '^1.0.0' }).versions, { lib: '1.10.0' });
});

test('R11 no matching version lists every request', () => {
  const reg = registry({
    a: { '1.0.0': { d: { c: '>=2.0.0' } } },
    b: { '1.0.0': { d: { c: '<1.5.0' } } },
    c: { '1.0.0': {}, '1.4.0': {}, '2.0.0': {} },
    aa: { '1.0.0': { d: { c: '1.5.x' } } },
  });
  fails(() => install(reg, { b: '1', a: '1' }), NoMatchingVersionError, 'no version of c satisfies >=2.0.0 (from a@1.0.0), <1.5.0 (from b@1.0.0)');
  fails(() => install(reg, { c: '^1', aa: '1' }), NoMatchingVersionError, 'no version of c satisfies ^1 (from <root>), 1.5.x (from aa@1.0.0)');
  fails(() => install(reg, { ghost: '1' }), NoMatchingVersionError, 'no version of ghost satisfies 1 (from <root>)');
});

test('R12 conflicts with an already selected version', () => {
  const reg = registry({
    a: { '1.0.0': { d: { b: '1' } } },
    b: { '1.0.0': { d: { a: '>=1.0.0 <1.0.1', c: '1' } } },
    c: { '1.0.0': { d: { a: '^2.0.0' } } },
  });
  fails(() => install(reg, { a: '1' }), VersionConflictError, 'a@1.0.0 does not satisfy ^2.0.0 required by c@1.0.0');
});

test('R13 root ranges are checked first', () => {
  fails(() => install(new Registry(), { aaa: '^1.0.0', zzz: 'nope' }), InvalidRangeError, 'invalid range: "nope"');
});

test('R14 order of publishing and of manifest keys does not matter', () => {
  const packages = (aDeps: Record<string, string>) => ({
    a: { '1.0.0': { d: aDeps } },
    b: { '1.0.0': { d: { g: '1' } } },
    c: { '1.0.0': { d: { e: '^1' } } },
    g: { '1.0.0': { d: { e: '1.0.x' } } },
    e: { '1.0.5': {}, '1.0.9': {}, '1.0.10': {}, '1.5.0': {} },
  });
  const expected = { versions: { a: '1.0.0', b: '1.0.0', c: '1.0.0', g: '1.0.0', e: '1.0.10' }, order: ['e@1.0.10', 'c@1.0.0', 'g@1.0.0', 'b@1.0.0', 'a@1.0.0'] };
  for (const deps of [{ c: '1', b: '1' }, { b: '1', c: '1' }]) {
    for (const reverse of [false, true]) assert.deepEqual(install(registry(packages(deps), reverse), { a: '1' }), expected);
  }
});

test('R15 peer dependency checks', () => {
  const reg = registry({
    zplugin: { '1.0.0': { p: { host: '^2.0.0', alpha: '*' } } },
    yplugin: { '1.0.0': { p: { host: '1.x' } } },
    host: { '1.4.0': {}, '2.1.0': {} },
    alpha: { '1.0.0': {} },
  });
  fails(() => install(reg, { zplugin: '1', host: '^2' }), PeerDependencyError, 'zplugin@1.0.0 requires peer alpha@*, but alpha is not installed');
  fails(() => install(reg, { zplugin: '1', yplugin: '1', host: '^2', alpha: '1' }), PeerDependencyError,
    'yplugin@1.0.0 requires peer host@1.x, but host@2.1.0 is installed');
  fails(() => install(reg, { zplugin: '1', host: '1', alpha: '1' }), PeerDependencyError,
    'zplugin@1.0.0 requires peer host@^2.0.0, but host@1.4.0 is installed');
  assert.deepEqual(install(reg, { yplugin: '1', host: '1' }).versions, { host: '1.4.0', yplugin: '1.0.0' });
});

test('R16 install order respects dependencies and peers', () => {
  const reg = registry({
    alpha: { '1.0.0': { p: { zeta: '1' } } },
    zeta: { '1.0.0': { d: { mid: '1' } } },
    mid: { '1.0.0': {} },
  });
  assert.deepEqual(install(reg, { alpha: '1', zeta: '1' }).order, ['mid@1.0.0', 'zeta@1.0.0', 'alpha@1.0.0']);
});

test('R17 ties go to the smallest name', () => {
  const reg = registry({
    c: { '1.0.0': {} },
    d: { '1.0.0': { d: { b: '1' } } },
    b: { '1.0.0': {} },
    m: { '1.0.0': { d: { z: '1' } } },
    z: { '1.0.0': {} },
  });
  assert.deepEqual(install(reg, { d: '1', c: '1', m: '1' }).order, ['b@1.0.0', 'c@1.0.0', 'd@1.0.0', 'z@1.0.0', 'm@1.0.0']);
});

test('R18 cycles through dependencies and peers', () => {
  const reg = registry({ a: { '1.0.0': { d: { b: '1' } } }, b: { '1.0.0': { p: { a: '1' } } } });
  assert.throws(() => install(reg, { a: '1' }), (error: unknown) => {
    assert.ok(error instanceof DependencyCycleError);
    assert.deepEqual(error.cycle, ['a', 'b', 'a']);
    assert.equal(error.message, 'dependency cycle: a -> b -> a');
    return true;
  });
  const self = registry({ s: { '1.0.0': { d: { s: '1' } } } });
  fails(() => install(self, { s: '1' }), DependencyCycleError, 'dependency cycle: s -> s');
});

test('R19 canonical cycle', () => {
  const rotated = registry({ d: { '1.0.0': { d: { c: '1' } } }, c: { '1.0.0': { d: { b: '1' } } }, b: { '1.0.0': { d: { d: '1' } } } });
  fails(() => install(rotated, { d: '1' }), DependencyCycleError, 'dependency cycle: b -> d -> c -> b');
  const inner = registry({ a: { '1.0.0': { d: { z: '1' } } }, z: { '1.0.0': { d: { y: '1' } } }, y: { '1.0.0': { d: { z: '1' } } } });
  fails(() => install(inner, { a: '1' }), DependencyCycleError, 'dependency cycle: y -> z -> y');
  const two = registry({ p: { '1.0.0': { d: { r: '1' }, p: { q: '1' } } }, q: { '1.0.0': { d: { p: '1' } } }, r: { '1.0.0': { d: { p: '1' } } } });
  fails(() => install(two, { p: '1', q: '1' }), DependencyCycleError, 'dependency cycle: p -> q -> p');
  const later = registry({ m: { '1.0.0': { d: { n: '1' } } }, n: { '1.0.0': {} }, k: { '1.0.0': { d: { l: '1' } } }, l: { '1.0.0': { d: { k: '1' } } } });
  fails(() => install(later, { m: '1', l: '1' }), DependencyCycleError, 'dependency cycle: k -> l -> k');
});

test('R20 order of checks', () => {
  const reg = registry({
    plugin: { '1.0.0': { p: { host: '2' } } },
    host: { '1.0.0': { d: { loop: '1' } } },
    loop: { '1.0.0': { d: { host: '1' } } },
  });
  fails(() => install(reg, { plugin: '1', ghost: '1' }), NoMatchingVersionError, 'no version of ghost satisfies 1 (from <root>)');
  fails(() => install(reg, { plugin: '1', host: '1' }), PeerDependencyError, 'plugin@1.0.0 requires peer host@2, but host@1.0.0 is installed');
  fails(() => install(reg, { host: '1' }), DependencyCycleError, 'dependency cycle: host -> loop -> host');
  fails(() => install(reg, { ghost: '1', host: 'x.1' }), InvalidRangeError, 'invalid range: "x.1"');
});
