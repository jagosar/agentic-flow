"""Reports over an Inventory."""


def low_stock(inv, threshold):
    """Every SKU ever added whose quantity is below threshold, zeros included, sorted by quantity then SKU."""
    return sorted(((sku, qty) for sku, qty in inv.items().items() if qty < threshold), key=lambda p: (p[1], p[0]))
