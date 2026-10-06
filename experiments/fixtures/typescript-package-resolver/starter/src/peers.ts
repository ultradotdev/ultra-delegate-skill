import { PeerDependencyError } from './errors.ts';
import type { Registry } from './registry.ts';

/** Check every selected package's peer dependencies against the selection (SPEC R15). */
export function checkPeers(registry: Registry, selected: Map<string, string>): void {
  for (const name of [...selected.keys()].sort()) {
    const version = selected.get(name)!;
    const peers = registry.get(name, version).peerDependencies;
    for (const peer of Object.keys(peers).sort()) {
      if (!selected.has(peer)) {
        throw new PeerDependencyError(`${name}@${version} requires peer ${peer}@${peers[peer]}, but ${peer} is not installed`);
      }
    }
  }
}
