import copy
import unittest

from config import ConfigError, merge_config

SCHEMA = {
    "server.host": "str",
    "server.port": "int",
    "server.tls.enabled": "bool",
    "debug": "bool",
    "log_level": "str",
    "db.pool_size": "int",
    "plugins": "list",
    "name": "str",
}


def merge(defaults=None, file=None, env=None, cli=None, schema=SCHEMA):
    return merge_config(schema, defaults or {}, file or {}, env or {}, cli or [])


class Hidden(unittest.TestCase):
    def assertConfigError(self, kind, keys, **layers):
        with self.assertRaises(ConfigError) as ctx:
            merge(**layers)
        self.assertEqual(ctx.exception.kind, kind)
        self.assertEqual(ctx.exception.keys, keys)
        return ctx.exception

    def test_R1_precedence(self):
        result = merge(
            defaults={"name": "d", "log_level": "info", "debug": False, "server": {"host": "h0"}},
            file={"log_level": "warn", "server": {"host": "h1"}},
            env={"APP_DEBUG": "yes", "APP_SERVER__HOST": "h2"},
            cli=["server.host=h3"],
        )
        self.assertEqual(result, {"name": "d", "log_level": "warn", "debug": True, "server": {"host": "h3"}})
        self.assertEqual(merge(file={"name": "f"}, cli=["name=c"]), {"name": "c"})
        self.assertEqual(merge(defaults={"name": "d"}, env={"APP_NAME": "e"}), {"name": "e"})

    def test_R2_dotted_and_nested(self):
        result = merge(
            defaults={"server.port": 1, "server": {"tls": {"enabled": False}}},
            file={"server.tls": {"enabled": True}, "db": {"pool_size": 4}},
        )
        self.assertEqual(result, {"server": {"port": 1, "tls": {"enabled": True}}, "db": {"pool_size": 4}})
        self.assertEqual(merge(file={"server.tls.enabled": True}), {"server": {"tls": {"enabled": True}}})

    def test_R3_absent_keys_omitted(self):
        self.assertEqual(merge(), {})
        self.assertEqual(merge(file={"server": {}}, defaults={"db": {}}), {})
        self.assertEqual(merge(cli=["debug=true"]), {"debug": True})
        self.assertEqual(merge(defaults={"server": {"tls": {}}, "name": "n"}), {"name": "n"})

    def test_R4_env_names(self):
        result = merge(env={
            "APP_LOG_LEVEL": "debug",
            "APP_DB__POOL_SIZE": "8",
            "APP_SERVER__TLS__ENABLED": "on",
            "app_name": "ignored",
            "MYAPP_NAME": "ignored",
            "APPNAME": "ignored",
            "PATH": "/bin",
        })
        self.assertEqual(result, {"log_level": "debug", "db": {"pool_size": 8}, "server": {"tls": {"enabled": True}}})

    def test_R5_cli_items(self):
        self.assertEqual(merge(cli=["name=a=b=c"]), {"name": "a=b=c"})
        self.assertEqual(merge(cli=["name="]), {"name": ""})
        for item in ("name", "=x", ""):
            with self.subTest(item=item), self.assertRaises(ValueError):
                merge(cli=[item])

    def test_R6_string_conversion(self):
        self.assertEqual(merge(cli=["server.port=+5"]), {"server": {"port": 5}})
        self.assertEqual(merge(env={"APP_SERVER__PORT": "-3"}), {"server": {"port": -3}})
        for raw, expected in (("YES", True), ("On", True), ("1", True), ("true", True),
                              ("FALSE", False), ("off", False), ("No", False), ("0", False)):
            with self.subTest(raw=raw):
                self.assertEqual(merge(cli=[f"debug={raw}"]), {"debug": expected})
        self.assertEqual(merge(cli=["plugins= a , ,b ,"]), {"plugins": ["a", "b"]})
        self.assertEqual(merge(env={"APP_PLUGINS": ""}), {"plugins": []})
        self.assertEqual(merge(cli=["name= keep me "]), {"name": " keep me "})
        for raw in (" 8", "8 ", "1_000", "1.0", "٣", "", "0x10", "+"):
            with self.subTest(int_raw=raw):
                self.assertConfigError("invalid", ["server.port"], cli=[f"server.port={raw}"])
        for raw in ("maybe", "", "y", "2", " true"):
            with self.subTest(bool_raw=raw):
                self.assertConfigError("invalid", ["debug"], env={"APP_DEBUG": raw})

    def test_R7_typed_layers_not_coerced(self):
        self.assertEqual(merge(file={"server": {"port": 0}, "debug": False, "plugins": []}),
                         {"server": {"port": 0}, "debug": False, "plugins": []})
        cases = [
            ("server.port", {"server": {"port": "80"}}),
            ("server.port", {"server": {"port": True}}),
            ("server.port", {"server": {"port": 8.0}}),
            ("debug", {"debug": 1}),
            ("debug", {"debug": "true"}),
            ("name", {"name": 5}),
            ("plugins", {"plugins": "a,b"}),
            ("plugins", {"plugins": ["a", 2]}),
        ]
        for key, layer in cases:
            with self.subTest(layer=layer):
                self.assertConfigError("invalid", [key], file=layer)
                self.assertConfigError("invalid", [key], defaults=layer)

    def test_R8_lists_replace(self):
        self.assertEqual(merge(defaults={"plugins": ["a", "b"]}, file={"plugins": ["c"]}), {"plugins": ["c"]})
        self.assertEqual(merge(defaults={"plugins": ["a"]}, env={"APP_PLUGINS": "d"}), {"plugins": ["d"]})
        self.assertEqual(merge(defaults={"plugins": ["a"]}, cli=["plugins="]), {"plugins": []})

    def test_R9_append_marker(self):
        result = merge(defaults={"plugins": ["a"]}, file={"plugins": ["+", "b"]},
                       env={"APP_PLUGINS": "+c, a"}, cli=["plugins=+d,d"])
        self.assertEqual(result, {"plugins": ["a", "b", "c", "d"]})
        self.assertEqual(merge(cli=["plugins=+x,y"]), {"plugins": ["x", "y"]})
        self.assertEqual(merge(file={"plugins": ["+"]}), {"plugins": []})
        self.assertEqual(merge(defaults={"plugins": ["a"]}, file={"plugins": ["+"]}), {"plugins": ["a"]})
        self.assertEqual(merge(file={"plugins": ["+", "b"]}, cli=["plugins=z"]), {"plugins": ["z"]})
        self.assertEqual(merge(defaults={"plugins": ["b", "a"]}, env={"APP_PLUGINS": "+a,c,b,e"}),
                         {"plugins": ["b", "a", "c", "e"]})

    def test_R10_unknown_keys_aggregated(self):
        err = self.assertConfigError(
            "unknown", ["alpha.x", "beta", "mid", "zeta"],
            defaults={"zeta": 1, "name": "ok"},
            file={"alpha": {"x": 1}},
            env={"APP_MID": "1", "OTHER": "x"},
            cli=["beta=2", "alpha.x=3"],
        )
        self.assertEqual(str(err), "unknown keys: alpha.x, beta, mid, zeta")
        self.assertConfigError("unknown", ["server.tls"], file={"server": {"tls": "yes"}})

    def test_R11_invalid_values_aggregated(self):
        err = self.assertConfigError(
            "invalid", ["debug", "server.port"],
            env={"APP_SERVER__PORT": " 8"},
            cli=["debug=maybe", "server.port=x"],
        )
        self.assertEqual(str(err), "invalid values: debug, server.port")
        self.assertConfigError("invalid", ["server.port"],
                               file={"server": {"port": "80"}}, env={"APP_SERVER__PORT": "90"})
        self.assertConfigError("invalid", ["db.pool_size", "name"],
                               defaults={"name": 1}, file={"db": {"pool_size": "4"}}, cli=["name=ok", "db.pool_size=4"])

    def test_R12_unknown_beats_invalid(self):
        self.assertConfigError("unknown", ["nope"], env={"APP_SERVER__PORT": "abc"}, cli=["nope=1"])
        self.assertConfigError("unknown", ["ghost"], file={"debug": "x"}, defaults={"ghost": 1})

    def test_R13_no_mutation(self):
        schema = dict(SCHEMA)
        defaults = {"plugins": ["a"], "server": {"host": "h", "port": 1}}
        file = {"plugins": ["+", "b"], "server": {"port": 2}}
        env = {"APP_PLUGINS": "+c"}
        cli = ["plugins=+d", "server.host=x"]
        snapshot = copy.deepcopy((schema, defaults, file, env, cli))
        first = merge_config(schema, defaults, file, env, cli)
        self.assertEqual((schema, defaults, file, env, cli), snapshot)
        second = merge_config(schema, defaults, file, env, cli)
        self.assertEqual(first, second)
        self.assertEqual(first, {"plugins": ["a", "b", "c", "d"], "server": {"host": "x", "port": 2}})
        only_defaults = {"plugins": ["a"]}
        merge_config(SCHEMA, only_defaults, {}, {}, ["plugins=+z"])
        self.assertEqual(only_defaults, {"plugins": ["a"]})


if __name__ == "__main__":
    unittest.main()
