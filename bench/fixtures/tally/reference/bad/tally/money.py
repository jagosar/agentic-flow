"""Amounts in cents."""
from __future__ import annotations


def parse_amount(text: str) -> int:
    try:
        return int(round(float(text.strip()) * 100))
    except ValueError:
        raise ValueError(f"invalid amount: {text!r}") from None


def format_amount(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    whole, frac = divmod(abs(cents), 100)
    return f"{sign}{whole}.{frac:02d}"


def split(cents: int, parts: int) -> list[int]:
    if parts < 1:
        raise ValueError("parts must be at least 1")
    share = round(cents / parts)
    shares = [share] * parts
    shares[0] += cents - share * parts
    return shares
