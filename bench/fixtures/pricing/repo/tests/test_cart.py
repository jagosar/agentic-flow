"""Tests of shop.cart."""
import unittest

from shop.cart import Cart


class CartTests(unittest.TestCase):
    def test_total_and_lines(self):
        cart = Cart()
        cart.add("pen", "1.20", 3)
        cart.add("ink", "4")
        self.assertEqual(cart.total(), 760)
        self.assertEqual(cart.lines(), [("pen", 3, 360), ("ink", 1, 400)])

    def test_rejects_qty_below_one(self):
        with self.assertRaises(ValueError):
            Cart().add("pen", "1.00", 0)

    def test_rejects_a_bad_price_and_keeps_the_cart_unchanged(self):
        cart = Cart()
        with self.assertRaises(ValueError):
            cart.add("pen", "x")
        self.assertEqual(cart.lines(), [])


if __name__ == "__main__":
    unittest.main()
