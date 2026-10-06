// Inline parsing: backslash escapes, code spans, links, then emphasis pairing.

export type Inline =
  | { kind: 'text'; text: string }
  | { kind: 'code'; text: string }
  | { kind: 'em'; children: Inline[] }
  | { kind: 'strong'; children: Inline[] }
  | { kind: 'link'; href: string; title: string | null; children: Inline[] };

interface Delim {
  kind: 'delim';
  ch: string;
  len: number;
  canOpen: boolean;
  canClose: boolean;
}

type Token = Inline | Delim;

const ESCAPABLE = new Set(['\\', '`', '*', '_', '[', ']', '(', ')', '#', '+', '-', '.', '!', '>']);

function isWhitespace(c: string): boolean {
  return c === ' ' || c === '\n';
}

function isAlnum(c: string): boolean {
  return /^[A-Za-z0-9]$/.test(c);
}

function runLength(src: string, at: number, ch: string): number {
  let n = 0;
  while (src[at + n] === ch) n++;
  return n;
}

// Start index of the next maximal backtick run of exactly `n`, at or after `from`; -1 if none.
function findClosingRun(src: string, from: number, n: number): number {
  let i = from;
  while (i < src.length) {
    if (src[i] !== '`') {
      i++;
      continue;
    }
    const len = runLength(src, i, '`');
    if (len === n) return i;
    i += len;
  }
  return -1;
}

function codeContent(raw: string): string {
  if (raw.length >= 2 && raw.startsWith(' ') && raw.endsWith(' ') && raw.trim() !== '') {
    return raw.slice(1, -1);
  }
  return raw;
}

interface LinkMatch {
  text: string;
  href: string;
  title: string | null;
  end: number;
}

function matchLink(src: string, open: number): LinkMatch | null {
  let i = open + 1;
  while (i < src.length && src[i] !== ']') {
    if (src[i] === '\\' && i + 1 < src.length && ESCAPABLE.has(src[i + 1])) {
      i += 2;
    } else if (src[i] === '`') {
      const n = runLength(src, i, '`');
      const close = findClosingRun(src, i + n, n);
      i = close < 0 ? i + n : close + n;
    } else {
      i++;
    }
  }
  if (i >= src.length || src[i + 1] !== '(') return null;
  const text = src.slice(open + 1, i);
  let j = i + 2;
  const urlStart = j;
  while (j < src.length && !isWhitespace(src[j]) && src[j] !== ')') j++;
  if (j === urlStart) return null;
  const href = src.slice(urlStart, j);
  if (src[j] === ')') return { text, href, title: null, end: j + 1 };
  let k = j;
  while (src[k] === ' ') k++;
  if (k === j || src[k] !== '"') return null;
  const titleEnd = src.indexOf('"', k + 1);
  if (titleEnd < 0) return null;
  let m = titleEnd + 1;
  while (src[m] === ' ') m++;
  if (src[m] !== ')') return null;
  return { text, href, title: src.slice(k + 1, titleEnd), end: m + 1 };
}

function tokenize(src: string): Token[] {
  const tokens: Token[] = [];
  let text = '';
  const flush = () => {
    if (text !== '') tokens.push({ kind: 'text', text });
    text = '';
  };
  let i = 0;
  while (i < src.length) {
    const c = src[i];
    if (c === '\\' && i + 1 < src.length && ESCAPABLE.has(src[i + 1])) {
      text += src[i + 1];
      i += 2;
    } else if (c === '`') {
      const n = runLength(src, i, '`');
      const close = findClosingRun(src, i + n, n);
      if (close < 0) {
        text += src.slice(i, i + n);
        i += n;
      } else {
        flush();
        tokens.push({ kind: 'code', text: codeContent(src.slice(i + n, close)) });
        i = close + n;
      }
    } else if (c === '[' && matchLink(src, i)) {
      const link = matchLink(src, i)!;
      flush();
      tokens.push({ kind: 'link', href: link.href, title: link.title, children: parseInline(link.text) });
      i = link.end;
    } else if (c === '*' || c === '_') {
      const n = runLength(src, i, c);
      if (n >= 3) {
        text += src.slice(i, i + n);
      } else {
        const prev = i > 0 ? src[i - 1] : '';
        const next = i + n < src.length ? src[i + n] : '';
        let canOpen = next !== '' && !isWhitespace(next);
        let canClose = prev !== '' && !isWhitespace(prev);
        if (c === '_') {
          canOpen = canOpen && !isAlnum(prev);
          canClose = canClose && !isAlnum(next);
        }
        flush();
        tokens.push({ kind: 'delim', ch: c, len: n, canOpen, canClose });
      }
      i += n;
    } else {
      text += c;
      i++;
    }
  }
  flush();
  return tokens;
}

function plain(tokens: Token[]): Inline[] {
  return tokens.map((t) => (t.kind === 'delim' ? { kind: 'text', text: t.ch.repeat(t.len) } : t));
}

function pair(tokens: Token[]): Inline[] {
  const out: Token[] = [];
  const openers: number[] = []; // indexes into `out`
  for (const t of tokens) {
    if (t.kind !== 'delim') {
      out.push(t);
      continue;
    }
    if (t.canClose) {
      let k = openers.length - 1;
      while (k >= 0) {
        const o = out[openers[k]] as Delim;
        if (o.ch === t.ch && o.len === t.len) break;
        k--;
      }
      if (k >= 0) {
        const at = openers[k];
        openers.length = k;
        const inner = plain(out.splice(at + 1));
        out.pop();
        out.push(t.len === 1 ? { kind: 'em', children: inner } : { kind: 'strong', children: inner });
        continue;
      }
    }
    if (t.canOpen) openers.push(out.length);
    out.push(t);
  }
  return plain(out);
}

export function parseInline(src: string): Inline[] {
  return pair(tokenize(src));
}
