> Brief for AT: the parts of architecture.md this agent needs. Read architecture.md only if this brief points to something it does not contain.

# Architecture: roster
Type: feature · Size: standard

## 1. Goal
A shift-scheduling library: time intervals in minutes, shift text such as `09:00-17:30`, a schedule of who works when, and a rest rule between shifts. It has no dependencies and no persistence: everything is in memory.

## 2. Scope
### Included
- `roster/intervals.py`: `Interval`, `overlaps`, `merge` and `gaps`.
- `roster/shifts.py`: `parse_shift` and `format_shift`.
- `roster/schedule.py`: `ConflictError` and `Schedule`.
- `roster/rules.py`: `rest_violations`.
### Excluded (non-goals)
- Persistence, time zones, user interfaces, shifts longer than two days.

## 3. Stack
Python 3.9+, standard library only. Tests with `unittest`.
- Tests: `python3 -m unittest discover -s tests`
- Acceptance: `python3 -m unittest discover -s acceptance`

## 4b. Existing code context
| What an implementer needs to know | Where it is | Pattern or rule |
|---|---|---|
| The package and its version | `roster/__init__.py:1-3` | Module docstring, then `__version__` |
| Test style | `tests/test_version.py:1-15` | `unittest.TestCase`, one behaviour per test |

## 5. Data model
An `Interval` is a frozen dataclass. A `Schedule` keeps the shifts of each person in a private structure. Times are `int` minutes since midnight; days are `datetime.date`.

## 6. Contracts between modules
**`roster/intervals.py`** (WP-01)
```python
@dataclass(frozen=True)
class Interval:
    start: int
    end: int

def overlaps(a: Interval, b: Interval) -> bool: ...
def merge(intervals: list[Interval]) -> list[Interval]: ...
def gaps(intervals: list[Interval], window: Interval) -> list[Interval]: ...
```
- An interval is half-open, `[start, end)`. `start < end` and both are in `0..2880`: an overnight shift ends on the next day, so its `end` is above 1440. Anything else raises `ValueError` at construction.
- `overlaps` is true when the two intervals share at least one minute. Touching intervals (`[540, 720)` and `[720, 900)`) do not overlap.
- `merge` returns the intervals sorted by `start`, where overlapping or touching intervals become one. The input list is not changed.
- `gaps` returns the parts of `window` that no interval covers, sorted. The intervals are merged first.

**`roster/shifts.py`** (WP-02)
```python
def parse_shift(text: str) -> Interval: ...
def format_shift(shift: Interval) -> str: ...
```
- `parse_shift("09:00-17:30")` is `Interval(540, 1050)`. When the end clock is earlier than the start clock the shift ends on the next day: `parse_shift("22:00-06:00")` is `Interval(1320, 1800)`.
- The text is exactly `HH:MM-HH:MM`, two digits each, hours `00`-`23`, minutes `00`-`59`. Anything else raises `ValueError`, as does a shift whose start and end are the same time.
- `format_shift` is the inverse; an end past midnight prints as its clock time (`Interval(1320, 1800)` is `"22:00-06:00"`).

**`roster/schedule.py`** (WP-03)
```python
class ConflictError(ValueError): ...

class Schedule:                      # Schedule() takes no arguments
    def assign(self, person: str, day: date, shift_text: str) -> Interval: ...
    def shifts(self, person: str) -> list[tuple[date, Interval]]: ...
    def coverage_gaps(self, day: date, window: Interval) -> list[Interval]: ...
    def minutes(self, person: str) -> int: ...
```
- `assign` parses the shift with `parse_shift`, stores it for the person on that day and returns the interval. Names are stripped and must be non-empty (`ValueError`). If the new shift overlaps a shift of the same person on the same day it raises `ConflictError`. A failed `assign` changes nothing.
- `shifts` returns the person's shifts sorted by day, then by start; an unknown person has none.
- `coverage_gaps` returns the parts of `window` that no person works on that `day`, merged and sorted.
- `minutes` is the sum of the lengths of all the person's shifts; an unknown person has 0.

**`roster/rules.py`** (WP-04)
```python
def rest_violations(shifts: list[tuple[date, Interval]], min_rest: int) -> list[tuple[date, date]]: ...
```
- Returns the `(day, day)` pairs of consecutive shifts of the list, in `(day, start)` order, with insufficient rest between them. `min_rest` is in minutes. The input list is not changed.

## 7. Conventions
- English; small functions; type annotations on public signatures; `from __future__ import annotations` for Python 3.9.
- Errors: `ValueError` for invalid arguments. Validate before changing any state.
- Times are integer minutes; days are `datetime.date`.

## 8. Work packages and acceptance criteria
### Acceptance criteria
- AC-001 · Overlap of two intervals
  - Scenario: no state.
  - Action: `overlaps` of `[540, 720)` with `[600, 900)`, and of `[540, 600)` with `[700, 900)`.
  - Expected: `True` and `False`.
  - Must not: report a gap between two intervals as an overlap.
  - Check: `acceptance/test_intervals.py::test_overlap_of_two_intervals`
  - WP: WP-01
- AC-002 · Merging intervals
  - Scenario: no state.
  - Action: `merge` of `[700, 900)`, `[540, 720)` and `[1000, 1100)`.
  - Expected: `[540, 900)` and `[1000, 1100)`, in that order.
  - Must not: change the list it receives.
  - Check: `acceptance/test_intervals.py::test_merging_intervals`
  - WP: WP-01
- AC-003 · Gaps in a window
  - Scenario: no state.
  - Action: `gaps` of `[600, 700)` and `[800, 900)` over the window `[540, 1000)`.
  - Expected: `[540, 600)`, `[700, 800)` and `[900, 1000)`.
  - Must not: return a part of the window that an interval covers.
  - Check: `acceptance/test_intervals.py::test_gaps_in_a_window`
  - WP: WP-01
- AC-004 · Shift text becomes an interval
  - Scenario: no state.
  - Action: `parse_shift` of `"09:00-17:30"` and `"22:00-06:00"`.
  - Expected: `Interval(540, 1050)` and `Interval(1320, 1800)`.
  - Must not: end the overnight shift before it starts.
  - Check: `acceptance/test_shifts.py::test_shift_text_becomes_an_interval`
  - WP: WP-02
- AC-005 · An interval becomes shift text
  - Scenario: no state.
  - Action: `format_shift` of `Interval(540, 1050)` and `Interval(1320, 1800)`.
  - Expected: `"09:00-17:30"` and `"22:00-06:00"`.
  - Must not: print a clock time above `23:59`.
  - Check: `acceptance/test_shifts.py::test_an_interval_becomes_shift_text`
  - WP: WP-02
- AC-006 · Nonsense shift text is rejected
  - Scenario: no state.
  - Action: `parse_shift` of `""`, `"abc"` and `"25:00-26:00"`.
  - Expected: each raises `ValueError`.
  - Must not: return an interval for text that is not a shift.
  - Check: `acceptance/test_shifts.py::test_nonsense_shift_text_is_rejected`
  - WP: WP-02
- AC-007 · Shifts are listed in order
  - Scenario: an empty `Schedule`, then Ann assigned `"09:00-12:00"` on 2026-01-06, `"14:00-18:00"` on 2026-01-05 and `"06:00-10:00"` on 2026-01-05.
  - Action: `shifts("Ann")`.
  - Expected: the three shifts, 2026-01-05 `[360, 600)`, 2026-01-05 `[840, 1080)`, 2026-01-06 `[540, 720)`.
  - Must not: return them in the order they were assigned.
  - Check: `acceptance/test_schedule.py::test_shifts_are_listed_in_order`
  - WP: WP-03
- AC-008 · Coverage gaps across people
  - Scenario: Ann works `"08:00-12:00"` and Bob `"14:00-18:00"` on 2026-01-05; Bob also works `"08:00-18:00"` on 2026-01-06.
  - Action: `coverage_gaps(2026-01-05, [480, 1080))`.
  - Expected: `[720, 840)`.
  - Must not: count a shift of another day.
  - Check: `acceptance/test_schedule.py::test_coverage_gaps_across_people`
  - WP: WP-03
- AC-009 · Minutes worked
  - Scenario: Ann works `"09:00-17:00"` on 2026-01-05 and `"22:00-06:00"` on 2026-01-06.
  - Action: `minutes("Ann")` and `minutes("Bob")`.
  - Expected: 960 and 0.
  - Must not: fail for a person who has no shifts.
  - Check: `acceptance/test_schedule.py::test_minutes_worked`
  - WP: WP-03
- AC-010 · A double booking is refused
  - Scenario: Ann works `"09:00-17:00"` on 2026-01-05.
  - Action: `assign("Ann", 2026-01-05, "16:00-20:00")`.
  - Expected: it raises `ConflictError`.
  - Must not: store the second shift.
  - Check: `acceptance/test_schedule.py::test_a_double_booking_is_refused`
  - WP: WP-03
- AC-011 · A short rest is reported
  - Scenario: shifts on 2026-01-05 of `[540, 1020)` and `[1200, 1400)`, and on 2026-01-06 of `[540, 1020)`; `min_rest` 480.
  - Action: `rest_violations` of the list.
  - Expected: `[(2026-01-05, 2026-01-05)]`.
  - Must not: report the pair of the 05th evening and the 06th morning.
  - Check: `acceptance/test_rules.py::test_a_short_rest_is_reported`
  - WP: WP-04
- AC-012 · Few shifts, no violations
  - Scenario: no state.
  - Action: `rest_violations` of an empty list and of a list with one shift, `min_rest` 480.
  - Expected: `[]` both times.
  - Must not: fail on a list with fewer than two shifts.
  - Check: `acceptance/test_rules.py::test_few_shifts_no_violations`
  - WP: WP-04

## 9. Test strategy
- Unit: each WP writes its tests in `tests/`, with `unittest`.
- Acceptance: written first from the ACs in `acceptance/`.
- Run: `python3 -m unittest discover -s tests` and `python3 -m unittest discover -s acceptance`.

```json
{
  "acceptance": {
    "files": [
      "acceptance/"
    ],
    "command": "python3 -m unittest discover -s acceptance"
  }
}
```
