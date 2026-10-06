import unittest
from datetime import date

from recur.conflicts import Conflict, find_conflicts
from recur.datemath import days_in_month
from recur.expand import Event, expand
from recur.rule import parse_rule


class Public(unittest.TestCase):
    def test_days_in_month(self):
        self.assertEqual(days_in_month(2024, 2), 29)
        self.assertEqual(days_in_month(2023, 2), 28)
        self.assertEqual(days_in_month(2023, 4), 30)

    def test_parse_rule(self):
        rule = parse_rule('FREQ=WEEKLY;INTERVAL=2;BYDAY=TH,MO;COUNT=6')
        self.assertEqual(rule.freq, 'WEEKLY')
        self.assertEqual(rule.interval, 2)
        self.assertEqual(rule.count, 6)
        self.assertEqual(rule.byday, (0, 3))
        self.assertIsNone(rule.until)

    def test_daily_interval(self):
        event = Event('standup', date(2024, 1, 1), 'FREQ=DAILY;INTERVAL=2;COUNT=3')
        self.assertEqual(expand(event, date(2024, 1, 1), date(2024, 2, 1)),
                         [date(2024, 1, 1), date(2024, 1, 3), date(2024, 1, 5)])

    def test_weekly_byday(self):
        event = Event('gym', date(2024, 1, 1), 'FREQ=WEEKLY;BYDAY=MO,WE;COUNT=4')
        self.assertEqual(expand(event, date(2024, 1, 1), date(2024, 3, 1)),
                         [date(2024, 1, 1), date(2024, 1, 3), date(2024, 1, 8), date(2024, 1, 10)])

    def test_monthly_on_the_31st_skips_short_months(self):
        event = Event('rent', date(2024, 1, 31), 'FREQ=MONTHLY;BYMONTHDAY=31;COUNT=4')
        self.assertEqual(expand(event, date(2024, 1, 1), date(2025, 1, 1)),
                         [date(2024, 1, 31), date(2024, 3, 31), date(2024, 5, 31), date(2024, 7, 31)])

    def test_same_day_conflict(self):
        a = Event('review', date(2024, 1, 1), 'FREQ=DAILY;COUNT=2', start_minute=540, duration=60)
        b = Event('lunch', date(2024, 1, 2), 'FREQ=DAILY;COUNT=1', start_minute=570, duration=60)
        self.assertEqual(find_conflicts([a, b], date(2024, 1, 1), date(2024, 1, 8)),
                         [Conflict('review', date(2024, 1, 2), 'lunch', date(2024, 1, 2))])


if __name__ == '__main__':
    unittest.main()
