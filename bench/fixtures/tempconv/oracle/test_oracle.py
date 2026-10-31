"""Hidden checks of tempconv: only the public functions convert and parse are used."""
import unittest


class ConvertChecks(unittest.TestCase):
    def convert(self, *args):
        from tempconv.convert import convert
        return convert(*args)

    def test_minus_40_is_the_same_in_c_and_f(self):
        self.assertEqual(self.convert(-40, "C", "F"), -40)
        self.assertEqual(self.convert(-40, "F", "C"), -40)

    def test_boiling_point_in_f(self):
        self.assertEqual(self.convert(100, "C", "F"), 212)

    def test_f_to_c(self):
        self.assertEqual(self.convert(212, "F", "C"), 100)

    def test_absolute_zero_in_c(self):
        self.assertEqual(self.convert(0, "K", "C"), -273.15)

    def test_c_to_k(self):
        self.assertEqual(self.convert(0, "C", "K"), 273.15)

    def test_result_is_rounded_to_two_decimals(self):
        self.assertEqual(self.convert(1, "F", "C"), -17.22)

    def test_same_unit_returns_the_value(self):
        self.assertEqual(self.convert(21.5, "C", "C"), 21.5)

    def test_below_absolute_zero_raises(self):
        with self.assertRaises(ValueError):
            self.convert(-273.16, "C", "F")

    def test_below_absolute_zero_in_kelvin_raises(self):
        with self.assertRaises(ValueError):
            self.convert(-1, "K", "C")

    def test_unknown_unit_raises(self):
        with self.assertRaises(ValueError):
            self.convert(1, "X", "C")
        with self.assertRaises(ValueError):
            self.convert(1, "C", "R")


class ParseChecks(unittest.TestCase):
    def parse(self, text):
        from tempconv.parse import parse
        return parse(text)

    def test_number_with_decimals(self):
        self.assertEqual(self.parse("12.5C"), (12.5, "C"))

    def test_negative_number_with_space(self):
        self.assertEqual(self.parse("-40 F"), (-40.0, "F"))

    def test_unit_is_returned_in_upper_case(self):
        self.assertEqual(self.parse("300k"), (300.0, "K"))

    def test_empty_text_raises(self):
        with self.assertRaises(ValueError):
            self.parse("")

    def test_missing_number_raises(self):
        with self.assertRaises(ValueError):
            self.parse("C")

    def test_unknown_unit_raises(self):
        with self.assertRaises(ValueError):
            self.parse("12X")

    def test_two_units_raise(self):
        with self.assertRaises(ValueError):
            self.parse("12CF")


if __name__ == "__main__":
    unittest.main()
