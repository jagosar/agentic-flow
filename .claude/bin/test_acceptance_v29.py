"""Acceptance tests of agentic-flow 2.9.0: AC-001 .. AC-011 of docs/architecture/0015 (release from the merge).

Run: python3 -m unittest discover -s .claude/bin -p test_acceptance_v29.py
The check runs a copy of this checkout's .claude/bin in temporary git repositories with their own tags, versions and
history; the workflows and the guide are read as text. Nothing is spent and nothing touches the network.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parent
ROOT = BIN.parents[1]
sys.path.insert(0, str(BIN))
import agentic  # noqa: E402
import upgrade  # noqa: E402

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
QA = ".claude/agents/qa.md"
PLUGIN = ".claude-plugin/plugin.json"
RELEASE_YML = ROOT / ".github/workflows/agentic-flow-release.yml"
CI_YML = ROOT / ".github/workflows/agentic-flow-ci.yml"


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PROJECT_DIR", "CLAUDECODE")}
    env.update(extra)
    return env


def run(cmd, cwd, env=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=env or clean_env())


class FlowCopy:
    """A temporary git repository holding a copy of the flow's scripts, a plugin.json and an agent file."""

    def __init__(self, version="1.0.0", qa="A"):
        self.dir = Path(tempfile.mkdtemp(prefix="v29-"))
        (self.dir / ".claude/bin").mkdir(parents=True)
        for f in BIN.glob("*.py"):
            if not f.name.startswith("test_"):
                shutil.copy(f, self.dir / ".claude/bin" / f.name)
        run(["git", "init", "-q"], self.dir)
        self.set(version=version, qa=qa)
        self.commit("init")

    def set(self, version=None, qa=None):
        if version is not None:
            (self.dir / ".claude-plugin").mkdir(exist_ok=True)
            (self.dir / PLUGIN).write_text(json.dumps({"name": "agentic-flow", "version": version}) + "\n",
                                           encoding="utf-8")
        if qa is not None:
            (self.dir / ".claude/agents").mkdir(parents=True, exist_ok=True)
            (self.dir / QA).write_text(qa + "\n", encoding="utf-8")

    def commit(self, msg):
        run(["git", "add", "-A"], self.dir)
        r = run(GIT + ["commit", "-qm", msg], self.dir)
        assert r.returncode == 0, r.stderr

    def tag(self, name):
        run(["git", "tag", name], self.dir)

    def agentic(self, *args, env=None):
        return run([sys.executable, str(self.dir / ".claude/bin/agentic.py"), *args], self.dir, env)

    def regenerate(self):
        r = self.agentic("flow-history")
        assert r.returncode == 0, r.stderr
        self.commit("history")

    def history_bytes(self):
        return (self.dir / ".claude/flow-history.json").read_bytes()

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class CheckTests(unittest.TestCase):
    def copy(self, **kw):
        repo = FlowCopy(**kw)
        self.addCleanup(repo.cleanup)
        return repo

    def check(self, repo):
        r = repo.agentic("flow-history", "--check")
        try:
            data = json.loads(r.stdout)
        except ValueError:
            data = None
        return r, data

    def published(self):
        """AC-001's scenario: version 1.0.0, qa.md A, history committed, tagged."""
        repo = self.copy()
        repo.regenerate()
        repo.tag("agentic-flow--v1.0.0")
        return repo

    def test_ac_001_covered_tags_pass(self):
        repo = self.published()
        before = repo.history_bytes()
        r, data = self.check(repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(data, {"ok": True, "tags": 1, "pending": None, "missing": []})
        self.assertEqual(repo.history_bytes(), before, "the check writes nothing")
        self.assertEqual(run(["git", "status", "--porcelain"], repo.dir).stdout, "")

    def test_ac_002_unknown_tag_content_fails(self):
        repo = self.copy()
        repo.regenerate()
        repo.set(qa="B")
        repo.commit("B")
        repo.tag("agentic-flow--v1.0.0")
        before = repo.history_bytes()
        r, data = self.check(repo)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertFalse(data["ok"])
        self.assertEqual(data["missing"], [{"ref": "agentic-flow--v1.0.0", "path": QA}])
        self.assertEqual(repo.history_bytes(), before, "the check does not regenerate")

    def test_ac_003_pending_version_needs_head(self):
        repo = self.published()
        repo.set(version="1.1.0", qa="C")
        repo.commit("bump")
        r, data = self.check(repo)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertEqual(data["pending"], "1.1.0")
        self.assertEqual(data["missing"], [{"ref": "HEAD", "path": PLUGIN}, {"ref": "HEAD", "path": QA}])
        repo.regenerate()
        r, data = self.check(repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((data["pending"], data["missing"]), ("1.1.0", []))

    def test_ac_004_no_bump_no_head_check(self):
        repo = self.published()
        repo.set(qa="D")
        repo.commit("D")
        r, data = self.check(repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((data["pending"], data["missing"]), (None, []))

    def test_ac_005_shallow_clone_refused(self):
        repo = self.published()
        clone = Path(tempfile.mkdtemp(prefix="v29-shallow-"))
        self.addCleanup(shutil.rmtree, clone, ignore_errors=True)
        r = run(["git", "clone", "-q", "--depth", "1", repo.dir.as_uri(), str(clone / "c")], clone)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = run([sys.executable, str(clone / "c/.claude/bin/agentic.py"), "flow-history", "--check"], clone / "c")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("flow-history: needs the full git history", r.stderr)
        self.assertNotIn('"ok"', r.stdout)


class NotesTests(unittest.TestCase):
    def notes(self, *args):
        return run([sys.executable, str(BIN / "agentic.py"), "release-notes", *args], ROOT)

    def test_ac_006_notes_by_version(self):
        r = self.notes("2.8.1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "".join(f"- {n}\n" for n in upgrade.NOTES["2.8.1"]))
        for note in upgrade.NOTES["2.8.0"]:
            self.assertNotIn(note, r.stdout)
        version = json.loads((ROOT / PLUGIN).read_text(encoding="utf-8"))["version"]
        r = self.notes()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "".join(f"- {n}\n" for n in upgrade.NOTES[version]))
        r = self.notes("9.9.9")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no upgrade notes for 9.9.9", r.stderr)
        self.assertEqual(r.stdout, "")


class CommandTests(unittest.TestCase):
    def test_ac_007_usage_table_and_exemption(self):
        r = run([sys.executable, str(BIN / "agentic.py"), "flow-history", "extra"], ROOT)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Uso: flow-history [--check]", r.stderr)
        r = run([sys.executable, str(BIN / "agentic.py"), "flow-history", "--chek"], ROOT)
        self.assertEqual(r.returncode, 1, "a misspelt --check must not write the history")
        r = run([sys.executable, str(BIN / "agentic.py"), "release-notes", "a", "b"], ROOT)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Uso: release-notes [VERSION]", r.stderr)
        self.assertEqual(len(agentic.COMMANDS), 35)
        self.assertIn("release-notes", agentic.COMMANDS)
        self.assertRegex(agentic.__doc__, r"\n  release-notes")
        repo, other = FlowCopy(), FlowCopy()
        self.addCleanup(repo.cleanup)
        self.addCleanup(other.cleanup)
        repo.regenerate()
        env = clean_env(CLAUDE_PROJECT_DIR=str(other.dir))
        for args in (("release-notes", "2.8.1"), ("flow-history", "--check")):
            with self.subTest(args=args):
                r = repo.agentic(*args, env=env)
                self.assertNotIn("CLAUDE_PROJECT_DIR names", r.stderr)
                self.assertIn(r.returncode, (0, 3), r.stderr)


def block(text, header_re):
    """The lines from the first line matching header_re up to the next line at the same or a lower indentation."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if re.match(header_re, line))
    indent = len(lines[start]) - len(lines[start].lstrip())
    out = [lines[start]]
    for line in lines[start + 1:]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        out.append(line)
    return "\n".join(out)


def run_scripts(text):
    """The text of every run: step, its block lines included."""
    scripts, lines = [], text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(\s*)(?:- )?run:(.*)$", line)
        if m:
            scripts.append(block("\n".join(lines[i:]), r"^\s*(?:- )?run:"))
    return scripts


class WorkflowTests(unittest.TestCase):
    def test_ac_008_release_workflow(self):
        self.assertTrue(RELEASE_YML.exists())
        text = RELEASE_YML.read_text(encoding="utf-8")
        on = block(text, r"^on:")
        self.assertIn("workflow_dispatch", on)
        self.assertRegex(on, r"push:\s*\n\s+branches:\s*\[main\]")
        self.assertIn(".claude-plugin/plugin.json", on)
        for forbidden in ("pull_request", "schedule", "tags"):
            self.assertNotIn(forbidden, on)
        self.assertRegex(block(text, r"^permissions:"), r"permissions:\s*\n\s+contents: read\s*$")
        self.assertRegex(block(text, r"^jobs:"), r"permissions:\s*\n\s+contents: write")
        uses = re.findall(r"uses:\s*\S+@(\S+)", text)
        self.assertTrue(uses)
        for ref in uses:
            self.assertRegex(ref, r"^[0-9a-f]{40}$")
        for needle in ("fetch-depth: 0", "persist-credentials: false", "github.repository == 'jagosar/agentic-flow'",
                       "github.ref == 'refs/heads/main'", "agentic-flow--v", "GH_TOKEN"):
            self.assertIn(needle, text)
        order = [text.find(s) for s in ("already exists", "agentic.py flow-history --check",
                                        "agentic.py release-notes", "gh release create")]
        self.assertTrue(all(i >= 0 for i in order), order)
        self.assertEqual(order, sorted(order))
        self.assertNotIn("softprops", text)
        for script in run_scripts(text):
            self.assertNotIn("${{", script, "values reach scripts through env:, not ${{ }}")

    def test_ac_009_history_job(self):
        ci = CI_YML.read_text(encoding="utf-8")
        job = block(ci, r"^  history:")
        for needle in ("github.repository == 'jagosar/agentic-flow'", "fetch-depth: 0",
                       "persist-credentials: false", "agentic.py flow-history --check"):
            self.assertIn(needle, job)
        paths = re.findall(r"^\s*paths:\s*\[(.*)\]", ci, re.M)
        self.assertEqual(len(paths), 2)
        for line in paths:
            self.assertIn('".github/workflows/agentic-flow-release.yml"', line)
            self.assertIn('"bench/**"', line)
        for name in ("test", "installed", "plugin"):
            self.assertNotIn("fetch-depth", block(ci, rf"^  {name}:"))


def is_shallow():
    return run(["git", "rev-parse", "--is-shallow-repository"], ROOT).stdout.strip() != "false"


class ReleaseTests(unittest.TestCase):
    def test_ac_010_version_notes_and_history(self):
        self.assertEqual(json.loads((ROOT / PLUGIN).read_text(encoding="utf-8"))["version"], "2.9.0")
        notes = " ".join(upgrade.NOTES.get("2.9.0", []))
        self.assertIn("release-notes", notes)
        self.assertIn("flow-history --check", notes)
        self.assertFalse([g for g in upgrade.EXTRA_GLOBS if "release" in g])
        if is_shallow() or not agentic.is_flow_repo(ROOT):
            self.skipTest("needs a full clone of the agentic-flow repository")
        r = run([sys.executable, str(BIN / "agentic.py"), "flow-history", "--check"], ROOT)
        self.assertIn(r.returncode, (0, 3), r.stderr)
        self.assertEqual([m for m in json.loads(r.stdout)["missing"] if m["ref"] != "HEAD"], [])


class DocsTests(unittest.TestCase):
    def test_ac_011_ceremony(self):
        guide = (ROOT / "docs/how-to/plugin.md").read_text(encoding="utf-8")
        section = guide.split("## Publish a version (maintainers)", 1)[1].split("\n## ", 1)[0]
        for needle in ("upgrade.py", "agentic.py flow-history", "history", "agentic-flow-release", "Run workflow"):
            self.assertIn(needle, section)
        self.assertNotIn("claude plugin tag", section)
        self.assertNotRegex(section, r"(?i)create (the|a) release (by hand|in the GitHub UI)")
        r = run([sys.executable, str(BIN / "agentic.py"), "docs-check"], ROOT, clean_env(CLAUDE_PROJECT_DIR=str(ROOT)))
        problems = [p for p in json.loads(r.stdout)["broken"] if "plugin.md" in json.dumps(p)]
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
