"""Variable lookup: undefined values, dotted names and the scope chain."""
from collections.abc import Mapping


class Undefined:
    """The value of a name or lookup that does not exist."""

    __slots__ = ()

    def __bool__(self):
        return False

    def __iter__(self):
        return iter(())

    def __str__(self):
        return ''

    def __repr__(self):
        return 'UNDEFINED'


UNDEFINED = Undefined()


def text_of(value):
    """The text a value renders as, before any escaping."""
    if value is None or isinstance(value, Undefined):
        return ''
    return str(value)


def iterate(value):
    if value is None or isinstance(value, Undefined):
        return []
    if isinstance(value, Mapping):
        return list(value.keys())
    return list(value)


def get_segment(value, segment):
    if isinstance(value, Mapping):
        return value[segment] if segment in value else UNDEFINED
    if isinstance(value, (list, tuple)):
        if segment.isascii() and segment.isdigit() and int(segment) < len(value):
            return value[int(segment)]
        return UNDEFINED
    if isinstance(value, Undefined) or segment.startswith('_'):
        return UNDEFINED
    return getattr(value, segment, UNDEFINED)


class Context:
    """A chain of scopes; the first one is a copy of the caller's variables."""

    def __init__(self, data):
        self._scopes = [dict(data)]

    def push(self):
        self._scopes.append({})

    def pop(self):
        self._scopes.pop()

    def set(self, name, value):
        """Bind `name` in the innermost scope, shadowing outer bindings."""
        self._scopes[-1][name] = value

    def resolve(self, path):
        first, *rest = path.split('.')
        value = UNDEFINED
        for scope in reversed(self._scopes):
            if first in scope:
                value = scope[first]
                break
        for segment in rest:
            value = get_segment(value, segment)
        return value
