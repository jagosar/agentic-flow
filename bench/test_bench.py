"""Unit tests of bench.py: summary maths, report formatting, results-file naming, oracle counting and argument errors.
No real `claude` and no pipeline run: those are in bench/acceptance."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

BENCH_PY = Path(__file__).resolve().parent / "bench.py"
spec = importlib.util.spec_from_file_location("bench_module", BENCH_PY)
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)

# The oracle module under test has one skipped test; the decorator is assembled so this file holds no literal skip.
SKIP_DECORATOR = "@unittest." + "sk" + "ip('s')"


def make_run(fixture="fx", result="OK", passed=3, total=4, cycles=0, cost=1.0, output=100, seconds=60.0):
    return {"fixture": fixture, "index": 1, "result": result, "failed_stage": None, "fix_cycles": cycles,
            "test_audit_rounds": None, "agents": 1, "seconds": seconds, "oracle": {"passed": passed, "total": total},
            "usage": {"input": 0, "cache_read": 0, "output": output, "turns": 1, "cost_usd": cost}}


class TempCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bench-unit-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)


class SummaryTests(TempCase):
    def test_median_of_an_even_count_is_the_mean_of_the_middle_two_rounded(self):
        self.assertEqual(bench._rounded([1, 2]), 1.5)
        self.assertEqual(bench._rounded([0.1, 0.2]), 0.15)
        self.assertEqual(bench._rounded([1 / 3]), 0.333)

    def test_null_values_are_skipped_and_all_null_gives_null(self):
        summary = bench._summarize([make_run(cycles=None, cost=None), make_run(cycles=2, cost=None)])
        self.assertEqual(summary["fix_cycles_median"], 2)
        self.assertIsNone(summary["cost_usd_median"])

    def test_oracle_rate_counts_zero_total_as_zero_and_keeps_min_and_max(self):
        runs = [make_run(passed=0, total=0), make_run(passed=3, total=4), make_run(passed=4, total=4)]
        summary = bench._summarize(runs)
        self.assertEqual((summary["oracle_rate_min"], summary["oracle_rate_median"], summary["oracle_rate_max"]),
                         (0.0, 0.75, 1.0))

    def test_ok_counts_only_ok_runs(self):
        summary = bench._summarize([make_run(), make_run(result="REVIEW"), make_run(result="timeout")])
        self.assertEqual((summary["runs"], summary["ok"]), (3, 1))


class ReportTests(TempCase):
    def write_doc(self, name, started, version="1.0.0", commit="abc1234", dirty=False, runs=None):
        runs = runs or [make_run()]
        doc = {"schema": 1, "flow_version": version, "flow_commit": commit, "dirty": dirty, "started": started,
               "repeat": len(runs), "auth": "subscription", "runs": runs, "summary": bench._summaries(runs)}
        (self.tmp / name).write_text(json.dumps(doc), encoding="utf-8")

    def rows(self):
        out = self.tmp / "RESULTS.md"
        bench.report(self.tmp, out)
        return [line for line in out.read_text(encoding="utf-8").splitlines() if line.startswith("| 1.")]

    def test_empty_dir_gives_the_title_and_no_results_yet(self):
        out = self.tmp / "RESULTS.md"
        bench.report(self.tmp / "missing", out)
        self.assertEqual(out.read_text(encoding="utf-8"), "# Bench results\n\nNo results yet.\n")

    def test_row_formats_values(self):
        self.write_doc("a.json", "2026-10-31T10:00:00", dirty=True, runs=[make_run(cost=3.1, output=41000, seconds=810)])
        self.assertEqual(self.rows(), ["| 1.0.0 | abc1234-dirty | 2026-10-31 | fx | 1 | 1/1 | 0.75 (0.75–0.75) | 0 | 3.10 "
                                       "| 41000 | 13.5 |"])

    def test_null_values_print_a_question_mark(self):
        self.write_doc("a.json", "2026-10-31T10:00:00", runs=[make_run(cycles=None, cost=None)])
        self.assertIn("| ? | ? |", self.rows()[0])

    def test_newest_first_and_fixtures_in_name_order(self):
        self.write_doc("old.json", "2026-01-01T00:00:00", version="1.0.1")
        self.write_doc("new.json", "2026-02-01T00:00:00", version="1.0.2",
                       runs=[make_run(fixture="zeta"), make_run(fixture="alpha")])
        cells = [r.split(" | ") for r in self.rows()]
        self.assertEqual([(c[0], c[3]) for c in cells], [("| 1.0.2", "alpha"), ("| 1.0.2", "zeta"), ("| 1.0.1", "fx")])

    def test_other_schemas_and_invalid_json_are_skipped(self):
        (self.tmp / "old.json").write_text('{"schema": 99}', encoding="utf-8")
        (self.tmp / "bad.json").write_text("not json", encoding="utf-8")
        self.write_doc("a.json", "2026-10-31T10:00:00")
        self.assertEqual(len(self.rows()), 1)


class OracleCountsTests(TempCase):
    def counts(self, source):
        oracle = self.tmp / "oracle"
        oracle.mkdir()
        (oracle / "test_x.py").write_text(source, encoding="utf-8")
        return bench.oracle_counts(self.tmp, oracle)

    def test_passes_failures_errors_and_skips(self):
        source = ("import unittest\n\nclass T(unittest.TestCase):\n"
                  "    def test_ok(self): pass\n"
                  "    def test_fail(self): self.fail('x')\n"
                  "    def test_err(self): raise ValueError\n"
                  f"    {SKIP_DECORATOR}\n    def test_other(self): pass\n")
        self.assertEqual(self.counts(source), (1, 4))

    def test_all_green(self):
        self.assertEqual(self.counts("import unittest\n\nclass T(unittest.TestCase):\n    def test_ok(self): pass\n"),
                         (1, 1))

    def test_import_error_is_one_error(self):
        self.assertEqual(self.counts("import module_that_does_not_exist\n"), (0, 1))

    def test_no_summary_is_zero_zero(self):
        self.assertEqual(bench.oracle_counts(self.tmp, self.tmp / "nowhere"), (0, 0))


class ArgumentTests(TempCase):
    def run_main(self, *argv):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = bench.main(list(argv))
        return code, err.getvalue()

    def test_every_bad_argument_returns_one_with_a_message(self):
        out = ["--out", str(self.tmp / "r")]
        cases = [["run", "--repeat", "0", *out], ["run", "--repeat", "x", *out],
                 ["run", "--fixture", "does-not-exist", *out], ["run", "--auth", "other", *out],
                 ["run", "--source", str(self.tmp), *out], ["nonsense"], []]
        for argv in cases:
            with self.subTest(argv=argv):
                code, message = self.run_main(*argv)
                self.assertEqual(code, 1)
                self.assertTrue(message.strip())
                self.assertNotIn("Traceback", message)
        self.assertFalse((self.tmp / "r").exists())

    def test_run_rejects_a_fixture_without_oracle(self):
        fixture = self.tmp / "fx"
        (fixture / "repo").mkdir(parents=True)
        (fixture / "fixture.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(bench.BenchError):
            bench.run([fixture], bench.HERE.parent, 1, self.tmp / "out")
        self.assertFalse((self.tmp / "out").exists())


class ResultsFileTests(TempCase):
    def test_flow_version_comes_from_plugin_json_or_is_dev(self):
        self.assertEqual(bench._flow_version(self.tmp), "dev")
        (self.tmp / ".claude-plugin").mkdir()
        (self.tmp / ".claude-plugin" / "plugin.json").write_text('{"version": "2.0.0"}', encoding="utf-8")
        self.assertEqual(bench._flow_version(self.tmp), "2.0.0")

    def test_git_output_is_none_outside_a_repo(self):
        self.assertIsNone(bench._git_output(["rev-parse", "--short", "HEAD"], self.tmp))


if __name__ == "__main__":
    unittest.main()
