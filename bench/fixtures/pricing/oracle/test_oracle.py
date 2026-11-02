"""Hidden checks of the pricing fixture. Each test imports inside and touches the new behaviour, so the bare repo fails
every one of them."""
import unittest


class MoneyTests(unittest.TestCase):
    def test_ac_plain_price_in_eur(self):
        from shop.money import parse_price

        self.assertEqual(parse_price("12.50", "EUR"), 1250)

    def test_ac_plain_price_in_usd(self):
        from shop.money import parse_price

        self.assertEqual(parse_price("3", "USD"), 300)

    def test_ac_prefix_of_the_same_currency(self):
        from shop.money import parse_price

        self.assertEqual(parse_price("EUR 12.50", "EUR"), 1250)
        self.assertEqual(parse_price("GBP 0.5", "GBP"), 50)

    def test_ac_prefix_of_another_currency_is_a_mismatch(self):
        from shop.money import CurrencyMismatch, parse_price

        with self.assertRaises(CurrencyMismatch):
            parse_price("USD 1.00", "EUR")

    def test_ac_mismatch_is_a_value_error(self):
        from shop.money import CurrencyMismatch

        self.assertTrue(issubclass(CurrencyMismatch, ValueError))

    def test_ac_unknown_currency_argument(self):
        from shop.money import parse_price

        with self.assertRaises(ValueError):
            parse_price("1.00", "JPY")

    def test_ac_unknown_prefix_is_a_plain_value_error(self):
        from shop.money import parse_price

        with self.assertRaises(ValueError) as caught:
            parse_price("JPY 1.00", "EUR")
        self.assertIs(type(caught.exception), ValueError)

    def test_ac_prefix_needs_the_space(self):
        from shop.money import parse_price

        with self.assertRaises(ValueError):
            parse_price("EUR12.50", "EUR")

    def test_ac_old_errors_still_raise(self):
        from shop.money import parse_price

        for text in ("", "-1.00", "1.234", "abc", "EUR ", "EUR -1.00"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_price(text, "EUR")

    def test_ac_currencies_constant(self):
        from shop.money import CURRENCIES

        self.assertEqual(CURRENCIES, ("EUR", "USD", "GBP"))

    def test_ac_format_cents_unchanged(self):
        from shop.money import format_cents, parse_price

        self.assertEqual(parse_price("0.05", "EUR"), 5)
        self.assertEqual(format_cents(1250), "12.50")
        self.assertEqual(format_cents(-5), "-0.05")


class CartTests(unittest.TestCase):
    def test_ac_cart_defaults_to_eur(self):
        from shop.cart import Cart

        self.assertEqual(Cart().currency, "EUR")

    def test_ac_cart_in_usd(self):
        from shop.cart import Cart

        cart = Cart(currency="USD")
        cart.add("pen", "1.20", 3)
        cart.add("ink", "USD 4")
        self.assertEqual(cart.currency, "USD")
        self.assertEqual(cart.total(), 760)
        self.assertEqual(cart.lines(), [("pen", 3, 360), ("ink", 1, 400)])

    def test_ac_cart_refuses_another_currency_and_stays_unchanged(self):
        from shop.cart import Cart
        from shop.money import CurrencyMismatch

        cart = Cart(currency="USD")
        with self.assertRaises(CurrencyMismatch):
            cart.add("pen", "EUR 1.00")
        self.assertEqual(cart.lines(), [])

    def test_ac_cart_unknown_currency(self):
        from shop.cart import Cart

        with self.assertRaises(ValueError):
            Cart(currency="JPY")

    def test_ac_cart_still_rejects_bad_qty_and_price(self):
        from shop.cart import Cart

        cart = Cart(currency="EUR")
        with self.assertRaises(ValueError):
            cart.add("pen", "1.00", 0)
        with self.assertRaises(ValueError):
            cart.add("pen", "1.234")
        self.assertEqual(cart.lines(), [])


class ContextTests(unittest.TestCase):
    """Code that already used parse_price with one argument must keep working."""

    def setUp(self):
        from shop.money import parse_price

        self.assertEqual(parse_price("EUR 1.00", "EUR"), 100)

    def test_ctx_two_rows(self):
        from shop.receipt import from_rows

        text = from_rows([("pen", "1.20", 3), ("ink", "4", 1)])
        self.assertEqual(text.splitlines(), ["pen x3  3.60", "ink x1  4.00", "TOTAL  7.60"])

    def test_ctx_row_with_currency_prefix(self):
        from shop.receipt import from_rows

        self.assertEqual(from_rows([("pen", "EUR 2.50", 2)]).splitlines(), ["pen x2  5.00", "TOTAL  5.00"])

    def test_ctx_total_line(self):
        from shop.receipt import from_rows

        self.assertEqual(from_rows([]), "TOTAL  0.00")
        self.assertEqual(from_rows([("a", "0.10", 1), ("b", "0.20", 1)]).splitlines()[-1], "TOTAL  0.30")


if __name__ == "__main__":
    unittest.main()
