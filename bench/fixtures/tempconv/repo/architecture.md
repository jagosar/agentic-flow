# Architecture: tempconv
Type: feature · Size: small

## 1. Goal
`tempconv` is a small library that converts temperatures between Celsius, Fahrenheit and Kelvin and parses text such as `"12.5C"` into a value and a unit. It is split into two independent modules so they can be built in parallel.

## 2. Scope
### Included
- `tempconv/convert.py`: `convert`.
- `tempconv/parse.py`: `parse`.
### Excluded (non-goals)
- Other units (Rankine, Réaumur), command line, localisation of numbers.

## 3. Stack
Python 3.9+, standard library only. Tests: `python3 -m unittest discover -s tests`. Acceptance: `python3 -m unittest discover -s acceptance`. No `__init__.py` in `tests/` or `acceptance/`: `python3 -m` puts the repo root on `sys.path`, so `import tempconv` works.

## 4. Repository structure
```
README.md                  existing
tempconv/__init__.py       existing
tempconv/convert.py        WP-01
tempconv/parse.py          WP-02
tests/test_version.py      existing
tests/test_convert.py      WP-01
tests/test_parse.py        WP-02
acceptance/                AT
```

## 4b. Existing code context
| What an implementer needs to know | Where it is | Pattern or rule |
|---|---|---|
| The package declares its version and a one-line docstring | `tempconv/__init__.py:1-3` | Module docstring first, then the code |
| Tests are `unittest` classes, one behaviour per test | `tests/test_version.py:1-14` | Plain `unittest.TestCase`, `import tempconv` at top, no `__init__.py` in `tests/` |

## 5. Data model
No persistent data. A temperature is a `float` and a unit is one of the strings `"C"`, `"F"`, `"K"`.

## 6. Contracts between modules
```python
# tempconv/convert.py
def convert(value: float, from_unit: str, to_unit: str) -> float:
    """Converts value between "C", "F" and "K" (upper case) and rounds to 2 decimals.
    Raises ValueError for an unknown unit or for a temperature below absolute zero (-273.15 C)."""

# tempconv/parse.py
def parse(text: str) -> tuple[float, str]:
    """Parses "12.5C", "-40 F" or "300k": a number, optional spaces, one unit letter in any case.
    Returns (number, unit) with the unit in upper case.
    Raises ValueError for anything else: empty text, no number, unknown unit, two units."""
```
The two modules do not import each other.

## 7. Conventions
- Standard library only; English; small functions; public signatures annotated, with `from __future__ import annotations` for Python 3.9.
- Errors are `ValueError` with a short message.
- Tests: `unittest`, one behaviour per test.

## 8. Work packages and acceptance criteria
### Acceptance criteria
- AC-001 · Celsius and Fahrenheit convert both ways
  - Scenario: the package is importable from the repo root.
  - Action: `convert(-40, "C", "F")`, `convert(100, "C", "F")` and `convert(212, "F", "C")`.
  - Expected: `-40.0`, `212.0` and `100.0`.
  - Must not: return an unrounded float or swap the formula.
  - Check: `acceptance/test_convert_units.py::test_ac_001_celsius_fahrenheit`.
  - WP: WP-01
- AC-002 · Kelvin converts to and from the other units, rounded to 2 decimals
  - Scenario: as above.
  - Action: `convert(0, "K", "C")` and `convert(20.555, "C", "K")`.
  - Expected: `-273.15` and a value with at most 2 decimals.
  - Must not: return more than 2 decimals.
  - Check: `acceptance/test_convert_units.py::test_ac_002_kelvin_and_rounding`.
  - WP: WP-01
- AC-003 · Invalid conversions raise
  - Scenario: as above.
  - Action: `convert(1, "X", "C")`, `convert(1, "c", "F")` and `convert(-300, "C", "F")`.
  - Expected: each raises `ValueError`.
  - Must not: accept lower-case units or a temperature below absolute zero.
  - Check: `acceptance/test_convert_units.py::test_ac_003_invalid_conversions`.
  - WP: WP-01
- AC-004 · Valid texts are parsed
  - Scenario: as above.
  - Action: `parse("12.5C")`, `parse("-40 F")` and `parse("300k")`.
  - Expected: `(12.5, "C")`, `(-40.0, "F")` and `(300.0, "K")`.
  - Must not: return a lower-case unit.
  - Check: `acceptance/test_parse_text.py::test_ac_004_valid_texts`.
  - WP: WP-02
- AC-005 · Invalid texts raise
  - Scenario: as above.
  - Action: `parse("")`, `parse("C")`, `parse("12X")` and `parse("12CF")`.
  - Expected: each raises `ValueError`.
  - Must not: return a default value or raise another exception type.
  - Check: `acceptance/test_parse_text.py::test_ac_005_invalid_texts`.
  - WP: WP-02

### Work packages
#### WP-01 · Conversion
- Wave 1. Files: `tempconv/convert.py`, `tests/test_convert.py`.
- Implements `convert` (section 6). Consumes nothing.
- ACs: AC-001, AC-002, AC-003.
- **Patterns to mirror:** `tempconv/__init__.py:1-3` (docstring first) and `tests/test_version.py:1-14` (unittest style).
- **Gotchas:** convert through Celsius; check absolute zero on the input, in its own unit; round only the result.
- **Exact imports and APIs:** standard library only.
- **WP validation:** `python3 -m unittest discover -s tests`.

#### WP-02 · Parsing
- Wave 1. Files: `tempconv/parse.py`, `tests/test_parse.py`.
- Implements `parse` (section 6). Consumes nothing.
- ACs: AC-004, AC-005.
- **Patterns to mirror:** `tempconv/__init__.py:1-3` (docstring first) and `tests/test_version.py:1-14` (unittest style).
- **Gotchas:** the unit is exactly one letter of C, F or K; "12CF" and "C" are invalid; do not import `tempconv.convert`.
- **Exact imports and APIs:** standard library only (`re` is enough).
- **WP validation:** `python3 -m unittest discover -s tests`.

```json wp-manifest
{
  "stack": ["python"],
  "allow_bash": ["Bash(python3 -m unittest:*)"],
  "acceptance": {"files": ["acceptance/"], "command": "python3 -m unittest discover -s acceptance"},
  "verify": {"tests": "python3 -m unittest discover -s tests"},
  "docs": {"files": ["README.md"], "codemap": null},
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": ["tempconv/convert.py", "tests/test_convert.py"],
     "acs": ["AC-001", "AC-002", "AC-003"], "mirror": ["tempconv/__init__.py:1-3", "tests/test_version.py:1-14"]},
    {"id": "WP-02", "wave": 1, "depends_on": [], "files": ["tempconv/parse.py", "tests/test_parse.py"],
     "acs": ["AC-004", "AC-005"], "mirror": ["tempconv/__init__.py:1-3", "tests/test_version.py:1-14"]}
  ]
}
```

## 9. Test strategy
- Unit: each WP writes its own tests in `tests/` with `unittest`.
- Acceptance: written first from the ACs in `acceptance/`.
- QA: exploratory, after integration.

## 10. Decisions
- Convert through Celsius: one formula pair per unit instead of six direct formulas.
- Two modules that do not import each other, so both WPs fit in one wave.

## 11. Risks and open questions
None.
