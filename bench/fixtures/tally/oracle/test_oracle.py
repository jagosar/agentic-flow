"""Hidden checks of the tally fixture. Each test imports inside, so a missing module fails one test."""
import datetime
import unittest

D = datetime.date


def make_ledger(*rows):
    from tally.ledger import Ledger

    ledger = Ledger()
    for row in rows:
        ledger.add(*row)
    return ledger


class MoneyTests(unittest.TestCase):
    def test_parse_amount_plain(self):
        from tally.money import parse_amount

        self.assertEqual(parse_amount("12.30"), 1230)
        self.assertEqual(parse_amount("12"), 1200)
        self.assertEqual(parse_amount("0.5"), 50)
        self.assertEqual(parse_amount("0.29"), 29)

    def test_parse_amount_negative_and_spaces(self):
        from tally.money import parse_amount

        self.assertEqual(parse_amount("-3.10"), -310)
        self.assertEqual(parse_amount("  7.25 "), 725)

    def test_parse_amount_rejects_garbage(self):
        from tally.money import parse_amount

        for text in ("", "   ", "abc", "$5", "1,000.00", "1.", ".5", "1e3"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_amount(text)

    def test_edge_two_decimal_limit(self):
        from tally.money import parse_amount

        for text in ("1.234", "0.001", "5.999"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_amount(text)

    def test_format_amount(self):
        from tally.money import format_amount

        self.assertEqual(format_amount(1230), "12.30")
        self.assertEqual(format_amount(0), "0.00")
        self.assertEqual(format_amount(-5), "-0.05")

    def test_split_even(self):
        from tally.money import split

        self.assertEqual(split(90, 3), [30, 30, 30])
        self.assertEqual(split(7, 1), [7])

    def test_split_rejects_no_parts(self):
        from tally.money import split

        for parts in (0, -2):
            with self.assertRaises(ValueError):
                split(100, parts)

    def test_edge_largest_remainder(self):
        from tally.money import split

        self.assertEqual(split(100, 3), [34, 33, 33])
        self.assertEqual(split(10, 4), [3, 3, 2, 2])
        self.assertEqual(split(2, 5), [1, 1, 0, 0, 0])

    def test_edge_negative_split(self):
        from tally.money import split

        self.assertEqual(split(-100, 3), [-34, -33, -33])
        self.assertEqual(split(-10, 4), [-3, -3, -2, -2])

    def test_edge_bool_as_parts(self):
        from tally.money import split

        with self.assertRaises(ValueError):
            split(100, True)


class DatesTests(unittest.TestCase):
    def test_parse_date_plain(self):
        from tally.dates import parse_date

        self.assertEqual(parse_date("2026-01-05"), D(2026, 1, 5))

    def test_parse_date_rejects_garbage(self):
        from tally.dates import parse_date

        for text in ("", "tomorrow", "2026-13-01", "2026/01/05"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_date(text)

    def test_edge_leap_day(self):
        from tally.dates import month_end, parse_date

        self.assertEqual(parse_date("2024-02-29"), D(2024, 2, 29))
        self.assertEqual(month_end(D(2024, 2, 10)), D(2024, 2, 29))
        self.assertEqual(month_end(D(2023, 2, 10)), D(2023, 2, 28))

    def test_edge_invalid_29_february(self):
        from tally.dates import parse_date

        with self.assertRaises(ValueError):
            parse_date("2023-02-29")

    def test_edge_unpadded_date(self):
        from tally.dates import parse_date

        for text in ("2026-1-5", "2026-01-5", "2026-1-05"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_date(text)

    def test_month_end_plain(self):
        from tally.dates import month_end

        self.assertEqual(month_end(D(2026, 4, 1)), D(2026, 4, 30))
        self.assertEqual(month_end(D(2026, 1, 31)), D(2026, 1, 31))

    def test_months_between_one_month(self):
        from tally.dates import months_between

        self.assertEqual(
            months_between(D(2026, 3, 5), D(2026, 3, 20)), [(D(2026, 3, 5), D(2026, 3, 20))]
        )

    def test_edge_month_rollover_across_a_year(self):
        from tally.dates import months_between

        self.assertEqual(
            months_between(D(2025, 11, 20), D(2026, 1, 5)),
            [
                (D(2025, 11, 20), D(2025, 11, 30)),
                (D(2025, 12, 1), D(2025, 12, 31)),
                (D(2026, 1, 1), D(2026, 1, 5)),
            ],
        )

    def test_edge_clipped_periods(self):
        from tally.dates import months_between

        self.assertEqual(
            months_between(D(2024, 1, 31), D(2024, 3, 1)),
            [
                (D(2024, 1, 31), D(2024, 1, 31)),
                (D(2024, 2, 1), D(2024, 2, 29)),
                (D(2024, 3, 1), D(2024, 3, 1)),
            ],
        )

    def test_months_between_rejects_reversed_range(self):
        from tally.dates import months_between

        with self.assertRaises(ValueError):
            months_between(D(2026, 2, 1), D(2026, 1, 31))


class LedgerTests(unittest.TestCase):
    def test_add_returns_expense(self):
        ledger = make_ledger()
        expense = ledger.add("2026-01-05", " Ann ", "12.50", ["Bob", " Ann"], "lunch")
        self.assertEqual(expense.date, D(2026, 1, 5))
        self.assertEqual(expense.payer, "Ann")
        self.assertEqual(expense.cents, 1250)
        self.assertEqual(expense.description, "lunch")

    def test_add_description_defaults_to_empty(self):
        expense = make_ledger().add("2026-01-05", "Ann", "1", ["Ann"])
        self.assertEqual(expense.description, "")

    def test_add_rejects_non_positive_amount(self):
        ledger = make_ledger()
        for amount in ("0", "0.00", "-5"):
            with self.subTest(amount=amount):
                with self.assertRaises(ValueError):
                    ledger.add("2026-01-05", "Ann", amount, ["Ann"])
        self.assertEqual(ledger.balances(), {})

    def test_add_rejects_empty_names(self):
        ledger = make_ledger()
        with self.assertRaises(ValueError):
            ledger.add("2026-01-05", "  ", "5", ["Ann"])
        with self.assertRaises(ValueError):
            ledger.add("2026-01-05", "Ann", "5", ["Bob", " "])
        self.assertEqual(ledger.balances(), {})

    def test_edge_duplicate_participants(self):
        ledger = make_ledger()
        with self.assertRaises(ValueError):
            ledger.add("2026-01-05", "Ann", "5", ["Bob", "Bob"])
        with self.assertRaises(ValueError):
            ledger.add("2026-01-05", "Ann", "5", ["Bob", " Bob "])
        self.assertEqual(ledger.balances(), {})

    def test_balances_payer_not_a_participant(self):
        ledger = make_ledger(("2026-01-05", "Ann", "10", ["Bob", "Cy"]))
        self.assertEqual(ledger.balances(), {"Ann": 1000, "Bob": -500, "Cy": -500})

    def test_balances_include_everyone_sorted(self):
        ledger = make_ledger(("2026-01-05", "Zed", "10", ["Zed"]), ("2026-01-06", "Amy", "4", ["Amy", "Zed"]))
        balances = ledger.balances()
        self.assertEqual(list(balances), ["Amy", "Zed"])
        self.assertEqual(balances, {"Amy": 200, "Zed": -200})

    def test_balances_sum_to_zero(self):
        ledger = make_ledger(
            ("2026-01-05", "Ann", "10.00", ["Ann", "Bob", "Cy"]),
            ("2026-01-06", "Bob", "0.07", ["Ann", "Bob", "Cy"]),
        )
        self.assertEqual(sum(ledger.balances().values()), 0)

    def test_edge_extra_cents_to_first_sorted_names(self):
        ledger = make_ledger(("2026-01-05", "Dan", "1.00", ["Cy", "Ann", "Bob"]))
        self.assertEqual(ledger.balances(), {"Ann": -34, "Bob": -33, "Cy": -33, "Dan": 100})
        self.assertEqual(ledger.add("2026-01-06", "Dan", "1", ["Cy", "Ann"]).participants, ("Ann", "Cy"))

    def test_edge_inclusive_balance_bounds(self):
        ledger = make_ledger(
            ("2026-01-01", "Ann", "10", ["Bob"]),
            ("2026-01-15", "Ann", "20", ["Bob"]),
            ("2026-01-31", "Ann", "40", ["Bob"]),
        )
        self.assertEqual(ledger.balances(D(2026, 1, 15), D(2026, 1, 15)), {"Ann": 2000, "Bob": -2000})
        self.assertEqual(ledger.balances(D(2026, 1, 2)), {"Ann": 6000, "Bob": -6000})
        self.assertEqual(ledger.balances(end=D(2026, 1, 1)), {"Ann": 1000, "Bob": -1000})
        self.assertEqual(ledger.balances(D(2026, 1, 1), D(2026, 1, 31)), {"Ann": 7000, "Bob": -7000})

    def test_balances_list_people_outside_the_range_at_zero(self):
        ledger = make_ledger(("2026-01-01", "Ann", "10", ["Bob"]), ("2026-03-01", "Cy", "9", ["Dee"]))
        self.assertEqual(
            ledger.balances(D(2026, 3, 1), D(2026, 3, 31)),
            {"Ann": 0, "Bob": 0, "Cy": 900, "Dee": -900},
        )


class SettleTests(unittest.TestCase):
    def test_settle_example(self):
        from tally.settle import settle

        self.assertEqual(
            settle({"A": -10, "B": -10, "C": 20}), [("A", "C", 10), ("B", "C", 10)]
        )

    def test_settle_all_zero(self):
        from tally.settle import settle

        self.assertEqual(settle({"A": 0, "B": 0}), [])
        self.assertEqual(settle({}), [])

    def test_settle_largest_first(self):
        from tally.settle import settle

        self.assertEqual(
            settle({"A": -30, "B": -70, "C": 60, "D": 40}),
            [("B", "C", 60), ("A", "D", 30), ("B", "D", 10)],
        )

    def test_settle_brings_everything_to_zero_in_few_transfers(self):
        from tally.settle import settle

        balances = {"A": -5, "B": 12, "C": -9, "D": 3, "E": -1}
        left = dict(balances)
        transfers = settle(balances)
        for debtor, creditor, cents in transfers:
            self.assertGreater(cents, 0)
            left[debtor] += cents
            left[creditor] -= cents
        self.assertEqual(set(left.values()), {0})
        self.assertLessEqual(len(transfers), len(balances) - 1)

    def test_settle_does_not_change_its_input(self):
        from tally.settle import settle

        balances = {"A": -1, "B": 1}
        settle(balances)
        self.assertEqual(balances, {"A": -1, "B": 1})

    def test_edge_settlement_tie_order(self):
        from tally.settle import settle

        self.assertEqual(
            settle({"B": -10, "A": -10, "C": 20}), [("A", "C", 10), ("B", "C", 10)]
        )
        self.assertEqual(
            settle({"Y": 10, "X": 10, "Z": -20}), [("Z", "X", 10), ("Z", "Y", 10)]
        )

    def test_edge_unbalanced_input(self):
        from tally.settle import settle

        for balances in ({"A": -10, "B": 5}, {"A": 1}):
            with self.assertRaises(ValueError):
                settle(balances)


class EndToEndTests(unittest.TestCase):
    def test_ledger_balances_settle(self):
        from tally.settle import settle

        ledger = make_ledger(
            ("2026-01-05", "Ann", "30.00", ["Ann", "Bob", "Cy"]),
            ("2026-01-09", "Bob", "9.00", ["Bob", "Cy"]),
        )
        self.assertEqual(ledger.balances(), {"Ann": 2000, "Bob": -550, "Cy": -1450})
        self.assertEqual(settle(ledger.balances()), [("Cy", "Ann", 1450), ("Bob", "Ann", 550)])


if __name__ == "__main__":
    unittest.main()
