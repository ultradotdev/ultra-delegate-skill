import { PeerDependencyError } from './errors.ts';
import { satisfies } from './range.ts';
import type { Registry } from './registry.ts';

/** Check every selected package's peer dependencies against the selection (SPEC R15). */
export function checkPeers(registry: Registry, selected: Map<string, string>): void {
  for (const name of [...selected.keys()].sort()) {
    const version = selected.get(name)!;
    const peers = registry.get(name, version).peerDependencies;
    for (const peer of Object.keys(peers).sort()) {
      const found = selected.get(peer);
      if (found === undefined) {
        throw new PeerDependencyError(`${name}@${version} requires peer ${peer}@${peers[peer]}, but ${peer} is not installed`);
      }
      if (!satisfies(found, peers[peer])) {
        throw new PeerDependencyError(`${name}@${version} requires peer ${peer}@${peers[peer]}, but ${peer}@${found} is installed`);
      }
    }
  }
}
