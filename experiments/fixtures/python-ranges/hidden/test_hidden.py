import unittest
from ranges import parse_ranges


class Hidden(unittest.TestCase):
    def test_R1_inclusive(self):
        self.assertEqual(parse_ranges('2-2'), [2])
        self.assertEqual(parse_ranges('0-3'), [0, 1, 2, 3])

    def test_R2_sorted_unique(self):
        self.assertEqual(parse_ranges('5,1-3,3'), [1, 2, 3, 5])

    def test_R3_whitespace(self):
        self.assertEqual(parse_ranges(' 1 , 3 - 4 '), [1, 3, 4])

    def test_R4_blank(self):
        self.assertEqual(parse_ranges('   '), [])

    def test_R5_ascii_digits(self):
        for text in ('-1', '+2', 'a', '١', '1.5'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_ranges(text)

    def test_R6_empty_token(self):
        for text in ('1,', ',1', '1,,2'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_ranges(text)

    def test_R7_multiple_dashes(self):
        with self.assertRaises(ValueError):
            parse_ranges('1-2-3')

    def test_R8_reversed(self):
        with self.assertRaises(ValueError):
            parse_ranges('3-1')


if __name__ == '__main__':
    unittest.main()
