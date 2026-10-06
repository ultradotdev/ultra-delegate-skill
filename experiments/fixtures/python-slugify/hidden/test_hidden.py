import re
import unittest
from slugify import slugify


class Hidden(unittest.TestCase):
    def test_R1_charset(self):
        for text in ('a_b١c\U0001F600d', 'Mixed CASE 123 été 日本', '\t\n x  y '):
            with self.subTest(text=text):
                self.assertRegex(slugify(text), r'\A[a-z0-9-]*\Z')
        self.assertEqual(slugify('a_b١c\U0001F600d'), 'a-b-c-d')

    def test_R2_lowercase(self):
        self.assertEqual(slugify('ABC Def 42'), 'abc-def-42')
        self.assertEqual(slugify('x1Y2z3'), 'x1y2z3')

    def test_R3_collapse_runs(self):
        self.assertEqual(slugify('a  --  b...c'), 'a-b-c')
        self.assertEqual(slugify('snake_case__name'), 'snake-case-name')
        self.assertEqual(slugify('one\t\ttwo\nthree'), 'one-two-three')

    def test_R4_no_edge_hyphens(self):
        self.assertEqual(slugify('--hello--'), 'hello')
        self.assertEqual(slugify('!!!x!!!'), 'x')
        self.assertEqual(slugify(' (draft) '), 'draft')

    def test_R5_empty_result(self):
        for text in ('', '   ', '!!!', '---', '日本語', '\U0001F600'):
            with self.subTest(text=text):
                self.assertEqual(slugify(text), '')

    def test_R6_transliteration(self):
        self.assertEqual(slugify('Café Crème'), 'cafe-creme')
        self.assertEqual(slugify('Ångström'), 'angstrom')
        self.assertEqual(slugify('naïve'), 'naive')
        self.assertEqual(slugify('Café'), 'cafe')
        self.assertEqual(slugify('ﬁle'), 'file')
        self.assertEqual(slugify('straße'), 'stra-e')

    def test_R7_max_length(self):
        self.assertEqual(slugify('hello world', 6), 'hello')
        self.assertEqual(slugify('hello world', 5), 'hello')
        self.assertEqual(slugify('hello world', 7), 'hello-w')
        self.assertEqual(slugify('hello', 10), 'hello')
        self.assertEqual(slugify('Hello,   World', 8), 'hello-wo')
        self.assertEqual(slugify('Ünïcödé', 3), 'uni')
        self.assertEqual(slugify('a b c d e f', None), 'a-b-c-d-e-f')
        self.assertEqual(slugify('a b c d e f'), 'a-b-c-d-e-f')

    def test_R8_invalid_max_length(self):
        for bad in (0, -1, -10):
            with self.subTest(max_length=bad), self.assertRaises(ValueError):
                slugify('hello', bad)


if __name__ == '__main__':
    unittest.main()
