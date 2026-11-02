"""Prices as integer cents, in a currency."""
from __future__ import annotations

import re

CURRENCIES = ("EUR", "USD", "GBP")
PRICE_RE = re.compile(r"(\d+)(?:\.(\d{1,2}))?")


class CurrencyMismatch(ValueError):
    """The price text names a currency other than the expected one."""


def parse_price(text: str, currency: str) -> int:
    """'12.50' or 'EUR 12.50' (prefix, one space) -> 1250. currency not in CURRENCIES -> ValueError. A prefix that is
    a known currency other than `currency` -> CurrencyMismatch. Old errors unchanged."""
    if currency not in CURRENCIES:
        raise ValueError(f"unknown currency: {currency!r}")
    head, space, rest = text.partition(" ")
    if space:
        if head not in CURRENCIES:
            raise ValueError(f"not a price: {text!r}")
        if head != currency:
            raise CurrencyMismatch(f"{head} price in a {currency} context")
        text = rest
    match = PRICE_RE.fullmatch(text)
    if match is None:
        raise ValueError(f"not a price: {text!r}")
    whole, decimals = match.groups()
    return int(whole) * 100 + int((decimals or "").ljust(2, "0"))


def format_cents(cents: int) -> str:
    """1250 -> '12.50'; -5 -> '-0.05'."""
    sign = "-" if cents < 0 else ""
    whole, rest = divmod(abs(cents), 100)
    return f"{sign}{whole}.{rest:02d}"
