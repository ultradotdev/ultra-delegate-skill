"""Layered configuration merge: defaults < file < env < cli."""
from __future__ import annotations

ENV_PREFIX = "APP_"


class ConfigError(Exception):
    def __init__(self, kind: str, keys):
        self.kind = kind
        self.keys = list(keys)
        label = "unknown keys" if kind == "unknown" else "invalid values"
        super().__init__(f"{label}: {', '.join(self.keys)}")


def _flatten(tree: dict, prefix: str = "") -> dict:
    out = {}
    for key, value in tree.items():
        full = f"{prefix}{key}"
        if isinstance(value, dict):
            out.update(_flatten(value, full + "."))
        else:
            out[full] = value
    return out


def _env_layer(env: dict) -> dict:
    out = {}
    for name, value in env.items():
        if name.upper().startswith(ENV_PREFIX):
            key = name[len(ENV_PREFIX):].lower().replace("_", ".")
            out[key] = value
    return out


def _cli_layer(cli: list) -> dict:
    out = {}
    for item in cli:
        key, value = item.split("=")
        out[key] = value
    return out


def _coerce(kind: str, raw: str):
    if kind == "int":
        return int(raw)
    if kind == "bool":
        return raw.lower() in ("true", "1")
    if kind == "list":
        return raw.split(",")
    return raw


def _nest(flat: dict) -> dict:
    result: dict = {}
    for key, value in flat.items():
        node = result
        parts = key.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    return result


def merge_config(schema: dict, defaults: dict, file: dict, env: dict, cli: list) -> dict:
    layers = [_flatten(defaults), _flatten(file), _env_layer(env), _cli_layer(cli)]
    merged: dict = {}
    for index, layer in enumerate(layers):
        for key, value in layer.items():
            if key not in schema:
                raise ConfigError("unknown", [key])
            if index < 2:
                # defaults and file come from JSON, so they are already typed
                merged[key] = value
                continue
            if schema[key] == "list" and value.startswith("+"):
                existing = merged.setdefault(key, [])
                existing.extend(_coerce("list", value[1:]))
                continue
            try:
                merged[key] = _coerce(schema[key], value)
            except ValueError:
                raise ConfigError("invalid", [key])
    return _nest(merged)
