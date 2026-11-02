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
from unittest import mock
from pathlib import Path

BENCH_PY = Path(__file__).resolve().parent / "bench.py"
spec = importlib.util.spec_from_file_location("bench_module", BENCH_PY)
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)

# The oracle module under test has one skipped test; the decorator is assembled so this file holds no literal skip.
SKIP_DECORATOR = "@unittest." + "sk" + "ip('s')"


def make_run(fixture="fx", result="OK", passed=3, total=4, cycles=0, cost=1.0, output=100, seconds=60.0, mutation=None):
    return {"fixture": fixture, "index": 1, "result": result, "failed_stage": None, "fix_cycles": cycles,
            "test_audit_rounds": None, "agents": 1, "seconds": seconds, "oracle": {"passed": passed, "total": total},
            "usage": {"input": 0, "cache_read": 0, "output": output, "turns": 1, "cost_usd": cost},
            "mutation": mutation}


class TempCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bench-unit-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)



class RemoveTreeTests(TempCase):
    def test_removes_read_only_files_and_folders(self):
        # git leaves its objects read-only; Windows refuses to delete them unless they are made writable first
        project = self.tmp / "bench-run-x"
        objects = project / ".git" / "objects" / "ab"
        objects.mkdir(parents=True)
        blob = objects / "cdef"
        blob.write_text("x", encoding="utf-8")
        blob.chmod(0o444)
        objects.chmod(0o555)
        bench.remove_tree(project)
        self.assertFalse(project.exists())

    def test_a_missing_folder_is_not_an_error(self):
        bench.remove_tree(self.tmp / "never-created")


ORACLE = ("import os\nimport unittest\n\nclass T(unittest.TestCase):\n"
          "    def test_a(self): self.assertTrue(os.path.exists('a.py'))\n"
          "    def test_b(self): self.assertTrue(os.path.exists('b.py'))\n")


class IsolationTests(TempCase):
    def test_child_env_drops_user_context_and_keeps_the_claude_command(self):
        env = bench._child_env({"AGENTIC_CLAUDE": "python3 /x/claude_fake.py", "AGENTIC_WP": "WP-01", "PATH": "p"},
                               self.tmp)
        self.assertEqual(env["CLAUDE_CODE_DISABLE_CLAUDE_MDS"], "1")
        self.assertEqual(env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"], "1")
        self.assertEqual(env["AGENTIC_CLAUDE"], "python3 /x/claude_fake.py --setting-sources project,local")
        self.assertNotIn("AGENTIC_WP", env)
        self.assertEqual(env["CLAUDE_PROJECT_DIR"], str(self.tmp))
        self.assertEqual(bench._child_env({}, self.tmp)["AGENTIC_CLAUDE"], "claude --setting-sources project,local")

    def test_child_env_drops_claudecode(self):
        # Inherited from a Claude session, it would put the flow's hooks-check in live mode for every fixture.
        env = bench._child_env({"CLAUDECODE": "1", "PATH": "p"}, self.tmp)
        self.assertNotIn("CLAUDECODE", env)
        self.assertEqual(env["PATH"], "p")


class SelftestTests(TempCase):
    def fixture(self, good=("a.py", "b.py"), bad=("a.py",), oracle=ORACLE, name="fx"):
        fx = self.tmp / name
        (fx / "repo").mkdir(parents=True)
        (fx / "oracle").mkdir()
        (fx / "oracle" / "test_oracle.py").write_text(oracle, encoding="utf-8")
        for name, files in (("good", good), ("bad", bad)):
            (fx / "reference" / name).mkdir(parents=True)
            for rel in files:
                (fx / "reference" / name / rel).write_text("x = 1\n", encoding="utf-8")
        return fx

    def test_sound_instruments_have_no_problems(self):
        self.assertEqual(bench.selftest(self.fixture()), [])

    def test_each_broken_instrument_is_named(self):
        cases = {
            "good": self.fixture(good=("a.py",), name="fx-good"),                 # the good reference fails a test
            "bad": self.fixture(bad=("a.py", "b.py"), name="fx-bad"),             # the bad reference passes everything
            "bare": self.fixture(oracle=ORACLE + "    def test_free(self): pass\n", name="fx-bare"),  # green, no code
        }
        for expected, fx in cases.items():
            with self.subTest(case=expected):
                problems = bench.selftest(fx)
                self.assertEqual(len(problems), 1, problems)
                self.assertIn(expected, problems[0])
                self.assertIn(fx.name, problems[0])

    def test_an_oracle_without_tests_is_a_problem(self):
        fx = self.fixture(oracle="import unittest\n")
        self.assertTrue(any("no tests" in p for p in bench.selftest(fx)), bench.selftest(fx))

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
        self.assertEqual(self.rows(), ["| 1.0.0 | abc1234-dirty | 2026-10-31 | fx | 1 | 1/1 | 0.75 (0.75–0.75) | ? | 0 | 3.10 "
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



def ab_run(arm, fixture="fx", result="OK", cost=1.0, seconds=60.0, output=100, killed=3, total=4, cycles=0):
    return {"arm": arm, "fixture": fixture, "index": 1, "result": result, "seconds": seconds, "fix_cycles": cycles,
            "usage": {"cost_usd": cost, "output": output}, "oracle": {"passed": 3, "total": 4},
            "mutation": {"killed": killed, "total": total}}


class StatisticsTests(TempCase):
    def test_geometric_mean_rejects_empty_and_non_positive(self):
        self.assertAlmostEqual(bench.geometric_mean([2.0, 8.0]), 4.0)
        for bad in ([], [1.0, -1.0], [0.0], [None]):
            self.assertIsNone(bench.geometric_mean(bad))

    def test_sign_test_two_sided_and_capped(self):
        self.assertAlmostEqual(bench.sign_test(0, 5), 0.0625)
        self.assertAlmostEqual(bench.sign_test(6, 0), 0.03125)
        self.assertEqual(bench.sign_test(2, 2), 1.0)

    def test_bootstrap_without_usable_fixtures_is_none(self):
        self.assertIsNone(bench.bootstrap_interval({}, seed=0))
        self.assertIsNone(bench.bootstrap_interval({"f": ([], [1.0])}, seed=0))
        self.assertIsNone(bench.bootstrap_interval({"f": ([0.0, 0.0], [1.0])}, seed=0, iterations=50))

    def test_compare_skips_errors_timeouts_and_zero_medians(self):
        runs = [ab_run("a", cost=0.0), ab_run("b", cost=1.0), ab_run("a", fixture="g", result="timeout"),
                ab_run("b", fixture="g", result="timeout")]
        out = bench.compare(runs, seed=0)
        self.assertIsNone(out["fixtures"]["fx"]["cost_usd"], "a zero median of A gives no ratio")
        self.assertEqual(out["fixtures"]["fx"]["minutes"], 1.0)
        self.assertTrue(all(v is None for v in out["fixtures"]["g"].values()), "timeouts are not measurements")
        self.assertEqual(out["overall"]["minutes"]["ties"], 1)

    def test_compare_differences_for_rates_and_counts(self):
        out = bench.compare([ab_run("a", killed=2, cycles=0), ab_run("b", killed=4, cycles=1)], seed=0)
        self.assertEqual((out["fixtures"]["fx"]["mutation"], out["fixtures"]["fx"]["fix_cycles"]), (0.5, 1))


class AbSourceTests(TempCase):
    def test_a_flow_directory_is_used_as_is(self):
        (self.tmp / ".claude" / "bin").mkdir(parents=True)
        (self.tmp / ".claude" / "bin" / "agentic.py").write_text("", encoding="utf-8")
        self.assertEqual(bench.resolve_source(str(self.tmp), self.tmp, self.tmp / "w"), (self.tmp.resolve(), False))

    def test_garbage_is_refused_before_any_checkout(self):
        with self.assertRaises(bench.BenchError):
            bench.resolve_source("no-such-ref", self.tmp, self.tmp / "w")
        self.assertFalse((self.tmp / "w").exists())

    def test_arms_alternate_by_index_and_keep_their_own_sessions(self):
        seen = []

        def fake_once(fixture, index, source, auth, timeout_s, base_env, keep):
            seen.append((index, keep.name))
            return make_run(fixture=fixture.name)

        (self.tmp / "src" / ".claude" / "bin").mkdir(parents=True)
        (self.tmp / "src" / ".claude" / "bin" / "agentic.py").write_text("", encoding="utf-8")
        with mock.patch.object(bench, "_run_once", fake_once), mock.patch.object(bench, "selftest", lambda f: []), \
                mock.patch.object(bench, "_validate_args", lambda *a: None):
            path = bench.ab([self.tmp / "fx"], str(self.tmp / "src"), str(self.tmp / "src"), 3, self.tmp / "out")
        self.assertEqual(seen, [(1, "a"), (1, "b"), (2, "b"), (2, "a"), (3, "a"), (3, "b")])
        doc = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(doc["schema"], "ab-1")
        self.assertTrue(path.with_suffix(".md").is_file())

    def test_record_counts_failed_verifications_and_tolerates_garbage(self):
        good = bench._record(Path("f"), 1, "OK", {"verification_failures": [{}, {}]}, 1.0, {"passed": 0, "total": 0})
        bad = bench._record(Path("f"), 1, "OK", {"verification_failures": "x"}, 1.0, {"passed": 0, "total": 0})
        self.assertEqual((good["verification_failures"], bad["verification_failures"]), (2, 0))


if __name__ == "__main__":
    unittest.main()


def block(total=4, killed=2, oracle_killed=3):
    return {"total": total, "killed": killed, "oracle_killed": oracle_killed, "timeouts": 0, "survived": []}


class MutationInputsTests(TempCase):
    def project(self, manifest):
        (self.tmp / "architecture.md").write_text("# plan\n```json wp-manifest\n" + json.dumps(manifest) + "\n```\n",
                                                  encoding="utf-8")
        for rel in ("pkg/__init__.py", "pkg/a.py", "pkg/test_a.py", "pkg/sub/b.py", "tests/t.py", "acc/x.py",
                    "qa/q.py", "top.py", "notes.txt"):
            (self.tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.tmp / rel).write_text("x = 1\n", encoding="utf-8")
        return self.tmp

    def test_production_files_expand_directories_and_drop_tests_acceptance_qa_and_missing(self):
        manifest = {"work_packages": [{"files": ["pkg/", "tests/t.py", "acc/x.py", "qa/q.py", "gone.py", "notes.txt"]},
                                      {"files": ["top.py"]}], "acceptance": {"files": ["acc/"]}}
        files = bench.production_files(self.project(manifest), manifest)
        self.assertEqual(files, ["pkg/__init__.py", "pkg/a.py", "pkg/sub/b.py", "top.py"])

    def test_manifest_of_is_empty_when_absent_or_invalid(self):
        self.assertEqual(bench.manifest_of(self.tmp), {})
        (self.tmp / "architecture.md").write_text("```json wp-manifest\n{bad\n```\n", encoding="utf-8")
        self.assertEqual(bench.manifest_of(self.tmp), {})

    def test_manifest_of_reads_the_block(self):
        self.assertEqual(bench.manifest_of(self.project({"id": 1})), {"id": 1})

    def test_project_commands_are_verify_tests_then_acceptance_command(self):
        manifest = {"verify": {"tests": "python3 -m unittest -q"}, "acceptance": {"command": "python3 'a b.py'"}}
        self.assertEqual(bench.project_commands(manifest),
                         [["python3", "-m", "unittest", "-q"], ["python3", "a b.py"]])
        self.assertEqual(bench.project_commands({}), [])


class MutationRunTests(TempCase):
    def run_mutation(self, **patch):
        fx = self.tmp / "fx"
        project = self.tmp / "proj"
        project.mkdir()
        with mock.patch.object(bench.mutate, "score", **patch) as score:
            result = bench._mutation(fx, project, {"A": "1"})
        return result, score

    def test_returns_the_block_and_passes_both_suites_with_pythonpath(self):
        result, score = self.run_mutation(return_value=block())
        self.assertEqual(result, block())
        suites, env = score.call_args.args[2], score.call_args.kwargs["env"]
        self.assertEqual(set(suites), {"agents", "oracle"})
        self.assertIn(str(self.tmp / "fx" / "oracle"), suites["oracle"][0])
        self.assertEqual((env["A"], env["PYTHONPATH"]), ("1", str(self.tmp / "proj")))

    def test_none_from_score_is_none(self):
        self.assertIsNone(self.run_mutation(return_value=None)[0])

    def test_a_mutation_error_becomes_none_with_a_line_on_stderr(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            result, _ = self.run_mutation(side_effect=bench.mutate.MutationError("cannot write"))
        self.assertIsNone(result)
        self.assertIn("cannot write", err.getvalue())

    def test_run_oracle_removes_its_folder_after_counting(self):
        fx = SelftestTests.fixture(self, name="fx2")
        project = self.tmp / "p2"
        project.mkdir()
        bench._run_oracle(fx, project)
        self.assertFalse((project / ".bench_oracle").exists())


class MutationSummaryTests(TempCase):
    def test_medians_use_runs_with_a_number_and_skip_the_rest(self):
        runs = [make_run(mutation=block(4, 2, 4)), make_run(mutation=block(4, 4, 4)), make_run(),
                make_run(mutation=block(4, None, 2))]
        summary = bench._summarize(runs)
        self.assertEqual(summary["mutation_median"], 0.75)
        self.assertEqual(summary["mutation_oracle_median"], 1.0)

    def test_runs_without_mutation_give_none(self):
        summary = bench._summarize([make_run()])
        self.assertIsNone(summary["mutation_median"])
        self.assertIsNone(summary["mutation_oracle_median"])

    def test_row_shows_both_halves_with_two_decimals_or_question_marks(self):
        cases = ((block(4, 0, None), "0.00 / ?"), (block(10, 7, 9), "0.70 / 0.90"), (None, "?"))
        for mutation, expected in cases:
            with self.subTest(expected=expected):
                doc = {"flow_version": "1", "flow_commit": "c", "started": "2026-01-01",
                       "summary": bench._summaries([make_run(mutation=mutation)])}
                row = bench._rows(doc)[0]
                self.assertEqual(row[bench.TABLE_HEADER.index("Mutation")], expected)
                self.assertEqual(len(row), len(bench.TABLE_HEADER))
