"""Events with recurrence rules and exceptions, expanded over a date window."""
from dataclasses import dataclass, field
from datetime import date

from .rule import Rule, parse_rule


@dataclass(frozen=True)
class Event:
    name: str
    dtstart: date
    rule: Rule
    start_minute: int = 0
    duration: int = 60
    exdates: frozenset = field(default_factory=frozenset)

    def __post_init__(self):
        if isinstance(self.rule, str):
            object.__setattr__(self, 'rule', parse_rule(self.rule))
        object.__setattr__(self, 'exdates', frozenset(self.exdates))
        if not 0 <= self.start_minute < 1440:
            raise ValueError(f'start_minute out of range: {self.start_minute}')
        if self.duration <= 0:
            raise ValueError(f'duration must be positive: {self.duration}')


def expand(event, window_start, window_end):
    """Instance dates d of the event with window_start <= d < window_end."""
    if window_end <= window_start:
        return []
    # Nothing before the window is needed, so generation starts at whichever
    # comes later: the event's first day or the window's first day.
    anchor = max(event.dtstart, window_start)
    return list(event.rule.dates(anchor, before=window_end, skip=event.exdates))
