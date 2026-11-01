"""Rest rules."""
from __future__ import annotations

from datetime import date

from roster.intervals import Interval

DAY_MINUTES = 1440


def _absolute(day: date, minute: int) -> int:
    return day.toordinal() * DAY_MINUTES + minute


def rest_violations(shifts: list[tuple[date, Interval]], min_rest: int) -> list[tuple[date, date]]:
    ordered = sorted(shifts, key=lambda item: (item[0], item[1].start))
    found: list[tuple[date, date]] = []
    for (day, shift), (next_day, following) in zip(ordered, ordered[1:]):
        rest = _absolute(next_day, following.start) - _absolute(day, shift.end)
        if rest < min_rest:
            found.append((day, next_day))
    return found
