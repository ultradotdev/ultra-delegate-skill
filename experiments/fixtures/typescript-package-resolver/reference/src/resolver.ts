import { NoMatchingVersionError, VersionConflictError } from './errors.ts';
import { parseRange, satisfies } from './range.ts';
import type { Registry } from './registry.ts';

type Request = { range: string; from: string };

const ROOT = '<root>';

/** Select one version per package name (SPEC R9-R12). Returns name -> version in selection order. */
export function resolve(registry: Registry, dependencies: Record<string, string>): Map<string, string> {
  for (const range of Object.values(dependencies)) parseRange(range);

  const selected = new Map<string, string>();
  const requests = new Map<string, Request[]>();
  const queued = new Set<string>();
  const queue: string[] = [];

  const request = (name: string, range: string, from: string): void => {
    const current = selected.get(name);
    if (current !== undefined && !satisfies(current, range)) {
      throw new VersionConflictError(`${name}@${current} does not satisfy ${range} required by ${from}`);
    }
    const list = requests.get(name) ?? [];
    list.push({ range, from });
    requests.set(name, list);
    if (!queued.has(name)) {
      queued.add(name);
      queue.push(name);
    }
  };

  for (const name of Object.keys(dependencies).sort()) request(name, dependencies[name], ROOT);

  while (queue.length > 0) {
    const name = queue.shift()!;
    const wanted = requests.get(name)!;
    const candidates = registry.versions(name).filter((version) => wanted.every((r) => satisfies(version, r.range)));
    if (candidates.length === 0) {
      const list = wanted.map((r) => `${r.range} (from ${r.from})`).join(', ');
      throw new NoMatchingVersionError(`no version of ${name} satisfies ${list}`);
    }
    const version = candidates[candidates.length - 1];
    selected.set(name, version);
    const { dependencies: deps } = registry.get(name, version);
    for (const dep of Object.keys(deps).sort()) request(dep, deps[dep], `${name}@${version}`);
  }
  return selected;
}
