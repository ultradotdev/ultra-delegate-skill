# mdlite: a Markdown subset to HTML

`markdownToHtml(src: string): string` in `src/markdown.ts` converts a Markdown subset to
HTML. The work is split across:

- `src/escape.ts`: HTML escaping.
- `src/lexer.ts`: classifies single lines.
- `src/blocks.ts`: groups lines into a block tree (headings, paragraphs, code, lists, blockquotes).
- `src/inline.ts`: parses inline text (code spans, links, emphasis) into nodes.
- `src/render.ts`: renders blocks and inline nodes to HTML.

Terms: the *indent* of a line is its number of leading space characters. *Whitespace*
means a space or a newline (`\n`). *Alphanumeric* means an ASCII letter or digit.

## Document and escaping

R1. Line endings `\r\n` and `\r` are normalized to `\n` before anything else. The output is the HTML of each top-level block joined by a single `\n`, with no leading or trailing newline. Input without blocks gives `""`.
R2. Outside fenced code, a blank line (empty or only spaces) produces no output and ends the current paragraph or list.
R3. Text escaping: in all text output (headings, paragraphs, list items, link text, code spans and code blocks) `&`, `<` and `>` become `&amp;`, `&lt;` and `&gt;`. Every source character is escaped exactly once and entities are not recognized, so `&lt;` in the source becomes `&amp;lt;`. Quotes are not changed in text.
R4. Attribute escaping: in attribute values (`href`, `title`, and the code block `class`) `&`, `<`, `>` and `"` become `&amp;`, `&lt;`, `&gt;` and `&quot;`. `'` is not changed.

## Blocks

R5. Heading: a line that starts at indent 0 with 1 to 6 `#` characters followed by a space or the end of the line. Its content is the rest of the line with leading and trailing spaces removed, parsed as inline text, and it renders as `<hN>content</hN>` where N is the number of `#`. `#5 bolts`, `####### seven` and an indented `#` line are paragraph text, not headings.
R6. Paragraph: a run of consecutive lines that are not blank and do not start another block (R8). Each line has its leading and trailing spaces removed, the lines are joined with `\n`, and the result renders as `<p>content</p>`.
R7. Inline parsing applies to the whole joined text of a paragraph, so code spans, emphasis and links may span the line breaks inside it.
R8. A paragraph ends at a blank line or at a line that starts a heading, a fenced code block, a blockquote, or a list (an item line at indent 0, R14). An item line with an indent greater than 0 does not interrupt a paragraph; it is paragraph text.
R9. Fenced code: a line that starts with three backticks at indent 0 opens a code block. The rest of that line with leading and trailing spaces removed is the info string; if it is not empty, its first space-separated word `W` gives `<pre><code class="language-W">` (W attribute-escaped), otherwise `<pre><code>`.
R10. The code block ends at the next line that, with trailing spaces removed, is exactly three backticks; that line is not content. If there is no such line, the block runs to the end of the input (inside a blockquote: to the end of the blockquote).
R11. Code content lines are kept exactly (no trimming, no inline parsing, blank lines kept) and text-escaped (R3). The output is `<pre><code…>`, then each content line followed by `\n`, then `</code></pre>`; an empty block is `<pre><code></code></pre>`.
R12. Blockquote: a run of consecutive lines that start with `>` at indent 0. From each line the `>` and at most one space directly after it are removed. The resulting lines are parsed as blocks with these same rules, so they may contain headings, paragraphs, lists, code and nested blockquotes. Output: `<blockquote>\n` + inner HTML + `\n</blockquote>`, or `<blockquote>\n</blockquote>` when the inner HTML is empty.
R13. Because only one space is removed, any further indentation is kept and list nesting (R16) and code content inside a blockquote behave exactly as at top level: `>   - b` is an item line at indent 2, `>  - b` is an item line at indent 1, and inside a fenced block `>     x` is the content line `    x`.

## Lists

R14. An item line is: its indent, a marker, one or more spaces, then non-empty text. The marker is `-`, `*` or `+` for an unordered item, or 1 to 9 ASCII digits followed by `.` for an ordered item. The item's text is the rest of the line with leading and trailing spaces removed, parsed as inline text.
R15. A list starts with an item line at indent 0 and continues while the following lines are item lines (at any indent). It ends at a blank line or at any line that is not an item line; that line then starts the next block.
R16. Nesting. Keep a stack of open lists, each with the indent of its first item. For an item at indent j, first close every open list whose indent is greater than j. If the innermost remaining list has indent j and the same kind (ordered or unordered), the item is added to it. If it has indent j but the other kind, close it as well and start a new list of the item's kind at indent j in its place (a sibling list: nested in the same parent item, or a new top-level list). Otherwise the innermost remaining list has an indent less than j: start a new list at indent j nested inside the last item of that list.
R17. An ordered list renders as `<ol>` when its first item's number is 1 and as `<ol start="N">` otherwise, where N is that number in decimal without leading zeros (`007.` gives `start="7"`, `0.` gives `start="0"`). The numbers of later items are ignored.
R18. List HTML: `<ul>` (or the `<ol…>` tag), `\n`, the items joined by `\n`, `\n`, then `</ul>` or `</ol>`. An item without nested lists is `<li>text</li>`; an item with nested lists is `<li>text\n` + its nested lists joined by `\n` + `\n</li>`.

## Inline text

Inline text is scanned left to right. At each position the first of R19 to R22 that applies
wins; any other character is plain text.

R19. Backslash escape: `\` followed by one of `` \ ` * _ [ ] ( ) # + - . ! > `` produces that character as plain text; it never opens or closes a code span, emphasis or link. A backslash followed by any other character, or at the end, is a plain backslash.
R20. Code span: a maximal run of N backticks starts a code span that ends at the next maximal run of exactly N backticks (longer or shorter runs do not close it). The content between them is literal: no backslash escapes, emphasis or links. If the content both starts and ends with a space and is not all spaces, one space is removed from each end. It renders as `<code>content</code>`, text-escaped once.
R21. A backtick run with no closing run of the same length is plain text, and scanning continues right after it (later backticks may still form code spans).
R22. Link: `[text](url)` or `[text](url "title")`. The text ends at the first `]` that is not backslash-escaped and not inside a code span. Directly after that `]` must come `(`, then the url: one or more characters that are neither whitespace nor `)`. Then either `)`, or one or more spaces, `"`, a title containing no `"`, `"`, optional spaces and `)`. If any part does not match, the `[` is plain text and scanning continues after it.
R23. A link renders as `<a href="url">text</a>`, or `<a href="url" title="title">text</a>` when it has a title. The url and title are used literally (no backslash escapes) and attribute-escaped (R4). The link text is parsed as inline text, so code spans and emphasis work inside it.
R24. Delimiter runs: a maximal run of `*` characters or of `_` characters (R22 is tried first at `[`, so these are runs outside code spans and link syntax). A run of 3 or more is plain text. A run can open if the next character exists and is not whitespace, and can close if the previous character exists and is not whitespace. In addition, a `_` run can open only if the previous character is not alphanumeric (or does not exist) and can close only if the next character is not alphanumeric (or does not exist). Previous and next characters are taken from the source of the text being parsed; for link text, that is the text between the brackets.
R25. Pairing: process the runs left to right with a stack of openers. A run that can close looks down the stack for the nearest opener with the same character and the same length; if there is one, the content between the two becomes `<em>…</em>` (length 1) or `<strong>…</strong>` (length 2), and every opener above it on the stack is discarded as plain text. If there is none and the run can open, it is pushed on the stack. A run that can both open and close tries to close first. Runs that end up unused are plain text.
R26. Precedence: code spans and links are recognized during the left-to-right scan, before any pairing. Delimiters inside a code span are plain text, and a delimiter inside a link's text can only pair with delimiters inside that same text. For example `` *a `*` b* `` gives `<em>a <code>*</code> b</em>`.
