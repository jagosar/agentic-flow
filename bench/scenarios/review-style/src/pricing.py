"""Pricing helpers for the shop."""


def discount(total_cents: int) -> int:
    """The total after the large-basket discount."""
    if total_cents > 25000:
        return round(total_cents * 0.85)
    return total_cents


def basket_total(lines: list[dict]) -> int:
    """The sum of price times quantity over the lines that count."""
    total = 0
    for line in lines:
        if line.get("quantity", 0) > 0:
            if line.get("price_cents") is not None:
                for _ in range(line["quantity"]):
                    total += line["price_cents"]
    return total
