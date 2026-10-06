"""Layered configuration merge: defaults < file < env < cli."""
from __future__ import annotations

import re

ENV_PREFIX = "APP_"
_INT = re.compile(r"[+-]?[0-9]+", re.ASCII)
_TRUE = {"true", "yes", "on", "1"}
_FALSE = {"false", "no", "off", "0"}


class ConfigError(Exception):
    def __init__(self, kind: str, keys):
        self.kind = kind
        self.keys = sorted(set(keys))
        label = "unknown keys" if kind == "unknown" else "invalid values"
        super().__init__(f"{label}: {', '.join(self.keys)}")


class _Invalid(Exception):
    pass


def _flatten(tree: dict, prefix: str = ""):
    """Yield (dotted_key, value) pairs; nested dicts are joined with '.'."""
    for key, value in tree.items():
        full = f"{prefix}{key}"
        if isinstance(value, dict):
            yield from _flatten(value, full + ".")
        else:
            yield full, value


def _env_pairs(env: dict):
    for name, value in env.items():
        if name.startswith(ENV_PREFIX):
            yield name[len(ENV_PREFIX):].lower().replace("__", "."), value


def _cli_pairs(cli: list):
    for item in cli:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise ValueError(f"malformed CLI item: {item!r}")
        yield key, value


def _from_string(kind: str, raw: str):
    """Return (value, append) for an env/CLI string."""
    if kind == "int":
        if not _INT.fullmatch(raw):
            raise _Invalid
        return int(raw), False
    if kind == "bool":
        word = raw.lower()
        if word in _TRUE:
            return True, False
        if word in _FALSE:
            return False, False
        raise _Invalid
    if kind == "list":
        append = raw.startswith("+")
        body = raw[1:] if append else raw
        return [item.strip() for item in body.split(",") if item.strip()], append
    return raw, False


def _typed(kind: str, value, allow_marker: bool):
    """Return (value, append) for a defaults/file value that must already be typed."""
    if kind == "int" and type(value) is int:
        return value, False
    if kind == "bool" and type(value) is bool:
        return value, False
    if kind == "str" and isinstance(value, str):
        return value, False
    if kind == "list" and isinstance(value, list) and all(isinstance(v, str) for v in value):
        if allow_marker and value[:1] == ["+"]:
            return list(value[1:]), True
        return list(value), False
    raise _Invalid


def merge_config(schema: dict, defaults: dict, file: dict, env: dict, cli: list) -> dict:
    layers = [
        [(k, v, "typed", False) for k, v in _flatten(defaults)],
        [(k, v, "typed", True) for k, v in _flatten(file)],
        [(k, v, "string", True) for k, v in _env_pairs(env)],
        [(k, v, "string", True) for k, v in _cli_pairs(cli)],
    ]
    unknown = {k for layer in layers for k, *_ in layer if k not in schema}
    if unknown:
        raise ConfigError("unknown", unknown)

    merged: dict = {}
    invalid = set()
    for layer in layers:
        for key, raw, source, allow_marker in layer:
            try:
                if source == "typed":
                    value, append = _typed(schema[key], raw, allow_marker)
                else:
                    value, append = _from_string(schema[key], raw)
            except _Invalid:
                invalid.add(key)
                continue
            if append:
                combined = list(merged.get(key, []))
                for item in value:
                    if item not in combined:
                        combined.append(item)
                value = combined
            merged[key] = value
    if invalid:
        raise ConfigError("invalid", invalid)

    result: dict = {}
    for key, value in merged.items():
        node = result
        *parents, leaf = key.split(".")
        for part in parents:
            node = node.setdefault(part, {})
        node[leaf] = value
    return result
