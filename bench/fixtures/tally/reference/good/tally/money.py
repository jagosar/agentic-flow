"""Amounts in cents."""
from __future__ import annotations

import re

_AMOUNT = re.compile(r"-?[0-9]+(\.[0-9]{1,2})?")


def parse_amount(text: str) -> int:
    clean = text.strip()
    if not _AMOUNT.fullmatch(clean):
        raise ValueError(f"invalid amount: {text!r}")
    sign = -1 if clean.startswith("-") else 1
    whole, _, frac = clean.lstrip("-").partition(".")
    return sign * (int(whole) * 100 + int(frac.ljust(2, "0") or "0"))


def format_amount(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    whole, frac = divmod(abs(cents), 100)
    return f"{sign}{whole}.{frac:02d}"


def split(cents: int, parts: int) -> list[int]:
    if isinstance(parts, bool) or parts < 1:
        raise ValueError("parts must be at least 1")
    base, extra = divmod(abs(cents), parts)
    sign = -1 if cents < 0 else 1
    return [sign * (base + (1 if i < extra else 0)) for i in range(parts)]
