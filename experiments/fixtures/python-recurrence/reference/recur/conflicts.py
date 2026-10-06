"""Overlap detection between the instances of several events."""
from typing import NamedTuple
from datetime import date

from .datemath import abs_minute
from .expand import expand


class Conflict(NamedTuple):
    first: str
    first_date: date
    second: str
    second_date: date


def _slots(events, window_start, window_end):
    """(start, name, date, end) for every instance in the window, in absolute minutes."""
    slots = []
    for event in events:
        for d in expand(event, window_start, window_end):
            start = abs_minute(d, event.start_minute)
            slots.append((start, event.name, d, start + event.duration))
    slots.sort()
    return slots


def find_conflicts(events, window_start, window_end):
    names = [event.name for event in events]
    if len(set(names)) != len(names):
        raise ValueError('event names must be unique')
    slots = _slots(events, window_start, window_end)
    found = []
    for i, a in enumerate(slots):
        for b in slots[i + 1:]:
            if b[0] >= a[3]:
                break  # slots are sorted by start: nothing later overlaps a
            if b[1] == a[1]:
                continue
            found.append(((a[0], b[0], a[1], b[1]), Conflict(a[1], a[2], b[1], b[2])))
    found.sort(key=lambda item: item[0])
    return [conflict for _, conflict in found]
