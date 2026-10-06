"""Overlap detection between the instances of several events."""
from collections import defaultdict
from typing import NamedTuple
from datetime import date

from .expand import expand


class Conflict(NamedTuple):
    first: str
    first_date: date
    second: str
    second_date: date


def _slots_by_date(events, window_start, window_end):
    """{date: [(start, name, end), ...]} with minutes counted from that date's midnight."""
    by_date = defaultdict(list)
    for event in events:
        for d in expand(event, window_start, window_end):
            start = event.start_minute
            by_date[d].append((start, event.name, start + event.duration))
    return by_date


def find_conflicts(events, window_start, window_end):
    names = [event.name for event in events]
    if len(set(names)) != len(names):
        raise ValueError('event names must be unique')
    by_date = _slots_by_date(events, window_start, window_end)
    found = []
    for d in sorted(by_date):
        slots = sorted(by_date[d])
        day = []
        for i, a in enumerate(slots):
            for b in slots[i + 1:]:
                if b[0] >= a[2]:
                    break  # slots are sorted by start: nothing later overlaps a
                if b[1] == a[1]:
                    continue
                day.append(((a[0], b[0], a[1], b[1]), Conflict(a[1], d, b[1], d)))
        day.sort(key=lambda item: item[0])
        found.extend(conflict for _, conflict in day)
    return found
