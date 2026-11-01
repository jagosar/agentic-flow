"""Dates and calendar months."""
from __future__ import annotations

import datetime
import re

_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def parse_date(text: str) -> datetime.date:
    if not _ISO_DATE.fullmatch(text):
        raise ValueError(f"invalid date: {text!r}")
    return datetime.date.fromisoformat(text)


def month_end(day: datetime.date) -> datetime.date:
    first_next = (day.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    return first_next - datetime.timedelta(days=1)


def months_between(
    start: datetime.date, end: datetime.date
) -> list[tuple[datetime.date, datetime.date]]:
    if start > end:
        raise ValueError("start is after end")
    periods = []
    first = start
    while first <= end:
        periods.append((first, min(month_end(first), end)))
        first = month_end(first) + datetime.timedelta(days=1)
    return periods
