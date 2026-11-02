"""Acceptance tests of the pricing bench fixture and the bench's review metrics (AC-001 ... AC-006). Black box: bench.py
runs as a subprocess or is loaded as a module; the flow's `callers` step runs as the flow's own CLI."""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_acceptance_fixtures import FixtureCase, manifest_of  # noqa: E402
from test_acceptance_bench import run_in  # noqa: E402

AGENTIC_PY = REPO / ".claude" / "bin" / "agentic.py"
spec = importlib.util.spec_from_file_location("bench_module_pricing", REPO / "bench" / "bench.py")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)

MIN_ORACLE_TESTS, MIN_CTX_TESTS = 15, 3
FORBIDDEN_WORDS = ("receipt", "oracle", "reference")
RECEIPT = "shop/receipt.py"
ZERO_ORACLE = {"passed": 0, "total": 0}


class SoundTests(FixtureCase):
    name = "pricing"

    def test_ac_001_selftest_and_info(self):
        self.check_selftest_and_info()

    def test_ac_001_good_reference_passes_every_oracle_test(self):
        self.check_good(MIN_ORACLE_TESTS, "test_ctx_", MIN_CTX_TESTS)

    def test_ac_001_bad_reference_fails_only_ctx_tests(self):
        self.check_bad("test_ctx_", MIN_CTX_TESTS)

    def test_ac_001_no_oracle_test_passes_on_the_bare_repo(self):
        bare = self.oracle_counts(None)
        self.assertGreaterEqual(len(bare), MIN_ORACLE_TESTS)
        self.assertEqual({k: v for k, v in bare.items() if v == "ok"}, {})


class TrapShapeTests(FixtureCase):
    name = "pricing"

    def test_ac_002_caller_is_hidden_from_tests_docs_and_plan(self):
        _fixture, _info, copy, _env = self.prepare("pricing")
        receipt = (copy / RECEIPT).read_text(encoding="utf-8")
        calls = re.findall(r"parse_price\(([^()]*)\)", receipt)
        self.assertTrue(calls, "receipt code must call parse_price(")
        for args in calls:
            self.assertNotIn(",", args, "the caller passes ONE argument")
        for test_file in (copy / "tests").rglob("*"):
            if test_file.is_file():
                self.assertNotIn("receipt", test_file.read_text(encoding="utf-8", errors="replace").lower(),
                                 str(test_file))
        for doc in (copy / "README.md", copy / "architecture.md"):
            lowered = doc.read_text(encoding="utf-8").lower()
            for word in FORBIDDEN_WORDS:
                self.assertNotIn(word, lowered, f"{word} in {doc.name}")

    def test_ac_002_plan_lists_the_only_known_caller_and_has_two_wave_1_packages(self):
        _fixture, _info, copy, _env = self.prepare("pricing")
        plan = copy / "architecture.md"
        lines = plan.read_text(encoding="utf-8").splitlines()
        self.assertTrue(any("shop/cart.py:" in line and "parse_price" in line for line in lines))
        packages = manifest_of(plan)["work_packages"]
        self.assertEqual(len(packages), 2)
        self.assertEqual({wp["wave"] for wp in packages}, {1})
        for wp in packages:
            for owned in wp["files"]:
                self.assertNotEqual(owned.rstrip("/"), RECEIPT)
                self.assertFalse(RECEIPT.startswith(owned.rstrip("/") + "/"), owned)

    def test_ac_002_existing_tests_pass_on_the_bare_repo(self):
        _fixture, _info, copy, env = self.prepare("pricing")
        self.run_plan_tests(manifest_of(copy / "architecture.md"), copy, env)


class CallersTests(FixtureCase):
    name = "pricing"

    def test_ac_003_callers_step_sees_the_hidden_caller(self):
        fixture, _info, copy, env = self.prepare("pricing")
        shutil.copytree(fixture / "reference" / "bad", copy, dirs_exist_ok=True)
        proc = run_in(copy, [sys.executable, str(AGENTIC_PY), "callers"], env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertIn("shop/money.py", data["changed"])
        self.assertIn("parse_price", data["symbols"]["shop/money.py"])
        hits = [c for c in data["callers"] if c["file"] == RECEIPT and c["symbol"] == "parse_price"]
        self.assertTrue(hits, data)


class RecordTests(unittest.TestCase):
    CASES = (
        ("a", {"callers": 3, "confirmed": [{}], "refuted": [{}, {}]}, (3, 1, 2)),
        ("b", {"confirmed": [{}], "refuted": [{}, {}]}, (None, 1, 2)),
        ("c", None, (None, None, None)),
        ("d", "x", (None, None, None)),
        ("e", {"callers": "3", "confirmed": [{}], "refuted": []}, (None, 1, 0)),
        ("f", {"callers": True, "confirmed": "x", "refuted": None}, (None, None, None)),
    )

    def record(self, review):
        result = {} if review is None else {"review": review}
        return bench._record(Path("f"), 1, "OK", result, 1.0, dict(ZERO_ORACLE))

    def test_ac_004_review_fields_per_case(self):
        for label, review, expected in self.CASES:
            with self.subTest(case=label):
                rec = self.record(review)
                self.assertEqual((rec["review_callers"], rec["review_confirmed"], rec["review_refuted"]), expected)

    def test_ac_004_no_result_at_all_does_not_raise(self):
        rec = bench._record(Path("f"), 1, "error", None, 1.0, dict(ZERO_ORACLE))
        self.assertEqual((rec["review_callers"], rec["review_confirmed"], rec["review_refuted"]),
                         (None, None, None))


def ab_run(arm, callers, confirmed, fixture="fx", result="OK"):
    return {"arm": arm, "fixture": fixture, "index": 1, "result": result, "seconds": 60.0, "fix_cycles": 0,
            "usage": {"cost_usd": 1.0, "output": 100}, "oracle": {"passed": 3, "total": 4},
            "mutation": {"killed": 3, "total": 4}, "review_callers": callers, "review_confirmed": confirmed}


class CompareTests(unittest.TestCase):
    def doc(self, runs):
        return {"a": {"version": "1", "spec": "x"}, "b": {"version": "2", "spec": "y"}, "repeat": 1, "seed": 0,
                "comparison": bench.compare(runs, seed=0)}

    def runs(self):
        return [ab_run("a", None, 0), ab_run("b", 2, 1)]

    def test_ac_005_compare_differences(self):
        row = bench.compare(self.runs(), seed=0)["fixtures"]["fx"]
        self.assertIsNone(row["review_callers"])
        self.assertEqual(row["review_confirmed"], 1.0)

    def test_ac_005_diff_metrics_and_ratio_metrics_keep_their_place(self):
        self.assertEqual(bench.DIFF_METRICS[-2:], ("review_callers", "review_confirmed"))
        self.assertEqual(bench.DIFF_METRICS[:3], ("mutation", "oracle", "fix_cycles"))
        overall = bench.compare(self.runs(), seed=0)["overall"]
        self.assertEqual(set(overall), set(bench.RATIO_METRICS))

    def test_ac_005_markdown_has_callers_and_confirmed_columns(self):
        lines = bench.ab_markdown(self.doc(self.runs())).splitlines()
        header = next(i for i, line in enumerate(lines) if line.startswith("| Fixture |"))
        self.assertTrue(lines[header].endswith("| Callers | Confirmed |"), lines[header])
        self.assertEqual(lines[header + 1].strip("|").count("|") + 1, 9)
        row = lines[header + 2]
        self.assertTrue(row.startswith("| fx |"))
        self.assertEqual(row.strip().strip("|").count("|") + 1, 9)

    def test_ac_005_other_results_are_not_measurements(self):
        runs = [ab_run("a", 0, 0, result="timeout"), ab_run("b", 2, 1, result="timeout")]
        row = bench.compare(runs, seed=0)["fixtures"]["fx"]
        self.assertIsNone(row["review_callers"])
        self.assertIsNone(row["review_confirmed"])


class DocsTests(unittest.TestCase):
    def test_ac_006_guide_names_the_fixture_and_the_fields(self):
        guide = (REPO / "docs" / "how-to" / "bench.md").read_text(encoding="utf-8")
        rows = [line for line in guide.splitlines() if line.startswith("|") and "pricing" in line]
        self.assertTrue(rows, "no pricing row in the fixture table")
        self.assertIn("test_ctx_", rows[0])
        self.assertIn("caller", rows[0].lower())
        self.assertIn("review_callers", guide)
        self.assertIn("review_confirmed", guide)

    def test_ac_006_guide_hardcodes_no_version_or_test_count(self):
        guide = (REPO / "docs" / "how-to" / "bench.md").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"\b\d+ (Python |workflow |bench |QA )?(tests|scenarios)\b", guide))

    def test_ac_006_roadmap_entry_says_shipped(self):
        roadmap = (REPO / "docs" / "roadmap" / "repo-review-2026-11.md").read_text(encoding="utf-8")
        entries = [line for line in roadmap.splitlines()
                   if "bench" in line and "caller" in line and "reviewer" in line]
        self.assertTrue(entries)
        self.assertTrue(any("Shipped" in line for line in entries), entries)


if __name__ == "__main__":
    unittest.main()
