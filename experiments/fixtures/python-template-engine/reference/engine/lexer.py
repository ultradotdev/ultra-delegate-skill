"""Split template source into text, var, block and comment tokens."""
import re
from dataclasses import dataclass

from .errors import TemplateSyntaxError

_OPEN = re.compile(r'\{[{%#]')
_KINDS = {'{{': ('var', '}}'), '{%': ('block', '%}'), '{#': ('comment', '#}')}


@dataclass
class Token:
    kind: str  # 'text', 'var', 'block' or 'comment'
    value: str  # for tags: the content between the delimiters, stripped
    line: int
    column: int


def _advance(line, column, text):
    """Position just after `text`, which starts at (line, column)."""
    newlines = text.count('\n')
    if newlines:
        return line + newlines, len(text) - text.rfind('\n')
    return line, column + len(text)


def tokenize(source):
    tokens = []
    pos, line, column = 0, 1, 1
    strip_next = False
    while True:
        match = _OPEN.search(source, pos)
        end = match.start() if match else len(source)
        raw = source[pos:end]
        text = raw.lstrip() if strip_next else raw
        if match and source.startswith('-', match.end()):
            text = text.rstrip()
        if text:
            tokens.append(Token('text', text, line, column))
        line, column = _advance(line, column, raw)  # positions follow the original source
        if not match:
            return tokens

        kind, closer = _KINDS[match.group()]
        close = source.find(closer, match.end())
        if close == -1:
            raise TemplateSyntaxError('unclosed tag', line, column)
        inner = source[match.end():close]
        if inner.startswith('-'):
            inner = inner[1:]
        strip_next = inner.endswith('-')
        if strip_next:
            inner = inner[:-1]
        tokens.append(Token(kind, inner.strip(), line, column))
        line, column = _advance(line, column, source[match.start():close + len(closer)])
        pos = close + len(closer)
