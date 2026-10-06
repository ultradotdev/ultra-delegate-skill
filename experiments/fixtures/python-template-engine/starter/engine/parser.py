"""Turn tokens into a syntax tree. All syntax errors are raised here or in the lexer."""
import re

from . import nodes as n
from .errors import TemplateSyntaxError
from .filters import FILTERS

_EXPR_TOKEN = re.compile(r'''\s*(?:
      (?P<str>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')
    | (?P<int>-?[0-9]+)
    | (?P<name>[A-Za-z_][A-Za-z0-9_]*(?:\.(?:[A-Za-z_][A-Za-z0-9_]*|[0-9]+))*)
    | (?P<op>==|!=|[|(),])
    )''', re.X)
_KEYWORDS = {'and', 'or', 'not', 'true', 'false', 'none'}
_LITERALS = {'true': True, 'false': False, 'none': None}
_TAG = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)(.*)\Z', re.S)
_FOR = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s+in\s+(.+)\Z', re.S)
_ESCAPE = re.compile(r'''\\(["'\\])''')


def _error(message, token):
    return TemplateSyntaxError(message, token.line, token.column)


class ExpressionParser:
    def __init__(self, text, token):
        self.token = token
        self.items = []
        pos, text = 0, text.rstrip()
        while pos < len(text):
            match = _EXPR_TOKEN.match(text, pos)
            if not match:
                raise _error('invalid syntax', token)
            pos = match.end()
            kind, value = match.lastgroup, match.group(match.lastgroup)
            if kind == 'name' and value in _KEYWORDS:
                kind = value
            self.items.append((kind, value))
        self.pos = 0

    def parse(self):
        node = self.or_expr()
        if self.pos != len(self.items):
            raise _error('invalid syntax', self.token)
        return node

    def peek(self, kind, value=None):
        if self.pos >= len(self.items):
            return False
        item_kind, item_value = self.items[self.pos]
        return item_kind == kind and (value is None or item_value == value)

    def take(self, kind=None, value=None):
        if self.pos >= len(self.items) or (kind and not self.peek(kind, value)):
            raise _error('invalid syntax', self.token)
        self.pos += 1
        return self.items[self.pos - 1]

    def or_expr(self):
        node = self.and_expr()
        while self.peek('or'):
            self.take()
            node = n.Or(node, self.and_expr())
        return node

    def and_expr(self):
        node = self.not_expr()
        while self.peek('and'):
            self.take()
            node = n.And(node, self.not_expr())
        return node

    def not_expr(self):
        if self.peek('not'):
            self.take()
            return n.Not(self.not_expr())
        return self.comparison()

    def comparison(self):
        left = self.filtered()
        if self.peek('op', '==') or self.peek('op', '!='):
            op = self.take()[1]
            return n.Compare(op, left, self.filtered())
        return left

    def filtered(self):
        node = self.primary()
        while self.peek('op', '|'):
            self.take()
            name = self.take('name')[1]
            if name not in FILTERS:
                raise _error(f"unknown filter '{name}'", self.token)
            args = []
            if self.peek('op', '('):
                self.take()
                if not self.peek('op', ')'):
                    args.append(self.argument())
                    while self.peek('op', ','):
                        self.take()
                        args.append(self.argument())
                self.take('op', ')')
            node = n.Filter(node, name, args)
        return node

    def argument(self):
        if self.peek('op'):
            raise _error('invalid syntax', self.token)
        return self.primary()

    def primary(self):
        kind, value = self.take()
        if kind == 'str':
            return n.Literal(_ESCAPE.sub(r'\1', value[1:-1]))
        if kind == 'int':
            return n.Literal(int(value))
        if kind in _LITERALS:
            return n.Literal(_LITERALS[kind])
        if kind == 'name':
            return n.Name(value)
        if kind == 'op' and value == '(':
            node = self.or_expr()
            self.take('op', ')')
            return node
        raise _error('invalid syntax', self.token)


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def parse(self):
        body, _ = self.body(stops=())
        return body

    def expression(self, text, token):
        return ExpressionParser(text, token).parse()

    def body(self, stops):
        """Parse nodes until a block tag whose keyword is in `stops` (or the end).

        Returns (nodes, (keyword, rest, token)) with the stopping tag, or (nodes, None).
        The stopping tag is not consumed.
        """
        nodes = []
        while self.pos < len(self.tokens):
            token = self.tokens[self.pos]
            if token.kind == 'text':
                nodes.append(n.Text(token.value))
            elif token.kind == 'var':
                nodes.append(n.Output(self.expression(token.value, token)))
            elif token.kind == 'block':
                match = _TAG.match(token.value)
                if not match:
                    raise _error('invalid syntax', token)
                keyword, rest = match.group(1), match.group(2).strip()
                if keyword in stops:
                    return nodes, (keyword, rest, token)
                self.pos += 1
                if keyword == 'if':
                    nodes.append(self.parse_if(rest, token))
                elif keyword == 'for':
                    nodes.append(self.parse_for(rest, token))
                elif keyword in ('else', 'endif', 'endfor'):
                    raise _error(f"unexpected '{keyword}'", token)
                else:
                    raise _error(f"unknown tag '{keyword}'", token)
                continue
            self.pos += 1
        return nodes, None

    def close(self, end, opener, kind):
        """Consume the stopping tag `end`, which must exist and take no arguments."""
        if end is None:
            raise _error(f"unclosed '{kind}' block", opener)
        keyword, rest, token = end
        if rest:
            raise _error('invalid syntax', token)
        self.pos += 1
        return keyword

    def parse_if(self, rest, token):
        cond = self.expression(rest, token)
        body, end = self.body(stops=('else', 'endif'))
        else_body = None
        if self.close(end, token, 'if') == 'else':
            else_body, end = self.body(stops=('endif',))
            self.close(end, token, 'if')
        return n.If(cond, body, else_body)

    def parse_for(self, rest, token):
        match = _FOR.match(rest)
        if not match:
            raise _error('invalid syntax', token)
        var, iterable = match.group(1), self.expression(match.group(2), token)
        body, end = self.body(stops=('else', 'endfor'))
        else_body = None
        if self.close(end, token, 'for') == 'else':
            else_body, end = self.body(stops=('endfor',))
            self.close(end, token, 'for')
        return n.For(var, iterable, body, else_body)


def parse(tokens):
    return Parser(tokens).parse()
