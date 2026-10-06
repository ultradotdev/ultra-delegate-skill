# A tiny template engine

`engine.Template(source, autoescape=True)` compiles a template; `template.render(context)`
renders it with a dict of variables (optional) and returns a `str`.
`engine.render(source, context=None, autoescape=True)` does both in one call.
`engine.Markup` is the `str` subclass used for safe strings, and syntax errors are
`engine.TemplateSyntaxError`.

```
Hello {{ user.name | upper }}!
{% for item in items %}{{ loop.index }}. {{ item | default("?") }}{% else %}nothing{% endfor %}
{% if a and not b %}x{% elif c == "y" %}y{% else %}z{% endif %}
{# a comment #}
```

## Syntax

R1. Text outside tags is copied to the output unchanged (it is never escaped). `{{ expr }}` outputs an expression, `{% ... %}` is a statement, and `{# ... #}` is a comment that outputs nothing; comments may span lines.
R2. A tag ends at the first occurrence of its closing delimiter (`}}`, `%}` or `#}`).
R3. Whitespace control: a `-` right after an opening delimiter (`{{-`, `{%-`, `{#-`) removes all whitespace (anything `str.isspace` accepts, newlines included) from the end of the text just before the tag; a `-` right before a closing delimiter (`-}}`, `-%}`, `-#}`) removes all whitespace from the start of the text just after the tag.

## Expressions

R4. A name is one or more dot-separated segments (`user.address.city`, `items.0`). The first segment is looked up in the current scope (see R14). Each further segment is applied to the current value: a mapping is indexed with the segment as a string key; a list or tuple is indexed with the segment if it is made of ASCII digits and in range; any other value gives its attribute of that name unless the segment starts with `_`. Anything else (missing key, bad or out-of-range index, missing attribute, any lookup on an undefined value) gives *undefined*.
R5. Undefined renders as the empty string, is falsy, and iterates as an empty sequence. `None` also renders as the empty string; every other value renders as `str(value)` (before escaping, R15).
R6. Literals: strings in double or single quotes, in which `\"`, `\'` and `\\` are escapes and any other backslash is kept as it is; integers with an optional leading `-`; `true`, `false` and `none`.
R7. Conditions may use `==`, `!=`, `not`, `and`, `or` and parentheses. `==` and `!=` bind tightest, then `not`, then `and`, then `or`; all of them produce booleans. Truthiness is Python's.

## Filters

R8. `expr | name` or `expr | name(arg, ...)` applies a filter; several filters apply left to right. Filter arguments are literals or names.
R9. Built-in filters: `upper`, `lower`, `trim` (strip surrounding whitespace), `truncate(n)` (the first n characters followed by `...` when the text is longer than n characters, otherwise unchanged), `length` (`len`; undefined or `None` gives 0), `default(x)` (x if the value is undefined or `None`, otherwise the value), `join(sep)` (R19), `safe` (R16) and `escape` (R17). Filters that work on text treat undefined and `None` as the empty string and other values as `str(value)`.

## Statements

R10. `{% if c %}...{% elif c %}...{% else %}...{% endif %}` takes any number of `elif` branches and at most one `else`, which comes last. The first branch whose condition is truthy is rendered; if none is, the `else` body (if any) is rendered.
R11. `{% for name in expr %}...{% else %}...{% endfor %}` renders the body once per item with `name` bound to the item; the optional `else` body is rendered instead when there are no items. A mapping iterates over its keys in insertion order; undefined and `None` have no items.
R12. Inside a loop body, `loop.index` (counting from 1), `loop.index0` (from 0), `loop.first`, `loop.last` and `loop.length` describe the current iteration.
R13. In nested loops `loop` refers to the innermost loop; after an inner loop ends, `loop` again describes the current iteration of the enclosing loop.
R14. The names a `for` binds (its loop variable and `loop`) exist only inside its body. After the loop each of them has the value it had before the loop (for example a context variable with the same name), or is undefined if it had none. Rendering never modifies the caller's context dict.

## Escaping

R15. With autoescape on (the default), every rendered value that is not safe is HTML-escaped: `&` becomes `&amp;`, `<` becomes `&lt;`, `>` becomes `&gt;`, `"` becomes `&quot;` and `'` becomes `&#39;`. With `autoescape=False` nothing is escaped automatically.
R16. `safe` marks its value's text as safe, so it is output without escaping.
R17. `escape` returns its value's text escaped with the table of R15 and marked safe, so the text is escaped exactly once whether autoescape is on or off. A value that is already safe is returned unchanged.
R18. `upper`, `lower`, `trim` and `truncate` return a safe result when their input is safe and an unsafe one otherwise. `default` returns the value it picks as it is.
R19. `join(sep)` joins the items' texts with `sep`. With autoescape off that is all. With autoescape on, each item and the separator are escaped first unless they are safe, and the joined result is safe.
R20. String literals are not safe: they are escaped like any other value.

## Errors

R21. Every syntax error is raised by the `Template` constructor as `TemplateSyntaxError` with attributes `line`, `column` and `message`; `str(error)` is `"<line>:<column>: <message>"`. Unless stated otherwise, the position is that of the first character of the opening delimiter of the offending tag.
R22. Lines and columns count from 1 and refer to the original source: whitespace removed by whitespace control (R3) does not shift them. Every character, tab included, is one column.
R23. A tag without its closing delimiter raises `unclosed tag`. A block still open at the end of the template raises `unclosed 'if' block` or `unclosed 'for' block`, positioned at the tag that opened it (the innermost one when several are open).
R24. An `elif`, `else`, `endif` or `endfor` that does not fit the innermost open block raises `unexpected '<keyword>'`. This includes `elif` or a second `else` after an `else`, `elif` inside a `for`, a closing tag of the wrong kind, and any of these with no open block.
R25. A statement whose first word is not one of `if`, `elif`, `else`, `endif`, `for`, `endfor` raises `unknown tag '<word>'`; a filter name that is not built in raises `unknown filter '<name>'`; any other malformed tag content raises `invalid syntax`.
