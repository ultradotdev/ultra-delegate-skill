import { InvalidRangeError } from './errors.ts';
import { compareParsed, parseVersion } from './version.ts';
import type { Version } from './version.ts';

type Op = '>=' | '>' | '<' | '<=' | '=';
export type Comparator = { op: Op; version: Version };
/** Alternatives (joined by ||), each a list of comparators that must all hold. */
export type Range = Comparator[][];

const PART = '(?:0|[1-9]\\d*|[xX*])';
const CHUNK = new RegExp(`^(<=|>=|<|>|=|\\^|~)?(${PART}(?:\\.${PART}){0,2})$`);
const OPERATORS = new Set(['<=', '>=', '<', '>', '=', '^', '~']);

const ge = (major: number, minor: number, patch: number): Comparator => ({ op: '>=', version: [major, minor, patch] });
const lt = (major: number, minor: number, patch: number): Comparator => ({ op: '<', version: [major, minor, patch] });

export function parseRange(text: string): Range {
  if (text.trim() === '') return [[]];
  return text.split('||').map((alternative) => parseAlternative(alternative, text));
}

function parseAlternative(alternative: string, text: string): Comparator[] {
  const words = alternative.trim().split(/\s+/).filter((word) => word !== '');
  if (words.length === 0) throw new InvalidRangeError(text);
  const chunks: string[] = [];
  for (let i = 0; i < words.length; i++) {
    if (OPERATORS.has(words[i])) {
      // An operator separated from its version by whitespace: `>= 1.2.0`.
      if (i + 1 === words.length) throw new InvalidRangeError(text);
      chunks.push(words[i] + words[i + 1]);
      i++;
    } else {
      chunks.push(words[i]);
    }
  }
  return chunks.flatMap((chunk) => desugar(chunk, text));
}

function desugar(chunk: string, text: string): Comparator[] {
  const match = CHUNK.exec(chunk);
  if (!match) throw new InvalidRangeError(text);
  const op = match[1] ?? '';
  const parts: (number | null)[] = match[2].split('.').map((part) => (/^[xX*]$/.test(part) ? null : Number(part)));
  while (parts.length < 3) parts.push(null);
  const firstWildcard = parts.indexOf(null);
  if (firstWildcard !== -1 && parts.slice(firstWildcard).some((part) => part !== null)) {
    throw new InvalidRangeError(text);
  }
  const [major, minor, patch] = parts;

  if (op === '' || op === '=') {
    if (major === null) return [];
    if (minor === null) return [ge(major, 0, 0), lt(major + 1, 0, 0)];
    if (patch === null) return [ge(major, minor, 0), lt(major, minor + 1, 0)];
    return [{ op: '=', version: [major, minor, patch] }];
  }
  if (op === '^') {
    if (major === null) return [];
    return [ge(major, minor ?? 0, patch ?? 0), lt(major + 1, 0, 0)];
  }
  if (op === '~') {
    if (major === null) return [];
    if (minor === null) return [ge(major, 0, 0), lt(major + 1, 0, 0)];
    return [ge(major, minor, patch ?? 0), lt(major, minor + 1, 0)];
  }
  if (major === null) throw new InvalidRangeError(text);
  if (minor !== null && patch !== null) return [{ op: op as Op, version: [major, minor, patch] }];
  const floor: Version = [major, minor ?? 0, 0];
  const next: Version = minor === null ? [major + 1, 0, 0] : [major, minor + 1, 0];
  switch (op) {
    case '>=':
      return [ge(...floor)];
    case '<':
      return [lt(...floor)];
    case '>':
      return [ge(...next)];
    default: // '<='
      return [lt(...next)];
  }
}

function holds(version: Version, comparator: Comparator): boolean {
  const order = compareParsed(version, comparator.version);
  switch (comparator.op) {
    case '>=':
      return order >= 0;
    case '>':
      return order > 0;
    case '<':
      return order < 0;
    case '<=':
      return order <= 0;
    case '=':
      return order === 0;
  }
}

export function satisfies(version: string, range: string | Range): boolean {
  const parsed = parseVersion(version);
  const alternatives = typeof range === 'string' ? parseRange(range) : range;
  return alternatives.some((comparators) => comparators.every((comparator) => holds(parsed, comparator)));
}
