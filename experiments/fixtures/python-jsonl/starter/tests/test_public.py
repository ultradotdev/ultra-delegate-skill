import json
import subprocess
import sys
import unittest
from pathlib import Path

SOLUTION = Path(__file__).resolve().parent.parent / 'solution.py'


def run(data):
    return subprocess.run([sys.executable, str(SOLUTION)], input=data, capture_output=True, timeout=10)


class Public(unittest.TestCase):
    def test_totals(self):
        r = run(b'{"name":"a","count":2}\n{"name":"b","count":3}\n')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.endswith(b'\n'))
        self.assertEqual(json.loads(r.stdout), {'total': 5, 'names': ['a', 'b']})

    def test_empty_input(self):
        r = run(b'')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), {'total': 0, 'names': []})

    def test_invalid_record(self):
        r = run(b'{"name":"a","count":"2"}\n')
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, b'')
        self.assertTrue(r.stderr)


if __name__ == '__main__':
    unittest.main()
