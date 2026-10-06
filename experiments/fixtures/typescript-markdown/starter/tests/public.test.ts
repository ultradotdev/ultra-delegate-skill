import { test } from 'node:test';
import assert from 'node:assert/strict';
import { markdownToHtml } from '../src/markdown.ts';

test('heading and paragraph with emphasis', () => {
  assert.equal(
    markdownToHtml('# Title\n\nSome *emphasis* and **strong** text.\n'),
    '<h1>Title</h1>\n<p>Some <em>emphasis</em> and <strong>strong</strong> text.</p>',
  );
});

test('text is escaped', () => {
  assert.equal(markdownToHtml('a < b & c'), '<p>a &lt; b &amp; c</p>');
});

test('code span', () => {
  assert.equal(markdownToHtml('call `run()` now'), '<p>call <code>run()</code> now</p>');
});

test('nested unordered list', () => {
  assert.equal(
    markdownToHtml('- a\n  - b\n- c'),
    '<ul>\n<li>a\n<ul>\n<li>b</li>\n</ul>\n</li>\n<li>c</li>\n</ul>',
  );
});

test('ordered list keeps its start number', () => {
  assert.equal(markdownToHtml('3. three\n4. four'), '<ol start="3">\n<li>three</li>\n<li>four</li>\n</ol>');
  assert.equal(markdownToHtml('1. one\n2. two'), '<ol>\n<li>one</li>\n<li>two</li>\n</ol>');
});

test('link with title', () => {
  assert.equal(
    markdownToHtml('See [the docs](https://x.test/a?b=1&c=2 "The docs").'),
    '<p>See <a href="https://x.test/a?b=1&amp;c=2" title="The docs">the docs</a>.</p>',
  );
});

test('fenced code block', () => {
  assert.equal(
    markdownToHtml('```js\nif (a < b) {}\n```'),
    '<pre><code class="language-js">if (a &lt; b) {}\n</code></pre>',
  );
});
