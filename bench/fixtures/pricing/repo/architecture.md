# Architecture: prices with a currency
Type: feature · Size: small

## 1. Goal
`shop` parses prices into cents and keeps a cart of priced lines. Today every price is implicitly in one currency. This change makes the currency explicit: `parse_price` takes the currency it expects and accepts an optional currency prefix in the text, and a `Cart` has a currency and refuses prices in another one. The work is split in two packages that can be built in parallel.

## 2. Scope
### Included
- `shop/money.py`: `CURRENCIES`, `CurrencyMismatch`, `parse_price` with a currency.
- `shop/cart.py`: `Cart` with a currency.
### Excluded (non-goals)
- Currency conversion, other currencies, rounding rules, localisation of numbers.

## 3. Stack
Python 3.9+, standard library only. Tests: `python3 -m unittest discover -s tests`. Acceptance: `python3 -m unittest discover -s acceptance`. No `__init__.py` in `tests/` or `acceptance/`: `python3 -m` puts the repo root on `sys.path`, so `import shop` works.

## 4. Repository structure
```
README.md                existing
shop/__init__.py         existing
shop/money.py            WP-01
shop/cart.py             WP-02
tests/test_money.py      WP-01
tests/test_cart.py       WP-02
acceptance/              AT
```

## 4b. Existing code context
| What an implementer needs to know | Where it is | Pattern or rule |
|---|---|---|
| `parse_price` turns a price text into cents and raises `ValueError` for bad text | `shop/money.py:9-16` | Annotated signature, docstring with the errors, a compiled pattern at module level |
| `Cart.add` is where `parse_price` is called from | `shop/cart.py:14` (`cents = parse_price(price_text)`) | Validate, then store; a failed `add` leaves the cart unchanged |
| Tests are `unittest` classes, one behaviour per test | `tests/test_money.py:1-31` | Plain `unittest.TestCase`, imports at top, no `__init__.py` in `tests/` |

## 5. Data model
No persistent data. A price is an `int` number of cents; a currency is one of the strings in `CURRENCIES`.

## 6. Contracts between modules
```python
# shop/money.py
CURRENCIES = ("EUR", "USD", "GBP")
class CurrencyMismatch(ValueError): ...
def parse_price(text: str, currency: str) -> int:
    """'12.50' or 'EUR 12.50' (prefix, one space) -> 1250. currency not in CURRENCIES -> ValueError. A prefix that is
    a known currency other than `currency` -> CurrencyMismatch. Old errors unchanged."""
def format_cents(cents: int) -> str   # unchanged

# shop/cart.py
class Cart:
    def __init__(self, currency: str = "EUR") -> None   # unknown currency -> ValueError
    currency: str
    def add(self, name: str, price_text: str, qty: int = 1) -> None   # parse_price(price_text, self.currency)
```
The old errors of `parse_price` are `ValueError` for empty text, a negative amount, more than two decimals or no number. A prefix that is not one of `CURRENCIES` (`"JPY 1.00"`) is a plain `ValueError`, not `CurrencyMismatch`. A prefix without the space (`"EUR12.50"`) is a `ValueError`.

## 7. Conventions
- Standard library only; English; small functions; public signatures annotated, with `from __future__ import annotations` for Python 3.9.
- Errors are `ValueError` (or its subclass `CurrencyMismatch`) with a short message.
- Tests: `unittest`, one behaviour per test.

## 8. Work packages and acceptance criteria
### Acceptance criteria
- AC-001 · A price with the expected prefix, or none, is parsed
  - Scenario: the package is importable from the repo root.
  - Action: `parse_price("12.50", "EUR")`, `parse_price("EUR 12.50", "EUR")` and `parse_price("GBP 0.5", "GBP")`.
  - Expected: `1250`, `1250` and `50`.
  - Must not: reject the prefix of the expected currency.
  - Check: `acceptance/test_money_currency.py::test_ac_001_prefix_and_plain`.
  - WP: WP-01
- AC-002 · A prefix of another known currency is a mismatch
  - Scenario: as above.
  - Action: `parse_price("USD 1.00", "EUR")`.
  - Expected: raises `CurrencyMismatch`, which is a `ValueError`.
  - Must not: return a value.
  - Check: `acceptance/test_money_currency.py::test_ac_002_mismatch`.
  - WP: WP-01
- AC-003 · Unknown currencies and prefixes are plain value errors
  - Scenario: as above.
  - Action: `parse_price("1.00", "JPY")`, `parse_price("JPY 1.00", "EUR")` and `parse_price("EUR12.50", "EUR")`.
  - Expected: each raises `ValueError`, and its type is exactly `ValueError`, not `CurrencyMismatch`.
  - Must not: raise `CurrencyMismatch` for an unknown prefix.
  - Check: `acceptance/test_money_currency.py::test_ac_003_unknown_currency`.
  - WP: WP-01
- AC-004 · The old errors still raise
  - Scenario: as above.
  - Action: `parse_price` of `""`, `"-1.00"`, `"1.234"`, `"abc"` and `"EUR -1.00"`, each with `"EUR"`.
  - Expected: each raises `ValueError`.
  - Must not: return a value or raise another exception type.
  - Check: `acceptance/test_money_currency.py::test_ac_004_old_errors`.
  - WP: WP-01
- AC-005 · A cart has a currency and parses its prices in it
  - Scenario: `Cart(currency="USD")`, then `add("pen", "1.20", 3)` and `add("ink", "USD 4")`.
  - Action: `total()`, `lines()` and `currency`.
  - Expected: `760`, `[("pen", 3, 360), ("ink", 1, 400)]` and `"USD"`; `Cart().currency` is `"EUR"`.
  - Must not: ignore the cart's currency.
  - Check: `acceptance/test_cart_currency.py::test_ac_005_cart_in_usd`.
  - WP: WP-02
- AC-006 · A cart refuses a price in another currency
  - Scenario: `Cart(currency="USD")`.
  - Action: `add("pen", "EUR 1.00")`, then `lines()`.
  - Expected: `add` raises `CurrencyMismatch` and `lines()` is `[]`.
  - Must not: store the line.
  - Check: `acceptance/test_cart_currency.py::test_ac_006_cart_refuses_other_currency`.
  - WP: WP-02
- AC-007 · A cart with an unknown currency cannot be built
  - Scenario: as above.
  - Action: `Cart(currency="JPY")`.
  - Expected: raises `ValueError`.
  - Must not: build the cart.
  - Check: `acceptance/test_cart_currency.py::test_ac_007_unknown_cart_currency`.
  - WP: WP-02

### Work packages
#### WP-01 · Money
- Wave 1. Files: `shop/money.py`, `tests/test_money.py`.
- Implements `CURRENCIES`, `CurrencyMismatch` and `parse_price` (section 6). Consumes nothing.
- ACs: AC-001, AC-002, AC-003, AC-004.
- **Patterns to mirror:** `shop/money.py:9-16` (signature, docstring, errors) and `tests/test_money.py:1-31` (unittest style).
- **Gotchas:** check the `currency` argument before the text; the prefix is exactly three letters and one space; update the existing tests in `tests/test_money.py` to the new signature.
- **Exact imports and APIs:** standard library only (`re` is enough).
- **WP validation:** `python3 -m unittest discover -s tests`.

#### WP-02 · Cart
- Wave 1. Files: `shop/cart.py`, `tests/test_cart.py`.
- Implements `Cart` with a currency (section 6). Consumes `parse_price`, `CURRENCIES` and `CurrencyMismatch` from WP-01 by signature.
- ACs: AC-005, AC-006, AC-007.
- **Patterns to mirror:** `shop/cart.py:11-15` (validate, then store) and `tests/test_cart.py:1-27` (unittest style).
- **Gotchas:** a failed `add` leaves the cart unchanged; update the existing tests in `tests/test_cart.py` to the new signature.
- **Exact imports and APIs:** `from shop.money import CURRENCIES, parse_price`.
- **WP validation:** `python3 -m unittest discover -s tests`.

```json wp-manifest
{
  "stack": ["python"],
  "allow_bash": ["Bash(python3 -m unittest:*)"],
  "acceptance": {"files": ["acceptance/"], "command": "python3 -m unittest discover -s acceptance"},
  "verify": {"tests": "python3 -m unittest discover -s tests"},
  "docs": {"files": ["README.md"], "codemap": null},
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": ["shop/money.py", "tests/test_money.py"],
     "acs": ["AC-001", "AC-002", "AC-003", "AC-004"], "mirror": ["shop/money.py:9-16", "tests/test_money.py:1-31"]},
    {"id": "WP-02", "wave": 1, "depends_on": [], "files": ["shop/cart.py", "tests/test_cart.py"],
     "acs": ["AC-005", "AC-006", "AC-007"], "mirror": ["shop/cart.py:11-15", "tests/test_cart.py:1-27"]}
  ]
}
```

## 9. Test strategy
- Unit: each WP updates and extends its own tests in `tests/`, with `unittest`.
- Acceptance: written first from the ACs in `acceptance/`.
- QA: exploratory, after integration.

## 10. Decisions
- The currency is an argument of `parse_price`, so the text and the expected currency are checked in one place.
- Two modules that do not import each other's tests, so both packages fit in one wave.

## 11. Risks and open questions
None.
