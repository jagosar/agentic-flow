"""Prices as integer cents."""
from __future__ import annotations

import re

PRICE_RE = re.compile(r"(\d+)(?:\.(\d{1,2}))?")


def parse_price(text: str) -> int:
    """'12.50' -> 1250 (cents). ValueError for empty text, a negative amount, more than two decimals or no number."""
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
