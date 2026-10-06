"""Built-in filters. Each takes the filtered value followed by the filter's arguments."""
from .context import UNDEFINED, iterate, text_of
from .markup import Markup, escape


def _like(value, result):
    """`result`, marked safe if `value` was safe."""
    return Markup(result) if isinstance(value, Markup) else result


def f_upper(value):
    return _like(value, text_of(value).upper())


def f_lower(value):
    return _like(value, text_of(value).lower())


def f_trim(value):
    return _like(value, text_of(value).strip())


def f_truncate(value, length):
    text = text_of(value)
    return _like(value, text if len(text) <= length else text[:length] + '...')


def f_length(value):
    if value is None or value is UNDEFINED:
        return 0
    return len(value)


def f_default(value, fallback):
    return fallback if value is None or value is UNDEFINED else value


def _escaped(value):
    return escape(value if isinstance(value, Markup) else text_of(value))


def f_join(value, sep='', *, autoescape=False):
    items = iterate(value)
    if not autoescape:
        return text_of(sep).join(text_of(item) for item in items)
    return Markup(_escaped(sep).join(_escaped(item) for item in items))


f_join.needs_autoescape = True


def f_safe(value):
    return value if isinstance(value, Markup) else Markup(text_of(value))


def f_escape(value):
    return _escaped(value)


FILTERS = {
    'upper': f_upper,
    'lower': f_lower,
    'trim': f_trim,
    'truncate': f_truncate,
    'length': f_length,
    'default': f_default,
    'join': f_join,
    'safe': f_safe,
    'escape': f_escape,
}
