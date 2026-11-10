"""Pricing helpers for the shop."""

DISCOUNT_THRESHOLD_CENTS = 25000
DISCOUNT_FACTOR = 0.85


def discount(total_cents: int) -> int:
    """The total after the large-basket discount."""
    if total_cents > DISCOUNT_THRESHOLD_CENTS:
        return total_cents * DISCOUNT_FACTOR
    return total_cents


def basket_total(lines: list[dict]) -> int:
    """The sum of price times quantity over the lines that count."""
    return sum(line["price_cents"] * line["quantity"] for line in lines
               if line.get("quantity", 0) > 0 and line.get("price_cents") is not None)
