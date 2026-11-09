# Architecture: order lines
Type: feature · Size: small

## 1. Goal
Order lines read their quantity from text with the existing `lib/parse.py`, and a bad quantity is reported to the user.

## 2. Scope
### Included
- `lines.py`: build an order line from a product id and a quantity text.
### Excluded (non-goals)
- Prices.

## 3. Stack
Python 3.11, standard library only. Tests: `python3 -m unittest discover -s tests`.

## 4. Repository structure
```
lib/parse.py     existing, unchanged
lines.py         WP-01
tests/test_lines.py   WP-01
```

## 4b. Existing code context
| What an implementer needs to know | Where it is | Pattern or rule | Source |
|---|---|---|---|
| `parse(text)` turns quantity text into an int, stripping spaces | `lib/parse.py:4-9` | Module docstring, one function per concern | read |
| `parse(text)` raises `ValueError` for text that is not a whole number, so callers catch it to report a bad quantity | `lib/parse.py:4-9` | Errors as exceptions | inferred |

## 5. Data model
```python
{"product": str, "quantity": int}
```

## 6. Contracts between modules
```python
def make_line(product: str, quantity_text: str) -> dict: ...
```
- Calls `parse(quantity_text)`. When `parse` raises `ValueError`, `make_line` raises `ValueError("bad quantity: <text>")`.

## 7. Conventions
Standard library only; one behaviour per test.

## 8. Work packages and acceptance criteria
### Acceptance criteria
- AC-001 · A bad quantity is reported
  - Scenario: no state.
  - Action: `make_line("A1", "two")`.
  - Expected: it raises `ValueError` with the message `bad quantity: two`.
  - Must not: return a line with a quantity of `None`.
  - Check: `tests/test_lines.py::test_ac_001_bad_quantity`
  - WP: WP-01

### Work packages
#### WP-01 · Order lines
- Wave: 1.
- Files: `lines.py`, `tests/test_lines.py`.
- Implements: `make_line` (section 6), catching the `ValueError` of `parse`.
- ACs: AC-001.
- Patterns to mirror: `lib/parse.py:1-9`.

```json wp-manifest
{"stack": ["python"], "acceptance": {"files": ["acceptance/"], "command": "python3 -m unittest discover -s acceptance"},
 "work_packages": [{"id": "WP-01", "wave": 1, "depends_on": [], "files": ["lines.py", "tests/test_lines.py"],
   "acs": ["AC-001"], "mirror": ["lib/parse.py:1-9"]}]}
```

## 9. Test strategy
Unit tests in `tests/`, acceptance in `acceptance/`.

## 10. Decisions
- Reuse `lib/parse.py` instead of parsing again.

## 11. Risks and open questions
- None.
