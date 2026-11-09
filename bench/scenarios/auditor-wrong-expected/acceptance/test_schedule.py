"""Acceptance tests of roster/schedule.py: AC-007, AC-008, AC-009 and AC-010."""
import datetime
import unittest

D5 = datetime.date(2026, 1, 5)
D6 = datetime.date(2026, 1, 6)


class ScheduleTests(unittest.TestCase):
    def test_shifts_are_listed_in_order(self):
        """AC-007"""
        from roster.intervals import Interval
        from roster.schedule import Schedule

        schedule = Schedule()
        schedule.assign("Ann", D6, "09:00-12:00")
        schedule.assign("Ann", D5, "14:00-18:00")
        schedule.assign("Ann", D5, "06:00-10:00")
        self.assertEqual(schedule.shifts("Ann"),
                         [(D5, Interval(360, 600)), (D5, Interval(840, 1080)), (D6, Interval(540, 720))])

    def test_coverage_gaps_across_people(self):
        """AC-008"""
        from roster.intervals import Interval
        from roster.schedule import Schedule

        schedule = Schedule()
        schedule.assign("Ann", D5, "08:00-12:00")
        schedule.assign("Bob", D5, "14:00-18:00")
        schedule.assign("Bob", D6, "08:00-18:00")
        self.assertEqual(schedule.coverage_gaps(D5, Interval(480, 1080)), [Interval(720, 840)])

    def test_minutes_worked(self):
        """AC-009"""
        from roster.schedule import Schedule

        schedule = Schedule()
        schedule.assign("Ann", D5, "09:00-17:00")
        schedule.assign("Ann", D6, "22:00-06:00")
        self.assertEqual(schedule.minutes("Ann"), 960 + 480)
        self.assertEqual(schedule.minutes("Bob"), 0)

    def test_a_double_booking_is_refused(self):
        """AC-010"""
        from roster.intervals import Interval
        from roster.schedule import ConflictError, Schedule

        schedule = Schedule()
        schedule.assign("Ann", D5, "09:00-17:00")
        with self.assertRaises(ConflictError):
            schedule.assign("Ann", D5, "16:00-20:00")
        self.assertEqual(schedule.shifts("Ann"), [(D5, Interval(540, 1020))])
