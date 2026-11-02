"""Tests of shop.money."""
import unittest

from shop.money import format_cents, parse_price


class ParsePriceTests(unittest.TestCase):
    def test_parses_two_decimals(self):
        self.assertEqual(parse_price("12.50"), 1250)

    def test_parses_whole_amount(self):
        self.assertEqual(parse_price("3"), 300)

    def test_one_decimal_is_tenths(self):
        self.assertEqual(parse_price("0.5"), 50)

    def test_rejects_empty_negative_and_three_decimals(self):
        for text in ("", "-1.00", "1.234", "abc"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_price(text)


class FormatCentsTests(unittest.TestCase):
    def test_formats_positive_and_negative(self):
        self.assertEqual(format_cents(1250), "12.50")
        self.assertEqual(format_cents(-5), "-0.05")


if __name__ == "__main__":
    unittest.main()
