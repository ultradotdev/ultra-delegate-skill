import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

SOLUTION = Path(__file__).resolve().parent / 'solution.py'
PREFIX = b'{"name":"ok","count":1}\n'


def run(data, encoding='latin1'):
    env = dict(os.environ, PYTHONIOENCODING=encoding)
    return subprocess.run([sys.executable, str(SOLUTION)], input=data, capture_output=True, env=env, timeout=10)


class Hidden(unittest.TestCase):
    def valid(self, data, want):
        r = run(data)
        self.assertEqual(r.returncode, 0, (data[:80], r.stderr))
        self.assertTrue(r.stdout.endswith(b'\n'), r.stdout[-80:])
        self.assertEqual(json.loads(r.stdout.decode('utf-8')), want)

    def invalid(self, *bodies):
        # R10: every invalid input follows a valid line; nothing may reach stdout
        for body in bodies:
            with self.subTest(body=body[:80]):
                r = run(PREFIX + body)
                self.assertEqual(r.returncode, 2, (body[:80], r.returncode, r.stderr[-300:]))
                self.assertEqual(r.stdout, b'', body[:80])
                self.assertTrue(r.stderr, body[:80])

    def test_R1_bom_and_utf8(self):
        self.valid(b'\xef\xbb\xbf' + '{"name":"雪","count":2}\n{"name":"a","count":0}\n'.encode(),
                   {'total': 2, 'names': ['雪', 'a']})
        self.invalid(b'\xff', b'{"name":"\xc3","count":1}\n')

    def test_R2_blank_lines(self):
        self.valid(b'', {'total': 0, 'names': []})
        self.valid(b' \n\n', {'total': 0, 'names': []})
        self.valid(b'\n{"name":"a","count":1}\n \t \n\n{"name":"b","count":2}', {'total': 3, 'names': ['a', 'b']})
        self.valid(b'{"name":"a","count":1}\r\n{"name":"b","count":2}\r\n', {'total': 3, 'names': ['a', 'b']})

    def test_R3_objects_only(self):
        self.invalid(b'[]', b'null', b'{', b'"x"', b'7', b'{"name":"a","count":1} {"name":"b","count":2}')

    def test_R4_exact_keys(self):
        self.invalid(b'{"name":"a","count":1,"count":2}', b'{"name":"a","count":1,"extra":0}',
                     b'{"name":"a"}', b'{"count":1}', b'{"name":"a","name":"a","count":1}')

    def test_R5_name(self):
        self.invalid(b'{"name":"","count":0}', b'{"name":1,"count":0}', b'{"name":null,"count":0}')

    def test_R6_count(self):
        self.invalid(b'{"name":"a","count":true}', b'{"name":"a","count":1.0}', b'{"name":"a","count":-1}',
                     b'{"name":"a","count":1000001}', b'{"name":"a","count":"1"}',
                     b'{"name":"a","count":' + b'9' * 5000 + b'}')
        self.valid(b'{"name":"a","count":1000000}\n{"name":"a","count":3}', {'total': 1000003, 'names': ['a', 'a']})

    def test_R7_nonfinite(self):
        self.invalid(b'{"name":"a","count":NaN}', b'{"name":"a","count":Infinity}', b'{"name":"a","count":-Infinity}')

    def test_R8_output(self):
        self.valid(b'{"name":"x","count":4}\n{"name":"y","count":5}\n{"name":"x","count":6}\n',
                   {'total': 15, 'names': ['x', 'y', 'x']})
        r = run(b'')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), {'total': 0, 'names': []})

    def test_R9_output_encoding(self):
        self.valid('{"name":"雪","count":2}\n{"name":"café","count":1}\n'.encode(),
                   {'total': 3, 'names': ['雪', 'café']})

    def test_R10_all_or_nothing(self):
        self.invalid(b'{"name":"a","count":-1}\n' + PREFIX, b'not json\n')


if __name__ == '__main__':
    unittest.main()
