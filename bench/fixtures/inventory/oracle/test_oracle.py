"""Hidden checks of the inventory fixture. Each test imports inside, so a missing module fails one test."""
import unittest


def make(*pairs):
    from inventory.stock import Inventory

    inv = Inventory()
    for sku, qty in pairs:
        inv.add(sku, qty)
    return inv


class StockTests(unittest.TestCase):
    def test_add_and_quantity(self):
        inv = make(("A", 2), ("A", 3))
        self.assertEqual(inv.quantity("A"), 5)

    def test_unknown_sku_is_zero(self):
        self.assertEqual(make().quantity("Z"), 0)

    def test_sku_is_normalised(self):
        inv = make((" ab-1 ", 5))
        self.assertEqual(inv.quantity("AB-1"), 5)
        self.assertEqual(inv.quantity("  ab-1"), 5)
        self.assertEqual(inv.items(), {"AB-1": 5})

    def test_remove_normalises_sku(self):
        inv = make(("A", 5))
        inv.remove(" a ", 2)
        self.assertEqual(inv.quantity("A"), 3)

    def test_empty_sku_rejected_on_add(self):
        inv = make()
        for sku in ("", "   "):
            with self.assertRaises(ValueError):
                inv.add(sku, 1)
        self.assertEqual(inv.items(), {})

    def test_empty_sku_rejected_on_remove_and_quantity(self):
        inv = make(("A", 1))
        with self.assertRaises(ValueError):
            inv.remove("  ", 1)
        with self.assertRaises(ValueError):
            inv.quantity("")

    def test_true_rejected_as_quantity(self):
        inv = make(("A", 5))
        with self.assertRaises(ValueError):
            inv.add("A", True)
        with self.assertRaises(ValueError):
            inv.remove("A", True)
        self.assertEqual(inv.quantity("A"), 5)

    def test_zero_and_negative_rejected(self):
        inv = make(("A", 5))
        for qty in (0, -1):
            with self.assertRaises(ValueError):
                inv.add("A", qty)
            with self.assertRaises(ValueError):
                inv.remove("A", qty)
        self.assertEqual(inv.quantity("A"), 5)

    def test_non_int_rejected(self):
        inv = make(("A", 5))
        for qty in (1.5, "2", None):
            with self.assertRaises(ValueError):
                inv.add("A", qty)

    def test_remove_beyond_stock_raises_and_keeps_stock(self):
        from inventory.stock import InsufficientStock

        inv = make(("A", 3))
        with self.assertRaises(InsufficientStock):
            inv.remove("A", 4)
        self.assertEqual(inv.quantity("A"), 3)

    def test_remove_unknown_sku_raises_and_creates_nothing(self):
        from inventory.stock import InsufficientStock

        inv = make()
        with self.assertRaises(InsufficientStock):
            inv.remove("B", 1)
        self.assertEqual(inv.items(), {})

    def test_items_is_a_copy(self):
        inv = make(("A", 2))
        snapshot = inv.items()
        snapshot["A"] = 99
        snapshot["B"] = 1
        self.assertEqual(inv.items(), {"A": 2})


class ReportTests(unittest.TestCase):
    def test_low_stock_is_strict_and_sorted(self):
        from inventory.report import low_stock

        inv = make(("A", 1), ("B", 5), ("C", 3))
        self.assertEqual(low_stock(inv, 5), [("A", 1), ("C", 3)])

    def test_sku_removed_to_zero_still_listed(self):
        from inventory.report import low_stock

        inv = make(("A", 1), ("B", 5), ("C", 2))
        inv.remove("C", 2)
        self.assertEqual(low_stock(inv, 5), [("C", 0), ("A", 1)])

    def test_ties_ordered_by_sku(self):
        from inventory.report import low_stock

        inv = make(("B", 2), ("A", 2), ("C", 2), ("D", 1))
        self.assertEqual(low_stock(inv, 10), [("D", 1), ("A", 2), ("B", 2), ("C", 2)])

    def test_nothing_below_threshold(self):
        from inventory.report import low_stock

        self.assertEqual(low_stock(make(("A", 5)), 5), [])


if __name__ == "__main__":
    unittest.main()
