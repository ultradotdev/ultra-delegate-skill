# config.py: layered configuration merge

`merge_config(schema, defaults, file, env, cli)` merges four configuration layers
into one nested dict. Use only the standard library.

- `schema`: a flat dict mapping every allowed dotted key to a type name, one of
  `"int"`, `"bool"`, `"str"`, `"list"`. Example: `{"server.port": "int", "debug": "bool"}`.
- `defaults` and `file`: dicts, possibly nested (`{"server": {"port": 80}}`), with
  already-typed values (as loaded from JSON).
- `env`: a dict of environment variables (`str` to `str`).
- `cli`: a list of `"key=value"` strings.

`ConfigError(Exception)` has two attributes: `kind` (`"unknown"` or `"invalid"`)
and `keys` (a list of dotted keys).

## Requirements

R1. Precedence is defaults < file < env < cli: for each key, the value from the highest layer that supplies it wins.

R2. `defaults` and `file` are flattened to dotted keys by joining nested dict keys with `.`; a dotted key written directly (`{"server.port": 80}`) means the same as the nested form. The result is a nested dict built by splitting the final keys on `.` (`{"server": {"port": 80}}`).

R3. Schema keys that no layer supplies are left out of the result (no `None` placeholders, no empty nested dicts).

R4. Only environment variables whose name starts with `APP_` (case-sensitive) are used; all others are ignored. The rest of the name is lowercased and each `__` (double underscore) becomes `.`, while a single `_` is kept: `APP_SERVER__PORT` is `server.port`, `APP_LOG_LEVEL` is `log_level`, `APP_DB__POOL_SIZE` is `db.pool_size`.

R5. Each CLI item is split at its first `=` into key and value (`a=b=c` sets `a` to `b=c`). An item with no `=` or an empty key raises `ValueError`.

R6. Env and CLI values are strings converted by the key's schema type. `int`: an optional `+` or `-` followed by one or more ASCII digits, and nothing else (no whitespace, underscores, decimal points or non-ASCII digits). `bool`: case-insensitively `true`, `yes`, `on` or `1` is `True`, and `false`, `no`, `off` or `0` is `False`; anything else is invalid. `str`: the string unchanged. `list`: split on `,`, each item stripped of surrounding whitespace, empty items dropped (so `""` is `[]`).

R7. Values in `defaults` and `file` are not converted; each must already have the schema type, otherwise it is invalid. An `int` key needs an `int` that is not a `bool`; a `bool` key needs a `bool`; a `str` key needs a `str`; a `list` key needs a list whose items are all `str`.

R8. A list value replaces the list from lower layers by default.

R9. Append marker: an env or CLI list string that starts with `+` (`"+b,c"`), or a `file` list whose first item is `"+"` (`["+", "b", "c"]`), appends its items (without the marker) to the list accumulated from the lower layers, or to `[]` if no lower layer has one. Order is kept: existing items first, then new items in order; an item already in the list (including one added earlier in the same append) is skipped. `defaults` never use the marker.

R10. Unknown keys: a key from any layer (`defaults`, `file`, an `APP_` env variable, or the CLI) that is not in `schema` is unknown. If any exist, raise `ConfigError` with `kind == "unknown"` and `keys` = the sorted list of all distinct unknown keys from all layers; `str(error)` is `"unknown keys: "` followed by the keys joined with `", "`.

R11. Invalid values: every value supplied by any layer is checked under R6/R7, even when a higher layer overrides it. If any are invalid, raise `ConfigError` with `kind == "invalid"` and `keys` = the sorted list of all distinct keys with an invalid value; `str(error)` is `"invalid values: "` followed by the keys joined with `", "`.

R12. When there are both unknown keys and invalid values, only the unknown-key error (R10) is raised.

R13. `merge_config` never mutates its arguments: `schema`, `defaults`, `file`, `env`, `cli` and every nested dict or list inside them are unchanged afterwards, so calling it twice with the same arguments gives the same result.
