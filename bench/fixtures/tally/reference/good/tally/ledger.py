"""A ledger of shared expenses."""
from __future__ import annotations

import datetime
from dataclasses import dataclass

from tally.dates import parse_date
from tally.money import parse_amount, split


@dataclass(frozen=True)
class Expense:
    date: datetime.date
    payer: str
    cents: int
    participants: tuple[str, ...]
    description: str


class Ledger:
    def __init__(self) -> None:
        self._expenses: list[Expense] = []

    def add(
        self,
        date_text: str,
        payer: str,
        amount_text: str,
        participants: list[str],
        description: str = "",
    ) -> Expense:
        date = parse_date(date_text)
        cents = parse_amount(amount_text)
        if cents <= 0:
            raise ValueError("amount must be positive")
        payer = payer.strip()
        names = [name.strip() for name in participants]
        if not payer or not names or not all(names):
            raise ValueError("names must not be empty")
        if len(set(names)) != len(names):
            raise ValueError("duplicate participants")
        expense = Expense(date, payer, cents, tuple(sorted(names)), description)
        self._expenses.append(expense)
        return expense

    def balances(
        self,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> dict[str, int]:
        result: dict[str, int] = {}
        for expense in self._expenses:
            result.setdefault(expense.payer, 0)
            for name in expense.participants:
                result.setdefault(name, 0)
        for expense in self._expenses:
            if start is not None and expense.date < start:
                continue
            if end is not None and expense.date > end:
                continue
            result[expense.payer] += expense.cents
            shares = split(expense.cents, len(expense.participants))
            for name, share in zip(expense.participants, shares):
                result[name] -= share
        return dict(sorted(result.items()))
