# recur: recurring events, expansion and conflicts

The `recur` package expands recurring calendar events and finds conflicts between them.

- `recur/datemath.py`: calendar arithmetic.
- `recur/rule.py`: recurrence rules (`parse_rule`, `Rule`, `Rule.dates`).
- `recur/expand.py`: events, exceptions and window expansion (`Event`, `expand`).
- `recur/conflicts.py`: overlap detection (`Conflict`, `find_conflicts`).

Dates are `datetime.date` values (proleptic Gregorian calendar, no time zones). A time of
day is an integer number of minutes after midnight. Weekday numbers follow
`date.weekday()`: Monday is 0 and Sunday is 6.

## Date math (`recur/datemath.py`)

R1. `days_in_month(year, month)` returns the number of days in that month using the Gregorian leap-year rule: a year is a leap year if it is divisible by 4, except years divisible by 100 that are not divisible by 400 (2000 is a leap year, 1900 is not).
R2. `add_months(year, month, n)` returns the `(year, month)` pair `n` calendar months later, for any `n >= 0` (for example `add_months(2024, 11, 3) == (2025, 2)`).
R3. `resolve_monthday(year, month, k)` turns a month-day value into a `date` or `None`. A `k` from 1 to 31 is that day of the month; a `k` from -1 to -31 counts back from the end of the month (-1 is the last day, -2 the day before it). If the month has no such day (for example `31` or `-31` in a 30-day month) the result is `None`. It never clamps to a nearby day.
R4. `week_start(d)` returns the Monday on or before `d`.
R5. `abs_minute(d, minute)` returns `d.toordinal() * 1440 + minute`. All overlap comparisons (R21 to R24) use absolute minutes.

## Rules (`recur/rule.py`)

`parse_rule(text)` turns a rule string such as `FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,TH;COUNT=6`
into a `Rule` with the attributes `freq`, `interval`, `count`, `until`, `byday` and
`bymonthday`.

R6. The string is a `;`-separated list of `KEY=VALUE` parts. Keys and values are case-sensitive. The keys are `FREQ` (required: `DAILY`, `WEEKLY` or `MONTHLY`), `INTERVAL` (positive integer, default 1), `COUNT` (positive integer, default `None`), `UNTIL` (a date written `YYYYMMDD`, default `None`), `BYDAY` (comma-separated day codes `MO`, `TU`, `WE`, `TH`, `FR`, `SA`, `SU`) and `BYMONTHDAY` (comma-separated integers from -31 to -1 or 1 to 31). `byday` is the sorted tuple of distinct weekday numbers and `bymonthday` the sorted tuple of distinct integers; each is `None` when its key is absent.
R7. `parse_rule` raises `ValueError` for: an empty part (including one left by a trailing `;`) or a part without `=`, a missing `FREQ`, an unknown key, a repeated key, a `FREQ` value other than the three above, an `INTERVAL` or `COUNT` that is not a positive integer written in ASCII digits, an `UNTIL` that is not 8 ASCII digits forming a real date, an unknown day code, and a `BYMONTHDAY` value that is not an integer, is 0, or is outside -31..31.
R8. A rule that has both `COUNT` and `UNTIL` raises `ValueError`.
R9. `BYDAY` is allowed only with `FREQ=WEEKLY` and `BYMONTHDAY` only with `FREQ=MONTHLY`; any other combination raises `ValueError`.

## Generating dates (`Rule.dates`)

`rule.dates(dtstart, before=None)` is a generator of instance dates in strictly ascending
order. The rule is anchored at `dtstart`: intervals, defaults and `COUNT` are all measured
from it.

R10. No date earlier than `dtstart` is generated. `dtstart` itself is generated only if it matches the rule; it is not automatically an instance.
R11. `DAILY`: the dates `dtstart + k * INTERVAL` days for k = 0, 1, 2, ...
R12. `WEEKLY`: weeks run Monday to Sunday. The week containing `dtstart` is week 0, and week `w` is used when `w % INTERVAL == 0`. In a used week the candidates are the days listed in `BYDAY`; without `BYDAY` the only day is `dtstart`'s weekday.
R13. `MONTHLY`: `dtstart`'s month is month 0, and month `m` is used when `m % INTERVAL == 0`; months are counted in calendar months whether or not they produce a date. In a used month the candidates are the `BYMONTHDAY` values resolved with `resolve_monthday` (R3); `None` results are skipped and dates that coincide are produced once (in February 2023, `BYMONTHDAY=28,-1` gives one date, the 28th). Without `BYMONTHDAY` the only value is `dtstart`'s day of the month, so a rule starting on the 31st skips months that have no 31st.
R14. `UNTIL` is inclusive: a date equal to `UNTIL` is generated, later dates are not.
R15. `COUNT` is the number of dates generated, counted in order from `dtstart`. Exceptions are applied afterwards: a date removed by `exdates` (R17) still uses up one of the `COUNT`.
R16. Without `COUNT` or `UNTIL` the generator is unbounded. When `before` is given, only dates earlier than `before` are generated, and the generator stops once no further date could be earlier than `before`, even if the rule never produces a date (for example `FREQ=MONTHLY;INTERVAL=12;BYMONTHDAY=30` starting in February).

## Events and expansion (`recur/expand.py`)

`Event(name, dtstart, rule, start_minute=0, duration=60, exdates=())`: `rule` is a rule
string or a `Rule`, `start_minute` is from 0 to 1439 and `duration` is a positive number of
minutes. A duration may run past midnight, so an instance can end on a later date than the
one it starts on.

R17. `exdates` lists dates removed from the event's instances. An exdate that is not an instance has no effect.
R18. `expand(event, window_start, window_end)` returns the instance dates `d` with `window_start <= d < window_end`, in ascending order.
R19. `expand` terminates for every rule, including unbounded rules and rules that never produce a date in or after the window; it returns `[]` when there is none.
R20. The window only filters. Expanding a window that starts after `dtstart` returns exactly the dates that expanding from `dtstart` returns inside that window: `COUNT`, `INTERVAL` alignment and the default weekday or month day still come from `dtstart`.

## Conflicts (`recur/conflicts.py`)

An instance on date `d` occupies the half-open interval of absolute minutes
`[abs_minute(d, start_minute), abs_minute(d, start_minute) + duration)`.

R21. `find_conflicts(events, window_start, window_end)` takes the instances `expand` returns for each event over the window and reports every pair of instances of two different events whose intervals overlap by at least one minute.
R22. Intervals that only touch (one ends at the minute the other starts) do not conflict.
R23. An instance that runs past midnight conflicts with the instances on later dates that it overlaps.
R24. Instances of the same event never conflict with each other, even when they overlap.
R25. Each conflict is a `Conflict(first, first_date, second, second_date)` holding event names and instance dates. `first` is the instance with the earlier absolute start minute (`abs_minute(d, start_minute)`, not the minute of the day); when the starts are equal, it is the instance of the event whose name sorts first.
R26. The result lists each conflicting pair once, sorted by first's absolute start minute, then second's absolute start minute, then first's name, then second's name.
R27. Event names must be unique: `find_conflicts` raises `ValueError` if two events share a name.
