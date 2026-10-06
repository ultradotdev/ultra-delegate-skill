import unittest

from engine import Template, TemplateSyntaxError, render


class Public(unittest.TestCase):
    def test_variables_and_dotted_lookup(self):
        context = {'user': {'name': 'Ada', 'langs': ['en', 'fr']}}
        self.assertEqual(render('Hi {{ user.name }} ({{ user.langs.1 }}){{ user.age }}!', context), 'Hi Ada (fr)!')

    def test_filters(self):
        out = render('{{ name | upper }} {{ missing | default("n/a") }} {{ title | truncate(5) }}',
                     {'name': 'ada', 'title': 'Engines'})
        self.assertEqual(out, 'ADA n/a Engin...')

    def test_if_elif_else(self):
        template = Template('{% if n == 1 %}one{% elif n == 2 %}two{% elif n == 3 %}three{% else %}many{% endif %}')
        self.assertEqual([template.render({'n': n}) for n in (1, 2, 3, 4)], ['one', 'two', 'three', 'many'])

    def test_for_loop(self):
        out = render('{% for x in xs %}{{ loop.index }}:{{ x }}{% if not loop.last %}, {% endif %}{% endfor %}',
                     {'xs': ['a', 'b', 'c']})
        self.assertEqual(out, '1:a, 2:b, 3:c')

    def test_autoescape_and_safe(self):
        context = {'v': '<b>"Tom" & \'Jerry\'</b>'}
        self.assertEqual(render('<p>{{ v }}</p>', context),
                         '<p>&lt;b&gt;&quot;Tom&quot; &amp; &#39;Jerry&#39;&lt;/b&gt;</p>')
        self.assertEqual(render('{{ v | safe }}', context), context['v'])

    def test_unclosed_block_error(self):
        with self.assertRaises(TemplateSyntaxError) as caught:
            Template('<ul>\n  {% for x in xs %}\n    <li>{{ x }}</li>\n</ul>')
        self.assertEqual(str(caught.exception), "2:3: unclosed 'for' block")
        self.assertEqual((caught.exception.line, caught.exception.column), (2, 3))


if __name__ == '__main__':
    unittest.main()
