# Architecture: inventory
Type: feature · Size: standard

## 1. Goal
A small stock-keeping library. An `Inventory` tracks the quantity of each SKU (add, remove, query), and a report lists the SKUs whose quantity is below a threshold. It has no dependencies and no persistence: everything is in memory.

## 2. Scope
### Included
- `inventory/stock.py`: `InsufficientStock` and `Inventory`.
- `inventory/report.py`: `low_stock`.
### Excluded (non-goals)
- Persistence, concurrency, units of measure, prices.

## 3. Stack
Python 3.9+, standard library only. Tests with `unittest`.
- Tests: `python3 -m unittest discover -s tests`
- Acceptance: `python3 -m unittest discover -s acceptance`

## 4. Repository structure
```
README.md                  (docs)
inventory/__init__.py      (existing)
inventory/stock.py         WP-01
inventory/report.py        WP-02
tests/test_version.py      (existing)
tests/test_stock.py        WP-01
tests/test_report.py       WP-02
acceptance/                AT
```
Do not add `__init__.py` to `tests/` or `acceptance/`: `python3 -m unittest discover -s <dir>` puts the repo root on `sys.path`, so `import inventory` works.

## 4b. Existing code context
| What an implementer needs to know | Where it is | Pattern or rule |
|---|---|---|
| The package and its version | `inventory/__init__.py:1-3` | Module docstring, then `__version__` |
| Test style | `tests/test_version.py:1-15` | `unittest.TestCase`, one behaviour per test |

## 5. Data model
`Inventory` keeps a private `dict[str, int]` from normalised SKU to quantity. A SKU that was added and later removed down to 0 stays in the dict with quantity 0.

## 6. Contracts between modules
**`inventory/stock.py`** (WP-01)
```python
class InsufficientStock(Exception): ...

class Inventory:
    def add(self, sku: str, qty: int) -> None: ...
    def remove(self, sku: str, qty: int) -> None: ...
    def quantity(self, sku: str) -> int: ...
    def items(self) -> dict[str, int]: ...
```
- SKU normalisation: `sku.strip().upper()`, applied in `add`, `remove` and `quantity`. A SKU that is empty after that raises `ValueError`.
- `qty` must be an `int`, greater than 0, and not a `bool` (`True` is rejected). Anything else raises `ValueError`.
- `add` adds `qty` to the stock of the SKU.
- `remove` raises `InsufficientStock` if `qty` is more than the stock (an unknown SKU has stock 0) and then leaves the stock unchanged. Removing exactly the stock leaves the SKU at 0.
- `quantity` returns 0 for an unknown SKU.
- `items` returns a new dict of every SKU ever added, including those at 0. Changing the returned dict does not change the inventory.

**`inventory/report.py`** (WP-02)
```python
def low_stock(inv: Inventory, threshold: int) -> list[tuple[str, int]]: ...
```
Returns `(sku, quantity)` for every SKU ever added whose quantity is below `threshold` (strictly), including those at 0, sorted by quantity ascending and then by SKU ascending.

## 7. Conventions
- English; small functions; type annotations on public signatures; `from __future__ import annotations` for Python 3.9.
- Errors: `ValueError` for invalid arguments, `InsufficientStock` for a removal beyond the stock. Validate before changing any state.

## 8. Work packages and acceptance criteria
### Acceptance criteria
- AC-001 · SKUs are normalised
  - Scenario: an empty `Inventory`.
  - Action: `add(" ab-1 ", 5)`, then `quantity("AB-1")`, `quantity("  ab-1")` and `items()`.
  - Expected: both quantities are 5 and `items()` is `{"AB-1": 5}`.
  - Must not: keep two entries for the same SKU written in different case or spacing.
  - Check: `acceptance/test_stock.py::test_sku_is_normalised`
  - WP: WP-01
- AC-002 · An empty SKU is rejected
  - Scenario: an empty `Inventory`.
  - Action: `add("", 1)` and `add("   ", 1)`; `remove("  ", 1)`; `quantity("")`.
  - Expected: each raises `ValueError`; `items()` is `{}`.
  - Must not: create a SKU with an empty name.
  - Check: `acceptance/test_stock.py::test_empty_sku_is_rejected`
  - WP: WP-01
- AC-003 · Invalid quantities are rejected
  - Scenario: an `Inventory` with `A` at 5.
  - Action: `add` and `remove` with `qty` of `True`, `0`, `-1`, `1.5` and `"2"`.
  - Expected: each raises `ValueError`; the quantity of `A` is still 5.
  - Must not: accept `True` as 1, or change the stock when the call fails.
  - Check: `acceptance/test_stock.py::test_invalid_quantities_are_rejected`
  - WP: WP-01
- AC-004 · A removal beyond the stock fails and changes nothing
  - Scenario: an `Inventory` with `A` at 3.
  - Action: `remove("A", 4)`; `remove("B", 1)` for an unknown SKU.
  - Expected: both raise `InsufficientStock`; `quantity("A")` is 3; `"B"` is not in `items()`.
  - Must not: leave the stock partly reduced, or create an entry for the unknown SKU.
  - Check: `acceptance/test_stock.py::test_failed_removal_changes_nothing`
  - WP: WP-01
- AC-005 · Quantities add up and an unknown SKU is 0
  - Scenario: an empty `Inventory`.
  - Action: `add("A", 2)`, `add("a", 3)`, `remove("A", 5)`; `quantity("Z")`.
  - Expected: `quantity("A")` is 0 after the removal; `quantity("Z")` is 0; `"A"` is still in `items()` with 0.
  - Must not: delete a SKU when it reaches 0.
  - Check: `acceptance/test_stock.py::test_quantities_add_up`
  - WP: WP-01
- AC-006 · `items()` is a copy
  - Scenario: an `Inventory` with `A` at 2.
  - Action: take `items()`, change the returned dict, call `items()` again.
  - Expected: the second result is `{"A": 2}`.
  - Must not: expose the internal dict.
  - Check: `acceptance/test_stock.py::test_items_is_a_copy`
  - WP: WP-01
- AC-007 · `low_stock` lists the SKUs below the threshold, including those at 0
  - Scenario: an `Inventory` with `A` at 1, `B` at 5 and `C` added with 2 and then removed down to 0.
  - Action: `low_stock(inv, 5)`.
  - Expected: `[("C", 0), ("A", 1)]`.
  - Must not: include `B` (the threshold is strict), or leave out `C` because it is at 0.
  - Check: `acceptance/test_report.py::test_low_stock_includes_zero`
  - WP: WP-02
- AC-008 · `low_stock` ordering
  - Scenario: an `Inventory` with `B`, `A` and `C` all at 2, and `D` at 1.
  - Action: `low_stock(inv, 10)`.
  - Expected: `[("D", 1), ("A", 2), ("B", 2), ("C", 2)]`.
  - Must not: order ties by insertion order.
  - Check: `acceptance/test_report.py::test_low_stock_ties_by_sku`
  - WP: WP-02

### Work packages
#### WP-01 · Stock
- Wave 1. Files: `inventory/stock.py`, `tests/test_stock.py`.
- Implements `InsufficientStock` and `Inventory` (section 6). Consumes nothing.
- ACs: AC-001 to AC-006.
- Patterns to mirror: `inventory/__init__.py:1-3` (module docstring), `tests/test_version.py:1-15` (unittest style).
- Gotchas: validate the SKU and the quantity before touching the stock; `bool` is a subclass of `int`, so check it explicitly; `remove` must not create an entry for an unknown SKU.
- Validation: `python3 -m unittest discover -s tests`

#### WP-02 · Low-stock report
- Wave 2, depends on WP-01. Files: `inventory/report.py`, `tests/test_report.py`.
- Implements `low_stock` (section 6). Consumes `Inventory` from WP-01 by implementation (use `inv.items()`).
- ACs: AC-007, AC-008.
- Patterns to mirror: `inventory/__init__.py:1-3`, `tests/test_version.py:1-15`.
- Gotchas: SKUs at 0 must be listed; the threshold is strict; sort by quantity and then by SKU.
- Validation: `python3 -m unittest discover -s tests`

```json wp-manifest
{
  "stack": ["python"],
  "allow_bash": ["Bash(python3 -m unittest:*)"],
  "acceptance": {"files": ["acceptance/"], "command": "python3 -m unittest discover -s acceptance"},
  "verify": {"tests": "python3 -m unittest discover -s tests"},
  "docs": {"files": ["README.md"], "codemap": null},
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": ["inventory/stock.py", "tests/test_stock.py"],
     "acs": ["AC-001", "AC-002", "AC-003", "AC-004", "AC-005", "AC-006"],
     "mirror": ["inventory/__init__.py", "tests/test_version.py"]},
    {"id": "WP-02", "wave": 2, "depends_on": ["WP-01"], "files": ["inventory/report.py", "tests/test_report.py"],
     "acs": ["AC-007", "AC-008"], "mirror": ["inventory/__init__.py", "tests/test_version.py"]}
  ]
}
```

## 9. Test strategy
- Unit: each WP writes its tests in `tests/`, with `unittest`.
- Acceptance: written first from the ACs in `acceptance/`.
- Run: `python3 -m unittest discover -s tests` and `python3 -m unittest discover -s acceptance`.

## 10. Decisions
- In memory only: persistence is out of scope.
- A SKU at 0 stays listed: the report must show what ran out.
- Two waves because the report needs the real `Inventory`.

## 11. Risks and open questions
- None open.
