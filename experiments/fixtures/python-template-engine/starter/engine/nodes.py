"""Syntax tree for templates and expressions."""
from dataclasses import dataclass, field


@dataclass
class Text:
    text: str


@dataclass
class Output:
    expr: object


@dataclass
class If:
    cond: object
    body: list
    else_body: list = None


@dataclass
class For:
    var: str
    iterable: object
    body: list
    else_body: list = None


@dataclass
class Literal:
    value: object


@dataclass
class Name:
    path: str


@dataclass
class Filter:
    expr: object
    name: str
    args: list = field(default_factory=list)


@dataclass
class Not:
    expr: object


@dataclass
class And:
    left: object
    right: object


@dataclass
class Or:
    left: object
    right: object


@dataclass
class Compare:
    op: str
    left: object
    right: object
