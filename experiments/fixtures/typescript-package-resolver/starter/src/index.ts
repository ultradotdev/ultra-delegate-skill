import { installOrder } from './graph.ts';
import { checkPeers } from './peers.ts';
import type { Registry } from './registry.ts';
import { resolve } from './resolver.ts';

export type Installation = { versions: Record<string, string>; order: string[] };

export function install(registry: Registry, dependencies: Record<string, string>): Installation {
  const selected = resolve(registry, dependencies);
  checkPeers(registry, selected);
  const order = installOrder(registry, selected);
  return { versions: Object.fromEntries(selected), order };
}

export { satisfies } from './range.ts';
export { compareVersions } from './version.ts';
export { Registry } from './registry.ts';
export * from './errors.ts';
