// Entry point: Markdown subset to HTML.
import { parseBlocks } from './blocks.ts';
import { renderBlocks } from './render.ts';

export function markdownToHtml(src: string): string {
  const lines = src.replace(/\r\n?/g, '\n').split('\n');
  return renderBlocks(parseBlocks(lines));
}
