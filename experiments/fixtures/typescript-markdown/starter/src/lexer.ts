// Classifies a single source line. Block structure is decided in blocks.ts.

export type Line =
  | { kind: 'blank' }
  | { kind: 'heading'; level: number; text: string }
  | { kind: 'fence'; info: string }
  | { kind: 'quote' }
  | { kind: 'item'; indent: number; ordered: boolean; text: string }
  | { kind: 'text'; indent: number; text: string };

const HEADING = /^(#{1,6})(?: (.*))?$/;
const ITEM = /^( *)([-*+]|[0-9]{1,9}\.) +(.*)$/;

export function trimSpaces(s: string): string {
  return s.replace(/^ +/, '').replace(/ +$/, '');
}

export function indentOf(s: string): number {
  return s.length - s.replace(/^ +/, '').length;
}

export function isFenceClose(line: string): boolean {
  return line.replace(/ +$/, '') === '```';
}

export function classify(line: string): Line {
  if (trimSpaces(line) === '') return { kind: 'blank' };
  const heading = HEADING.exec(line);
  if (heading) return { kind: 'heading', level: heading[1].length, text: trimSpaces(heading[2] ?? '') };
  if (line.startsWith('```')) return { kind: 'fence', info: trimSpaces(line.slice(3)) };
  if (line.startsWith('>')) return { kind: 'quote' };
  const item = ITEM.exec(line);
  if (item && trimSpaces(item[3]) !== '') {
    return {
      kind: 'item',
      indent: item[1].length,
      ordered: item[2].endsWith('.'),
      text: trimSpaces(item[3]),
    };
  }
  return { kind: 'text', indent: indentOf(line), text: trimSpaces(line) };
}
