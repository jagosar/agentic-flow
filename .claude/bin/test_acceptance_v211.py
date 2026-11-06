"""Acceptance tests of agentic-flow 2.11.0: AC-001 .. AC-008 of docs/architecture/0018 (agent shortcuts, validate
warnings, the workflow-subagent claim, clean UTF-8, and test_acceptance_v210.py retired).

Run: python3 -m unittest discover -s .claude/bin -p test_acceptance_v211.py
The hook and the stage check run against temporary repositories. Fixtures split the shortcut tokens and write
special characters as escapes, so this file itself adds no match.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parent
ROOT = BIN.parents[1]
sys.path.insert(0, str(BIN))
from test_agentic import MANIFEST, Repo, bash_payload, write_payload  # noqa: E402

DEBUG = "[DEB" "UG-"
ALWAYS = "assert " + "True"
SWALLOW = "try:\n    x()\nexcept Exception:\n" + "    pa" "ss\n"
EMPTY_CATCH = "try { x() } catch (e) {" + "}\n"


def flow_repo_files():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    return [line for line in out.stdout.splitlines() if line]


class Case(unittest.TestCase):
    def repo(self, manifest=MANIFEST):
        repo = Repo(manifest)
        self.addCleanup(repo.cleanup)
        return repo

    def write(self, repo, rel, content, env=None):
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(repo.dir / rel), "content": content}}
        return repo.run("hook", stdin=json.dumps(payload), env=env or {"AGENTIC_WP": "WP-01"})


class HookTests(Case):
    def test_ac_001_shortcuts_blocked(self):
        repo = self.repo()
        cases = [("src/a.py", SWALLOW, "an exception swallowed with pass"),
                 ("src/a.py", EMPTY_CATCH, "an empty catch block"),
                 ("src/a.py", f'print("{DEBUG}1]")\n', "a [DEBUG-] log left behind"),
                 ("tests/test_a.py", f"def test_a():\n    {ALWAYS}\n", "an assertion that is always true"),
                 ("tests/test_a.py", "def test_a():\n    x = 1\n", "a test without an assertion")]
        for rel, content, what in cases:
            with self.subTest(what=what):
                r = self.write(repo, rel, content)
                self.assertEqual(r.returncode, 2, r.stderr)
                self.assertIn(what, r.stderr)
                self.assertIn(rel, r.stderr)
        allowed = [("src/a.py", "try:\n    x()\nexcept ValueError:\n" + "    pa" "ss\n"),
                   ("tests/test_a.py", "def test_a(self):\n    self.assertEqual(1, 1)\n"),
                   ("tests/test_a.py", "def test_a():\n    check_total()\n"),
                   ("src/a.py", f"{ALWAYS}\n")]
        for rel, content in allowed:
            with self.subTest(allowed=content):
                r = self.write(repo, rel, content)
                self.assertEqual(r.returncode, 0, r.stderr)
        repo.write("src/a.py", SWALLOW)
        edit = {"tool_name": "Edit", "tool_input": {"file_path": str(repo.dir / "src/a.py"), "old_string": "x()",
                                                    "new_string": "y()"}}
        r = repo.run("hook", stdin=json.dumps(edit), env={"AGENTIC_WP": "WP-01"})
        self.assertEqual(r.returncode, 0, "what was already there once is not blamed: " + r.stderr)

    def test_ac_004_workflow_subagent(self):
        repo = self.repo()
        agent = {"agent_id": "w1", "agent_type": "workflow-subagent"}
        r = repo.run("hook", stdin=json.dumps({**write_payload(str(repo.dir / "src/a.py")), **agent}))
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("claim", r.stderr)
        r = repo.run("hook", stdin=json.dumps({**bash_payload("ls"), **agent}))
        self.assertEqual(r.returncode, 0, r.stderr)
        claim = {**bash_payload("python3 .claude/bin/agentic.py claim WP-01"), **agent}
        self.assertEqual(repo.run("hook", stdin=json.dumps(claim)).returncode, 0)
        own = repo.run("hook", stdin=json.dumps({**write_payload(str(repo.dir / "src/a.py")), **agent}))
        foreign = repo.run("hook", stdin=json.dumps({**write_payload(str(repo.dir / "src/b/x.py")), **agent}))
        self.assertEqual((own.returncode, foreign.returncode), (0, 2), own.stderr + foreign.stderr)
        self.assertEqual(repo.hook(write_payload(str(repo.dir / "anything.py"))), 0, "the main thread is free")
        other = {**write_payload(str(repo.dir / "anything.py")), "agent_id": "o1", "agent_type": "general-purpose"}
        self.assertEqual(repo.run("hook", stdin=json.dumps(other)).returncode, 0, "other unknown types unchanged")


class StageTests(Case):
    def test_ac_002_close_stage(self):
        repo = self.repo()
        repo.write("src/a.py", SWALLOW)
        subprocess.run(["git", "add", "-A"], cwd=repo.dir, check=True)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base"], cwd=repo.dir,
                       check=True)
        repo.run("snapshot", "1")
        repo.as_agent()
        repo.write("src/a.py", SWALLOW + SWALLOW + f'print("{DEBUG}x]")\n')
        r = repo.run("check-wave", "1")
        self.assertEqual(r.returncode, 3, r.stdout)
        self.assertIn("src/a.py: an exception swallowed with pass", r.stdout)
        self.assertIn("src/a.py: a [DEBUG-] log left behind", r.stdout)
        repo.write("src/a.py", SWALLOW)
        r = repo.run("check-wave", "1")
        self.assertEqual(r.returncode, 0, r.stdout)


class CoreTests(unittest.TestCase):
    def test_ac_003_assertless_tests(self):
        import core
        cases = [("def test_a():\n    assert 1\n\ndef test_b():\n    assert 2\n", 0),
                 ("class T:\n    def test_a(self):\n        self.assertIn(1, [1])\n", 0),
                 ("def test_a():\n    with pytest.raises(ValueError):\n        f()\n", 0),
                 ("def test_a():\n    x = 1\n", 1),
                 ("class T:\n    def test_b(self):\n        " + "pa" "ss\n", 1),
                 ("def (:\n", 0),
                 ("def helper():\n    x = 1\n", 0)]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(core.assertless_tests(text), expected)


def manifest_with(**changes):
    m = json.loads(json.dumps(MANIFEST))
    for key, value in changes.items():
        m[key] = value
    return m


class ValidateTests(Case):
    def warnings(self, manifest):
        r = self.repo(manifest).run("validate")
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[0], "Manifest valid.")
        return [line for line in lines if line.startswith("warning: ")]

    def test_ac_005_warnings(self):
        self.assertEqual(self.warnings(MANIFEST), [])
        big = json.loads(json.dumps(MANIFEST))
        big["work_packages"][0]["files"] = [f"src/f{i}.py" for i in range(16)]
        big["work_packages"][1]["acs"] = [f"AC-{i:03d}" for i in range(1, 10)]
        found = self.warnings(big)
        self.assertIn("warning: WP-01: owns 16 files (more than 15): consider splitting it", found)
        self.assertIn("warning: WP-02: answers for 9 criteria (more than 8): consider splitting it", found)
        wide = manifest_with(work_packages=[{"id": f"WP-{i:02d}", "wave": 1, "depends_on": [],
                                             "files": [f"src/p{i}.py"]} for i in range(1, 10)])
        self.assertIn("warning: wave 1: 9 packages (more than 8): consider another wave", self.warnings(wide))
        chain = manifest_with(work_packages=[{"id": f"WP-0{i}", "wave": i, "depends_on": [],
                                              "files": [f"src/c{i}.py"]} for i in range(1, 4)])
        self.assertIn("warning: every wave holds one package: the plan is a chain, nothing runs in parallel",
                      self.warnings(chain))
        r = self.repo(big).run("pipeline-plan")
        self.assertNotIn("warning:", r.stdout + r.stderr)


class EncodingTests(unittest.TestCase):
    def test_ac_006_text_problems(self):
        import test_encoding
        d = Path(tempfile.mkdtemp(prefix="utf8-"))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        (d / "ok.md").write_bytes("\u00f1\n".encode("utf-8"))
        (d / "latin.txt").write_bytes(b"caf\xe9\n")
        (d / "double.md").write_bytes("caf\u00c3\u00a9\n".encode("utf-8"))
        (d / "bom.md").write_bytes("\ufeffx\n".encode("utf-8"))
        (d / "bin.dat").write_bytes(b"\x00\xff")
        paths = ["ok.md", "latin.txt", "double.md", "bom.md", "bin.dat"]
        self.assertEqual(test_encoding.text_problems(d, paths),
                         ["bom.md: starts with a byte-order mark", "double.md: double-encoded text",
                          "latin.txt: not valid UTF-8"])


class ReleaseTests(unittest.TestCase):
    def test_ac_007_repo_and_release(self):
        import agentic
        import test_encoding
        import upgrade
        self.assertEqual(json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))["version"],
                         "2.11.0")
        notes = " ".join(upgrade.NOTES.get("2.11.0", []))
        for word in ("shortcut", "validate", "workflow-subagent"):
            self.assertIn(word, notes)
        if not agentic.is_flow_repo(ROOT):
            self.skipTest("the agentic-flow repository only")
        self.assertEqual(test_encoding.text_problems(ROOT, flow_repo_files()), [])


class RetireTests(unittest.TestCase):
    def test_ac_008_v210_retired(self):
        import test_guardrail
        import test_launcher
        self.assertTrue(hasattr(test_launcher, "ByHandPlanTests"))
        self.assertTrue(hasattr(test_launcher.ByHandPlanTests, "test_every_agent_command_refuses_before_writing"))
        self.assertTrue(hasattr(test_guardrail, "HookLauncherTests"))
        self.assertTrue(hasattr(test_guardrail.HookLauncherTests, "test_a_leftover_frozen_copy_is_never_run"))
        self.assertEqual(sorted(p.name for p in BIN.glob("test_acceptance*.py")), ["test_acceptance_v211.py"])


if __name__ == "__main__":
    unittest.main()
