"""`bench.py ab` end to end with the simulated `claude`: two arms over a temporary git repository and its worktree.
Moved here from the retired .claude/bin/test_acceptance_v23.py (design 0017, ac_005).

Run: python3 -m unittest discover -s bench/acceptance -p test_acceptance_ab.py
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_acceptance_bench import Sandbox

ROOT = Path(__file__).resolve().parents[2]
GIT_ID = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


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
        return [line for line in out.splitlines() if line.strip()]

    def sandbox(self, **env):
        box = Sandbox(**env)
        self.addCleanup(box.cleanup)
        return box

    def ab(self, box, repo, *extra, fixture=None, out=None):
        return box.bench("ab", "--a", str(repo), "--b", "HEAD", "--repo", str(repo), "--fixture",
                         str(fixture or box.fixture), "--out", str(out or box.results), *extra)

    def test_two_arms_interleave_and_leave_no_worktree(self):
        box, repo = self.sandbox(), self.make_repo()
        r = self.ab(box, repo, "--repeat", "2")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        files = sorted(box.results.glob("ab-*.json"))
        self.assertEqual(len(files), 1, list(box.results.iterdir()))
        doc = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertEqual(doc["schema"], "ab-1")
        self.assertEqual([run["arm"] for run in doc["runs"]], ["a", "b", "b", "a"])
        self.assertEqual((doc["a"]["spec"], doc["b"]["spec"]), (str(repo), "HEAD"))
        self.assertIn("benchfix", doc["comparison"]["fixtures"])
        self.assertTrue(all("verification_failures" in run for run in doc["runs"]))
        self.assertIn("benchfix", files[0].with_suffix(".md").read_text(encoding="utf-8"))
        stem = files[0].with_suffix("")
        self.assertEqual([len(list((stem / arm).glob("*.json"))) for arm in ("a", "b")], [2, 2])
        self.assertEqual(len(self.worktrees(repo)), 1)
        self.assertEqual(box.bench("report", "--out", str(box.results)).returncode, 0)
        self.assertNotIn("ab-", (box.root / "RESULTS.md").read_text(encoding="utf-8"))

    def test_it_refuses_before_spending(self):
        box, repo = self.sandbox(), self.make_repo()
        self.assertEqual(self.ab(box, repo, "--repeat", "0").returncode, 1)
        broken = box.root / "broken"
        shutil.copytree(box.fixture, broken)
        (broken / "oracle" / "test_oracle.py").write_text("import unittest\n", encoding="utf-8")
        none = box.root / "none"
        self.assertEqual(self.ab(box, repo, "--repeat", "1", fixture=broken, out=none).returncode, 1)
        self.assertFalse(none.exists() and list(none.glob("ab-*.json")))
        self.assertEqual(len(self.worktrees(repo)), 1)

    def test_sessions_that_time_out_are_recorded(self):
        box, repo = self.sandbox(FAKE_SLEEP="30"), self.make_repo()
        r = self.ab(box, repo, "--repeat", "1", "--timeout-min", "0.01")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        doc = json.loads(sorted(box.results.glob("ab-*.json"))[0].read_text(encoding="utf-8"))
        self.assertTrue(all(run["result"] == "timeout" for run in doc["runs"]))
        self.assertIsNone(doc["comparison"]["fixtures"]["benchfix"]["minutes"])
        self.assertEqual(len(self.worktrees(repo)), 1)


if __name__ == "__main__":
    unittest.main()
