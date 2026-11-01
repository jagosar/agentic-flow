"""Settlement of balances into transfers."""
from __future__ import annotations


def settle(balances: dict[str, int]) -> list[tuple[str, str, int]]:
    if sum(balances.values()) != 0:
        raise ValueError("balances do not sum to 0")
    left = dict(balances)
    transfers = []
    while any(left.values()):
        debtor = min(left, key=lambda name: left[name])
        creditor = min(left, key=lambda name: -left[name])
        cents = min(-left[debtor], left[creditor])
        left[debtor] += cents
        left[creditor] -= cents
        transfers.append((debtor, creditor, cents))
    return transfers
