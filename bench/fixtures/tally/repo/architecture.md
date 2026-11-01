# Architecture: tally
Type: feature · Size: standard

## 1. Goal
An expense-sharing library: amounts in cents, dates by month, a ledger of who paid what for whom, and the transfers that settle it. It has no dependencies and no persistence: everything is in memory.

## 2. Scope
### Included
- `tally/money.py`: `parse_amount`, `format_amount` and `split`.
- `tally/dates.py`: `parse_date`, `month_end` and `months_between`.
- `tally/ledger.py`: `Expense` and `Ledger`.
- `tally/settle.py`: `settle`.
### Excluded (non-goals)
- Persistence, currencies, rounding modes, user interfaces.

## 3. Stack
Python 3.9+, standard library only. Tests with `unittest`.
- Tests: `python3 -m unittest discover -s tests`
- Acceptance: `python3 -m unittest discover -s acceptance`

## 4. Repository structure
```
README.md                  (docs)
tally/__init__.py          (existing)
tally/money.py             WP-01
tally/dates.py             WP-02
tally/ledger.py            WP-03
tally/settle.py            WP-04
tests/test_version.py      (existing)
tests/test_money.py        WP-01
tests/test_dates.py        WP-02
tests/test_ledger.py       WP-03
tests/test_settle.py       WP-04
acceptance/                AT
```
Do not add `__init__.py` to `tests/` or `acceptance/`: `python3 -m unittest discover -s <dir>` puts the repo root on `sys.path`, so `import tally` works.

## 4b. Existing code context
| What an implementer needs to know | Where it is | Pattern or rule |
|---|---|---|
| The package and its version | `tally/__init__.py:1-3` | Module docstring, then `__version__` |
| Test style | `tests/test_version.py:1-15` | `unittest.TestCase`, one behaviour per test |

## 5. Data model
An `Expense` is a frozen dataclass. A `Ledger` keeps its expenses in a private list, in the order they were added. Money is always an `int` number of cents; there is no floating point anywhere.

## 6. Contracts between modules
**`tally/money.py`** (WP-01)
```python
def parse_amount(text: str) -> int: ...
def format_amount(cents: int) -> str: ...
def split(cents: int, parts: int) -> list[int]: ...
```
- `parse_amount`: `"12.30"` is 1230, `"12"` is 1200, `"0.5"` is 50, `"-3.10"` is -310; surrounding whitespace is allowed. The text is digits, optionally followed by `.` and one or two digits, with an optional leading `-`. Anything else raises `ValueError`: more than two decimals, a thousands separator, a currency sign, an empty string.
- `format_amount`: 1230 is `"12.30"`, -5 is `"-0.05"`, 0 is `"0.00"`.
- `split` returns `parts` shares whose sum is `cents`, by largest remainder: the first `cents mod parts` shares get one extra cent (100 by 3 is `[34, 33, 33]`). A negative amount is the negation of the split of its absolute value (-100 by 3 is `[-34, -33, -33]`). `ValueError` for `parts < 1` or a `bool` as `parts`.

**`tally/dates.py`** (WP-02)
```python
def parse_date(text: str) -> datetime.date: ...
def month_end(day: datetime.date) -> datetime.date: ...
def months_between(start: datetime.date, end: datetime.date) -> list[tuple[datetime.date, datetime.date]]: ...
```
- `parse_date` accepts exactly `YYYY-MM-DD`: `2024-02-29` is valid; `2023-02-29` and `2026-1-5` raise `ValueError`.
- `month_end(2024-02-10)` is `2024-02-29`.
- `months_between` returns one `(first, last)` pair per calendar month from the month of `start` to the month of `end` inclusive, clipped to `start` and `end`: `2025-11-20 .. 2026-01-05` gives `[(2025-11-20, 2025-11-30), (2025-12-01, 2025-12-31), (2026-01-01, 2026-01-05)]`. `ValueError` when `start > end`.

**`tally/ledger.py`** (WP-03)
```python
@dataclass(frozen=True)
class Expense:
    date: datetime.date
    payer: str
    cents: int
    participants: tuple[str, ...]
    description: str

class Ledger:                      # Ledger() takes no arguments
    def add(self, date_text: str, payer: str, amount_text: str, participants: list[str], description: str = "") -> Expense: ...
    def balances(self, start: datetime.date | None = None, end: datetime.date | None = None) -> dict[str, int]: ...
```
- `add` parses with `parse_date` and `parse_amount`; the amount must be positive (`ValueError`). Names are stripped and non-empty, and `participants` has no duplicates after stripping (`ValueError`). The payer need not be a participant. The stored `participants` are sorted by name. A failed `add` changes nothing.
- `balances` is `{name: cents}` for every person ever seen as payer or participant (0 included), sorted by name, over the expenses whose date is within `[start, end]` inclusive (`None` means no bound). The payer gets `+cents`; each participant gets `-share`, where the shares are `split(cents, len(participants))` assigned in sorted name order, so the first names carry the extra cents.

**`tally/settle.py`** (WP-04)
```python
def settle(balances: dict[str, int]) -> list[tuple[str, str, int]]: ...
```
- Returns `(debtor, creditor, cents)` transfers that bring every balance to 0, produced by this exact loop: while any balance is non-zero, take the most negative balance (ties by name ascending) and the most positive (ties by name ascending), transfer the smaller of the two magnitudes, and update both.
- `ValueError` when the balances do not sum to 0. `{A: -10, B: -10, C: 20}` gives `[("A", "C", 10), ("B", "C", 10)]`; at most `len(balances) - 1` transfers; a dict of zeros gives `[]`. The input dict is not changed.

## 7. Conventions
- English; small functions; type annotations on public signatures; `from __future__ import annotations` for Python 3.9.
- Errors: `ValueError` for invalid arguments. Validate before changing any state.
- Money is integer cents; never `float`.

## 8. Work packages and acceptance criteria
### Acceptance criteria
- AC-001 · Amounts parse into cents
  - Scenario: no state.
  - Action: `parse_amount` of `"12.30"`, `"12"`, `"0.5"`, `"0.29"`, `"-3.10"` and `"  7.25 "`.
  - Expected: 1230, 1200, 50, 29, -310 and 725.
  - Must not: go through floating point (`0.29` must not become 28).
  - Check: `acceptance/test_money.py::test_amounts_parse_into_cents`
  - WP: WP-01
- AC-002 · Malformed amounts are rejected
  - Scenario: no state.
  - Action: `parse_amount` of `""`, `"abc"`, `"$5"`, `"1,000.00"`, `"1.234"` and `"0.001"`.
  - Expected: each raises `ValueError`.
  - Must not: round an amount with more than two decimals.
  - Check: `acceptance/test_money.py::test_malformed_amounts_are_rejected`
  - WP: WP-01
- AC-003 · Cents format as amounts
  - Scenario: no state.
  - Action: `format_amount` of 1230, 0 and -5.
  - Expected: `"12.30"`, `"0.00"` and `"-0.05"`.
  - Must not: drop the leading zero of the cents or the sign of a small negative amount.
  - Check: `acceptance/test_money.py::test_cents_format_as_amounts`
  - WP: WP-01
- AC-004 · A split gives the extra cents to the first shares
  - Scenario: no state.
  - Action: `split(100, 3)`, `split(10, 4)`, `split(90, 3)`.
  - Expected: `[34, 33, 33]`, `[3, 3, 2, 2]` and `[30, 30, 30]`.
  - Must not: lose or invent a cent, or give the whole remainder to one share.
  - Check: `acceptance/test_money.py::test_split_gives_extra_cents_first`
  - WP: WP-01
- AC-005 · A negative split mirrors the positive one
  - Scenario: no state.
  - Action: `split(-100, 3)` and `split(-10, 4)`.
  - Expected: `[-34, -33, -33]` and `[-3, -3, -2, -2]`.
  - Must not: give the extra cents to the last shares.
  - Check: `acceptance/test_money.py::test_negative_split_mirrors_positive`
  - WP: WP-01
- AC-006 · A split needs a real number of parts
  - Scenario: no state.
  - Action: `split(100, 0)`, `split(100, -1)` and `split(100, True)`.
  - Expected: each raises `ValueError`.
  - Must not: accept `True` as 1.
  - Check: `acceptance/test_money.py::test_split_needs_real_parts`
  - WP: WP-01
- AC-007 · Dates are strict ISO dates
  - Scenario: no state.
  - Action: `parse_date` of `"2026-01-05"`, `"2024-02-29"`, `"2023-02-29"`, `"2026-1-5"` and `"2026-13-01"`.
  - Expected: the first two give the dates; the others raise `ValueError`.
  - Must not: accept a date that is not written `YYYY-MM-DD`.
  - Check: `acceptance/test_dates.py::test_dates_are_strict_iso`
  - WP: WP-02
- AC-008 · The end of a month
  - Scenario: no state.
  - Action: `month_end` of 2024-02-10, 2023-02-10 and 2026-04-01.
  - Expected: 2024-02-29, 2023-02-28 and 2026-04-30.
  - Must not: ignore leap years.
  - Check: `acceptance/test_dates.py::test_month_end`
  - WP: WP-02
- AC-009 · Months between two dates
  - Scenario: no state.
  - Action: `months_between(2025-11-20, 2026-01-05)`, `months_between(2024-01-31, 2024-03-01)` and `months_between(2026-02-01, 2026-01-31)`.
  - Expected: the three clipped periods of the contract; `[(2024-01-31, 2024-01-31), (2024-02-01, 2024-02-29), (2024-03-01, 2024-03-01)]`; the last call raises `ValueError`.
  - Must not: skip a month, or stop at the year boundary.
  - Check: `acceptance/test_dates.py::test_months_between`
  - WP: WP-02
- AC-010 · An expense is recorded cleanly
  - Scenario: an empty `Ledger`.
  - Action: `add("2026-01-05", " Ann ", "12.50", ["Cy", " Bob"], "lunch")`.
  - Expected: an `Expense` on 2026-01-05, payer `"Ann"`, 1250 cents, participants `("Bob", "Cy")`, description `"lunch"`.
  - Must not: keep the whitespace or the given order of the participants.
  - Check: `acceptance/test_ledger.py::test_expense_is_recorded_cleanly`
  - WP: WP-03
- AC-011 · Invalid expenses are rejected and change nothing
  - Scenario: an empty `Ledger`.
  - Action: `add` with the amounts `"0"` and `"-5"`, an empty payer, a blank participant, and the participants `["Bob", " Bob "]`.
  - Expected: each raises `ValueError`; `balances()` is `{}`.
  - Must not: record a partly valid expense.
  - Check: `acceptance/test_ledger.py::test_invalid_expenses_are_rejected`
  - WP: WP-03
- AC-012 · Balances include everyone, and the payer need not take part
  - Scenario: a `Ledger` with Ann paying 10.00 for Bob and Cy.
  - Action: `balances()`.
  - Expected: `{"Ann": 1000, "Bob": -500, "Cy": -500}`.
  - Must not: leave the payer out because she is not a participant.
  - Check: `acceptance/test_ledger.py::test_balances_include_everyone`
  - WP: WP-03
- AC-013 · The extra cents go to the first names in sorted order
  - Scenario: a `Ledger` with Dan paying 1.00 for `["Cy", "Ann", "Bob"]`.
  - Action: `balances()`.
  - Expected: `{"Ann": -34, "Bob": -33, "Cy": -33, "Dan": 100}`.
  - Must not: depend on the order the participants were given in.
  - Check: `acceptance/test_ledger.py::test_extra_cents_go_to_first_sorted_names`
  - WP: WP-03
- AC-014 · Balances over a period include both ends
  - Scenario: Ann pays 10.00, 20.00 and 40.00 for Bob on 2026-01-01, 2026-01-15 and 2026-01-31.
  - Action: `balances(start, end)` for 01-15 to 01-15; for `start` 01-02 alone; for `end` 01-01 alone.
  - Expected: Ann at 2000, 6000 and 1000, with Bob at the opposite.
  - Must not: drop an expense dated exactly on `start` or `end`, or drop a person who has no expense in the period (they stay at 0).
  - Check: `acceptance/test_ledger.py::test_balances_bounds_are_inclusive`
  - WP: WP-03
- AC-015 · Settlement transfers
  - Scenario: no state.
  - Action: `settle({"A": -10, "B": -10, "C": 20})` and `settle({"A": -30, "B": -70, "C": 60, "D": 40})`.
  - Expected: `[("A", "C", 10), ("B", "C", 10)]` and `[("B", "C", 60), ("A", "D", 30), ("B", "D", 10)]`.
  - Must not: use more than `len(balances) - 1` transfers.
  - Check: `acceptance/test_settle.py::test_settlement_transfers`
  - WP: WP-04
- AC-016 · Settlement ties are broken by name
  - Scenario: no state.
  - Action: `settle({"B": -10, "A": -10, "C": 20})` and `settle({"Y": 10, "X": 10, "Z": -20})`.
  - Expected: `[("A", "C", 10), ("B", "C", 10)]` and `[("Z", "X", 10), ("Z", "Y", 10)]`.
  - Must not: follow the insertion order of the dict.
  - Check: `acceptance/test_settle.py::test_settlement_ties_by_name`
  - WP: WP-04
- AC-017 · Unbalanced input is rejected, zeros need no transfer
  - Scenario: no state.
  - Action: `settle({"A": -10, "B": 5})`, `settle({"A": 0, "B": 0})`.
  - Expected: the first raises `ValueError`; the second gives `[]`.
  - Must not: change the dict it receives.
  - Check: `acceptance/test_settle.py::test_unbalanced_input_is_rejected`
  - WP: WP-04

### Work packages
#### WP-01 · Money
- Wave 1. Files: `tally/money.py`, `tests/test_money.py`.
- Implements `parse_amount`, `format_amount` and `split` (section 6). Consumes nothing.
- ACs: AC-001 to AC-006.
- Patterns to mirror: `tally/__init__.py:1-3` (module docstring), `tests/test_version.py:1-15` (unittest style).
- Gotchas: parse with a regular expression and integer arithmetic, never `float`; `split` works on the absolute value with `divmod` and negates after; `bool` is a subclass of `int`, so check it explicitly.
- Validation: `python3 -m unittest discover -s tests`

#### WP-02 · Dates
- Wave 1. Files: `tally/dates.py`, `tests/test_dates.py`.
- Implements `parse_date`, `month_end` and `months_between` (section 6). Consumes nothing.
- ACs: AC-007 to AC-009.
- Patterns to mirror: `tally/__init__.py:1-3`, `tests/test_version.py:1-15`.
- Gotchas: check the text is exactly `YYYY-MM-DD` before building the date; the end of a month is the day before the first day of the next one.
- Validation: `python3 -m unittest discover -s tests`

#### WP-03 · Ledger
- Wave 2, depends_on WP-01 and WP-02. Files: `tally/ledger.py`, `tests/test_ledger.py`.
- Implements `Expense` and `Ledger` (section 6). Consumes `parse_amount` and `split` from WP-01 and `parse_date` from WP-02 by implementation.
- ACs: AC-010 to AC-014.
- Patterns to mirror: `tally/__init__.py:1-3`, `tests/test_version.py:1-15`.
- Gotchas: validate everything before storing; `balances` lists the payer even when not a participant and every participant even at 0; shares are assigned in sorted name order.
- Validation: `python3 -m unittest discover -s tests`

#### WP-04 · Settlement
- Wave 3, depends_on WP-03. Files: `tally/settle.py`, `tests/test_settle.py`.
- Implements `settle` (section 6). Consumes the balances of `Ledger.balances` from WP-03 by implementation (a `dict[str, int]`).
- ACs: AC-015 to AC-017.
- Patterns to mirror: `tally/__init__.py:1-3`, `tests/test_version.py:1-15`.
- Gotchas: follow the loop of section 6 exactly so ties are deterministic; work on a copy of the input.
- Validation: `python3 -m unittest discover -s tests`

```json wp-manifest
{
  "stack": ["python"],
  "allow_bash": ["Bash(python3 -m unittest:*)"],
  "acceptance": {"files": ["acceptance/"], "command": "python3 -m unittest discover -s acceptance"},
  "verify": {"tests": "python3 -m unittest discover -s tests"},
  "docs": {"files": ["README.md"], "codemap": null},
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": ["tally/money.py", "tests/test_money.py"],
     "acs": ["AC-001", "AC-002", "AC-003", "AC-004", "AC-005", "AC-006"],
     "mirror": ["tally/__init__.py", "tests/test_version.py"]},
    {"id": "WP-02", "wave": 1, "depends_on": [], "files": ["tally/dates.py", "tests/test_dates.py"],
     "acs": ["AC-007", "AC-008", "AC-009"], "mirror": ["tally/__init__.py", "tests/test_version.py"]},
    {"id": "WP-03", "wave": 2, "depends_on": ["WP-01", "WP-02"], "files": ["tally/ledger.py", "tests/test_ledger.py"],
     "acs": ["AC-010", "AC-011", "AC-012", "AC-013", "AC-014"], "mirror": ["tally/__init__.py", "tests/test_version.py"]},
    {"id": "WP-04", "wave": 3, "depends_on": ["WP-03"], "files": ["tally/settle.py", "tests/test_settle.py"],
     "acs": ["AC-015", "AC-016", "AC-017"], "mirror": ["tally/__init__.py", "tests/test_version.py"]}
  ]
}
```

## 9. Test strategy
- Unit: each WP writes its tests in `tests/`, with `unittest`.
- Acceptance: written first from the ACs in `acceptance/`.
- Run: `python3 -m unittest discover -s tests` and `python3 -m unittest discover -s acceptance`.

## 10. Decisions
- Integer cents everywhere: floating point cannot represent money.
- Largest remainder for splits, so the shares always add up to the amount.
- Three waves because the ledger needs money and dates, and settlement works on the ledger's balances.

## 11. Risks and open questions
- None open.
