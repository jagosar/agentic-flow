"""Who works when."""
from __future__ import annotations

from datetime import date

from roster.intervals import Interval, gaps
from roster.shifts import parse_shift


class ConflictError(ValueError):
    pass


class Schedule:
    def __init__(self) -> None:
        self._shifts: dict[str, list[tuple[date, Interval]]] = {}

    def assign(self, person: str, day: date, shift_text: str) -> Interval:
        shift = parse_shift(shift_text)
        self._shifts.setdefault(person, []).append((day, shift))
        return shift

    def shifts(self, person: str) -> list[tuple[date, Interval]]:
        found = self._shifts.get(person, [])
        return sorted(found, key=lambda item: (item[0], item[1].start))

    def coverage_gaps(self, day: date, window: Interval) -> list[Interval]:
        worked = [s for items in self._shifts.values() for d, s in items if d == day]
        return gaps(worked, window)

    def minutes(self, person: str) -> int:
        return sum(s.end - s.start for _, s in self._shifts.get(person, []))
