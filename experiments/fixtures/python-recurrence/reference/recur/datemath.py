"""Calendar arithmetic on datetime.date values (proleptic Gregorian, no time zones)."""
from datetime import date, timedelta

MINUTES_PER_DAY = 1440
DAY_CODES = ('MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU')


def is_leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def days_in_month(year, month):
    if month == 2:
        return 29 if is_leap(year) else 28
    if month in (4, 6, 9, 11):
        return 30
    return 31


def add_months(year, month, n):
    """The (year, month) pair n calendar months after (year, month)."""
    index = year * 12 + (month - 1) + n
    return index // 12, index % 12 + 1


def first_of_month(year, month):
    return date(year, month, 1)


def resolve_monthday(year, month, k):
    """Day k of the month (negative k counts from the end), or None if there is none."""
    dim = days_in_month(year, month)
    if 1 <= k <= dim:
        return date(year, month, k)
    if -dim <= k <= -1:
        return date(year, month, dim + k + 1)
    return None


def week_start(d):
    """The Monday on or before d."""
    return d - timedelta(days=d.weekday())


def abs_minute(d, minute):
    """Minutes since the proleptic epoch for minute `minute` of date `d`."""
    return d.toordinal() * MINUTES_PER_DAY + minute


def parse_ymd(text):
    """Parse YYYYMMDD into a date; raise ValueError for anything else."""
    if len(text) != 8 or not (text.isascii() and text.isdigit()):
        raise ValueError(f'invalid date: {text!r}')
    return date(int(text[:4]), int(text[4:6]), int(text[6:]))
