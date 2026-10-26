"""Tests of upgrade.py: classification, versions and notes, guards and the history built from git."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import upgrade  # noqa: E402

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


class Repo:
    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix="upgrade-unit-"))
        subprocess.run(["git", "init", "-q"], cwd=self.dir, check=True)

    def commit(self, files):
        for rel, text in files.items():
            p = self.dir / rel
            if text is None:
                p.unlink()
                continue
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        subprocess.run(["git", "add", "-A"], cwd=self.dir, check=True)
        subprocess.run(GIT + ["commit", "-qm", "c"], cwd=self.dir, check=True)


class ClassifyTests(unittest.TestCase):
    def test_table(self):
        cases = [((None, "s", set(), False), "new"), (("s", "s", set(), False), "unchanged"),
                 (("old", "s", {"old"}, False), "updated"), (("mine", "s", {"old"}, False), "kept"),
                 (("mine", "s", set(), True), "updated")]
        for args, expected in cases:
            with self.subTest(args=args):
                self.assertEqual(upgrade.classify(*args), expected)


class LeftoverTests(unittest.TestCase):
    def test_a_partial_test_suite_is_completed_ci_and_plugin_files_are_not(self):
        shipped = {".claude/bin/test_a.py", ".claude/bin/conformance.json", ".github/workflows/ci.yml", "plugin/commands/init.md",
                   ".claude/bin/test_acceptance_x.py"}
        self.assertEqual(upgrade.leftovers(shipped, {".claude/bin/test_a.py"}),
                         {".claude/bin/test_a.py", ".claude/bin/conformance.json"})
        self.assertEqual(upgrade.leftovers(shipped, {".github/workflows/ci.yml"}), {".github/workflows/ci.yml"})
        self.assertEqual(upgrade.leftovers(shipped, set()), set())


class NotesTests(unittest.TestCase):
    NOTES = {"1.2.0": ["two"], "1.10.0": ["ten"], "1.1.0": ["one"]}

    def test_order_and_bounds(self):
        with mock.patch.dict(upgrade.NOTES, self.NOTES, clear=True):
            self.assertEqual(upgrade.notes_between("1.1.0", "1.10.0"), ["two", "ten"], "1.10 sorts after 1.2")
            self.assertEqual(upgrade.notes_between("1.10.0", "1.10.0"), [])
            self.assertEqual(upgrade.notes_between(None, "1.2.0"), ["one", "two"])
            self.assertEqual(upgrade.notes_between("unknown", "dev"), ["one", "two", "ten"])

    def test_real_notes_name_the_removed_commands(self):
        self.assertIn("wave-plan", " ".join(upgrade.notes_between("1.0.0", "1.1.0")))


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.addCleanup(shutil.rmtree, self.repo.dir, ignore_errors=True)
        self.repo.commit({"a.md": "x\n"})

    def test_not_a_git_repo(self):
        plain = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, plain, ignore_errors=True)
        self.assertEqual(upgrade.guard_problems(plain, ["a.md"]), ["not a git repository"])

    def test_tracked_changes_block_untracked_do_not(self):
        (self.repo.dir / "a.md").write_text("y\n")
        (self.repo.dir / "new.md").write_text("z\n")
        self.assertEqual(upgrade.guard_problems(self.repo.dir, ["a.md", "new.md"]), ["uncommitted: a.md"])
        self.assertEqual(upgrade.guard_problems(self.repo.dir, ["new.md"]), [])

    def test_a_running_agent_blocks_and_stage_keys_are_ignored(self):
        state = self.repo.dir / ".claude/state"
        state.mkdir(parents=True)
        (state / "ledger.json").write_text(json.dumps({"_stages": {"state": "running"}, "QA": {"state": "running"},
                                                       "WP-01": {"state": "done"}}))
        problems = upgrade.guard_problems(self.repo.dir, [])
        self.assertEqual(len(problems), 1)
        self.assertIn("a run is in progress (QA)", problems[0])


class HistoryTests(unittest.TestCase):
    def test_every_version_of_every_matching_path(self):
        repo = Repo()
        self.addCleanup(shutil.rmtree, repo.dir, ignore_errors=True)
        repo.commit({".claude/agents/qa.md": "A\n", "README.md": "r\n"})
        repo.commit({".claude/agents/qa.md": "B\n", ".claude/workflows/old.js": "X\n"})
        repo.commit({".claude/workflows/old.js": None})
        data = upgrade.build_history(repo.dir, [".claude/agents/*.md", ".claude/workflows/*.js"])
        self.assertEqual(data["files"], {".claude/agents/qa.md": sorted([sha("A\n"), sha("B\n")]),
                                         ".claude/workflows/old.js": [sha("X\n")]})
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo.dir, capture_output=True, text=True).stdout.strip()
        self.assertEqual(data["generated_from"], head)

    def test_refuses_without_git(self):
        plain = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, plain, ignore_errors=True)
        with self.assertRaisesRegex(ValueError, "not a git repository"):
            upgrade.build_history(plain, ["*"])

    def test_load_history_tolerates_missing_or_bad_files(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        self.assertEqual(upgrade.load_history(tmp), {})
        (tmp / ".claude").mkdir()
        (tmp / ".claude/flow-history.json").write_text("not json")
        self.assertEqual(upgrade.load_history(tmp), {})
        (tmp / ".claude/flow-history.json").write_text(json.dumps({"files": {"a": ["h"]}}))
        self.assertEqual(upgrade.load_history(tmp), {"a": {"h"}})


if __name__ == "__main__":
    unittest.main()
