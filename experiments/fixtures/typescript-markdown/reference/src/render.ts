// Renders the block tree and inline nodes to HTML.
import type { Block, ListBlock, ListItem } from './blocks.ts';
import { escapeAttr, escapeText } from './escape.ts';
import { parseInline } from './inline.ts';
import type { Inline } from './inline.ts';

export function renderInline(nodes: Inline[]): string {
  return nodes
    .map((n) => {
      switch (n.kind) {
        case 'text':
          return escapeText(n.text);
        case 'code':
          return `<code>${escapeText(n.text)}</code>`;
        case 'em':
          return `<em>${renderInline(n.children)}</em>`;
        case 'strong':
          return `<strong>${renderInline(n.children)}</strong>`;
        case 'link': {
          const title = n.title === null ? '' : ` title="${escapeAttr(n.title)}"`;
          return `<a href="${escapeAttr(n.href)}"${title}>${renderInline(n.children)}</a>`;
        }
      }
    })
    .join('');
}

function inline(text: string): string {
  return renderInline(parseInline(text));
}

function renderItem(item: ListItem): string {
  if (item.children.length === 0) return `<li>${inline(item.text)}</li>`;
  return `<li>${inline(item.text)}\n${item.children.map(renderList).join('\n')}\n</li>`;
}

function renderList(list: ListBlock): string {
  const tag = list.ordered ? 'ol' : 'ul';
  const open = list.ordered && list.start !== 1 ? `<ol start="${list.start}">` : `<${tag}>`;
  return `${open}\n${list.items.map(renderItem).join('\n')}\n</${tag}>`;
}

function renderBlock(block: Block): string {
  switch (block.kind) {
    case 'heading':
      return `<h${block.level}>${inline(block.text)}</h${block.level}>`;
    case 'paragraph':
      return `<p>${inline(block.text)}</p>`;
    case 'code': {
      const word = block.info.split(' ')[0];
      const cls = word ? ` class="language-${escapeAttr(word)}"` : '';
      const body = block.lines.map((l) => `${l}\n`).join('');
      return `<pre><code${cls}>${escapeText(body)}</code></pre>`;
    }
    case 'quote': {
      const inner = renderBlocks(block.children);
      return inner === '' ? '<blockquote>\n</blockquote>' : `<blockquote>\n${inner}\n</blockquote>`;
    }
    case 'list':
      return renderList(block);
  }
}

export function renderBlocks(blocks: Block[]): string {
  return blocks.map(renderBlock).join('\n');
}
