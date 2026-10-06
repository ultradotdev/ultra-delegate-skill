import { InvalidVersionError } from './errors.ts';

/** [major, minor, patch] */
export type Version = [number, number, number];

const VERSION = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/;

export function parseVersion(text: string): Version {
  const match = VERSION.exec(text);
  if (!match) throw new InvalidVersionError(text);
  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

export function compareParsed(a: Version, b: Version): number {
  for (let i = 0; i < 3; i++) {
    if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1;
  }
  return 0;
}

export function compareVersions(a: string, b: string): number {
  return compareParsed(parseVersion(a), parseVersion(b));
}
