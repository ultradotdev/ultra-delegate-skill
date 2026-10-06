from .lexer import tokenize
from .parser import parse
from .renderer import render_nodes


class Template:
    def __init__(self, source, autoescape=True):
        self.source = source
        self.autoescape = autoescape
        self.nodes = parse(tokenize(source))

    def render(self, context=None):
        return render_nodes(self.nodes, context or {}, self.autoescape)


def render(source, context=None, autoescape=True):
    return Template(source, autoescape).render(context)
