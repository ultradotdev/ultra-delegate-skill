import { test } from 'node:test';
import assert from 'node:assert/strict';
import { DependencyCycleError, install, NoMatchingVersionError, Registry, satisfies } from '../src/index.ts';

type Manifests = Record<string, Record<string, { dependencies?: Record<string, string>; peerDependencies?: Record<string, string> }>>;

function registry(packages: Manifests): Registry {
  const result = new Registry();
  for (const [name, versions] of Object.entries(packages)) {
    for (const [version, manifest] of Object.entries(versions)) result.publish(name, version, manifest);
  }
  return result;
}

test('resolves the highest satisfying versions in install order', () => {
  const reg = registry({
    web: { '1.0.0': {}, '1.4.2': { dependencies: { log: '^2.0.0', util: '1.x' } }, '2.0.0': {} },
    log: { '2.1.0': {}, '2.1.5': {}, '2.2.0': {} },
    util: { '1.0.0': {}, '1.3.0': {}, '2.0.0': {} },
  });
  const result = install(reg, { web: '^1.0.0', log: '~2.1.0' });
  assert.deepEqual(result.versions, { log: '2.1.5', web: '1.4.2', util: '1.3.0' });
  assert.deepEqual(result.order, ['log@2.1.5', 'util@1.3.0', 'web@1.4.2']);
});

test('caret ranges on 0.x versions', () => {
  const reg = registry({ tiny: { '0.2.0': {}, '0.2.1': {}, '0.2.9': {}, '0.3.0': {}, '1.0.0': {} } });
  assert.deepEqual(install(reg, { tiny: '^0.2.1' }).versions, { tiny: '0.2.9' });
  assert.equal(satisfies('0.0.4', '^0.0.3'), false);
});

test('comparators, alternatives and tilde', () => {
  assert.equal(satisfies('1.5.0', '>=1.2.0 <2.0.0 || ^3.0.0'), true);
  assert.equal(satisfies('2.1.0', '>=1.2.0 <2.0.0 || ^3.0.0'), false);
  assert.equal(satisfies('3.4.0', '>=1.2.0 <2.0.0 || ^3.0.0'), true);
  assert.equal(satisfies('1.2.9', '~1.2.3'), true);
  assert.equal(satisfies('1.3.0', '~1.2.3'), false);
});

test('no matching version', () => {
  const reg = registry({ web: { '1.0.0': {}, '2.0.0': {} } });
  assert.throws(() => install(reg, { web: '^3.0.0' }), (error: unknown) => {
    assert.ok(error instanceof NoMatchingVersionError);
    assert.equal(error.message, 'no version of web satisfies ^3.0.0 (from <root>)');
    return true;
  });
});

test('dependency cycles are reported', () => {
  const reg = registry({ a: { '1.0.0': { dependencies: { b: '1' } } }, b: { '1.0.0': { dependencies: { a: '1' } } } });
  assert.throws(() => install(reg, { a: '1.0.0' }), (error: unknown) => {
    assert.ok(error instanceof DependencyCycleError);
    assert.equal(error.message, 'dependency cycle: a -> b -> a');
    return true;
  });
});
