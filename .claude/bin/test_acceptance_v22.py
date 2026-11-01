"""Acceptance tests of "the reviewer reads beyond the diff" (agentic-flow 2.2): AC-001 .. AC-005 of
docs/architecture/0005.

Run: python3 -m unittest discover -s .claude/bin -p test_acceptance_v22.py
The callers command runs against temporary git repos; the engines run in the simulated conformance world.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parent
ROOT = BIN.parents[1]
sys.path.insert(0, str(BIN))
import upgrade  # noqa: E402
from test_agentic import Repo  # noqa: E402
from test_pipeline import CONFORMANCE, run_scenario  # noqa: E402

AGENTS = ROOT / ".claude" / "agents"
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
MONEY = "def split(cents, parts):\n    return [cents]\n\n\ndef parse_amount(text):\n    return int(text)\n"
LEDGER = ("from src.money import split, parse_amount\n\n"
          "shares = split(100, 3)\n"
          "total = parse_amount(\"1\")\n"
          "splitter = my_split(1)\n")
TEST_LEDGER = ("import unittest\nfrom src.money import split\n\n\nclass T(unittest.TestCase):\n"
               "    def test_split(self): assert split(1, 1) == [1]\n")
PHRASE = "the package that owns the changed symbol"


def text(path):
    return path.read_text(encoding="utf-8")


def commit_all(repo):
    subprocess.run(["git", "add", "-A"], cwd=repo.dir, check=True, capture_output=True)
    subprocess.run([*GIT, "commit", "-qm", "x"], cwd=repo.dir, check=True, capture_output=True)


def callers_of(repo, env=None):
    r = repo.run("callers", env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = [ln for ln in r.stdout.strip().splitlines() if ln.startswith("{")]
    return json.loads(lines[-1])


def scenario(name):
    return {d["name"]: d for d in CONFORMANCE["scenarios"]}[name]


class CallersTests(unittest.TestCase):
    def repo_with_money(self):
        repo = Repo()
        self.addCleanup(repo.cleanup)
        repo.write("src/money.py", MONEY)
        repo.write("src/ledger.py", LEDGER)
        repo.write("tests/test_ledger.py", TEST_LEDGER)
        repo.write("notes.md", "split is documented here\n")
        commit_all(repo)
        return repo

    def test_ac_001_callers_outside_the_diff(self):
        repo = self.repo_with_money()
        repo.write("src/money.py", MONEY.replace("    return [cents]\n", "    cents = cents\n    return [cents]\n"))
        out = callers_of(repo)
        self.assertEqual(out["changed"], ["src/money.py"])
        self.assertEqual(out["symbols"], {"src/money.py": ["split", "parse_amount"]})
        self.assertIs(out["truncated"], False)
        where = [(c["symbol"], c["file"], c["line"]) for c in out["callers"]]
        self.assertEqual(where, [("split", "src/ledger.py", 1), ("split", "src/ledger.py", 3),
                                 ("split", "tests/test_ledger.py", 2), ("split", "tests/test_ledger.py", 6),
                                 ("parse_amount", "src/ledger.py", 1), ("parse_amount", "src/ledger.py", 4)])
        for item in out["callers"]:
            self.assertEqual(set(item), {"symbol", "defined_in", "file", "line", "text"})
            self.assertEqual(item["defined_in"], "src/money.py")
        files = {c["file"] for c in out["callers"]}
        self.assertNotIn("notes.md", files)
        self.assertNotIn("src/money.py", files)
        self.assertFalse(any(c["line"] == 5 for c in out["callers"]), "splitter / my_split are not whole-word matches")

    def test_ac_002_new_files_caps_and_no_repo(self):
        repo = self.repo_with_money()
        repo.write("src/new.py", "class Thing:\n    pass\n")
        repo.write("src/ledger.py", LEDGER + "thing = Thing()\n")
        commit_all(repo)
        repo.write("src/new.py", "class Thing:\n    x = 1\n")
        out = callers_of(repo)
        self.assertIn("src/new.py", out["changed"])
        self.assertEqual(out["symbols"]["src/new.py"], ["Thing"])
        self.assertEqual([(c["file"], c["line"]) for c in out["callers"] if c["symbol"] == "Thing"], [("src/ledger.py", 6)])

        capped = Repo()
        self.addCleanup(capped.cleanup)
        capped.write("src/a.py", "def f():\n    pass\n\n\ndef g():\n    pass\n")
        capped.write("src/b.py", "".join("f()\n" for _ in range(12)))
        capped.write("src/c.py", "".join("g()\n" for _ in range(75)))
        commit_all(capped)
        capped.write("src/a.py", "def f():\n    return 1\n\n\ndef g():\n    pass\n")
        out = callers_of(capped)
        self.assertEqual(sum(1 for c in out["callers"] if c["symbol"] == "f"), 10)
        self.assertEqual(sum(1 for c in out["callers"] if c["symbol"] == "g"), 10)
        self.assertIs(out["truncated"], True)

        bare = Path(tempfile.mkdtemp(prefix="agentic-norepo-"))
        self.addCleanup(shutil.rmtree, bare, ignore_errors=True)
        (bare / "src").mkdir()
        (bare / "src" / "a.py").write_text("def f():\n    pass\n", encoding="utf-8")
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(bare), GIT_CEILING_DIRECTORIES=str(bare.parent))
        env.pop("AGENTIC_WP", None)
        r = subprocess.run([sys.executable, str(BIN / "agentic.py"), "callers"], cwd=bare, env=env,
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = json.loads([ln for ln in r.stdout.strip().splitlines() if ln.startswith("{")][-1])
        self.assertEqual((out["changed"], out["callers"]), ([], []))
        for item in callers_of(repo)["callers"]:
            self.assertFalse(item["file"].startswith(".claude/state/"))


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r = subprocess.run(["node", str(BIN / "test_workflow.mjs"), "--dump"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        assert r.returncode == 0, r.stdout + r.stderr
        cls.node = json.loads(r.stdout)

    def both(self, name):
        return run_scenario(scenario(name)), self.node[name]

    def test_ac_003_callers_in_the_review_call_and_prompt(self):
        happy = self.both("happy path")
        reached = self.both("callers reach the reviewer")
        ignored = self.both("callers that are not JSON are ignored")
        for summary in happy:
            gates = summary["gates"]
            i = gates.index("open-stage review")
            self.assertEqual(gates[i - 1:i + 2], ["verify", "open-stage review", "callers"])
            self.assertEqual(summary["gate_calls"], 10)
            self.assertNotIn("Callers", summary["prompts"]["reviewer:reviewer#1"])
            self.assertEqual(summary["review_callers"], 0)
        for summary in reached:
            prompt = summary["prompts"]["reviewer:reviewer#1"]
            for word in ("src/b/x.py", '"line":7', PHRASE):
                self.assertIn(word, prompt)
            self.assertEqual(summary["review_callers"], 1)
            self.assertEqual(summary["gates"].count("callers"), 1)
        for summary, plain in zip(ignored, happy):
            self.assertEqual(summary["prompts"]["reviewer:reviewer#1"], plain["prompts"]["reviewer:reviewer#1"])
            self.assertEqual(summary["review_callers"], 0)


class PromptTests(unittest.TestCase):
    def test_ac_004_reviewer_reads_callers(self):
        body = text(AGENTS / "reviewer.md")
        for phrase in ("the callers your prompt lists", "Read each one and check that the change keeps it working",
                       "a caller your prompt lists that the change breaks"):
            self.assertIn(phrase, body)
        self.assertNotIn("nor problems in code that was not touched, unless they are critical security issues.", body)
        for kept in ("No concrete case, no finding", "# Needs validation"):
            self.assertIn(kept, body)


class ReleaseTests(unittest.TestCase):
    def test_ac_005_version_and_notes(self):
        version = json.loads(text(ROOT / ".claude-plugin" / "plugin.json"))["version"]
        self.assertEqual(version, "2.3.0")
        notes = upgrade.NOTES["2.2.0"]
        self.assertGreaterEqual(len(notes), 2)
        joined = " ".join(notes)
        for word in ("callers", "reviewer", "install"):
            self.assertIn(word, joined)
        self.assertEqual(len(upgrade.NOTES["2.1.0"]), 4)
        self.assertEqual(len(upgrade.NOTES["2.0.0"]), 7)
        roadmap = text(ROOT / "docs" / "roadmap" / "repo-review-2026-11.md")
        line = next(ln for ln in roadmap.splitlines() if ln.startswith("| 3.1 |"))
        self.assertIn("Shipped in 2.2.0", line)


if __name__ == "__main__":
    unittest.main()
