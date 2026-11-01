"""Acceptance tests of the quality instruments (AC-001 ... AC-008): the mutation module, the mutation block of a
bench run and the report column, and the roster fixture. Black box: they load bench/mutate.py and bench/bench.py and
run the command line; every run uses the simulated `claude` of .claude/bin/testutil.py, so they never spend money."""
from __future__ import annotations

import ast
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

REPO = Path(__file__).resolve().parents[2]
BENCH_DIR = REPO / "bench"
BENCH_PY = BENCH_DIR / "bench.py"
MUTATE_PY = BENCH_DIR / "mutate.py"
AGENTIC = REPO / ".claude" / "bin" / "agentic.py"
RESULTS_2_1_0 = BENCH_DIR / "results" / "2.1.0-20261101-145223-dcc313a.json"
sys.path.insert(0, str(REPO / ".claude" / "bin"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_acceptance_bench as bench_acc  # noqa: E402
import test_acceptance_fixtures as fixtures_acc  # noqa: E402

SOURCE_AC1 = "def f(a, b):\n    if a < b and not a:\n        return a + 3\n    return b"
EXPECTED_OPERATORS = ["compare", "boolop", "not", "arith", "const"]
CALC_PY = "def add(a, b):\n    return a + b\n\n\ndef small(x):\n    return x < 3\n"
STRONG_TEST = ("import unittest\nfrom src.calc import add, small\n\n\nclass T(unittest.TestCase):\n"
               "    def test_it(self):\n        self.assertEqual(add(2, 3), 5)\n        self.assertTrue(small(2))\n"
               "        self.assertFalse(small(3))\n")
WEAK_TEST = ("import unittest\nfrom src.calc import add, small  # noqa: F401\n\n\nclass T(unittest.TestCase):\n"
             "    def test_it(self):\n        self.assertTrue(callable(add) and callable(small))\n")
RED_TEST = ("import unittest\nfrom src.calc import add\n\n\nclass T(unittest.TestCase):\n"
            "    def test_it(self):\n        self.assertEqual(add(1, 1), 3)\n")
LOOP_PY = "def count(n):\n    i = 0\n    while i < n:\n        i = i + 1\n    return i"
LOOP_TEST = ("import unittest\nfrom src.loop import count\n\n\nclass T(unittest.TestCase):\n"
             "    def test_it(self):\n        self.assertEqual(count(3), 3)\n        self.assertEqual(count(0), 0)\n")
ROSTER_MIN_TESTS, ROSTER_MIN_EDGE, ROSTER_MIN_CTX, ROSTER_MIN_BAD_FAILS = 24, 8, 2, 4
FORBIDDEN_ROSTER_WORDS = ("oracle", "reference", "bait", "trap", "mutation")
RUN_TIMEOUT_S = 1500


def load_mutate():
    sys.path.insert(0, str(REPO / ".claude" / "bin"))
    spec = importlib.util.spec_from_file_location("mutate_module", MUTATE_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def unittest_command(pattern: str) -> list:
    return [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", pattern]


class MutantTests(unittest.TestCase):
    def test_ac_001_candidates_are_deterministic(self):
        m = load_mutate()
        first = m.candidates(SOURCE_AC1, "m.py")
        self.assertEqual(first, m.candidates(SOURCE_AC1, "m.py"))
        self.assertEqual([mutant.operator for mutant, _ in first], EXPECTED_OPERATORS)
        by_op = {mutant.operator: text for mutant, text in first}
        self.assertIn("a <= b", by_op["compare"])
        self.assertIn("a - 3", by_op["arith"])
        self.assertIn("return a + 4", by_op["const"])
        self.assertIn("a < b and a", by_op["not"])
        self.assertIn("a < b or not a", by_op["boolop"])
        for mutant, _ in first:
            self.assertIn(mutant.line, (2, 3))
            self.assertEqual(mutant.file, "m.py")

    def test_ac_001_mutants_are_not_booleans_not_unparseable_not_multi_node(self):
        m = load_mutate()
        self.assertEqual(m.candidates("flag = True\nother = False\n", "b.py"), [])
        self.assertEqual(m.candidates("def (", "x.py"), [])
        base = ast.unparse(ast.parse(SOURCE_AC1)).splitlines()
        for _mutant, text in m.candidates(SOURCE_AC1, "m.py"):
            lines = text.splitlines()
            self.assertEqual(len(lines), len(base))
            self.assertEqual(sum(1 for a, b in zip(base, lines) if a != b), 1, text)

    def test_ac_002_sample_is_even_and_capped(self):
        m = load_mutate()
        items = list(range(100))
        picked = m.sample(items, 40)
        self.assertEqual(len(picked), 40)
        self.assertEqual(picked[0], 0)
        self.assertEqual(picked, sorted(set(picked)))
        gaps = {b - a for a, b in zip(picked, picked[1:])}
        self.assertTrue(gaps <= {2, 3}, gaps)
        self.assertEqual(picked, m.sample(items, 40))
        self.assertEqual(m.sample(items, 200), items)
        self.assertEqual(m.sample([], 40), [])


class ScoreTests(unittest.TestCase):
    def project(self, files: dict) -> Path:
        root = Path(tempfile.mkdtemp(prefix="quality-acc-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        for rel, text in files.items():
            write(root / rel, text)
        return root

    def test_ac_003_strong_kills_weak_survives(self):
        m = load_mutate()
        project = self.project({"src/calc.py": CALC_PY, "tests/test_strong.py": STRONG_TEST,
                                "tests/test_weak.py": WEAK_TEST, "tests/test_red.py": RED_TEST})
        original = (project / "src" / "calc.py").read_bytes()
        env = dict(os.environ, PYTHONPATH=str(project))
        strong, weak, red = (unittest_command(f"test_{n}.py") for n in ("strong", "weak", "red"))
        block = m.score(project, ["src/calc.py"], {"agents": [strong], "oracle": [weak]}, env=env)
        self.assertIsNotNone(block)
        self.assertEqual((block["total"], block["killed"], block["oracle_killed"]), (3, 3, 0))
        self.assertEqual((block["survived"], block["timeouts"]), ([], 0))
        self.assertEqual((project / "src" / "calc.py").read_bytes(), original)
        weak_block = m.score(project, ["src/calc.py"], {"agents": [weak]}, env=env)
        self.assertEqual(weak_block["killed"], 0)
        self.assertEqual(len(weak_block["survived"]), 3)
        for item in weak_block["survived"]:
            for key in ("file", "line", "operator", "description"):
                self.assertIn(key, item)
        red_block = m.score(project, ["src/calc.py"], {"agents": [red]}, env=env)
        self.assertIsNone(red_block["killed"])
        self.assertEqual(red_block["survived"], [])
        self.assertEqual(red_block["total"], 3)
        self.assertEqual((project / "src" / "calc.py").read_bytes(), original)

    def test_ac_004_timeout_kills_and_empty_is_none(self):
        m = load_mutate()
        looping = self.project({"src/loop.py": LOOP_PY, "tests/test_loop.py": LOOP_TEST})
        env = dict(os.environ, PYTHONPATH=str(looping))
        block = m.score(looping, ["src/loop.py"], {"agents": [unittest_command("test_loop.py")]},
                        timeout_s=5, env=env)
        self.assertIsNotNone(block)
        self.assertGreaterEqual(block["timeouts"], 1)
        self.assertEqual(block["killed"], block["total"])
        constant = self.project({"src/x.py": 'x = "a"\n', "tests/test_loop.py": LOOP_TEST})
        env = dict(os.environ, PYTHONPATH=str(constant))
        none = m.score(constant, ["src/x.py"], {"agents": [unittest_command("test_loop.py")]},
                       timeout_s=5, env=env)
        self.assertIsNone(none)


def column(text: str, header: str) -> int:
    for line in text.splitlines():
        cells = [c.strip() for c in line.split("|")]
        if line.startswith("|") and header in cells:
            return cells.index(header)
    raise AssertionError(f"no column {header} in {text}")


class BenchTests(unittest.TestCase):
    def test_ac_005_mutation_in_results_and_report(self):
        box = bench_acc.Sandbox()
        self.addCleanup(box.cleanup)
        proc = box.bench(*box.run_args("--repeat", "1"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        run_lines = [ln for ln in proc.stdout.splitlines() if ln.startswith(bench_acc.FIXTURE_NAME)]
        self.assertEqual(len(run_lines), 1, proc.stdout)
        self.assertTrue(run_lines[0].endswith(" mutation 0/3"), run_lines[0])
        data = box.load_result()
        block = data["runs"][0]["mutation"]
        self.assertEqual((block["total"], block["killed"], block["timeouts"]), (3, 0, 0))
        self.assertIsNone(block["oracle_killed"])
        self.assertEqual(len(block["survived"]), 3)
        summary = data["summary"][bench_acc.FIXTURE_NAME]
        self.assertEqual(summary["mutation_median"], 0.0)
        self.assertIsNone(summary["mutation_oracle_median"])
        report = box.bench("report", "--out", str(box.results))
        self.assertEqual(report.returncode, 0, report.stderr)
        text = (box.root / "RESULTS.md").read_text(encoding="utf-8")
        index = column(text, "Mutation")
        rows = [ln for ln in text.splitlines() if ln.startswith("|") and bench_acc.FIXTURE_NAME in ln]
        self.assertEqual(len(rows), 1, text)
        self.assertEqual(rows[0].split("|")[index].strip(), "0.00 / ?")

    def test_ac_005_timed_out_pipeline_runs_no_mutation(self):
        box = bench_acc.Sandbox(FAKE_SLEEP="30")
        self.addCleanup(box.cleanup)
        proc = box.bench(*box.run_args("--repeat", "1", "--timeout-min", "0.01"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        run = box.load_result()["runs"][0]
        self.assertEqual(run["result"], "timeout")
        self.assertIsNone(run["mutation"])

    def test_ac_005_results_without_mutation_still_report(self):
        box = bench_acc.Sandbox()
        self.addCleanup(box.cleanup)
        old = box.root / "old-results"
        old.mkdir()
        shutil.copy(RESULTS_2_1_0, old / RESULTS_2_1_0.name)
        report = box.bench("report", "--out", str(old))
        self.assertEqual(report.returncode, 0, report.stderr)
        text = (box.root / "RESULTS.md").read_text(encoding="utf-8")
        index = column(text, "Mutation")
        rows = [ln for ln in text.splitlines() if ln.startswith("|") and "2.1.0" in ln]
        self.assertTrue(rows, text)
        for row in rows:
            self.assertEqual(row.split("|")[index].strip(), "?")


class RosterTests(fixtures_acc.FixtureCase):
    name = "roster"

    def test_ac_006_sound_and_traps_named(self):
        self.check_selftest_and_info()
        good = self.oracle_counts("good")
        self.assertGreaterEqual(len(good), ROSTER_MIN_TESTS)
        self.assertEqual({k: v for k, v in good.items() if v != "ok"}, {})
        self.assertGreaterEqual(sum(1 for k in good if k.startswith("test_edge_")), ROSTER_MIN_EDGE)
        self.assertGreaterEqual(sum(1 for k in good if k.startswith("test_ctx_")), ROSTER_MIN_CTX)
        bad = self.oracle_counts("bad")
        failed = [k for k, v in bad.items() if v != "ok"]
        self.assertGreaterEqual(len(failed), ROSTER_MIN_BAD_FAILS, bad)
        for test in failed:
            self.assertTrue(test.startswith(("test_edge_", "test_ctx_")), test)
        self.assertTrue(any(t.startswith("test_ctx_") for t in failed), failed)

    def test_ac_006_no_oracle_test_passes_on_the_bare_repo(self):
        bare = self.oracle_counts(None)
        self.assertEqual({k: v for k, v in bare.items() if v == "ok"}, {})

    def test_ac_007_plan_valid_and_bait_hidden(self):
        _fixture, _info, copy, env = self.prepare("roster")
        text = (copy / "architecture.md").read_text(encoding="utf-8")
        manifest = fixtures_acc.manifest_of(copy / "architecture.md")
        wps = {wp["id"]: wp for wp in manifest["work_packages"]}
        self.assertEqual(sorted(wps), ["WP-01", "WP-02", "WP-03", "WP-04"])
        self.assertEqual((wps["WP-01"]["wave"], wps["WP-02"]["wave"]), (1, 1))
        self.assertEqual(wps["WP-03"]["wave"], 2)
        self.assertEqual(sorted(wps["WP-03"]["depends_on"]), ["WP-01", "WP-02"])
        self.assertEqual(wps["WP-04"]["wave"], 2)
        self.assertEqual(wps["WP-04"]["depends_on"], ["WP-01"])
        section = re.search(r"^## 10\b.*?(?=^## |\Z)", text, re.S | re.M)
        self.assertIsNotNone(section, "no section 10")
        self.assertIn("D3", section.group(0))
        self.assertIn("real end", section.group(0))
        self.assertEqual(text.count("real end"), 1)
        briefs = bench_acc.run_in(copy, [sys.executable, str(AGENTIC), "briefs"], env)
        self.assertEqual(briefs.returncode, 0, briefs.stderr + briefs.stdout)
        brief = (copy / ".claude" / "state" / "briefs" / "WP-04.md").read_text(encoding="utf-8")
        self.assertNotIn("real end", brief)
        self.assertNotIn("D3 ·", brief)
        readme = (copy / "README.md").read_text(encoding="utf-8")
        for word in FORBIDDEN_ROSTER_WORDS:
            self.assertNotIn(word, text.lower(), word)
            self.assertNotIn(word, readme.lower(), word)
        own = bench_acc.run_in(copy, [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                               dict(env, PYTHONPATH=str(copy)))
        self.assertEqual(own.returncode, 0, own.stderr)

    def test_ac_008_bench_runs_roster(self):
        self.assertFalse((fixtures_acc.FIXTURES / "roster" / "repo" / ".bench_oracle").exists())
        root = Path(tempfile.mkdtemp(prefix="bench-roster-run-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        tmp, logs, results, bin_dir = root / "tmp", root / "logs", root / "results", root / "bin"
        for path in (tmp, logs, bin_dir):
            path.mkdir()
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PROJECT_DIR", "AGENTIC_WP", "FAKE_WRITE")}
        env.update(TMPDIR=str(tmp), TEMP=str(tmp), TMP=str(tmp), FAKE_LOG_DIR=str(logs),
                   AGENTIC_CLAUDE=bench_acc.testutil.install_fake_claude(bin_dir))
        proc = subprocess.run([sys.executable, str(BENCH_PY), "run", "--fixture", "roster", "--repeat", "1",
                               "--out", str(results), "--source", str(REPO)], cwd=root, env=env,
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=RUN_TIMEOUT_S)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        files = sorted(results.glob("*.json"))
        self.assertEqual(len(files), 1)
        runs = json.loads(files[0].read_text(encoding="utf-8"))["runs"]
        self.assertEqual([r["fixture"] for r in runs], ["roster"])
        self.assertIn(runs[0]["result"], ("OK", "REVIEW"), runs[0])
        self.assertGreaterEqual(runs[0]["oracle"]["total"], ROSTER_MIN_TESTS)
        self.assertIn("mutation", runs[0])
        self.assertTrue(runs[0]["mutation"] is None or isinstance(runs[0]["mutation"], dict))


if __name__ == "__main__":
    unittest.main()
