"""QA tests for the vault and tally bench fixtures.
Run: python3 -m unittest discover -s qa -p "test_qa_fixtures.py"
Mutation tests: each mutant of a good reference must be killed by the fixture's oracle.
Tests named test_dN_ reproduce defect N and stay red on purpose until it is fixed."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ORACLE_TIMEOUT = 20
FIXTURES = Path(__file__).resolve().parent.parent / "bench" / "fixtures"


def run_oracle(case, name, edits):
    """Oracle result (returncode, output) on repo/ + good reference with `edits` applied.
    edits: list of (module file relative to the package dir, old text, new text)."""
    tmp = tempfile.TemporaryDirectory()
    case.addCleanup(tmp.cleanup)
    work = Path(tmp.name) / "work"
    shutil.copytree(FIXTURES / name / "repo", work)
    shutil.copytree(FIXTURES / name / "reference" / "good", work, dirs_exist_ok=True)
    for rel, old, new in edits:
        target = work / name / rel
        text = target.read_text(encoding="utf-8")
        case.assertIn(old, text, "mutation anchor missing: %r" % old)
        target.write_text(text.replace(old, new, 1), encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(work))
    oracle = FIXTURES / name / "oracle"
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", str(oracle), "-t", str(oracle), "-v"],
            cwd=work, env=env, capture_output=True, text=True, timeout=ORACLE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return 1, "oracle run hung (mutant loops forever): counts as killed"
    return proc.returncode, proc.stdout + proc.stderr


class VaultMutants(unittest.TestCase):
    def assert_killed(self, edits):
        code, out = run_oracle(self, "vault", edits)
        self.assertNotEqual(code, 0, "oracle did not notice the mutant:\n" + out[-800:])

    def test_control_unmutated_good_passes(self):
        code, out = run_oracle(self, "vault", [])
        self.assertEqual(code, 0, out[-800:])

    def test_mutant_storage_returns_base_for_dot(self):
        self.assert_killed([
            ("storage.py", 'any(part in (".", "..") for part in parts)', "False"),
            ("storage.py", "common == real_root and real_path != real_root", "common == real_root"),
        ])

    def test_mutant_token_ignores_expiry(self):
        self.assert_killed([("tokens.py", "if now >= expires_at:", "if False:")])

    def test_mutant_token_expires_one_late(self):
        self.assert_killed([("tokens.py", "if now >= expires_at:", "if now > expires_at:")])

    def test_mutant_token_ignores_secret(self):
        self.assert_killed([("tokens.py", "hmac.new(secret, payload", "hmac.new(b'x', payload")])

    def test_mutant_token_skips_mac_compare(self):
        self.assert_killed([("tokens.py", "if not hmac.compare_digest(_decode(parts[1]), _mac(secret, payload)):", "if False:")])

    def test_d2_mutant_token_mac_covers_only_file_id(self):
        # D2: a MAC over the file id only lets an attacker extend the expiry; the oracle's
        # flipped-character test accepts the original id, so this mutant survives.
        self.assert_killed([
            ("tokens.py", "return hmac.new(secret, payload, hashlib.sha256).digest()",
             "return hmac.new(secret, payload.rpartition(b':')[0], hashlib.sha256).digest()"),
        ])

    def test_mutant_catalogue_like_injection(self):
        self.assert_killed([
            ("catalogue.py", 'rows = self._conn.execute("SELECT name FROM files WHERE owner = ?", (owner,)).fetchall()',
             "rows = self._conn.execute(\"SELECT name FROM files WHERE owner = '%s'\" % owner).fetchall()"),
        ])

    def test_mutant_catalogue_case_sensitive(self):
        self.assert_killed([("catalogue.py", "needle in name.lower()", "text in name")])

    def test_mutant_catalogue_unsorted(self):
        self.assert_killed([("catalogue.py", "return sorted(name for (name,) in rows if needle in name.lower())",
                             "return [name for (name,) in rows if needle in name.lower()][::-1]")])

    def test_mutant_catalogue_ignores_owner(self):
        self.assert_killed([("catalogue.py", 'WHERE owner = ?", (owner,)', 'WHERE ? = ?", (owner, owner)')])


class TallyMutants(unittest.TestCase):
    def assert_killed(self, edits):
        code, out = run_oracle(self, "tally", edits)
        self.assertNotEqual(code, 0, "oracle did not notice the mutant:\n" + out[-800:])

    def test_control_unmutated_good_passes(self):
        code, out = run_oracle(self, "tally", [])
        self.assertEqual(code, 0, out[-800:])

    def test_mutant_split_extra_to_last(self):
        self.assert_killed([("money.py", "1 if i < extra else 0", "1 if i >= parts - extra else 0")])

    def test_mutant_split_negative_uses_floor(self):
        self.assert_killed([("money.py", "base, extra = divmod(abs(cents), parts)", "base, extra = divmod(cents, parts)"),
                            ("money.py", "sign = -1 if cents < 0 else 1", "sign = 1")])

    def test_mutant_split_accepts_zero_parts(self):
        self.assert_killed([("money.py", "isinstance(parts, bool) or parts < 1", "isinstance(parts, bool) or parts < 0")])

    def test_mutant_parse_amount_three_decimals(self):
        self.assert_killed([("money.py", r"\.[0-9]{1,2}", r"\.[0-9]{1,3}")])

    def test_mutant_format_loses_sign_of_small_negative(self):
        self.assert_killed([("money.py", 'sign = "-" if cents < 0 else ""', 'sign = "-" if cents <= -100 else ""')])

    def test_mutant_date_unpadded(self):
        self.assert_killed([("dates.py", r"[0-9]{4}-[0-9]{2}-[0-9]{2}", r"[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}"),
                            ("dates.py", "datetime.date.fromisoformat(text)",
                             "datetime.date(*map(int, text.split('-')))")])

    def test_mutant_month_end_ignores_leap(self):
        self.assert_killed([("dates.py", "return first_next - datetime.timedelta(days=1)",
                             "r = first_next - datetime.timedelta(days=1)\n    return r.replace(day=28) if r.month == 2 else r")])

    def test_mutant_months_between_reversed_ok(self):
        self.assert_killed([("dates.py", "if start > end:", "if False:")])

    def test_mutant_months_between_not_clipped(self):
        self.assert_killed([("dates.py", "min(month_end(first), end)", "month_end(first)")])

    def test_mutant_balances_exclusive_end(self):
        self.assert_killed([("ledger.py", "expense.date > end", "expense.date >= end")])

    def test_mutant_balances_exclusive_start(self):
        self.assert_killed([("ledger.py", "expense.date < start", "expense.date <= start")])

    def test_mutant_balances_only_people_in_range(self):
        self.assert_killed([("ledger.py", "result.setdefault(expense.payer, 0)\n            for name in expense.participants:\n                result.setdefault(name, 0)",
                             "pass")])

    def test_mutant_ledger_participants_unsorted(self):
        self.assert_killed([("ledger.py", "tuple(sorted(names))", "tuple(names)")])

    def test_mutant_ledger_no_duplicate_check(self):
        self.assert_killed([("ledger.py", "if len(set(names)) != len(names):", "if False:")])

    def test_mutant_ledger_accepts_zero_amount(self):
        self.assert_killed([("ledger.py", "if cents <= 0:", "if cents < 0:")])

    def test_mutant_ledger_failed_add_leaves_trace(self):
        self.assert_killed([("ledger.py", "        date = parse_date(date_text)\n",
                             "        date = parse_date(date_text)\n        self._expenses.append(Expense(date, payer.strip() or 'x', 1, ('x',), ''))\n")])

    def test_mutant_settle_ties_by_insertion(self):
        self.assert_killed([("settle.py", "key=lambda name: (left[name], name)", "key=lambda name: left[name]")])

    def test_mutant_settle_no_balance_check(self):
        self.assert_killed([("settle.py", "if sum(balances.values()) != 0:", "if False:")])

    def test_mutant_settle_mutates_input(self):
        self.assert_killed([("settle.py", "left = dict(balances)", "left = balances")])


class TallyContractProbes(unittest.TestCase):
    """Behaviour the plan states in words, probed on the good reference."""

    def setUp(self):
        sys.path.insert(0, str(FIXTURES / "tally" / "reference" / "good"))
        self.addCleanup(sys.path.remove, str(FIXTURES / "tally" / "reference" / "good"))
        for mod in [m for m in sys.modules if m == "tally" or m.startswith("tally.")]:
            del sys.modules[mod]
        self.addCleanup(lambda: [sys.modules.pop(m) for m in [m for m in sys.modules if m == "tally" or m.startswith("tally.")]])

    def test_d1_parse_amount_rejects_non_ascii_digits(self):
        # §5.2: "ValueError for ... anything else"; Arabic-Indic digits are not [0-9]
        from tally.money import parse_amount

        with self.assertRaises(ValueError):
            parse_amount("١٢")

    def test_parse_date_rejects_non_ascii_digits(self):
        # §5.2: "accepts exactly YYYY-MM-DD"
        from tally.dates import parse_date

        with self.assertRaises(ValueError):
            parse_date("２０２６-01-05")

    def test_split_conserves_sum(self):
        from tally.money import split

        for cents in (-1001, -1, 0, 1, 999, 100000):
            for parts in (1, 2, 3, 7, 13):
                self.assertEqual(sum(split(cents, parts)), cents)

    def test_parse_format_round_trip(self):
        from tally.money import format_amount, parse_amount

        for cents in (-100001, -5, 0, 5, 99, 100, 123456789):
            self.assertEqual(parse_amount(format_amount(cents)), cents)

    def test_settle_large_random_balanced(self):
        import random

        from tally.settle import settle

        rng = random.Random(7)
        names = ["n%02d" % i for i in range(30)]
        values = [rng.randint(-5000, 5000) for _ in names[:-1]]
        balances = dict(zip(names, values + [-sum(values)]))
        left = dict(balances)
        transfers = settle(balances)
        for debtor, creditor, cents in transfers:
            left[debtor] += cents
            left[creditor] -= cents
        self.assertEqual(set(left.values()), {0})
        self.assertLessEqual(len(transfers), len(balances) - 1)


if __name__ == "__main__":
    unittest.main()
