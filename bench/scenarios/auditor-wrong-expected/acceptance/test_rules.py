"""Acceptance tests of roster/rules.py: AC-011 and AC-012."""
import datetime
import unittest

D5 = datetime.date(2026, 1, 5)
D6 = datetime.date(2026, 1, 6)


class RestTests(unittest.TestCase):
    def test_a_short_rest_is_reported(self):
        """AC-011"""
        from roster.intervals import Interval
        from roster.rules import rest_violations

        shifts = [(D5, Interval(540, 1020)), (D5, Interval(1200, 1400)), (D6, Interval(540, 1020))]
        self.assertEqual(rest_violations(shifts, 480), [(D5, D5)])

    def test_few_shifts_no_violations(self):
        """AC-012"""
        from roster.intervals import Interval
        from roster.rules import rest_violations

        self.assertEqual(rest_violations([], 480), [])
        self.assertEqual(rest_violations([(D5, Interval(540, 1020))], 480), [])
