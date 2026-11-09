"""Acceptance tests of roster/intervals.py: AC-001, AC-002 and AC-003."""
import unittest


class IntervalTests(unittest.TestCase):
    def test_overlap_of_two_intervals(self):
        """AC-001"""
        from roster.intervals import Interval, overlaps

        self.assertTrue(overlaps(Interval(540, 720), Interval(600, 900)))
        self.assertFalse(overlaps(Interval(540, 600), Interval(700, 900)))

    def test_merging_intervals(self):
        """AC-002"""
        from roster.intervals import Interval, merge

        given = [Interval(700, 900), Interval(540, 720), Interval(1000, 1100)]
        copy = list(given)
        self.assertEqual(merge(given), [Interval(540, 900), Interval(1000, 1100)])
        self.assertEqual(given, copy)

    def test_gaps_in_a_window(self):
        """AC-003"""
        from roster.intervals import Interval, gaps

        result = gaps([Interval(600, 700), Interval(800, 900)], Interval(540, 1000))
        self.assertEqual(result, [Interval(540, 600), Interval(700, 800), Interval(900, 1000)])
