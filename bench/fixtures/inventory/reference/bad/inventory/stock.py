"""Stock by SKU."""


class InsufficientStock(Exception):
    """Removing more than the stock holds."""


def _sku(sku):
    if not isinstance(sku, str) or not sku.strip():
        raise ValueError("the SKU must be a non-empty string")
    return sku.strip().upper()


def _qty(qty):
    if not isinstance(qty, int) or qty <= 0:
        raise ValueError("the quantity must be a positive integer")
    return qty


class Inventory:
    def __init__(self):
        self._stock = {}

    def add(self, sku, qty):
        key, amount = _sku(sku), _qty(qty)
        self._stock[key] = self._stock.get(key, 0) + amount

    def remove(self, sku, qty):
        key, amount = _sku(sku), _qty(qty)
        self._stock[key] = self._stock.get(key, 0) - amount
        if self._stock[key] < 0:
            raise InsufficientStock(f"{key}: not enough stock for {amount}")

    def quantity(self, sku):
        return self._stock.get(_sku(sku), 0)

    def items(self):
        return dict(self._stock)
