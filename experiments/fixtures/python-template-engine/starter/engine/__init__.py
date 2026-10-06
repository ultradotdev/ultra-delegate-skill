"""A tiny template engine. See SPEC.md."""
from .errors import TemplateError, TemplateSyntaxError
from .markup import Markup
from .template import Template, render

__all__ = ['Markup', 'Template', 'TemplateError', 'TemplateSyntaxError', 'render']
