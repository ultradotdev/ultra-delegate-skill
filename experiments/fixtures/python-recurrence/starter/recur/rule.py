"""Recurrence rules: parsing and date generation."""
from dataclasses import dataclass
from datetime import date, timedelta

from . import datemath

FREQS = ('DAILY', 'WEEKLY', 'MONTHLY')
KEYS = ('FREQ', 'INTERVAL', 'COUNT', 'UNTIL', 'BYDAY', 'BYMONTHDAY')


@dataclass(frozen=True)
class Rule:
    freq: str
    interval: int = 1
    count: int | None = None
    until: date | None = None
    byday: tuple | None = None
    bymonthday: tuple | None = None

    def dates(self, dtstart, before=None, skip=()):
        """Instance dates in ascending order, anchored at dtstart.

        Dates listed in `skip` are left out of the output.
        """
        produced = 0
        for d in self._candidates(dtstart, self._limit(before)):
            if d in skip:
                continue
            yield d
            produced += 1
            if self.count is not None and produced >= self.count:
                return

    def _limit(self, before):
        """The first date that can never be generated, or None when unbounded."""
        limits = []
        if before is not None:
            limits.append(before)
        if self.until is not None:
            if self.until >= date.max:
                return before
            limits.append(self.until + timedelta(days=1))
        return min(limits) if limits else None

    def _candidates(self, dtstart, limit):
        if self.freq == 'DAILY':
            yield from self._daily(dtstart, limit)
        elif self.freq == 'WEEKLY':
            yield from self._weekly(dtstart, limit)
        else:
            yield from self._monthly(dtstart, limit)

    def _daily(self, dtstart, limit):
        step = timedelta(days=self.interval)
        d = dtstart
        while limit is None or d < limit:
            yield d
            try:
                d += step
            except OverflowError:
                return

    def _weekly(self, dtstart, limit):
        days = self.byday or (dtstart.weekday(),)
        week = datemath.week_start(dtstart)
        step = timedelta(weeks=self.interval)
        while limit is None or week < limit:
            for wd in days:
                d = week + timedelta(days=wd)
                if d < dtstart:
                    continue
                if limit is not None and d >= limit:
                    return
                yield d
            try:
                week += step
            except OverflowError:
                return

    def _monthly(self, dtstart, limit):
        values = self.bymonthday or (dtstart.day,)
        year, month = dtstart.year, dtstart.month
        while year <= date.max.year:
            if limit is not None and datemath.first_of_month(year, month) >= limit:
                return
            resolved = {datemath.resolve_monthday(year, month, k) for k in values}
            for d in sorted(d for d in resolved if d is not None):
                if d < dtstart:
                    continue
                if limit is not None and d >= limit:
                    return
                yield d
            year, month = datemath.add_months(year, month, self.interval)


def _positive(key, text):
    if not (text.isascii() and text.isdigit()) or int(text) <= 0:
        raise ValueError(f'{key} must be a positive integer: {text!r}')
    return int(text)


def _monthday(text):
    digits = text[1:] if text.startswith('-') else text
    if not (digits.isascii() and digits.isdigit()):
        raise ValueError(f'invalid BYMONTHDAY value: {text!r}')
    value = int(text)
    if value == 0 or not -31 <= value <= 31:
        raise ValueError(f'BYMONTHDAY out of range: {text!r}')
    return value


def parse_rule(text):
    fields = {}
    for part in text.split(';'):
        key, sep, value = part.partition('=')
        if not sep or not key or not value:
            raise ValueError(f'malformed rule part: {part!r}')
        if key not in KEYS:
            raise ValueError(f'unknown key: {key!r}')
        if key in fields:
            raise ValueError(f'repeated key: {key!r}')
        fields[key] = value
    if 'FREQ' not in fields:
        raise ValueError('FREQ is required')
    freq = fields['FREQ']
    if freq not in FREQS:
        raise ValueError(f'unsupported FREQ: {freq!r}')
    interval = _positive('INTERVAL', fields['INTERVAL']) if 'INTERVAL' in fields else 1
    count = _positive('COUNT', fields['COUNT']) if 'COUNT' in fields else None
    until = datemath.parse_ymd(fields['UNTIL']) if 'UNTIL' in fields else None
    if count is not None and until is not None:
        raise ValueError('COUNT and UNTIL are mutually exclusive')
    byday = None
    if 'BYDAY' in fields:
        if freq != 'WEEKLY':
            raise ValueError('BYDAY requires FREQ=WEEKLY')
        codes = fields['BYDAY'].split(',')
        if any(code not in datemath.DAY_CODES for code in codes):
            raise ValueError(f'invalid BYDAY: {fields["BYDAY"]!r}')
        byday = tuple(sorted({datemath.DAY_CODES.index(code) for code in codes}))
    bymonthday = None
    if 'BYMONTHDAY' in fields:
        if freq != 'MONTHLY':
            raise ValueError('BYMONTHDAY requires FREQ=MONTHLY')
        bymonthday = tuple(sorted({_monthday(v) for v in fields['BYMONTHDAY'].split(',')}))
    return Rule(freq, interval, count, until, byday, bymonthday)
