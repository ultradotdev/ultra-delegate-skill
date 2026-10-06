import threading
import unittest
from datetime import date, timedelta
from itertools import islice

from recur.conflicts import Conflict, find_conflicts
from recur.datemath import abs_minute, add_months, days_in_month, resolve_monthday, week_start
from recur.expand import Event, expand
from recur.rule import parse_rule

D = date


def bounded(fn, seconds=5):
    """Run fn in a daemon thread and fail if it does not finish in time."""
    box = {}

    def target():
        try:
            box['value'] = fn()
        except BaseException as exc:  # re-raised in the test thread
            box['error'] = exc

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(seconds)
    if thread.is_alive():
        raise AssertionError(f'did not finish within {seconds}s')
    if 'error' in box:
        raise box['error']
    return box['value']


def dates(rule_text, dtstart, **kw):
    return list(parse_rule(rule_text).dates(dtstart, **kw))


class DateMath(unittest.TestCase):
    def test_R1_days_in_month(self):
        cases = {(2024, 2): 29, (2023, 2): 28, (1900, 2): 28, (2000, 2): 29, (2100, 2): 28,
                 (2023, 1): 31, (2023, 4): 30, (2023, 9): 30, (2023, 12): 31}
        for (y, m), n in cases.items():
            with self.subTest(y=y, m=m):
                self.assertEqual(days_in_month(y, m), n)

    def test_R2_add_months(self):
        self.assertEqual(add_months(2024, 11, 3), (2025, 2))
        self.assertEqual(add_months(2024, 1, 0), (2024, 1))
        self.assertEqual(add_months(2024, 12, 1), (2025, 1))
        self.assertEqual(add_months(2023, 1, 11), (2023, 12))
        self.assertEqual(add_months(2023, 1, 12), (2024, 1))
        self.assertEqual(add_months(2023, 5, 25), (2025, 6))

    def test_R3_resolve_monthday(self):
        self.assertIsNone(resolve_monthday(2023, 4, 31))
        self.assertIsNone(resolve_monthday(2023, 4, -31))
        self.assertIsNone(resolve_monthday(2023, 2, 29))
        self.assertIsNone(resolve_monthday(2023, 2, -29))
        self.assertEqual(resolve_monthday(2023, 4, -1), D(2023, 4, 30))
        self.assertEqual(resolve_monthday(2023, 4, -30), D(2023, 4, 1))
        self.assertEqual(resolve_monthday(2024, 2, 29), D(2024, 2, 29))
        self.assertEqual(resolve_monthday(2024, 2, -2), D(2024, 2, 28))
        self.assertEqual(resolve_monthday(2023, 2, -28), D(2023, 2, 1))
        self.assertEqual(resolve_monthday(2023, 1, 31), D(2023, 1, 31))
        self.assertEqual(resolve_monthday(2023, 1, 1), D(2023, 1, 1))

    def test_R4_week_start(self):
        self.assertEqual(week_start(D(2024, 1, 3)), D(2024, 1, 1))
        self.assertEqual(week_start(D(2024, 1, 1)), D(2024, 1, 1))
        self.assertEqual(week_start(D(2024, 1, 7)), D(2024, 1, 1))
        self.assertEqual(week_start(D(2024, 1, 8)), D(2024, 1, 8))
        self.assertEqual(week_start(D(2024, 3, 1)), D(2024, 2, 26))

    def test_R5_abs_minute(self):
        self.assertEqual(abs_minute(D(2024, 1, 1), 90), D(2024, 1, 1).toordinal() * 1440 + 90)
        self.assertEqual(abs_minute(D(2024, 1, 2), 0) - abs_minute(D(2024, 1, 1), 1439), 1)


class Parsing(unittest.TestCase):
    def test_R6_parse_fields(self):
        rule = parse_rule('FREQ=MONTHLY;UNTIL=20240229;BYMONTHDAY=-1,15,15,1')
        self.assertEqual((rule.freq, rule.interval, rule.count, rule.until, rule.byday, rule.bymonthday),
                         ('MONTHLY', 1, None, D(2024, 2, 29), None, (-1, 1, 15)))
        rule = parse_rule('FREQ=DAILY')
        self.assertEqual((rule.freq, rule.interval, rule.count, rule.until, rule.byday, rule.bymonthday),
                         ('DAILY', 1, None, None, None, None))
        rule = parse_rule('BYDAY=SU,MO,SU;COUNT=3;FREQ=WEEKLY;INTERVAL=4')
        self.assertEqual((rule.freq, rule.interval, rule.count, rule.byday), ('WEEKLY', 4, 3, (0, 6)))

    def test_R7_invalid_rules(self):
        bad = ['', 'FREQ=DAILY;', ';FREQ=DAILY', 'FREQ', 'FREQ=', 'INTERVAL=2', 'FREQ=YEARLY',
               'FREQ=daily', 'freq=DAILY', 'FREQ=DAILY;FOO=1', 'FREQ=DAILY;FREQ=DAILY',
               'FREQ=DAILY;INTERVAL=0', 'FREQ=DAILY;INTERVAL=-1', 'FREQ=DAILY;INTERVAL=1.5',
               'FREQ=DAILY;INTERVAL=x', 'FREQ=DAILY;INTERVAL=١', 'FREQ=DAILY;COUNT=0',
               'FREQ=DAILY;COUNT=+3', 'FREQ=DAILY;UNTIL=2024-01-31', 'FREQ=DAILY;UNTIL=20240230',
               'FREQ=DAILY;UNTIL=2024013', 'FREQ=WEEKLY;BYDAY=MO,XX', 'FREQ=WEEKLY;BYDAY=mo',
               'FREQ=WEEKLY;BYDAY=MO,', 'FREQ=MONTHLY;BYMONTHDAY=0', 'FREQ=MONTHLY;BYMONTHDAY=32',
               'FREQ=MONTHLY;BYMONTHDAY=-32', 'FREQ=MONTHLY;BYMONTHDAY=x', 'FREQ=MONTHLY;BYMONTHDAY=1,,2']
        for text in bad:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_rule(text)

    def test_R8_count_and_until(self):
        with self.assertRaises(ValueError):
            parse_rule('FREQ=DAILY;COUNT=2;UNTIL=20240101')
        with self.assertRaises(ValueError):
            parse_rule('UNTIL=20240101;FREQ=WEEKLY;COUNT=1')

    def test_R9_by_rules_need_matching_freq(self):
        for text in ('FREQ=DAILY;BYDAY=MO', 'FREQ=MONTHLY;BYDAY=MO',
                     'FREQ=WEEKLY;BYMONTHDAY=1', 'FREQ=DAILY;BYMONTHDAY=1'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_rule(text)


class Generation(unittest.TestCase):
    def test_R10_dtstart_only_if_it_matches(self):
        self.assertEqual(dates('FREQ=WEEKLY;BYDAY=TU;COUNT=2', D(2024, 1, 3)), [D(2024, 1, 9), D(2024, 1, 16)])
        self.assertEqual(dates('FREQ=WEEKLY;BYDAY=MO,FR;COUNT=3', D(2024, 1, 3)),
                         [D(2024, 1, 5), D(2024, 1, 8), D(2024, 1, 12)])
        self.assertEqual(dates('FREQ=MONTHLY;BYMONTHDAY=1;COUNT=2', D(2024, 1, 15)), [D(2024, 2, 1), D(2024, 3, 1)])
        self.assertEqual(dates('FREQ=DAILY;COUNT=1', D(2024, 1, 3)), [D(2024, 1, 3)])

    def test_R11_daily(self):
        self.assertEqual(dates('FREQ=DAILY;INTERVAL=3;COUNT=4', D(2024, 2, 27)),
                         [D(2024, 2, 27), D(2024, 3, 1), D(2024, 3, 4), D(2024, 3, 7)])
        self.assertEqual(dates('FREQ=DAILY;INTERVAL=2;COUNT=3', D(2023, 12, 30)),
                         [D(2023, 12, 30), D(2024, 1, 1), D(2024, 1, 3)])

    def test_R12_weekly(self):
        self.assertEqual(dates('FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,TH;COUNT=4', D(2024, 1, 3)),
                         [D(2024, 1, 4), D(2024, 1, 15), D(2024, 1, 18), D(2024, 1, 29)])
        self.assertEqual(dates('FREQ=WEEKLY;COUNT=3', D(2024, 1, 4)), [D(2024, 1, 4), D(2024, 1, 11), D(2024, 1, 18)])
        self.assertEqual(dates('FREQ=WEEKLY;INTERVAL=3;BYDAY=SU;COUNT=3', D(2024, 1, 1)),
                         [D(2024, 1, 7), D(2024, 1, 28), D(2024, 2, 18)])

    def test_R13_monthly(self):
        self.assertEqual(dates('FREQ=MONTHLY;BYMONTHDAY=28,-1;UNTIL=20230331', D(2023, 1, 1)),
                         [D(2023, 1, 28), D(2023, 1, 31), D(2023, 2, 28), D(2023, 3, 28), D(2023, 3, 31)])
        self.assertEqual(dates('FREQ=MONTHLY;INTERVAL=2;BYMONTHDAY=31;COUNT=3', D(2024, 2, 15)),
                         [D(2024, 8, 31), D(2024, 10, 31), D(2024, 12, 31)])
        self.assertEqual(dates('FREQ=MONTHLY;COUNT=3', D(2024, 1, 30)), [D(2024, 1, 30), D(2024, 3, 30), D(2024, 4, 30)])
        self.assertEqual(dates('FREQ=MONTHLY;BYMONTHDAY=-1;COUNT=3', D(2024, 1, 15)),
                         [D(2024, 1, 31), D(2024, 2, 29), D(2024, 3, 31)])
        self.assertEqual(dates('FREQ=MONTHLY;BYMONTHDAY=-31;COUNT=3', D(2024, 1, 1)),
                         [D(2024, 1, 1), D(2024, 3, 1), D(2024, 5, 1)])
        self.assertEqual(dates('FREQ=MONTHLY;BYMONTHDAY=15,1;COUNT=3', D(2024, 1, 10)),
                         [D(2024, 1, 15), D(2024, 2, 1), D(2024, 2, 15)])

    def test_R14_until_inclusive(self):
        self.assertEqual(dates('FREQ=DAILY;UNTIL=20240105', D(2024, 1, 1)), [D(2024, 1, d) for d in range(1, 6)])
        self.assertEqual(dates('FREQ=WEEKLY;BYDAY=MO;UNTIL=20240115', D(2024, 1, 1)),
                         [D(2024, 1, 1), D(2024, 1, 8), D(2024, 1, 15)])
        self.assertEqual(dates('FREQ=DAILY;UNTIL=20231231', D(2024, 1, 1)), [])

    def test_R15_count_before_exdates(self):
        self.assertEqual(len(dates('FREQ=DAILY;COUNT=3', D(2024, 1, 1))), 3)
        event = Event('e', D(2024, 1, 1), 'FREQ=DAILY;COUNT=3', exdates=[D(2024, 1, 2)])
        self.assertEqual(expand(event, D(2024, 1, 1), D(2024, 2, 1)), [D(2024, 1, 1), D(2024, 1, 3)])
        event = Event('rent', D(2024, 1, 31), 'FREQ=MONTHLY;BYMONTHDAY=31;COUNT=3', exdates=[D(2024, 3, 31)])
        self.assertEqual(expand(event, D(2024, 1, 1), D(2025, 1, 1)), [D(2024, 1, 31), D(2024, 5, 31)])

    def test_R16_unbounded_and_before(self):
        first = list(islice(parse_rule('FREQ=DAILY').dates(D(2024, 1, 1)), 400))
        self.assertEqual(len(first), 400)
        self.assertEqual(first[-1], D(2024, 1, 1) + timedelta(days=399))
        self.assertEqual(dates('FREQ=DAILY;INTERVAL=2', D(2024, 1, 1), before=D(2024, 1, 6)),
                         [D(2024, 1, 1), D(2024, 1, 3), D(2024, 1, 5)])
        self.assertEqual(dates('FREQ=WEEKLY;BYDAY=MO,FR', D(2024, 1, 1), before=D(2024, 1, 8)),
                         [D(2024, 1, 1), D(2024, 1, 5)])
        never = bounded(lambda: dates('FREQ=MONTHLY;INTERVAL=12;BYMONTHDAY=30', D(2024, 2, 1), before=D(2200, 1, 1)))
        self.assertEqual(never, [])


class Expansion(unittest.TestCase):
    def test_R17_exdates(self):
        event = Event('e', D(2024, 1, 1), 'FREQ=WEEKLY;BYDAY=MO,WE', exdates=[D(2024, 1, 3), D(2024, 1, 9)])
        self.assertEqual(expand(event, D(2024, 1, 1), D(2024, 1, 15)), [D(2024, 1, 1), D(2024, 1, 8), D(2024, 1, 10)])

    def test_R18_half_open_window(self):
        event = Event('e', D(2024, 1, 1), 'FREQ=DAILY')
        self.assertEqual(expand(event, D(2024, 1, 3), D(2024, 1, 6)), [D(2024, 1, 3), D(2024, 1, 4), D(2024, 1, 5)])
        self.assertEqual(expand(event, D(2023, 12, 25), D(2024, 1, 3)), [D(2024, 1, 1), D(2024, 1, 2)])
        self.assertEqual(expand(event, D(2023, 12, 1), D(2024, 1, 1)), [])
        self.assertEqual(expand(event, D(2024, 1, 5), D(2024, 1, 5)), [])

    def test_R19_expansion_terminates(self):
        never = Event('never', D(2024, 2, 1), 'FREQ=MONTHLY;INTERVAL=12;BYMONTHDAY=30')
        self.assertEqual(bounded(lambda: expand(never, D(2030, 1, 1), D(2031, 1, 1))), [])
        daily = Event('daily', D(2024, 1, 1), 'FREQ=DAILY')
        self.assertEqual(bounded(lambda: expand(daily, D(2100, 1, 1), D(2100, 1, 3))), [D(2100, 1, 1), D(2100, 1, 2)])

    def test_R20_window_only_filters(self):
        e = Event('e', D(2024, 1, 1), 'FREQ=DAILY;COUNT=5')
        self.assertEqual(expand(e, D(2024, 1, 3), D(2024, 2, 1)), [D(2024, 1, 3), D(2024, 1, 4), D(2024, 1, 5)])
        e = Event('e', D(2024, 1, 1), 'FREQ=WEEKLY;INTERVAL=2')
        self.assertEqual(expand(e, D(2024, 1, 10), D(2024, 2, 1)), [D(2024, 1, 15), D(2024, 1, 29)])
        e = Event('e', D(2024, 1, 31), 'FREQ=MONTHLY')
        self.assertEqual(expand(e, D(2024, 3, 1), D(2024, 6, 1)), [D(2024, 3, 31), D(2024, 5, 31)])
        e = Event('e', D(2024, 1, 1), 'FREQ=MONTHLY;INTERVAL=3;BYMONTHDAY=1')
        self.assertEqual(expand(e, D(2024, 2, 15), D(2024, 12, 31)), [D(2024, 4, 1), D(2024, 7, 1), D(2024, 10, 1)])
        e = Event('e', D(2024, 1, 1), 'FREQ=DAILY;INTERVAL=3')
        self.assertEqual(expand(e, D(2024, 1, 5), D(2024, 1, 15)), [D(2024, 1, 7), D(2024, 1, 10), D(2024, 1, 13)])

    def test_R20_matches_full_expansion(self):
        events = [Event('a', D(2024, 1, 3), 'FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,TH;COUNT=9', exdates=[D(2024, 1, 18)]),
                  Event('b', D(2024, 1, 31), 'FREQ=MONTHLY;BYMONTHDAY=31,-2;COUNT=7'),
                  Event('c', D(2024, 1, 2), 'FREQ=DAILY;INTERVAL=5;UNTIL=20240320')]
        end = D(2024, 12, 31)
        for event in events:
            full = expand(event, event.dtstart, end)
            for offset in (1, 9, 17, 40, 75):
                ws = event.dtstart + timedelta(days=offset)
                with self.subTest(event=event.name, window_start=ws):
                    self.assertEqual(expand(event, ws, end), [d for d in full if d >= ws])


def once(name, day, minute, duration):
    return Event(name, day, 'FREQ=DAILY;COUNT=1', start_minute=minute, duration=duration)


class Conflicts(unittest.TestCase):
    def test_R21_overlapping_instances(self):
        a = Event('a', D(2024, 1, 1), 'FREQ=DAILY;COUNT=5', start_minute=540, duration=60)
        b = Event('b', D(2024, 1, 1), 'FREQ=WEEKLY;BYDAY=WE', start_minute=570, duration=30)
        self.assertEqual(find_conflicts([a, b], D(2024, 1, 1), D(2024, 1, 8)),
                         [Conflict('a', D(2024, 1, 3), 'b', D(2024, 1, 3))])

    def test_R22_touching_is_not_a_conflict(self):
        d = D(2024, 1, 1)
        self.assertEqual(find_conflicts([once('a', d, 540, 60), once('b', d, 600, 30)], d, d + timedelta(1)), [])
        self.assertEqual(find_conflicts([once('a', d, 540, 60), once('b', d, 599, 30)], d, d + timedelta(1)),
                         [Conflict('a', d, 'b', d)])

    def test_R23_past_midnight(self):
        d1, d2 = D(2024, 1, 1), D(2024, 1, 2)
        late = once('late', d1, 23 * 60, 120)
        early = once('early', d2, 30, 30)
        dawn = once('dawn', d2, 60, 30)
        self.assertEqual(find_conflicts([early, dawn, late], d1, D(2024, 1, 5)), [Conflict('late', d1, 'early', d2)])

    def test_R24_same_event_never_conflicts(self):
        marathon = Event('marathon', D(2024, 1, 1), 'FREQ=DAILY;COUNT=3', start_minute=600, duration=2000)
        self.assertEqual(find_conflicts([marathon], D(2024, 1, 1), D(2024, 1, 10)), [])
        x = once('x', D(2024, 1, 2), 0, 30)
        self.assertEqual(find_conflicts([x, marathon], D(2024, 1, 1), D(2024, 1, 10)),
                         [Conflict('marathon', D(2024, 1, 1), 'x', D(2024, 1, 2))])

    def test_R25_pair_order(self):
        d = D(2024, 1, 1)
        nxt = d + timedelta(1)
        self.assertEqual(find_conflicts([once('beta', d, 540, 60), once('alpha', d, 540, 60)], d, nxt),
                         [Conflict('alpha', d, 'beta', d)])
        self.assertEqual(find_conflicts([once('alpha', d, 600, 60), once('zeta', d, 570, 60)], d, nxt),
                         [Conflict('zeta', d, 'alpha', d)])

    def test_R26_result_order(self):
        d = D(2024, 1, 1)
        events = [once('w', d, 600, 30), once('z', d, 550, 10), once('y', d, 540, 20), once('x', d, 540, 160)]
        self.assertEqual(find_conflicts(events, d, d + timedelta(1)),
                         [Conflict('x', d, 'y', d), Conflict('x', d, 'z', d),
                          Conflict('y', d, 'z', d), Conflict('x', d, 'w', d)])
        a = Event('a', d, 'FREQ=DAILY;COUNT=2', start_minute=540, duration=60)
        b = Event('b', d, 'FREQ=DAILY;COUNT=2', start_minute=550, duration=10)
        self.assertEqual(find_conflicts([b, a], d, D(2024, 2, 1)),
                         [Conflict('a', d, 'b', d), Conflict('a', D(2024, 1, 2), 'b', D(2024, 1, 2))])

    def test_R26_mixed_days_sorted_by_absolute_start(self):
        d1, d2 = D(2024, 1, 1), D(2024, 1, 2)
        late = once('late', d1, 22 * 60, 240)
        early = once('early', d2, 60, 30)
        morning = once('morning', d2, 60, 60)
        evening = once('evening', d1, 21 * 60 + 30, 45)
        self.assertEqual(find_conflicts([morning, early, late, evening], d1, D(2024, 1, 3)),
                         [Conflict('evening', d1, 'late', d1), Conflict('late', d1, 'early', d2),
                          Conflict('late', d1, 'morning', d2), Conflict('early', d2, 'morning', d2)])

    def test_R27_duplicate_names(self):
        d = D(2024, 1, 1)
        with self.assertRaises(ValueError):
            find_conflicts([once('a', d, 0, 10), once('a', d, 600, 10)], d, d + timedelta(1))


if __name__ == '__main__':
    unittest.main()
