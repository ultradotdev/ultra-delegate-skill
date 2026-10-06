import unittest
from slugify import slugify


class Public(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(slugify('Hello, World!'), 'hello-world')

    def test_already_slugged(self):
        self.assertEqual(slugify('  already-slugged  '), 'already-slugged')


if __name__ == '__main__':
    unittest.main()
