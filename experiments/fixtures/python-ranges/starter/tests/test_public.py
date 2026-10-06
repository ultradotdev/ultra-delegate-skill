import unittest
from ranges import parse_ranges


class Public(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(parse_ranges('1,3-5'), [1, 3, 4, 5])

    def test_empty(self):
        self.assertEqual(parse_ranges(''), [])


if __name__ == '__main__':
    unittest.main()
