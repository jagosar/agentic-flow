"""Half-open intervals of minutes."""
from __future__ import annotations

from dataclasses import dataclass

MAX_MINUTE = 2880


@dataclass(frozen=True)
class Interval:
    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end > MAX_MINUTE or self.start >= self.end:
            raise ValueError(f"invalid interval: [{self.start}, {self.end})")


def overlaps(a: Interval, b: Interval) -> bool:
    return a.start < b.end and b.start < a.end


def merge(intervals: list[Interval]) -> list[Interval]:
    merged: list[Interval] = []
    for item in sorted(intervals, key=lambda i: (i.start, i.end)):
        if merged and item.start <= merged[-1].end:
            merged[-1] = Interval(merged[-1].start, max(merged[-1].end, item.end))
        else:
            merged.append(item)
    return merged


def gaps(intervals: list[Interval], window: Interval) -> list[Interval]:
    result: list[Interval] = []
    cursor = window.start
    for item in merge(intervals):
        if item.start >= window.end:
            break
        if item.start > cursor:
            result.append(Interval(cursor, item.start))
        cursor = max(cursor, item.end)
    if cursor < window.end:
        result.append(Interval(cursor, window.end))
    return result
