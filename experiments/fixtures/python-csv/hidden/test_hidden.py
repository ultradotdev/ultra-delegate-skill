import unittest
from solution import parse_counts


def rows(*pairs):
    return [{'name': n, 'count': c} for n, c in pairs]


class Hidden(unittest.TestCase):
    def test_R1_header_required(self):
        for bad in ('', 'wrong,count\na,1', 'name,count,extra\na,1\n', 'Name,Count\na,1\n', 'a,1\n'):
            with self.subTest(text=bad), self.assertRaises(ValueError):
                parse_counts(bad)

    def test_R2_crlf_and_bom(self):
        self.assertEqual(parse_counts('﻿name,count\r\na,1\r\nb,2\r\n'),
                         {'rows': rows(('a', 1), ('b', 2)), 'errors': []})

    def test_R3_quoting(self):
        # R2 R3: BOM, CRLF, quoted comma, doubled quote, embedded CRLF newline
        self.assertEqual(
            parse_counts('﻿name,count\r\n"a,b",3\r\n"a""b",4\r\n"two\r\nlines",5\r\n'),
            {'rows': rows(('a,b', 3), ('a"b', 4), ('two\r\nlines', 5)), 'errors': []})
        self.assertEqual(parse_counts('name,count\n"x\ny","7"\n'),
                         {'rows': rows(('x\ny', 7)), 'errors': []})

    def test_R4_malformed_csv(self):
        with self.assertRaises(ValueError):
            parse_counts('name,count\n"unclosed,1')

    def test_R5_blank_lines(self):
        self.assertEqual(parse_counts('\nname,count\n\na,1\n\n\nb,2\n\n'),
                         {'rows': rows(('a', 1), ('b', 2)), 'errors': []})

    def test_R6_shape_and_order(self):
        self.assertEqual(parse_counts('name,count\na,2\nb,0\n'),
                         {'rows': rows(('a', 2), ('b', 0)), 'errors': []})
        self.assertEqual(parse_counts('name,count\n'), {'rows': [], 'errors': []})
        self.assertEqual(parse_counts('name,count\nz,1\ny,2\nx,3'),
                         {'rows': rows(('z', 1), ('y', 2), ('x', 3)), 'errors': []})

    def test_R7_column_count(self):
        self.assertEqual(parse_counts('name,count\nx,2,3\nsolo\nok,1\n'),
                         {'rows': rows(('ok', 1)), 'errors': [1, 2]})

    def test_R8_name_nonempty_unstripped(self):
        self.assertEqual(parse_counts('name,count\n,2\n q ,3\n  ,4\n'),
                         {'rows': rows((' q ', 3), ('  ', 4)), 'errors': [1]})

    def test_R9_count_digits(self):
        self.assertEqual(
            parse_counts('name,count\na,-1\nb,+2\nc,١\nd,1e3\ne,1.0\nf,1 2\ng,\nh, \t0007\t \n'),
            {'rows': rows(('h', 7)), 'errors': [1, 2, 3, 4, 5, 6, 7]})

    def test_R10_range_and_long_fields(self):
        self.assertEqual(parse_counts('name,count\na,' + '9' * 5000 + '\nb,' + '0' * 5000 + '2\nc,1000001\n'),
                         {'rows': rows(('b', 2)), 'errors': [1, 3]})
        self.assertEqual(parse_counts('name,count\nend,1000000\nzero,0\n'),
                         {'rows': rows(('end', 1000000), ('zero', 0)), 'errors': []})

    def test_R11_errors_continue(self):
        # R5 R7 R8 R9 R10 R11: blank line not numbered, later records kept
        self.assertEqual(
            parse_counts('name,count\n\nbad,-1\nx,2,3\n,2\ny,+2\nz,١\n q , \t0007\t \nend,1000000\n'),
            {'rows': rows((' q ', 7), ('end', 1000000)), 'errors': [1, 2, 3, 4, 5]})


if __name__ == '__main__':
    unittest.main()
