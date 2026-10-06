import { test } from 'node:test';
import assert from 'node:assert/strict';
import { markdownToHtml as md } from './src/markdown.ts';

const p = (html: string) => `<p>${html}</p>`;

test('R1 document joining and line endings', () => {
  assert.equal(md(''), '');
  assert.equal(md('   \n\n  '), '');
  assert.equal(md('a\r\nb\rc'), '<p>a\nb\nc</p>');
  assert.equal(md('# A\r\n\r\npara\n'), '<h1>A</h1>\n<p>para</p>');
});

test('R2 blank lines separate blocks', () => {
  assert.equal(md('a\n\n\nb'), '<p>a</p>\n<p>b</p>');
  assert.equal(md('a\n   \nb'), '<p>a</p>\n<p>b</p>');
  assert.equal(md('- a\n\n- b'), '<ul>\n<li>a</li>\n</ul>\n<ul>\n<li>b</li>\n</ul>');
});

test('R3 text is escaped exactly once', () => {
  assert.equal(md('&lt; & <b>'), p('&amp;lt; &amp; &lt;b&gt;'));
  assert.equal(md(`say "hi" 'there'`), p(`say "hi" 'there'`));
  assert.equal(md('# a > b'), '<h1>a &gt; b</h1>');
  assert.equal(md('- x & y'), '<ul>\n<li>x &amp; y</li>\n</ul>');
  assert.equal(md('[a<b](u)'), p('<a href="u">a&lt;b</a>'));
  assert.equal(md('```\n<&>\n```'), '<pre><code>&lt;&amp;&gt;\n</code></pre>');
});

test('R3 code spans are escaped exactly once', () => {
  assert.equal(md('`a<b>&amp;`'), p('<code>a&lt;b&gt;&amp;amp;</code>'));
  assert.equal(md('use `x && y` here'), p('use <code>x &amp;&amp; y</code> here'));
});

test('R4 attribute escaping', () => {
  assert.equal(md('[a](x"y)'), p('<a href="x&quot;y">a</a>'));
  assert.equal(md('[a](u "<&>")'), p('<a href="u" title="&lt;&amp;&gt;">a</a>'));
  assert.equal(md("[a](it's)"), p(`<a href="it's">a</a>`));
  assert.equal(md('```c"x\n```'), '<pre><code class="language-c&quot;x"></code></pre>');
});

test('R5 headings', () => {
  assert.equal(md('###### six'), '<h6>six</h6>');
  assert.equal(md('####### seven'), p('####### seven'));
  assert.equal(md('#5 bolts'), p('#5 bolts'));
  assert.equal(md('#'), '<h1></h1>');
  assert.equal(md('##   spaced *out*   '), '<h2>spaced <em>out</em></h2>');
  assert.equal(md(' # indented'), p('# indented'));
});

test('R6 paragraph lines are trimmed and joined', () => {
  assert.equal(md('  first line  \n   second\nthird  '), p('first line\nsecond\nthird'));
});

test('R7 inline syntax spans line breaks in a paragraph', () => {
  assert.equal(md('some *emphasis\nacross* lines'), p('some <em>emphasis\nacross</em> lines'));
  assert.equal(md('a `code\nspan` b'), p('a <code>code\nspan</code> b'));
  assert.equal(md('[link\ntext](u)'), p('<a href="u">link\ntext</a>'));
  assert.equal(md('> **bold\n> text**'), '<blockquote>\n<p><strong>bold\ntext</strong></p>\n</blockquote>');
});

test('R8 what interrupts a paragraph', () => {
  assert.equal(md('para\n# Head'), '<p>para</p>\n<h1>Head</h1>');
  assert.equal(md('para\n- item'), '<p>para</p>\n<ul>\n<li>item</li>\n</ul>');
  assert.equal(md('para\n1. one'), '<p>para</p>\n<ol>\n<li>one</li>\n</ol>');
  assert.equal(md('para\n> quote'), '<p>para</p>\n<blockquote>\n<p>quote</p>\n</blockquote>');
  assert.equal(md('para\n```\ncode\n```'), '<p>para</p>\n<pre><code>code\n</code></pre>');
  assert.equal(md('para\n  - not an item'), p('para\n- not an item'));
});

test('R9 fence info string', () => {
  assert.equal(md('```js extra words\nx\n```'), '<pre><code class="language-js">x\n</code></pre>');
  assert.equal(md('```  python  \nx\n```'), '<pre><code class="language-python">x\n</code></pre>');
  assert.equal(md('```   \nx\n```'), '<pre><code>x\n</code></pre>');
});

test('R10 closing fence and unclosed fences', () => {
  assert.equal(md('```\na\n\nb'), '<pre><code>a\n\nb\n</code></pre>');
  assert.equal(md('```\na\n```   \nafter'), '<pre><code>a\n</code></pre>\n<p>after</p>');
  assert.equal(md('```\na\n````\n```'), '<pre><code>a\n````\n</code></pre>');
  assert.equal(md('```\n  ```\n```'), '<pre><code>  ```\n</code></pre>');
  assert.equal(md('> ```\n> a\nafter'), '<blockquote>\n<pre><code>a\n</code></pre>\n</blockquote>\n<p>after</p>');
});

test('R11 code content is verbatim', () => {
  assert.equal(
    md('```\n  indented *not em*\n\n# not heading\nx  \n```'),
    '<pre><code>  indented *not em*\n\n# not heading\nx  \n</code></pre>',
  );
  assert.equal(md('```\n```'), '<pre><code></code></pre>');
});

test('R12 blockquotes', () => {
  assert.equal(
    md('> # Title\n> body *em*\n>\n> - a'),
    '<blockquote>\n<h1>Title</h1>\n<p>body <em>em</em></p>\n<ul>\n<li>a</li>\n</ul>\n</blockquote>',
  );
  assert.equal(md('> > deep'), '<blockquote>\n<blockquote>\n<p>deep</p>\n</blockquote>\n</blockquote>');
  assert.equal(md('>'), '<blockquote>\n</blockquote>');
  assert.equal(md('> a\nb'), '<blockquote>\n<p>a</p>\n</blockquote>\n<p>b</p>');
  assert.equal(md('>no space'), '<blockquote>\n<p>no space</p>\n</blockquote>');
});

test('R13 blockquotes keep indentation after one space', () => {
  assert.equal(
    md('> - a\n>   - b\n> - c'),
    '<blockquote>\n<ul>\n<li>a\n<ul>\n<li>b</li>\n</ul>\n</li>\n<li>c</li>\n</ul>\n</blockquote>',
  );
  assert.equal(md('> ```\n>     x\n> ```'), '<blockquote>\n<pre><code>    x\n</code></pre>\n</blockquote>');
  assert.equal(md('>  - a'), '<blockquote>\n<p>- a</p>\n</blockquote>');
});

test('R14 item lines', () => {
  assert.equal(md('* star\n+ plus\n- dash'), '<ul>\n<li>star</li>\n<li>plus</li>\n<li>dash</li>\n</ul>');
  assert.equal(md('-no space'), p('-no space'));
  assert.equal(md('-   '), p('-'));
  assert.equal(md('1234567890. ten digits'), p('1234567890. ten digits'));
  assert.equal(md('123456789. nine'), '<ol start="123456789">\n<li>nine</li>\n</ol>');
  assert.equal(md('1) paren'), p('1) paren'));
  assert.equal(md('-  spaced text  '), '<ul>\n<li>spaced text</li>\n</ul>');
  assert.equal(md('*not* a list'), p('<em>not</em> a list'));
});

test('R15 where a list ends', () => {
  assert.equal(md('- a\n- b\npara'), '<ul>\n<li>a</li>\n<li>b</li>\n</ul>\n<p>para</p>');
  assert.equal(md('- a\n# h'), '<ul>\n<li>a</li>\n</ul>\n<h1>h</h1>');
  assert.equal(md('- a\n  continuation'), '<ul>\n<li>a</li>\n</ul>\n<p>continuation</p>');
  assert.equal(md('  - a'), p('- a'));
});

test('R16 nesting by indent', () => {
  assert.equal(
    md('- a\n  - b\n    - c\n- d'),
    '<ul>\n<li>a\n<ul>\n<li>b\n<ul>\n<li>c</li>\n</ul>\n</li>\n</ul>\n</li>\n<li>d</li>\n</ul>',
  );
  assert.equal(
    md('- a\n    - b\n  - c'),
    '<ul>\n<li>a\n<ul>\n<li>b</li>\n</ul>\n<ul>\n<li>c</li>\n</ul>\n</li>\n</ul>',
  );
  assert.equal(
    md('- a\n  1. b\n  - c'),
    '<ul>\n<li>a\n<ol>\n<li>b</li>\n</ol>\n<ul>\n<li>c</li>\n</ul>\n</li>\n</ul>',
  );
  assert.equal(md('- a\n1. b'), '<ul>\n<li>a</li>\n</ul>\n<ol>\n<li>b</li>\n</ol>');
  assert.equal(
    md('1. a\n   - b\n2. c\n   - d'),
    '<ol>\n<li>a\n<ul>\n<li>b</li>\n</ul>\n</li>\n<li>c\n<ul>\n<li>d</li>\n</ul>\n</li>\n</ol>',
  );
});

test('R17 ordered list start', () => {
  assert.equal(md('007. x'), '<ol start="7">\n<li>x</li>\n</ol>');
  assert.equal(md('0. zero'), '<ol start="0">\n<li>zero</li>\n</ol>');
  assert.equal(md('01. x'), '<ol>\n<li>x</li>\n</ol>');
  assert.equal(md('1. a\n5. b\n9. c'), '<ol>\n<li>a</li>\n<li>b</li>\n<li>c</li>\n</ol>');
  assert.equal(md('2. a\n1. b'), '<ol start="2">\n<li>a</li>\n<li>b</li>\n</ol>');
  assert.equal(md('- a\n  3. b'), '<ul>\n<li>a\n<ol start="3">\n<li>b</li>\n</ol>\n</li>\n</ul>');
});

test('R18 list markup', () => {
  assert.equal(md('- one\n- two'), '<ul>\n<li>one</li>\n<li>two</li>\n</ul>');
  assert.equal(md('- **b** and `c`'), '<ul>\n<li><strong>b</strong> and <code>c</code></li>\n</ul>');
});

test('R19 backslash escapes', () => {
  assert.equal(md('\\*not em\\*'), p('*not em*'));
  assert.equal(md('\\_x\\_'), p('_x_'));
  assert.equal(md('\\[a](b)'), p('[a](b)'));
  assert.equal(md('\\\\*a*'), p('\\<em>a</em>'));
  assert.equal(md('\\a'), p('\\a'));
  assert.equal(md('a\\'), p('a\\'));
  assert.equal(md('\\# not heading'), p('# not heading'));
  assert.equal(md('\\`not code`'), p('`not code`'));
  assert.equal(md('a\\<b'), p('a\\&lt;b'));
  assert.equal(md('a \\> b'), p('a &gt; b'));
});

test('R20 code spans', () => {
  assert.equal(md('``a`b``'), p('<code>a`b</code>'));
  assert.equal(md('`` `x` ``'), p('<code>`x`</code>'));
  assert.equal(md('` `'), p('<code> </code>'));
  assert.equal(md('`  two  `'), p('<code> two </code>'));
  assert.equal(md('`a\\`'), p('<code>a\\</code>'));
  assert.equal(md('`*a*`'), p('<code>*a*</code>'));
  assert.equal(md('`a``b`'), p('<code>a``b</code>'));
});

test('R21 unmatched backtick runs are plain text', () => {
  assert.equal(md('``a`'), p('``a`'));
  assert.equal(md('`a ``b``'), p('`a <code>b</code>'));
});

test('R22 link syntax', () => {
  assert.equal(md('[a](u)'), p('<a href="u">a</a>'));
  assert.equal(md('[a] (u)'), p('[a] (u)'));
  assert.equal(md('[a]()'), p('[a]()'));
  assert.equal(md('[a](u v)'), p('[a](u v)'));
  assert.equal(md('[a](u "t")'), p('<a href="u" title="t">a</a>'));
  assert.equal(md('[a](u  "t"  )'), p('<a href="u" title="t">a</a>'));
  assert.equal(md('[a](u "t)'), p('[a](u "t)'));
  assert.equal(md('[a](u'), p('[a](u'));
  assert.equal(md('[`]`](u)'), p('<a href="u"><code>]</code></a>'));
  assert.equal(md('[a\\]b](u)'), p('<a href="u">a]b</a>'));
});

test('R23 link output', () => {
  assert.equal(md('[*a* `b`](u)'), p('<a href="u"><em>a</em> <code>b</code></a>'));
  assert.equal(md('[a](x\\_y)'), p('<a href="x\\_y">a</a>'));
  assert.equal(md('[a](u "x\\_y")'), p('<a href="u" title="x\\_y">a</a>'));
});

test('R24 delimiter runs', () => {
  assert.equal(md('***x***'), p('***x***'));
  assert.equal(md('a * b * c'), p('a * b * c'));
  assert.equal(md('snake_case_name'), p('snake_case_name'));
  assert.equal(md('__init__'), p('<strong>init</strong>'));
  assert.equal(md('a*b*c'), p('a<em>b</em>c'));
  assert.equal(md('a_b_c'), p('a_b_c'));
  assert.equal(md('_a_b'), p('_a_b'));
  assert.equal(md('x _a_.'), p('x <em>a</em>.'));
  assert.equal(md('x * a*'), p('x * a*'));
  assert.equal(md('*a *'), p('*a *'));
  assert.equal(md('[_a_](u)'), p('<a href="u"><em>a</em></a>'));
});

test('R25 pairing', () => {
  assert.equal(md('*foo **bar* baz**'), p('<em>foo **bar</em> baz**'));
  assert.equal(md('**a *b* c**'), p('<strong>a <em>b</em> c</strong>'));
  assert.equal(md('*a **b** c*'), p('<em>a <strong>b</strong> c</em>'));
  assert.equal(md('**a*'), p('**a*'));
  assert.equal(md('*a**b*'), p('<em>a**b</em>'));
  assert.equal(md('*a_b*_'), p('<em>a_b</em>_'));
  assert.equal(md('_a *b_ c*'), p('<em>a *b</em> c*'));
  assert.equal(md('**a** **b**'), p('<strong>a</strong> <strong>b</strong>'));
});

test('R26 code spans and links take precedence over emphasis', () => {
  assert.equal(md('*a `*` b*'), p('<em>a <code>*</code> b</em>'));
  assert.equal(md('`*a` b*'), p('<code>*a</code> b*'));
  assert.equal(md('*[a*](u)'), p('*<a href="u">a*</a>'));
  assert.equal(md('**[a](u)**'), p('<strong><a href="u">a</a></strong>'));
  assert.equal(md('[a *b](u) c*'), p('<a href="u">a *b</a> c*'));
  assert.equal(md('`[a](b)`'), p('<code>[a](b)</code>'));
});
