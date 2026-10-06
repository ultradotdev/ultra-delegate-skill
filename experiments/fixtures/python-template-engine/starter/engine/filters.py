"""Built-in filters. Each takes the filtered value followed by the filter's arguments."""
import html

from .context import UNDEFINED, iterate, text_of
from .markup import Markup


def f_upper(value):
    return text_of(value).upper()


def f_lower(value):
    return text_of(value).lower()


def f_trim(value):
    return text_of(value).strip()


def f_truncate(value, length):
    text = text_of(value)
    return text if len(text) <= length else text[:length] + '...'


def f_length(value):
    if value is None or value is UNDEFINED:
        return 0
    return len(value)


def f_default(value, fallback):
    return fallback if value is None or value is UNDEFINED else value


def f_join(value, sep=''):
    return text_of(sep).join(text_of(item) for item in iterate(value))


def f_safe(value):
    return Markup(text_of(value))


def f_escape(value):
    return html.escape(text_of(value))


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
