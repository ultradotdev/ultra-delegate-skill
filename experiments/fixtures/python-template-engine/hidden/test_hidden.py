import unittest

from engine import Markup, Template, TemplateSyntaxError, render


def raw(source, context=None):
    return render(source, context, autoescape=False)


def error(source):
    with unittest.TestCase().assertRaises(TemplateSyntaxError) as caught:
        Template(source)
    return str(caught.exception)


class User:
    def __init__(self):
        self.name = 'Bo'
        self._secret = 'hidden'

    @property
    def initials(self):
        return 'B'


class Syntax(unittest.TestCase):
    def test_R1_text_verbatim_and_comments(self):
        self.assertEqual(render('a<b>&"\'{# one\ntwo #}z'), 'a<b>&"\'z')
        self.assertEqual(render('{# only a comment #}'), '')

    def test_R2_tag_ends_at_first_closer(self):
        self.assertEqual(render('{# a #} b #}'), ' b #}')
        self.assertEqual(render('{{ x }}}', {'x': 1}), '1}')
        with self.assertRaises(TemplateSyntaxError):
            Template('{{ "a}}" }}')

    def test_R3_whitespace_control(self):
        self.assertEqual(render('a  \n {{- x -}} \n\t b', {'x': 1}), 'a1b')
        self.assertEqual(render('<ul>\n  {%- for i in xs -%}\n    <li>{{ i }}</li>\n  {%- endfor -%}\n</ul>',
                                {'xs': [1, 2]}), '<ul><li>1</li><li>2</li></ul>')
        self.assertEqual(render('a \n{#- note -#}\n b'), 'ab')
        self.assertEqual(render('a {{ x }} {{- y }} b', {'x': 1, 'y': 2}), 'a 12 b')
        self.assertEqual(render('x {{ y -}} {{ z }} w', {'y': 1, 'z': 2}), 'x 12 w')


class Expressions(unittest.TestCase):
    def test_R4_dotted_lookup(self):
        context = {'u': User(), 'd': {'a': {'b': 'deep'}, '0': 'zero'}, 'e': {'items': 'key'},
                   'xs': ['first', 'second'], 't': ('t0',), 'plain': {'a': 1}}
        self.assertEqual(raw('{{ d.a.b }}|{{ d.0 }}|{{ e.items }}|{{ plain.items }}', context), 'deep|zero|key|')
        self.assertEqual(raw('{{ xs.1 }}|{{ xs.2 }}|{{ xs.length }}|{{ t.0 }}', context), 'second|||t0')
        self.assertEqual(raw('{{ u.name }}|{{ u.initials }}|{{ u._secret }}|{{ u.missing }}', context), 'Bo|B||')
        self.assertEqual(raw('{{ nope.a.b }}|{{ d.a.b.c }}', context), '|')

    def test_R5_undefined_and_none(self):
        self.assertEqual(raw('[{{ nope }}]{% if nope %}T{% else %}F{% endif %}'
                             '{% for x in nope %}x{% else %}empty{% endfor %}'), '[]Fempty')
        self.assertEqual(raw('[{{ n }}][{{ zero }}][{{ flag }}][{{ xs }}]',
                             {'n': None, 'zero': 0, 'flag': False, 'xs': [1, 2]}), '[][0][False][[1, 2]]')

    def test_R6_literals(self):
        self.assertEqual(raw('{{ "a\\"b" }}|{{ \'it\\\'s\' }}|{{ "x\\\\y" }}|{{ "a\\nb" }}'),
                         'a"b|it\'s|x\\y|a\\nb')
        self.assertEqual(raw('{{ -5 }}|{{ 42 }}|{{ none }}|{% if true %}T{% endif %}{% if false %}F{% endif %}'),
                         '-5|42||T')
        self.assertEqual(raw("{{ 'single' }}"), 'single')

    def test_R7_operators_and_precedence(self):
        check = '{% if COND %}y{% else %}n{% endif %}'
        cases = [
            ('not a == b', {'a': 1, 'b': 2}, 'y'),
            ('a or b and c', {'a': True, 'b': False, 'c': False}, 'y'),
            ('not a and b', {'a': False, 'b': False}, 'n'),
            ('(a or b) and c', {'a': True, 'b': False, 'c': False}, 'n'),
            ('a != "x"', {'a': 'x'}, 'n'),
            ('not not a', {'a': [1]}, 'y'),
            ('a == 3 or not b', {'a': 3, 'b': True}, 'y'),
        ]
        for cond, context, expected in cases:
            with self.subTest(cond=cond):
                self.assertEqual(raw(check.replace('COND', cond), context), expected)
        self.assertEqual(raw('{{ 1 and "x" }}|{{ "" or 0 }}|{{ a == "a" }}|{{ not none }}', {'a': 'a'}),
                         'True|False|True|True')


class Filters(unittest.TestCase):
    def test_R8_chaining_and_name_arguments(self):
        self.assertEqual(raw('{{ " ab " | trim | upper | truncate(1) }}'), 'A...')
        self.assertEqual(raw('{{ x | default(y) }}|{{ xs | join(sep) }}', {'y': 'why', 'xs': [1, 2], 'sep': '+'}),
                         'why|1+2')

    def test_R9_builtin_filters(self):
        context = {'m': 'MiXed', 's': '  a b \n', 'w': 'abcde', 'n': None, 'xs': [1, 2, 3], 'e': '', 'z': 0}
        self.assertEqual(raw('{{ m | upper }}|{{ m | lower }}|[{{ s | trim }}]', context), 'MIXED|mixed|[a b]')
        self.assertEqual(raw('{{ w | truncate(5) }}|{{ w | truncate(4) }}|{{ w | truncate(0) }}', context),
                         'abcde|abcd...|...')
        self.assertEqual(raw('{{ xs | length }}|{{ w | length }}|{{ nope | length }}|{{ n | length }}', context),
                         '3|5|0|0')
        self.assertEqual(raw('{{ n | default("d") }}|[{{ e | default("d") }}]|{{ z | default("d") }}|'
                             '{{ nope | default("d") }}', context), 'd|[]|0|d')
        self.assertEqual(raw('{{ xs | join("-") }}|[{{ n | upper }}]|{{ 5 | upper }}|[{{ nope | truncate(2) }}]',
                             context), '1-2-3|[]|5|[]')


class Statements(unittest.TestCase):
    def test_R10_if_elif_else(self):
        template = Template('{% if a %}A{% elif b %}B{% elif c %}C{% endif %}')
        self.assertEqual(template.render({'a': 0, 'b': 1, 'c': 1}), 'B')
        self.assertEqual(template.render({'c': 1}), 'C')
        self.assertEqual(template.render({}), '')
        nested = Template('{% if a %}A{% elif b %}{% if c %}BC{% else %}B{% endif %}{% else %}E{% endif %}')
        self.assertEqual([nested.render(ctx) for ctx in ({'a': 1}, {'b': 1, 'c': 1}, {'b': 1}, {})],
                         ['A', 'BC', 'B', 'E'])

    def test_R11_for_and_else(self):
        template = Template('{% for x in xs %}<{{ x }}>{% else %}none{% endfor %}')
        self.assertEqual(template.render({'xs': ['a', '&']}), '<a><&amp;>')
        for empty in ([], None, {}):
            self.assertEqual(template.render({'xs': empty}), 'none')
        self.assertEqual(template.render({}), 'none')
        self.assertEqual(raw('{% for k in d %}{{ k }};{% endfor %}', {'d': {'b': 1, 'a': 2}}), 'b;a;')
        self.assertEqual(raw('{% for c in s %}{{ c }}.{% endfor %}', {'s': 'ab'}), 'a.b.')

    def test_R12_loop_variables(self):
        out = raw('{% for x in xs %}{{ loop.index }}{{ loop.index0 }}{{ loop.first }}{{ loop.last }}'
                  '{{ loop.length }};{% endfor %}', {'xs': 'ab'})
        self.assertEqual(out, '10TrueFalse2;21FalseTrue2;')

    def test_R13_nested_loops(self):
        source = ('{% for a in xs %}{% for b in ys %}{{ loop.index }}{% endfor %}'
                  '|{{ loop.index }}{% if loop.last %}L{% endif %};{% endfor %}')
        self.assertEqual(raw(source, {'xs': [1, 2], 'ys': [1, 2, 3]}), '123|1;123|2L;')
        source = '{% for a in xs %}{% for b in ys %}{{ a }}{{ b }}{{ loop.first }} {% endfor %}{% endfor %}'
        self.assertEqual(raw(source, {'xs': 'ab', 'ys': 'xy'}), 'axTrue ayFalse bxTrue byFalse ')

    def test_R14_loop_scope(self):
        context = {'item': 'orig', 'loop': 'outer', 'xs': ['a', 'b']}
        snapshot = {k: (list(v) if isinstance(v, list) else v) for k, v in context.items()}
        out = raw('{% for item in xs %}{{ item }}{% endfor %}|{{ item }}|{{ loop }}', context)
        self.assertEqual(out, 'ab|orig|outer')
        self.assertEqual(context, snapshot)
        self.assertEqual(raw('{% for z in xs %}{% endfor %}[{{ z }}][{{ loop.index }}]', {'xs': [1]}), '[][]')
        out = raw('{% for x in xs %}{% for x in ys %}{{ x }}{% endfor %}{{ x }}{% endfor %}', {'xs': 'ab', 'ys': 'yz'})
        self.assertEqual(out, 'yzayzb')


class Escaping(unittest.TestCase):
    def test_R15_autoescape(self):
        context = {'v': '<a href="x">Tom & \'Jerry\'</a>', 'pre': '&amp;', 'xs': ['<']}
        self.assertEqual(render('{{ v }}', context),
                         '&lt;a href=&quot;x&quot;&gt;Tom &amp; &#39;Jerry&#39;&lt;/a&gt;')
        self.assertEqual(render('{{ pre }}|{{ xs }}', context), '&amp;amp;|[&#39;&lt;&#39;]')
        self.assertEqual(Template('{{ v }}', autoescape=False).render(context), context['v'])

    def test_R16_safe(self):
        context = {'v': '<i>x</i>', 'm': Markup('<b>m</b>')}
        self.assertEqual(render('{{ v | safe }}|{{ m }}|[{{ nope | safe }}]', context), '<i>x</i>|<b>m</b>|[]')
        self.assertEqual(raw('{{ v | safe }}', context), '<i>x</i>')

    def test_R17_escape_filter(self):
        context = {'v': "<a href='x'>&</a>"}
        once = '&lt;a href=&#39;x&#39;&gt;&amp;&lt;/a&gt;'
        self.assertEqual(render('{{ v | escape }}', context), once)
        self.assertEqual(raw('{{ v | escape }}', context), once)
        self.assertEqual(render('{{ v | escape | escape }}', context), once)
        self.assertEqual(render('{{ v | safe | escape }}', context), context['v'])

    def test_R18_safe_propagation(self):
        context = {'v': ' <b>Hi</b> ', 'm': Markup('<i>x</i>'), 'h': Markup('<u>d</u>')}
        self.assertEqual(render('{{ v | safe | upper }}|{{ v | upper }}', context),
                         ' <B>HI</B> | &lt;B&gt;HI&lt;/B&gt; ')
        self.assertEqual(render('{{ v | safe | trim }}|{{ v | safe | lower | truncate(4) }}|{{ m | upper }}', context),
                         '<b>Hi</b>| <b>...|<I>X</I>')
        self.assertEqual(render('{{ v | trim | truncate(3) }}', context), '&lt;b&gt;...')
        self.assertEqual(render('{{ nope | default(h) }}|{{ m | default("<x>") }}', context), '<u>d</u>|<i>x</i>')

    def test_R19_join(self):
        context = {'xs': ['<a>', Markup('<b>')], 'ms': [Markup('<i>1</i>'), Markup('<i>2</i>')],
                   'sep': Markup('<br>')}
        self.assertEqual(render('{{ xs | join(", ") }}', context), '&lt;a&gt;, <b>')
        self.assertEqual(render('{{ ms | join(" & ") }}', context), '<i>1</i> &amp; <i>2</i>')
        self.assertEqual(render('{{ ms | join(sep) }}', context), '<i>1</i><br><i>2</i>')
        self.assertEqual(render('{{ ms | join("|") | trim }}', context), '<i>1</i>|<i>2</i>')
        self.assertEqual(raw('{{ xs | join(" & ") }}', context), '<a> & <b>')

    def test_R20_string_literals_are_unsafe(self):
        self.assertEqual(render('{{ "<b>" }}|{{ x | default("<i>") }}|{{ "a&b" | upper }}'), '&lt;b&gt;|&lt;i&gt;|A&amp;B')
        self.assertEqual(raw('{{ "<b>" }}'), '<b>')


class Errors(unittest.TestCase):
    def test_R21_error_shape_at_construction(self):
        with self.assertRaises(TemplateSyntaxError) as caught:
            Template('ok\n  {{ x | nope }}')
        err = caught.exception
        self.assertEqual((err.line, err.column, err.message), (2, 3, "unknown filter 'nope'"))
        self.assertEqual(str(err), "2:3: unknown filter 'nope'")
        with self.assertRaises(TemplateSyntaxError):
            Template('{% for x in xs %}{% if x %}{{ x | shout }}{% endif %}{% endfor %}')

    def test_R22_positions_ignore_whitespace_control(self):
        self.assertEqual(error('{% if a -%}\n\n  {% for x in xs %}\n{{ x }}\n{% endif %}'), "5:1: unexpected 'endif'")
        self.assertEqual(error('abc \t {{- x | nope }}'), "1:7: unknown filter 'nope'")
        self.assertEqual(error('{{ a -}}\n\n   {{ b'), '3:4: unclosed tag')
        self.assertEqual(error('{#- c -#}\n  x\n {%- for x in y %}'), "3:2: unclosed 'for' block")
        self.assertEqual(error('\t{% endfor %}'), "1:2: unexpected 'endfor'")

    def test_R23_unclosed(self):
        self.assertEqual(error('ab {{ x '), '1:4: unclosed tag')
        self.assertEqual(error('{# never closed'), '1:1: unclosed tag')
        self.assertEqual(error('{% if x }}'), '1:1: unclosed tag')
        self.assertEqual(error('x{% if a %}y'), "1:2: unclosed 'if' block")
        self.assertEqual(error('{% if a %}\n{% for x in y %}'), "2:1: unclosed 'for' block")
        self.assertEqual(error('{% if a %}{% elif b %}{% else %}'), "1:1: unclosed 'if' block")
        self.assertEqual(error('{% for x in y %}{% else %}\n'), "1:1: unclosed 'for' block")

    def test_R24_unexpected(self):
        cases = [
            ('{% endif %}', "1:1: unexpected 'endif'"),
            ('{% for x in y %}{% endif %}', "1:17: unexpected 'endif'"),
            ('{% if a %}{% endfor %}', "1:11: unexpected 'endfor'"),
            ('{% if a %}{% else %}{% elif b %}{% endif %}', "1:21: unexpected 'elif'"),
            ('{% if a %}{% else %}{% else %}{% endif %}', "1:21: unexpected 'else'"),
            ('{% for x in y %}{% elif a %}{% endfor %}', "1:17: unexpected 'elif'"),
            ('{% elif a %}', "1:1: unexpected 'elif'"),
            ('a\n{% else %}', "2:1: unexpected 'else'"),
        ]
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(error(source), expected)

    def test_R25_unknown_and_invalid(self):
        cases = [
            ('{% while x %}', "1:1: unknown tag 'while'"),
            ('{{ x | shout }}', "1:1: unknown filter 'shout'"),
            ('{% if a %}{% elif b | nope %}{% endif %}', "1:11: unknown filter 'nope'"),
            ('{{ }}', '1:1: invalid syntax'),
            ('{{ a b }}', '1:1: invalid syntax'),
            ('{% for x of y %}{% endfor %}', '1:1: invalid syntax'),
            ('{% if %}{% endif %}', '1:1: invalid syntax'),
            ('{% if a %}{% endif a %}', '1:11: invalid syntax'),
            ('{{ x | truncate( }}', '1:1: invalid syntax'),
            ('{{ "abc }}', '1:1: invalid syntax'),
            ('{% %}', '1:1: invalid syntax'),
        ]
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(error(source), expected)


if __name__ == '__main__':
    unittest.main()
