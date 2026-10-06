"""Evaluate a syntax tree against a context and produce output text."""
from . import nodes as n
from .context import Context, Undefined, iterate
from .filters import FILTERS
from .markup import Markup, escape


def render_nodes(nodes, data, autoescape):
    out = []
    _render(nodes, Context(data), autoescape, out)
    return ''.join(out)


def _render(nodes, ctx, autoescape, out):
    for node in nodes:
        if isinstance(node, n.Text):
            out.append(node.text)
        elif isinstance(node, n.Output):
            out.append(_output(evaluate(node.expr, ctx, autoescape), autoescape))
        elif isinstance(node, n.If):
            if evaluate(node.cond, ctx, autoescape):
                _render(node.body, ctx, autoescape, out)
            elif node.else_body is not None:
                _render(node.else_body, ctx, autoescape, out)
        elif isinstance(node, n.For):
            _render_for(node, ctx, autoescape, out)
        else:
            raise TypeError(f'unknown node {node!r}')


def _render_for(node, ctx, autoescape, out):
    items = iterate(evaluate(node.iterable, ctx, autoescape))
    if not items:
        if node.else_body is not None:
            _render(node.else_body, ctx, autoescape, out)
        return
    ctx.push()
    try:
        for index, item in enumerate(items):
            ctx.set(node.var, item)
            ctx.set('loop', {'index': index + 1, 'index0': index, 'first': index == 0,
                             'last': index == len(items) - 1, 'length': len(items)})
            _render(node.body, ctx, autoescape, out)
    finally:
        ctx.pop()


def _output(value, autoescape):
    if value is None or isinstance(value, Undefined):
        return ''
    if isinstance(value, Markup):
        return str(value)
    text = str(value)
    return str(escape(text)) if autoescape else text


def evaluate(expr, ctx, autoescape):
    if isinstance(expr, n.Literal):
        return expr.value
    if isinstance(expr, n.Name):
        return ctx.resolve(expr.path)
    if isinstance(expr, n.Filter):
        value = evaluate(expr.expr, ctx, autoescape)
        args = [evaluate(arg, ctx, autoescape) for arg in expr.args]
        return FILTERS[expr.name](value, *args)
    if isinstance(expr, n.Not):
        return not evaluate(expr.expr, ctx, autoescape)
    if isinstance(expr, n.And):
        return bool(evaluate(expr.left, ctx, autoescape)) and bool(evaluate(expr.right, ctx, autoescape))
    if isinstance(expr, n.Or):
        return bool(evaluate(expr.left, ctx, autoescape)) or bool(evaluate(expr.right, ctx, autoescape))
    if isinstance(expr, n.Compare):
        equal = evaluate(expr.left, ctx, autoescape) == evaluate(expr.right, ctx, autoescape)
        return equal if expr.op == '==' else not equal
    raise TypeError(f'unknown expression {expr!r}')
