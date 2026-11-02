"""Plain-text summaries of priced rows."""
from __future__ import annotations

from shop.money import format_cents, parse_price


def from_rows(rows: list[tuple[str, str, int]]) -> str:
    """rows of (name, price_text, qty) -> one line per row 'name x{qty}  {price}' and a last line 'TOTAL  {sum}'."""
    lines = []
    total = 0
    for name, price_text, qty in rows:
        cents = parse_price(price_text) * qty
        total += cents
        lines.append(f"{name} x{qty}  {format_cents(cents)}")
    lines.append(f"TOTAL  {format_cents(total)}")
    return "\n".join(lines)
