"""Acceptance tests of roster/shifts.py: AC-004, AC-005 and AC-006."""
import unittest


class ShiftTests(unittest.TestCase):
    def test_shift_text_becomes_an_interval(self):
        """AC-004"""
        from roster.intervals import Interval
        from roster.shifts import parse_shift

        self.assertEqual(parse_shift("09:00-17:30"), Interval(540, 1050))
        self.assertEqual(parse_shift("22:00-06:00"), Interval(1320, 1800))

    def test_an_interval_becomes_shift_text(self):
        """AC-005"""
        from roster.intervals import Interval
        from roster.shifts import format_shift

        self.assertEqual(format_shift(Interval(540, 1050)), "09:00-17:30")
        self.assertEqual(format_shift(Interval(1320, 1800)), "22:00-06:00")

    def test_nonsense_shift_text_is_rejected(self):
        """AC-006"""
        from roster.shifts import parse_shift

        for text in ("", "abc", "25:00-26:00"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_shift(text)
