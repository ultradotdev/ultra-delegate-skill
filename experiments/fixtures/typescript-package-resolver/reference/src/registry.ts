import { parseRange } from './range.ts';
import { compareVersions, parseVersion } from './version.ts';

export type Manifest = { dependencies?: Record<string, string>; peerDependencies?: Record<string, string> };
export type PackageVersion = {
  name: string;
  version: string;
  dependencies: Record<string, string>;
  peerDependencies: Record<string, string>;
};

export class Registry {
  #packages = new Map<string, Map<string, PackageVersion>>();

  publish(name: string, version: string, manifest: Manifest = {}): void {
    parseVersion(version);
    const dependencies = { ...(manifest.dependencies ?? {}) };
    const peerDependencies = { ...(manifest.peerDependencies ?? {}) };
    for (const range of [...Object.values(dependencies), ...Object.values(peerDependencies)]) parseRange(range);
    const versions = this.#packages.get(name) ?? new Map<string, PackageVersion>();
    if (versions.has(version)) throw new Error(`${name}@${version} is already published`);
    versions.set(version, { name, version, dependencies, peerDependencies });
    this.#packages.set(name, versions);
  }

  /** Published versions of `name`, lowest first. */
  versions(name: string): string[] {
    return [...(this.#packages.get(name)?.keys() ?? [])].sort(compareVersions);
  }

  get(name: string, version: string): PackageVersion {
    const found = this.#packages.get(name)?.get(version);
    if (!found) throw new Error(`${name}@${version} is not published`);
    return found;
  }
}
