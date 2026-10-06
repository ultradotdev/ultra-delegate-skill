import unittest

from config import ConfigError, merge_config

SCHEMA = {
    "server.host": "str",
    "server.port": "int",
    "debug": "bool",
    "plugins": "list",
}


class Public(unittest.TestCase):
    def test_precedence(self):
        result = merge_config(
            SCHEMA,
            defaults={"server": {"host": "localhost", "port": 80}, "debug": False},
            file={"server": {"port": 8080}},
            env={"APP_SERVER__PORT": "9000", "APP_DEBUG": "true", "HOME": "/root"},
            cli=["server.port=9100"],
        )
        self.assertEqual(result, {"server": {"host": "localhost", "port": 9100}, "debug": True})

    def test_list_replaces(self):
        result = merge_config(SCHEMA, {"plugins": ["a"]}, {}, {}, ["plugins=b,c"])
        self.assertEqual(result, {"plugins": ["b", "c"]})

    def test_unknown_key(self):
        with self.assertRaises(ConfigError) as ctx:
            merge_config(SCHEMA, {}, {}, {}, ["nope=1"])
        self.assertEqual(ctx.exception.kind, "unknown")
        self.assertEqual(ctx.exception.keys, ["nope"])
        self.assertEqual(str(ctx.exception), "unknown keys: nope")


if __name__ == "__main__":
    unittest.main()
