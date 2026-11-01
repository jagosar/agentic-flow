"""Shift text."""
from __future__ import annotations

import re

from roster.intervals import Interval

DAY_MINUTES = 1440
SHIFT_PATTERN = re.compile(r"(\d{2}):(\d{2})-(\d{2}):(\d{2})")


def parse_shift(text: str) -> Interval:
    match = SHIFT_PATTERN.fullmatch(text)
    if not match:
        raise ValueError(f"invalid shift: {text!r}")
    start_h, start_m, end_h, end_m = (int(g) for g in match.groups())
    if start_h > 23 or end_h > 23 or start_m > 59 or end_m > 59:
        raise ValueError(f"invalid shift: {text!r}")
    start = start_h * 60 + start_m
    end = end_h * 60 + end_m
    if end == start:
        raise ValueError(f"empty shift: {text!r}")
    if end < start:
        end += DAY_MINUTES
    return Interval(start, end)


def _clock(minute: int) -> str:
    minute %= DAY_MINUTES
    return f"{minute // 60:02d}:{minute % 60:02d}"


def format_shift(shift: Interval) -> str:
    return f"{_clock(shift.start)}-{_clock(shift.end)}"
