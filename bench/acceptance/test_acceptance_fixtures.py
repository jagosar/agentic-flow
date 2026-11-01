"""Acceptance tests of the vault and tally bench fixtures (AC-001 ... AC-006). Black box: they run bench.py as a
subprocess and the fixtures' oracle through unittest; the simulated agent CLI of testutil never spends money."""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BENCH_PY = REPO / "bench" / "bench.py"
FIXTURES = REPO / "bench" / "fixtures"
sys.path.insert(0, str(REPO / ".claude" / "bin"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import testutil  # noqa: E402
from test_acceptance_bench import FixtureReady  # noqa: E402

TEST_LINE = re.compile(r"^(test\w*) \(.*\) \.\.\. (ok|FAIL|ERROR)\s*$", re.M)
MIN_VAULT_TESTS, MIN_VAULT_ADV = 15, 7
MIN_TALLY_TESTS, MIN_TALLY_EDGE = 20, 8
MIN_VAULT_BAD_FAILS, MIN_TALLY_BAD_FAILS = 3, 4
FORBIDDEN_VAULT_WORDS = ("traversal", "inject", "tamper", "forg", "hmac", "signature", "escap", "saniti",
                         "oracle", "reference")
TRUST_PHRASE = "are not trusted"


def manifest_of(plan: Path) -> dict:
    text = plan.read_text(encoding="utf-8")
    match = re.search(r"```json\s+wp-manifest\s*\n(.*?)\n```", text, re.S)
    assert match, "no wp-manifest block"
    return json.loads(match.group(1))


class FixtureCase(FixtureReady, unittest.TestCase):
    name = ""

    def selftest(self) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(BENCH_PY), "selftest", "--fixture", self.name,
                               "--source", str(REPO)], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=900)

    def oracle_counts(self, overlay: str | None) -> dict:
        fixture = FIXTURES / self.name
        self.assertTrue(fixture.is_dir(), f"missing {fixture}")
        copy = Path(tempfile.mkdtemp(prefix="bench-fx-"))
        self.addCleanup(shutil.rmtree, copy, ignore_errors=True)
        shutil.copytree(fixture / "repo", copy, dirs_exist_ok=True)
        if overlay:
            shutil.copytree(fixture / "reference" / overlay, copy, dirs_exist_ok=True)
        oracle = fixture / "oracle"
        env = dict(os.environ, PYTHONPATH=str(copy))
        proc = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(oracle), "-t", str(oracle),
                               "-v"], cwd=copy, env=env, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=600)
        outcomes = {m.group(1): m.group(2) for m in TEST_LINE.finditer(proc.stderr + proc.stdout)}
        self.assertTrue(outcomes, proc.stderr)
        return outcomes

    def check_selftest_and_info(self) -> None:
        proc = self.selftest()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn(f"{self.name}: ok", proc.stdout)
        info = json.loads((FIXTURES / self.name / "fixture.json").read_text(encoding="utf-8"))
        self.assertEqual(info["name"], self.name)
        self.assertEqual(info["difficulty"], "trap")

    def check_good(self, minimum: int, prefix: str, minimum_prefixed: int) -> None:
        good = self.oracle_counts("good")
        self.assertGreaterEqual(len(good), minimum)
        self.assertEqual({k: v for k, v in good.items() if v != "ok"}, {})
        self.assertGreaterEqual(sum(1 for k in good if k.startswith(prefix)), minimum_prefixed)

    def check_bad(self, prefix: str, minimum_failed: int) -> None:
        bad = self.oracle_counts("bad")
        plain_broken = {k: v for k, v in bad.items() if not k.startswith(prefix) and v != "ok"}
        self.assertEqual(plain_broken, {})
        failed = [k for k, v in bad.items() if k.startswith(prefix) and v in ("FAIL", "ERROR")]
        self.assertGreaterEqual(len(failed), minimum_failed, bad)

    def run_plan_tests(self, manifest: dict, copy: Path, env: dict) -> None:
        tests = shlex.split(manifest["verify"]["tests"])
        self.assertEqual(tests[0], "python3")
        proc = subprocess.run([sys.executable, *tests[1:]], cwd=copy, env=dict(env, PYTHONPATH=str(copy)),
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        self.assertEqual(proc.returncode, 0, proc.stderr)


class VaultTests(FixtureCase):
    name = "vault"

    def test_ac_001_sound(self):
        self.check_selftest_and_info()
        self.check_good(MIN_VAULT_TESTS, "test_adv_", MIN_VAULT_ADV)

    def test_ac_002_bad_reference_fails_only_adversarial(self):
        self.check_bad("test_adv_", MIN_VAULT_BAD_FAILS)

    def test_ac_003_plan_valid_and_implicit(self):
        _fixture, _info, copy, env = self.prepare("vault")
        text = (copy / "architecture.md").read_text(encoding="utf-8")
        lowered = text.lower()
        self.assertEqual(text.count(TRUST_PHRASE), 1)
        for word in FORBIDDEN_VAULT_WORDS:
            self.assertNotIn(word, lowered, word)
        manifest = manifest_of(copy / "architecture.md")
        wps = manifest["work_packages"]
        self.assertEqual(len(wps), 3)
        self.assertEqual({wp["wave"] for wp in wps}, {1})
        self.run_plan_tests(manifest, copy, env)


class TallyTests(FixtureCase):
    name = "tally"

    def test_ac_004_sound_and_three_waves(self):
        self.check_selftest_and_info()
        _fixture, _info, copy, env = self.prepare("tally")
        self.check_good(MIN_TALLY_TESTS, "test_edge_", MIN_TALLY_EDGE)
        text = (copy / "architecture.md").read_text(encoding="utf-8").lower()
        for word in ("oracle", "reference"):
            self.assertNotIn(word, text)
        manifest = manifest_of(copy / "architecture.md")
        wps = {wp["id"]: wp for wp in manifest["work_packages"]}
        self.assertEqual(sorted(wps), ["WP-01", "WP-02", "WP-03", "WP-04"])
        self.assertEqual({wp["wave"] for wp in wps.values()}, {1, 2, 3})
        self.assertEqual(wps["WP-03"]["wave"], 2)
        self.assertEqual(sorted(wps["WP-03"]["depends_on"]), ["WP-01", "WP-02"])
        self.assertEqual(wps["WP-04"]["wave"], 3)
        self.assertEqual(wps["WP-04"]["depends_on"], ["WP-03"])
        self.run_plan_tests(manifest, copy, env)

    def test_ac_005_bad_reference_fails_only_edges(self):
        self.check_bad("test_edge_", MIN_TALLY_BAD_FAILS)


class RunTests(unittest.TestCase):
    def test_ac_006_bench_runs_both(self):
        root = Path(tempfile.mkdtemp(prefix="bench-fx-run-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        tmp, logs, results, bin_dir = root / "tmp", root / "logs", root / "results", root / "bin"
        for path in (tmp, logs, bin_dir):
            path.mkdir()
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PROJECT_DIR", "AGENTIC_WP", "FAKE_WRITE")}
        env.update(TMPDIR=str(tmp), TEMP=str(tmp), TMP=str(tmp), FAKE_LOG_DIR=str(logs),
                   AGENTIC_CLAUDE=testutil.install_fake_claude(bin_dir))
        proc = subprocess.run([sys.executable, str(BENCH_PY), "run", "--fixture", "vault", "--fixture", "tally",
                               "--repeat", "1", "--out", str(results), "--source", str(REPO)], cwd=root, env=env,
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1500)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        files = sorted(results.glob("*.json"))
        self.assertEqual(len(files), 1)
        runs = json.loads(files[0].read_text(encoding="utf-8"))["runs"]
        self.assertEqual(len(runs), 2)
        minimum = {"vault": 15, "tally": 20}
        self.assertEqual({r["fixture"] for r in runs}, set(minimum))
        for run in runs:
            self.assertIn(run["result"], ("OK", "REVIEW"), run)
            self.assertTrue(run["failed_stage"] is None or isinstance(run["failed_stage"], str))
            self.assertGreater(run["agents"], 0)
            self.assertGreaterEqual(run["oracle"]["total"], minimum[run["fixture"]])
        self.assertEqual(sorted(p.name for p in tmp.glob("bench-run-*")), [])


if __name__ == "__main__":
    unittest.main()
