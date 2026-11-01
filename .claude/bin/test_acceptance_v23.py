"""Acceptance tests of agentic-flow 2.3: AC-001 .. AC-006 of docs/architecture/0007.

Run: python3 -m unittest discover -s .claude/bin -p test_acceptance_v23.py
run-wave and the bench run with the simulated `claude`; the engines in the simulated conformance world. Nothing is spent.
"""
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parent
ROOT = BIN.parents[1]
sys.path.insert(0, str(BIN))
sys.path.insert(0, str(ROOT / "bench" / "acceptance"))
import pipeline  # noqa: E402
import upgrade  # noqa: E402
from test_agentic import Repo, testutil  # noqa: E402
from test_pipeline import CONFORMANCE, SPEC, run_scenario, world  # noqa: E402

GIT_ID = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def finding(problem, severity="high", wp="WP-02"):
    return {"severity": severity, "wp": wp, "file": "src/b/x.py", "line": 1, "problem": problem, "evidence": "e",
            "fix": "f", "if_skipped": "s"}


def defect(repro, severity="high", wp="WP-02", kind="implementation"):
    return {"id": "D1", "severity": severity, "wp": wp, "kind": kind, "section": "6", "repro": repro, "fix": "f",
            "if_skipped": "s"}


def structured(report):
    return json.dumps({"structured_output": report})


class FixCase(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.addCleanup(self.repo.cleanup)
        self.bin = Path(tempfile.mkdtemp(prefix="fake-claude-"))
        self.logs = Path(tempfile.mkdtemp(prefix="fake-logs-"))
        self.addCleanup(shutil.rmtree, self.bin, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.logs, ignore_errors=True)
        self.repo.env.update(AGENTIC_CLAUDE=testutil.install_fake_claude(self.bin), FAKE_LOG_DIR=str(self.logs))
        self.runs = self.repo.dir / ".claude" / "state" / "runs"
        self.runs.mkdir(parents=True, exist_ok=True)
        self.clock = time.time() - 1000

    def put(self, name, text):
        """Writes runs/<name> with a modification time later than every file written before it."""
        path = self.runs / name
        path.write_text(text, encoding="utf-8")
        self.clock += 10
        os.utime(path, (self.clock, self.clock))

    def clear(self):
        shutil.rmtree(self.runs)
        self.runs.mkdir(parents=True)

    def fix(self, *extra):
        return self.repo.run("run-wave", "1", "WP-02", *extra)

    def prompt(self):
        return testutil.fake_calls(self.logs, "WP-02")[-1]["prompt"]


class FixTests(FixCase):
    def test_ac_001_newest_source(self):
        # (a) only the run record: confirmed is read, refuted is not
        self.put("workflow-result.json", json.dumps({"result": "REVIEW", "review": {
            "confirmed": [finding("confirmed one")], "refuted": [finding("refuted one")], "advisory": []},
            "qa": {"status": "PASS", "defects": []}}))
        r = self.fix("--fix")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("confirmed one", self.prompt())
        self.assertNotIn("refuted one", self.prompt())
        # (b) per-agent files of run-pipeline: the reviewer's, not a verifier's or the test-auditor's
        self.clear()
        self.put("REVIEW-7.json", structured({"status": "FAIL", "findings": [finding("reviewer seven")],
                                              "needs_validation": [], "not_checked": []}))
        self.put("REVIEW-9.json", structured({"is_real": True, "confidence": 0.9, "reasoning": "it holds"}))
        self.put("REVIEW-2.json", structured({"status": "FAIL", "findings": [finding("auditor two")], "not_checked": []}))
        r = self.fix("--fix")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("reviewer seven", self.prompt())
        self.assertNotIn("auditor two", self.prompt())
        # (c) a one-off run-review newer than the run record wins
        self.clear()
        self.put("workflow-result.json", json.dumps({"result": "REVIEW", "review": {
            "confirmed": [finding("from the record")], "refuted": [], "advisory": []}, "qa": None}))
        self.put("REVIEW.json", structured({"status": "FAIL", "findings": [finding("from run-review")],
                                            "needs_validation": [], "not_checked": []}))
        r = self.fix("--fix")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("from run-review", self.prompt())
        self.assertNotIn("from the record", self.prompt())

    def test_ac_002_all_and_messages(self):
        self.put("workflow-result.json", json.dumps({"result": "REVIEW", "review": {
            "confirmed": [], "refuted": [], "advisory": [finding("medium one", "medium")]},
            "qa": {"status": "FAIL", "defects": [defect("low one", "low"), defect("design one", "high", kind="design")]}}))
        r = self.fix("--fix")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no blocking defect", r.stderr)
        self.assertIn("workflow-result.json", r.stderr)
        r = self.fix("--fix", "--all")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for word in ("medium one", "low one"):
            self.assertIn(word, self.prompt())
        self.assertNotIn("design one", self.prompt())
        self.assertEqual(self.fix("--fix", "--all").returncode, 0)
        r = self.fix("--fix", "--all")
        self.assertEqual(r.returncode, 4, "the fix-cycle cap applies with --all too")
        r = self.fix("--all")
        self.assertEqual(r.returncode, 1)
        self.assertIn("--fix [--all]", r.stderr)
        self.clear()
        r = self.fix("--fix")
        self.assertEqual(r.returncode, 1)
        self.assertIn("run-pipeline, run-review or run-qa", r.stderr)


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r = subprocess.run(["node", str(BIN / "test_workflow.mjs"), "--dump"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        assert r.returncode == 0, r.stdout + r.stderr
        cls.node = json.loads(r.stdout)

    def test_ac_003_verification_failures(self):
        by_name = {d["name"]: d for d in CONFORMANCE["scenarios"]}
        expected = {"verification fails on a package: it is fixed and verified again": 1,
                    "verification never gets fixed": 3, "verification fails with no owner": 1, "happy path": 0}
        for name, count in expected.items():
            with self.subTest(scenario=name):
                self.assertEqual(run_scenario(by_name[name])["verification_failures"], count)
                self.assertEqual(self.node[name]["verification_failures"], count)
        state, gate, agent = world(by_name["verification fails on a package: it is fixed and verified again"])
        result = pipeline.Pipeline(SPEC, gate, agent, parallel=lambda ts: [t() for t in ts]).execute()
        first = result["verification_failures"][0]
        self.assertEqual(first["fix_cycle"], 0)
        self.assertEqual(first["blocking"], ["tests"])
        self.assertIn("WP-02", first["suspects"])
        self.assertEqual(first["failing"][0]["name"], "tests")


def load_bench():
    from test_acceptance_bench import load_bench as load
    return load()


class StatsTests(unittest.TestCase):
    def test_ac_004_statistics(self):
        bench = load_bench()
        self.assertAlmostEqual(bench.geometric_mean([0.5, 2.0]), 1.0)
        self.assertIsNone(bench.geometric_mean([]))
        self.assertIsNone(bench.geometric_mean([1.0, 0.0]))
        self.assertAlmostEqual(bench.sign_test(5, 0), 0.0625)
        self.assertEqual(bench.sign_test(3, 3), 1.0)
        self.assertEqual(bench.sign_test(0, 0), 1.0)
        self.assertEqual(bench.sign_test(1, 0), 1.0)
        doubled = {"f1": ([1, 1, 1], [2, 2, 2]), "f2": ([1, 1, 1], [2, 2, 2])}
        first = bench.bootstrap_interval(doubled, seed=0)
        random.seed(99)
        again = bench.bootstrap_interval(doubled, seed=0)
        self.assertEqual(first, again)
        self.assertEqual(tuple(first), (2.0, 2.0))
        self.assertEqual(tuple(bench.bootstrap_interval(doubled, seed=1)), (2.0, 2.0))
        low, high = bench.bootstrap_interval({"f": ([1.0, 1.1, 0.9], [1.0, 1.1, 0.9])}, seed=0)
        self.assertLessEqual(low, 1.0)
        self.assertGreaterEqual(high, 1.0)


class AbTests(unittest.TestCase):
    def make_repo(self):
        repo = Path(tempfile.mkdtemp(prefix="ab-repo-"))
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        ignore = shutil.ignore_patterns("state", "rules", "__pycache__")
        shutil.copytree(ROOT / ".claude", repo / ".claude", ignore=ignore)
        shutil.copytree(ROOT / ".claude-plugin", repo / ".claude-plugin")
        for cmd in (["git", "init", "-q"], ["git", "add", "-A"], ["git", *GIT_ID, "commit", "-qm", "init"]):
            subprocess.run(cmd, cwd=repo, check=True, capture_output=True)
        return repo

    def worktrees(self, repo):
        out = subprocess.run(["git", "worktree", "list"], cwd=repo, capture_output=True, text=True, check=True).stdout
        return [ln for ln in out.splitlines() if ln.strip()]

    def test_ac_005_ab_run(self):
        from test_acceptance_bench import Sandbox
        box = Sandbox()
        self.addCleanup(box.cleanup)
        repo = self.make_repo()
        args = ["ab", "--a", str(repo), "--b", "HEAD", "--repo", str(repo), "--fixture", str(box.fixture),
                "--out", str(box.results)]
        r = box.bench(*args, "--repeat", "2")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        files = sorted(box.results.glob("ab-*.json"))
        self.assertEqual(len(files), 1, list(box.results.iterdir()))
        doc = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertEqual(doc["schema"], "ab-1")
        self.assertEqual([run["arm"] for run in doc["runs"]], ["a", "b", "b", "a"])
        self.assertEqual((doc["a"]["spec"], doc["b"]["spec"]), (str(repo), "HEAD"))
        self.assertIn("benchfix", doc["comparison"]["fixtures"])
        self.assertIn("cost_usd", doc["comparison"]["overall"])
        for run in doc["runs"]:
            self.assertIn("verification_failures", run)
        md = files[0].with_suffix(".md")
        self.assertTrue(md.is_file())
        self.assertIn("benchfix", md.read_text(encoding="utf-8"))
        self.assertIn("benchfix", r.stdout)
        stem = files[0].with_suffix("")
        self.assertEqual(len(list((stem / "a").glob("*.json"))), 2)
        self.assertEqual(len(list((stem / "b").glob("*.json"))), 2)
        self.assertEqual(len(self.worktrees(repo)), 1)
        report = box.bench("report", "--out", str(box.results))
        self.assertEqual(report.returncode, 0, report.stderr)
        self.assertNotIn("ab-", (box.root / "RESULTS.md").read_text(encoding="utf-8"))
        # refusals before any spend
        self.assertEqual(box.bench(*args, "--repeat", "0").returncode, 1)
        broken = box.root / "broken"
        shutil.copytree(box.fixture, broken)
        (broken / "oracle" / "test_oracle.py").write_text("import unittest\n", encoding="utf-8")
        bad = box.bench("ab", "--a", str(repo), "--b", "HEAD", "--repo", str(repo), "--fixture", str(broken),
                        "--out", str(box.root / "none"), "--repeat", "1")
        self.assertEqual(bad.returncode, 1)
        self.assertFalse((box.root / "none").exists() and list((box.root / "none").glob("ab-*.json")))
        self.assertEqual(len(self.worktrees(repo)), 1)
        # every session times out: recorded, no minutes ratio, no worktree left
        slow = Sandbox(FAKE_SLEEP="30")
        self.addCleanup(slow.cleanup)
        r = slow.bench("ab", "--a", str(repo), "--b", "HEAD", "--repo", str(repo), "--fixture", str(slow.fixture),
                       "--out", str(slow.results), "--repeat", "1", "--timeout-min", "0.01")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        doc = json.loads(sorted(slow.results.glob("ab-*.json"))[0].read_text(encoding="utf-8"))
        self.assertTrue(all(run["result"] == "timeout" for run in doc["runs"]))
        self.assertIsNone(doc["comparison"]["fixtures"]["benchfix"]["minutes"])
        self.assertEqual(len(self.worktrees(repo)), 1)


class ReleaseTests(unittest.TestCase):
    def test_ac_006_version_notes_roadmap(self):
        version = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
        self.assertEqual(version, "2.3.0")
        notes = upgrade.NOTES["2.3.0"]
        self.assertGreaterEqual(len(notes), 2)
        joined = " ".join(notes)
        for word in ("--fix", "--all", "workflow-result.json", "verification_failures"):
            self.assertIn(word, joined)
        self.assertEqual([len(upgrade.NOTES[v]) for v in ("2.2.0", "2.1.0", "2.0.0")], [2, 4, 7])
        roadmap = (ROOT / "docs" / "roadmap" / "repo-review-2026-11.md").read_text(encoding="utf-8")
        lines = roadmap.splitlines()
        for item in ("1.1", "1.2", "1.4", "1.5", "3.2", "4.1", "4.2", "4.3"):
            with self.subTest(item=item):
                row = next(ln for ln in lines if ln.startswith(f"| {item} |"))
                self.assertIn("Shipped", row)
        for item in ("6.5", "6.6"):
            with self.subTest(item=item):
                bullet = next(ln for ln in lines if ln.startswith(f"- {item} "))
                self.assertIn("Shipped", bullet)
        self.assertIn("Partly", next(ln for ln in lines if ln.startswith("| 4.4 |")))
        found = roadmap[roadmap.index("## Found while using the flow"):]
        found = found[:found.index("\n## ", 1)] if "\n## " in found[1:] else found
        self.assertIn("Fixed in 2.3.0", found)
        for word in ("hooks", "test-auditor", "test_ac_013"):
            self.assertIn(word, found)


if __name__ == "__main__":
    unittest.main()
