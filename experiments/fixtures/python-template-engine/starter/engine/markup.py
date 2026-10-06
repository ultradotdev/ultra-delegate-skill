class Markup(str):
    """A string that is safe to output without escaping."""

    __slots__ = ()

    def __repr__(self):
        return f'Markup({str.__repr__(self)})'


_HTML = str.maketrans({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'})


def escape(value):
    """HTML-escape the text of `value` and mark it safe. Safe values pass through."""
    if isinstance(value, Markup):
        return value
    return Markup(str(value).translate(_HTML))
