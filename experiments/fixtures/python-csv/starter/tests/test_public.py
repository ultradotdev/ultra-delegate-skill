import unittest
from solution import parse_counts


class Public(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(parse_counts('name,count\na,2\nb,0\n'),
                         {'rows': [{'name': 'a', 'count': 2}, {'name': 'b', 'count': 0}], 'errors': []})

    def test_bad_count_is_reported(self):
        self.assertEqual(parse_counts('name,count\na,x\nb,3\n'),
                         {'rows': [{'name': 'b', 'count': 3}], 'errors': [1]})

    def test_wrong_header(self):
        with self.assertRaises(ValueError):
            parse_counts('wrong,count\na,1')


if __name__ == '__main__':
    unittest.main()
