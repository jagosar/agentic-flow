"""Shift text."""
from __future__ import annotations

from roster.intervals import Interval

DAY_MINUTES = 1440


def _minutes(clock: str) -> int:
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)


def parse_shift(text: str) -> Interval:
    try:
        start_text, end_text = text.split("-")
        start, end = _minutes(start_text), _minutes(end_text)
    except ValueError:
        raise ValueError(f"invalid shift: {text!r}") from None
    if end < start:
        end += DAY_MINUTES
    return Interval(start, end)


def _clock(minute: int) -> str:
    minute %= DAY_MINUTES
    return f"{minute // 60:02d}:{minute % 60:02d}"


def format_shift(shift: Interval) -> str:
    return f"{_clock(shift.start)}-{_clock(shift.end)}"
