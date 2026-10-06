// Groups source lines into a tree of blocks.
import { classify, isFenceClose, trimSpaces } from './lexer.ts';
import type { Line } from './lexer.ts';

export interface ListItem {
  text: string;
  children: ListBlock[];
}

export interface ListBlock {
  kind: 'list';
  ordered: boolean;
  indent: number;
  items: ListItem[];
}

export type Block =
  | { kind: 'heading'; level: number; text: string }
  | { kind: 'paragraph'; lines: string[] }
  | { kind: 'code'; info: string; lines: string[] }
  | { kind: 'quote'; children: Block[] }
  | ListBlock;

type ItemLine = Extract<Line, { kind: 'item' }>;

function stripQuote(line: string): string {
  // Remove the `>` marker and the spacing after it.
  return line.slice(1).trimStart();
}

function startsBlock(line: Line): boolean {
  switch (line.kind) {
    case 'blank':
    case 'heading':
    case 'fence':
    case 'quote':
      return true;
    case 'item':
      return line.indent === 0;
    default:
      return false;
  }
}

function newList(item: ItemLine): ListBlock {
  return {
    kind: 'list',
    ordered: item.ordered,
    indent: item.indent,
    items: [{ text: item.text, children: [] }],
  };
}

function lastItem(list: ListBlock): ListItem {
  return list.items[list.items.length - 1];
}

// Parses the list that starts at lines[start] (an item line at indent 0).
// Returns the list and the index of the first line after it.
function parseList(lines: string[], start: number): [ListBlock, number] {
  const root = newList(classify(lines[start]) as ItemLine);
  const open: ListBlock[] = [root];
  let i = start + 1;
  for (; i < lines.length; i++) {
    const line = classify(lines[i]);
    if (line.kind !== 'item') break;
    while (open.length > 0 && open[open.length - 1].indent > line.indent) open.pop();
    const top = open[open.length - 1];
    if (top.indent === line.indent) {
      if (top.ordered === line.ordered) {
        top.items.push({ text: line.text, children: [] });
        continue;
      }
      open.pop();
      if (open.length === 0) break; // a top-level list of the other kind starts here
      const sibling = newList(line);
      lastItem(open[open.length - 1]).children.push(sibling);
      open.push(sibling);
      continue;
    }
    const nested = newList(line);
    lastItem(top).children.push(nested);
    open.push(nested);
  }
  return [root, i];
}

export function parseBlocks(lines: string[]): Block[] {
  const blocks: Block[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = classify(lines[i]);
    if (line.kind === 'blank') {
      i++;
    } else if (line.kind === 'heading') {
      blocks.push({ kind: 'heading', level: line.level, text: line.text });
      i++;
    } else if (line.kind === 'fence') {
      const body: string[] = [];
      i++;
      while (i < lines.length && !isFenceClose(lines[i])) body.push(lines[i++]);
      i++; // the closing fence, if any
      blocks.push({ kind: 'code', info: line.info, lines: body });
    } else if (line.kind === 'quote') {
      const inner: string[] = [];
      while (i < lines.length && lines[i].startsWith('>')) inner.push(stripQuote(lines[i++]));
      blocks.push({ kind: 'quote', children: parseBlocks(inner) });
    } else if (line.kind === 'item' && line.indent === 0) {
      const [list, next] = parseList(lines, i);
      blocks.push(list);
      i = next;
    } else {
      const parts = [trimSpaces(lines[i++])];
      while (i < lines.length && !startsBlock(classify(lines[i]))) parts.push(trimSpaces(lines[i++]));
      blocks.push({ kind: 'paragraph', lines: parts });
    }
  }
  return blocks;
}
