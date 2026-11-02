"""A cart of priced lines."""
from __future__ import annotations

from shop.money import parse_price


class Cart:
    def __init__(self) -> None:
        self._items: list[tuple[str, int, int]] = []

    def add(self, name: str, price_text: str, qty: int = 1) -> None:
        if qty < 1:
            raise ValueError("qty must be at least 1")
        cents = parse_price(price_text)
        self._items.append((name, qty, cents))

    def total(self) -> int:
        return sum(qty * cents for _, qty, cents in self._items)

    def lines(self) -> list[tuple[str, int, int]]:
        return [(name, qty, qty * cents) for name, qty, cents in self._items]
