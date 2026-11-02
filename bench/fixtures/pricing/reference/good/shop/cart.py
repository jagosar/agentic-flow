"""A cart of priced lines, in one currency."""
from __future__ import annotations

from shop.money import CURRENCIES, parse_price


class Cart:
    def __init__(self, currency: str = "EUR") -> None:
        if currency not in CURRENCIES:
            raise ValueError(f"unknown currency: {currency!r}")
        self.currency = currency
        self._items: list[tuple[str, int, int]] = []

    def add(self, name: str, price_text: str, qty: int = 1) -> None:
        if qty < 1:
            raise ValueError("qty must be at least 1")
        cents = parse_price(price_text, self.currency)
        self._items.append((name, qty, cents))

    def total(self) -> int:
        return sum(qty * cents for _, qty, cents in self._items)

    def lines(self) -> list[tuple[str, int, int]]:
        return [(name, qty, qty * cents) for name, qty, cents in self._items]
