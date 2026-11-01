"""Hidden checks of the roster fixture. Each test imports inside, so a missing module fails one test."""
import datetime
import unittest

D = datetime.date


def iv(start, end):
    from roster.intervals import Interval

    return Interval(start, end)


class IntervalTests(unittest.TestCase):
    def test_overlaps_true_for_shared_minutes(self):
        from roster.intervals import overlaps

        self.assertTrue(overlaps(iv(540, 720), iv(600, 900)))
        self.assertTrue(overlaps(iv(540, 900), iv(600, 700)))

    def test_overlaps_false_for_disjoint(self):
        from roster.intervals import overlaps

        self.assertFalse(overlaps(iv(540, 600), iv(700, 900)))

    def test_merge_joins_overlapping_sorted(self):
        from roster.intervals import merge

        result = merge([iv(700, 900), iv(540, 720), iv(1000, 1100)])
        self.assertEqual(result, [iv(540, 900), iv(1000, 1100)])

    def test_merge_keeps_input_unchanged(self):
        from roster.intervals import merge

        data = [iv(700, 900), iv(540, 720)]
        merge(data)
        self.assertEqual(data, [iv(700, 900), iv(540, 720)])

    def test_merge_empty(self):
        from roster.intervals import merge

        self.assertEqual(merge([]), [])

    def test_gaps_of_window(self):
        from roster.intervals import gaps

        result = gaps([iv(600, 700), iv(800, 900)], iv(540, 1000))
        self.assertEqual(result, [iv(540, 600), iv(700, 800), iv(900, 1000)])

    def test_gaps_fully_covered_is_empty(self):
        from roster.intervals import gaps

        self.assertEqual(gaps([iv(500, 1100)], iv(540, 1000)), [])

    def test_edge_interval_rejects_empty_and_reversed(self):
        for start, end in ((100, 100), (200, 100)):
            with self.subTest(start=start, end=end):
                with self.assertRaises(ValueError):
                    iv(start, end)

    def test_edge_interval_rejects_out_of_range(self):
        with self.assertRaises(ValueError):
            iv(-1, 10)
        with self.assertRaises(ValueError):
            iv(0, 2881)
        self.assertEqual(iv(0, 2880).end, 2880)

    def test_edge_touching_intervals_do_not_overlap(self):
        from roster.intervals import overlaps

        self.assertFalse(overlaps(iv(540, 720), iv(720, 900)))
        self.assertFalse(overlaps(iv(720, 900), iv(540, 720)))

    def test_edge_merge_joins_touching(self):
        from roster.intervals import merge

        self.assertEqual(merge([iv(720, 900), iv(540, 720)]), [iv(540, 900)])

    def test_edge_gaps_merge_overlapping_input(self):
        from roster.intervals import gaps

        result = gaps([iv(600, 800), iv(700, 900), iv(900, 950)], iv(540, 1000))
        self.assertEqual(result, [iv(540, 600), iv(950, 1000)])


class ShiftTests(unittest.TestCase):
    def test_parse_shift_day(self):
        from roster.shifts import parse_shift

        self.assertEqual(parse_shift("09:00-17:30"), iv(540, 1050))

    def test_parse_shift_overnight(self):
        from roster.shifts import parse_shift

        self.assertEqual(parse_shift("22:00-06:00"), iv(1320, 1800))

    def test_format_shift_day(self):
        from roster.shifts import format_shift

        self.assertEqual(format_shift(iv(540, 1050)), "09:00-17:30")

    def test_format_shift_overnight_prints_next_day_clock(self):
        from roster.shifts import format_shift

        self.assertEqual(format_shift(iv(1320, 1800)), "22:00-06:00")

    def test_parse_shift_rejects_garbage(self):
        from roster.shifts import parse_shift

        for text in ("", "abc", "09:00"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_shift(text)

    def test_edge_parse_shift_rejects_hour_24(self):
        from roster.shifts import parse_shift

        for text in ("24:00-01:00", "25:00-26:00"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_shift(text)

    def test_edge_parse_shift_needs_two_digits(self):
        from roster.shifts import parse_shift

        with self.assertRaises(ValueError):
            parse_shift("9:00-17:00")

    def test_edge_parse_shift_rejects_empty_shift(self):
        from roster.shifts import parse_shift

        with self.assertRaises(ValueError):
            parse_shift("09:00-09:00")

    def test_edge_parse_shift_rejects_minute_60(self):
        from roster.shifts import parse_shift

        with self.assertRaises(ValueError):
            parse_shift("09:60-10:00")


class ScheduleTests(unittest.TestCase):
    def schedule(self):
        from roster.schedule import Schedule

        return Schedule()

    def test_assign_returns_interval(self):
        self.assertEqual(self.schedule().assign("Ann", D(2026, 1, 5), "09:00-17:00"), iv(540, 1020))

    def test_shifts_sorted_by_day_then_start(self):
        s = self.schedule()
        s.assign("Ann", D(2026, 1, 6), "09:00-12:00")
        s.assign("Ann", D(2026, 1, 5), "14:00-18:00")
        s.assign("Ann", D(2026, 1, 5), "06:00-10:00")
        self.assertEqual(s.shifts("Ann"), [(D(2026, 1, 5), iv(360, 600)), (D(2026, 1, 5), iv(840, 1080)),
                                           (D(2026, 1, 6), iv(540, 720))])

    def test_shifts_of_unknown_person_is_empty(self):
        self.assertEqual(self.schedule().shifts("Zed"), [])

    def test_minutes_sums_lengths(self):
        s = self.schedule()
        s.assign("Ann", D(2026, 1, 5), "09:00-17:00")
        s.assign("Ann", D(2026, 1, 6), "22:00-06:00")
        self.assertEqual(s.minutes("Ann"), 480 + 480)
        self.assertEqual(s.minutes("Bob"), 0)

    def test_coverage_gaps_across_people(self):
        s = self.schedule()
        s.assign("Ann", D(2026, 1, 5), "08:00-12:00")
        s.assign("Bob", D(2026, 1, 5), "14:00-18:00")
        s.assign("Bob", D(2026, 1, 6), "08:00-18:00")
        result = s.coverage_gaps(D(2026, 1, 5), iv(480, 1080))
        self.assertEqual(result, [iv(720, 840)])

    def test_edge_assign_conflict_on_overlap(self):
        from roster.schedule import ConflictError

        s = self.schedule()
        s.assign("Ann", D(2026, 1, 5), "09:00-17:00")
        with self.assertRaises(ConflictError):
            s.assign("Ann", D(2026, 1, 5), "16:00-20:00")

    def test_edge_conflict_error_is_value_error(self):
        from roster.schedule import ConflictError

        self.assertTrue(issubclass(ConflictError, ValueError))

    def test_edge_touching_shifts_do_not_conflict(self):
        s = self.schedule()
        s.assign("Ann", D(2026, 1, 5), "09:00-12:00")
        s.assign("Ann", D(2026, 1, 5), "12:00-15:00")
        self.assertEqual(len(s.shifts("Ann")), 2)

    def test_edge_failed_assign_changes_nothing(self):
        s = self.schedule()
        s.assign("Ann", D(2026, 1, 5), "09:00-17:00")
        for text in ("16:00-20:00", "bad"):
            with self.assertRaises(ValueError):
                s.assign("Ann", D(2026, 1, 5), text)
        self.assertEqual(s.shifts("Ann"), [(D(2026, 1, 5), iv(540, 1020))])
        self.assertEqual(s.minutes("Ann"), 480)

    def test_edge_names_are_stripped(self):
        s = self.schedule()
        s.assign(" Ann ", D(2026, 1, 5), "09:00-10:00")
        self.assertEqual(s.minutes("Ann"), 60)
        self.assertEqual(len(s.shifts(" Ann")), 1)

    def test_edge_blank_name_is_rejected(self):
        for name in ("", "   "):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    self.schedule().assign(name, D(2026, 1, 5), "09:00-10:00")


class RestTests(unittest.TestCase):
    def violations(self, shifts, min_rest):
        from roster.rules import rest_violations

        return rest_violations(shifts, min_rest)

    def test_rest_far_above_minimum_is_fine(self):
        shifts = [(D(2026, 1, 5), iv(540, 1020)), (D(2026, 1, 6), iv(540, 1020))]
        self.assertEqual(self.violations(shifts, 480), [])

    def test_short_rest_is_a_violation(self):
        shifts = [(D(2026, 1, 5), iv(540, 1020)), (D(2026, 1, 5), iv(1200, 1400))]
        self.assertEqual(self.violations(shifts, 480), [(D(2026, 1, 5), D(2026, 1, 5))])

    def test_unsorted_input_is_ordered_by_day_and_start(self):
        shifts = [(D(2026, 1, 6), iv(1000, 1100)), (D(2026, 1, 5), iv(540, 1020)), (D(2026, 1, 6), iv(1300, 1400))]
        self.assertEqual(self.violations(shifts, 1440), [(D(2026, 1, 5), D(2026, 1, 6)),
                                                        (D(2026, 1, 6), D(2026, 1, 6))])

    def test_empty_and_single_have_no_violations(self):
        self.assertEqual(self.violations([], 480), [])
        self.assertEqual(self.violations([(D(2026, 1, 5), iv(540, 1020))], 480), [])

    def test_ctx_rest_equal_to_minimum_is_enough(self):
        shifts = [(D(2026, 1, 5), iv(540, 1020)), (D(2026, 1, 5), iv(1500, 1600))]
        self.assertEqual(self.violations(shifts, 480), [])
        self.assertEqual(self.violations(shifts, 481), [(D(2026, 1, 5), D(2026, 1, 5))])

    def test_ctx_rest_after_overnight_shift_counts_from_real_end(self):
        shifts = [(D(2026, 1, 5), iv(1320, 1800)), (D(2026, 1, 6), iv(480, 960))]
        self.assertEqual(self.violations(shifts, 300), [(D(2026, 1, 5), D(2026, 1, 6))])
        self.assertEqual(self.violations(shifts, 120), [])

    def test_ctx_overnight_with_enough_rest_is_fine(self):
        shifts = [(D(2026, 1, 5), iv(1320, 1800)), (D(2026, 1, 6), iv(840, 1200))]
        self.assertEqual(self.violations(shifts, 480), [])


if __name__ == "__main__":
    unittest.main()
