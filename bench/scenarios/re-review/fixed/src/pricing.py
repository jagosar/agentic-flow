DISCOUNT_FROM_CENTS = 25000
DISCOUNT_RATE = 0.15


def discount(total_cents: int) -> int:
    if total_cents >= DISCOUNT_FROM_CENTS:
        return round(total_cents * (1 - DISCOUNT_RATE))
    return total_cents


def basket_total(lines: list[dict]) -> int:
    return sum(line["price_cents"] * line["quantity"] for line in lines
               if line.get("price_cents") is not None and line.get("quantity", 0) > 0)
