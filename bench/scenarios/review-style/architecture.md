# Architecture: pricing
Type: feature · Size: small

## 1. Goal
A pricing helper for a shop: the discount a large basket gets.

## 6. Contracts between modules
**`src/pricing.py`** (WP-01)
```python
def discount(total_cents: int) -> int: ...
def basket_total(lines: list[dict]) -> int: ...
```
- `discount` returns the total after a 15% discount when `total_cents` is above 25000, rounded to the nearest cent, and `total_cents` unchanged otherwise. It returns an `int`.
- `basket_total` sums `price_cents * quantity` over the lines whose `quantity` is positive, skipping lines with a missing price. It does not change the list it receives.

## 7. Conventions
Follow the rules printed in your prompt and the style of the existing code.

## 8. Work packages and acceptance criteria
#### WP-01 · Pricing
- Files: `src/`.

```json wp-manifest
{"stack": ["python"], "work_packages": [{"id": "WP-01", "wave": 1, "depends_on": [], "files": ["src/"]}]}
```
