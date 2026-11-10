"""QA tests for the pricing fixture and the bench review fields (issue 69).
Run: python3 -m unittest discover -s qa -p "test_qa_pricing.py"."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH_PY = ROOT / "bench" / "bench.py"
FIXTURE = ROOT / "bench" / "fixtures" / "pricing"
spec = importlib.util.spec_from_file_location("bench_module_pricing", BENCH_PY)
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)

ORACLE = {"passed": 0, "total": 0}
KEYS = ("review_callers", "review_confirmed", "review_refuted")


def fields(result):
    out = bench._review_fields(result)
    return tuple(out[k] for k in KEYS)


class ReviewFieldEdgeTests(unittest.TestCase):
    def test_malformed_results_never_raise_and_give_nones(self):
        for result in (None, [], "x", 5, {}, {"review": None}, {"review": []}, {"review": 7}, {"review": {}}):
            self.assertEqual(fields(result), (None, None, None), result)

    def test_float_negative_and_huge_callers(self):
        self.assertIsNone(fields({"review": {"callers": 2.0}})[0])
        self.assertEqual(fields({"review": {"callers": -1}})[0], -1)
        self.assertEqual(fields({"review": {"callers": 10 ** 30}})[0], 10 ** 30)
        self.assertIsNone(fields({"review": {"callers": [1]}})[0])

    def test_tuple_or_dict_findings_are_not_lists(self):
        self.assertEqual(fields({"review": {"confirmed": ({},), "refuted": {"a": 1}}})[1:], (None, None))

    def test_empty_lists_count_zero(self):
        self.assertEqual(fields({"review": {"callers": 0, "confirmed": [], "refuted": []}}), (0, 0, 0))

    def test_record_carries_keys_for_garbage_review(self):
        for review in ("x", 3, None, {"callers": True}):
            rec = bench._record(FIXTURE, 1, "OK", {"review": review}, 1.0, ORACLE)
            for k in KEYS:
                self.assertIn(k, rec)
                self.assertIsNone(rec[k])
        rec = bench._record(FIXTURE, 1, "ERROR", None, 1.0, ORACLE)
        self.assertEqual(tuple(rec[k] for k in KEYS), (None, None, None))
        json.dumps(rec)


def run(arm, fixture="f", result="OK", **kw):
    base = {"arm": arm, "fixture": fixture, "result": result, "cost_usd": 1.0, "seconds": 60.0,
            "usage": {"output": 10}, "mutation": None, "oracle": {"passed": 1, "total": 1}, "fix_cycles": 0}
    base.update(kw)
    return base


class CompareTests(unittest.TestCase):
    def test_old_records_without_new_keys_compare_to_none(self):
        row = bench.compare([run("a"), run("b")], seed=0)["fixtures"]["f"]
        self.assertIsNone(row["review_callers"])
        self.assertIsNone(row["review_confirmed"])

    def test_confirmed_difference_ignores_non_ok_runs(self):
        runs = [run("a", review_confirmed=0), run("b", review_confirmed=3),
                run("b", result="ERROR", review_confirmed=99)]
        row = bench.compare(runs, seed=0)["fixtures"]["f"]
        self.assertEqual(row["review_confirmed"], 3.0)

    def test_bool_and_string_values_are_not_numbers(self):
        runs = [run("a", review_callers=True), run("b", review_callers="2")]
        self.assertIsNone(bench.compare(runs, seed=0)["fixtures"]["f"]["review_callers"])

    def test_markdown_with_doc_from_old_comparison_has_ten_cells(self):
        doc = {"a": {"version": "1", "spec": "x"}, "b": {"version": "2", "spec": "y"}, "repeat": 1, "seed": 0,
               "comparison": {"fixtures": {"f": {"cost_usd": 1.0, "minutes": 1.0, "output": 1.0, "mutation": None,
                                                "oracle": None, "fix_cycles": 0}},
                              "overall": {}}}
        lines = [x for x in bench.ab_markdown(doc).splitlines() if x.startswith("| f ")]
        self.assertEqual(len(lines), 1)
        self.assertEqual(len(lines[0].strip("|").split("|")), 10)  # agent_calls joined in 2.14.0


class FixtureHygieneTests(unittest.TestCase):
    def test_agent_visible_files_hide_the_trap(self):
        for rel in ("repo/README.md", "repo/architecture.md"):
            text = (FIXTURE / rel).read_text(encoding="utf-8").lower()
            for word in ("receipt", "oracle", "reference"):
                self.assertNotIn(word, text, f"{rel}: {word}")
        for path in (FIXTURE / "repo" / "tests").glob("*.py"):
            self.assertNotIn("receipt", path.read_text(encoding="utf-8").lower())

    def test_references_differ_only_in_the_default(self):
        good = (FIXTURE / "reference/good/shop/money.py").read_text(encoding="utf-8")
        bad = (FIXTURE / "reference/bad/shop/money.py").read_text(encoding="utf-8")
        self.assertEqual((FIXTURE / "reference/good/shop/cart.py").read_bytes(),
                         (FIXTURE / "reference/bad/shop/cart.py").read_bytes())
        self.assertRegex(good, r'def parse_price\(text: str, currency: str = "EUR"\)')
        self.assertRegex(bad, r"def parse_price\(text: str, currency: str\)")
        self.assertEqual(good.replace(' = "EUR"', "", 1), bad)

    def test_references_hold_only_money_and_cart(self):
        for arm in ("good", "bad"):
            base = FIXTURE / "reference" / arm
            files = sorted(p.relative_to(base).as_posix() for p in base.rglob("*.py"))
            self.assertEqual(files, ["shop/cart.py", "shop/money.py"])

    def test_oracle_has_no_typeerror_expectations(self):
        text = (FIXTURE / "oracle" / "test_oracle.py").read_text(encoding="utf-8")
        self.assertNotIn("assertRaises(TypeError", text)
        self.assertGreaterEqual(len(re.findall(r"def test_ctx_", text)), 3)

    def test_fixture_code_uses_future_annotations(self):
        for path in (FIXTURE / "repo" / "shop").glob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "def " in text or "class " in text:
                self.assertIn("from __future__ import annotations", text, path.name)

    def test_caller_survives_only_with_the_default(self):
        tmp = Path(tempfile.mkdtemp(prefix="qa-pricing-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        code = "from shop import receipt; print(receipt.from_rows([('a','1.50',2),('b','EUR 2.00',1)]))"
        for arm, expect_ok in (("good", True), ("bad", False)):
            work = tmp / arm
            shutil.copytree(FIXTURE / "repo", work)
            shutil.copytree(FIXTURE / "reference" / arm, work, dirs_exist_ok=True)
            proc = subprocess.run([sys.executable, "-c", code], cwd=work, capture_output=True, text=True, timeout=60)
            self.assertEqual(proc.returncode == 0, expect_ok, proc.stderr)
            if expect_ok:
                self.assertEqual(proc.stdout.strip().splitlines()[-1], "TOTAL  5.00")
            else:
                self.assertIn("TypeError", proc.stderr)


class DryRunTests(unittest.TestCase):
    def test_run_pricing_with_fake_claude_completes(self):
        sys.path.insert(0, str(ROOT / "bench" / "acceptance"))
        try:
            import testutil
        finally:
            sys.path.pop(0)
        root = Path(tempfile.mkdtemp(prefix="qa-pricing-run-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        tmp, logs, results, bin_dir = root / "tmp", root / "logs", root / "results", root / "bin"
        for p in (tmp, logs, bin_dir):
            p.mkdir()
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PROJECT_DIR", "AGENTIC_WP", "FAKE_WRITE")}
        env.update(TMPDIR=str(tmp), TEMP=str(tmp), TMP=str(tmp), FAKE_LOG_DIR=str(logs),
                   AGENTIC_CLAUDE=testutil.install_fake_claude(bin_dir))
        proc = subprocess.run([sys.executable, str(BENCH_PY), "run", "--fixture", "pricing", "--repeat", "1",
                               "--out", str(results), "--source", str(ROOT)], cwd=root, env=env,
                              capture_output=True, text=True, timeout=900)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        files = sorted(results.glob("*.json"))
        self.assertEqual(len(files), 1)
        runs = json.loads(files[0].read_text(encoding="utf-8"))["runs"]
        self.assertEqual(len(runs), 1)
        for k in KEYS:
            self.assertIn(k, runs[0])
        self.assertEqual(sorted(p.name for p in tmp.glob("bench-run-*")), [])


if __name__ == "__main__":
    unittest.main()
