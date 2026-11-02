"""Acceptance tests of the safe upgrade (design "safe upgrades of repos on an older flow", AC-001..AC-010).

Each test builds a *source* (a copy of this flow with a test-made history) and a *target* (a git repo with an older
flow) and runs the source's installer on the target. They never read this repo's git history (CI clones are shallow).
Run: python3 -m unittest discover -s .claude/bin -p test_acceptance_upgrade.py
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def write(root, files):
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def commit(root, message="c"):
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(GIT + ["commit", "-qm", message], cwd=root, check=True, capture_output=True)


class Upgrade(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="upgrade-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.src = self.make_source()
        self.env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}

    def make_source(self, history=None):
        src = self.tmp / "source"
        for rel in (".claude/agents", ".claude/commands", ".claude/workflows", ".claude/rules-library", "plugin/commands",
                    ".github/workflows"):
            shutil.copytree(ROOT / rel, src / rel, dirs_exist_ok=True)
        shutil.copytree(ROOT / ".claude/bin", src / ".claude/bin", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy(ROOT / ".claude/settings.json", src / ".claude/settings.json")
        plugin = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        write(src, {".claude-plugin/plugin.json": json.dumps(dict(plugin, version="1.1.0"))})
        self.history(src, history or {})
        return src

    def history(self, src, files):
        write(src, {".claude/flow-history.json": json.dumps(
            {"generated_from": "test", "files": {k: sorted(sha(t) for t in v) for k, v in files.items()}})})

    def target(self, files, name="target"):
        t = self.tmp / name
        t.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=t, check=True)
        write(t, dict({"main.py": "print(1)\n"}, **files))
        commit(t, "old flow")
        return t

    def install(self, target, *flags, src=None):
        return subprocess.run([sys.executable, str((src or self.src) / ".claude/bin/agentic.py"), "install",
                               str(target), *flags], capture_output=True, text=True, env=self.env, encoding="utf-8", errors="replace")

    @staticmethod
    def listed(out, kind):
        """The paths the installer lists under `<kind>: N`."""
        lines, found, inside = out.splitlines(), [], False
        for line in lines:
            if line.strip().startswith(f"{kind}:"):
                inside = True
            elif inside and line.startswith("    "):
                found.append(line.strip())
            else:
                inside = False
        return found

    def same_as_source(self, target, rel):
        return (target / rel).read_bytes() == (self.src / rel).read_bytes()


class IntactAndEditedTests(Upgrade):
    def test_ac_001_intact_without_record(self):
        self.history(self.src, {".claude/agents/implementer.md": ["OLD IMPLEMENTER\n"]})
        t = self.target({".claude/agents/implementer.md": "OLD IMPLEMENTER\n"})
        r = self.install(t)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(self.same_as_source(t, ".claude/agents/implementer.md"))
        self.assertIn(".claude/agents/implementer.md", self.listed(r.stdout, "updated"))
        self.assertNotIn(".claude/agents/implementer.md", self.listed(r.stdout, "modified by you (left alone)"))
        self.assertEqual(json.loads((t / ".claude/agentic-install.json").read_text(encoding="utf-8"))["version"], "1.1.0")

    def test_ac_002_edited_file_kept(self):
        t = self.target({".claude/agents/qa.md": "MY OWN QA\n"})
        r = self.install(t)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((t / ".claude/agents/qa.md").read_text(encoding="utf-8"), "MY OWN QA\n")
        copy = t / ".claude/state/upgrade/.claude/agents/qa.md"
        self.assertEqual(copy.read_bytes(), (self.src / ".claude/agents/qa.md").read_bytes())
        self.assertIn(".claude/agents/qa.md", self.listed(r.stdout, "modified by you (left alone)"))
        self.assertIn("kept files: new versions in .claude/state/upgrade/", r.stdout)
        dry = self.target({".claude/agents/qa.md": "MY OWN QA\n"}, "dry")
        self.assertEqual(self.install(dry, "--dry-run").returncode, 0)
        self.assertFalse((dry / ".claude/state/upgrade").exists())

    def test_ac_003_template_leftovers(self):
        self.history(self.src, {".claude/bin/test_agentic.py": ["OLD TESTS\n"]})
        t = self.target({".claude/bin/test_agentic.py": "OLD TESTS\n", ".claude/bin/test_brief.py": "MINE\n"})
        r = self.install(t)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(self.same_as_source(t, ".claude/bin/test_agentic.py"))
        self.assertEqual((t / ".claude/bin/test_brief.py").read_text(encoding="utf-8"), "MINE\n")
        self.assertTrue((t / ".claude/state/upgrade/.claude/bin/test_brief.py").exists())
        self.assertTrue((self.src / ".github/workflows/agentic-flow-ci.yml").exists(), "the source ships it")
        self.assertFalse((t / ".github/workflows/agentic-flow-ci.yml").exists(), "never added where absent")
        self.assertTrue(self.same_as_source(t, ".claude/bin/conformance.json"), "a partial test suite is completed")

    def test_ac_004_removed_only_if_intact(self):
        self.history(self.src, {".claude/workflows/agentic-wave.js": ["OLD WAVE\n"], ".claude/commands/qa.md": ["OLD QA CMD\n"]})
        t = self.target({".claude/workflows/agentic-wave.js": "OLD WAVE\n", ".claude/commands/qa.md": "USER QA CMD\n"})
        r = self.install(t)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((t / ".claude/workflows/agentic-wave.js").exists())
        self.assertIn(".claude/workflows/agentic-wave.js", self.listed(r.stdout, "removed"))
        self.assertEqual((t / ".claude/commands/qa.md").read_text(encoding="utf-8"), "USER QA CMD\n")
        self.assertNotIn(".claude/commands/qa.md", self.listed(r.stdout, "removed"))


class GuardTests(Upgrade):
    def dirty_target(self, name):
        self.history(self.src, {".claude/agents/implementer.md": ["OLD IMPLEMENTER\n"]})
        t = self.target({".claude/agents/implementer.md": "OLD IMPLEMENTER\n"}, name)
        (t / ".claude/agents/implementer.md").write_text("EDITED\n", encoding="utf-8")
        return t

    def test_ac_005_dirty_and_not_git(self):
        t = self.dirty_target("dirty")
        r = self.install(t)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("uncommitted: .claude/agents/implementer.md", r.stderr)
        self.assertFalse((t / ".claude/agentic-install.json").exists())
        self.assertFalse((t / ".claude/bin/agentic.py").exists(), "nothing is written before refusing")
        self.assertEqual((t / ".claude/agents/implementer.md").read_text(encoding="utf-8"), "EDITED\n")
        self.assertEqual(self.install(t, "--allow-dirty").returncode, 0)
        dry = self.dirty_target("dry")
        r = self.install(dry, "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("warning: uncommitted: .claude/agents/implementer.md", r.stdout)
        plain = self.tmp / "plain"
        plain.mkdir()
        r = self.install(plain)
        self.assertEqual(r.returncode, 1)
        self.assertIn("not a git repository", r.stderr)

    def test_ac_006_run_in_progress(self):
        t = self.target({})
        ledger = t / ".claude/state/ledger.json"
        write(t, {".claude/state/ledger.json": json.dumps({"_stages": {"1": "OK"}, "WP-01": {"state": "running"}})})
        for flags in ((), ("--allow-dirty",)):
            r = self.install(t, *flags)
            self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
            self.assertIn("a run is in progress (WP-01)", r.stderr)
            self.assertIn("agentic.py stop", r.stderr)
        ledger.write_text(json.dumps({"WP-01": {"state": "stopped"}}), encoding="utf-8")
        self.assertEqual(self.install(t).returncode, 0)


class VersionTests(Upgrade):
    def first_line(self, record_version):
        # With no record, an old flow file stands for a repo created from the template.
        files = {".claude/agents/qa.md": "OLD QA\n"} if record_version is None else {
            ".claude/agentic-install.json": json.dumps({"version": record_version, "files": {}})}
        t = self.target(files, f"v-{record_version}")
        r = self.install(t)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout.splitlines()[0], r.stdout

    def test_ac_007_versions_and_notes(self):
        line, out = self.first_line("1.0.0")
        self.assertTrue(line.startswith("agentic-flow 1.0.0 -> 1.1.0 -> "), line)
        self.assertIn("upgrade notes:", out)
        self.assertIn("wave-plan", out)
        line, out = self.first_line("1.1.0")
        self.assertTrue(line.startswith("agentic-flow 1.1.0 -> 1.1.0 -> "), line)
        self.assertNotIn("upgrade notes:", out)
        line, out = self.first_line(None)
        self.assertTrue(line.startswith("agentic-flow unknown -> 1.1.0 -> "), line)
        self.assertIn("upgrade notes:", out)

    def test_ac_009_validate_after(self):
        bad = "```json wp-manifest\n" + json.dumps({"work_packages": []}) + "\n```\n"
        t = self.target({"architecture.md": bad}, "bad-plan")
        r = self.install(t)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("validate: FAILED:", r.stdout)
        self.assertLess(r.stdout.index("validate: FAILED:"), r.stdout.index("RESULT: OK"))
        good = "```json wp-manifest\n" + json.dumps({"work_packages": [{"id": "WP-01", "wave": 1, "files": ["src/a.py"]}]}) + "\n```\n"
        t = self.target({"architecture.md": good}, "good-plan")
        r = self.install(t)
        self.assertIn("validate: OK", r.stdout, r.stdout + r.stderr)


class FlowHistoryTests(Upgrade):
    def test_ac_008_flow_history(self):
        src = self.src
        (src / ".claude/flow-history.json").unlink()
        subprocess.run(["git", "init", "-q"], cwd=src, check=True)
        write(src, {".claude/agents/qa.md": "A\n", "README.md": "readme\n"})
        commit(src, "a")
        write(src, {".claude/agents/qa.md": "B\n", ".claude/workflows/old.js": "X\n"})
        commit(src, "b")
        (src / ".claude/workflows/old.js").unlink()
        commit(src, "c")
        r = subprocess.run([sys.executable, str(src / ".claude/bin/agentic.py"), "flow-history"], cwd=src,
                           capture_output=True, text=True, env=self.env, encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        summary = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertIn("paths", summary)
        self.assertIn("hashes", summary)
        data = json.loads((src / ".claude/flow-history.json").read_text(encoding="utf-8"))
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=src, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
        self.assertEqual(data["generated_from"], head)
        self.assertTrue({sha("A\n"), sha("B\n")} <= set(data["files"][".claude/agents/qa.md"]))
        self.assertIn(sha("X\n"), data["files"][".claude/workflows/old.js"])
        self.assertNotIn("README.md", data["files"])
        clone = self.tmp / "shallow"
        subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{src}", str(clone)], check=True, capture_output=True)
        r = subprocess.run([sys.executable, str(clone / ".claude/bin/agentic.py"), "flow-history"], cwd=clone,
                           capture_output=True, text=True, env=self.env, encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 1)
        self.assertIn("needs the full git history", r.stderr)


class DocsTests(unittest.TestCase):
    @staticmethod
    def section(text, heading):
        start = text.index(heading)
        end = text.find("\n## ", start + len(heading))
        return text[start:] if end == -1 else text[start:end]

    def test_ac_010_docs(self):
        init = (ROOT / "plugin/commands/init.md").read_text(encoding="utf-8")
        self.assertIn("--allow-dirty", init.splitlines()[2], "argument-hint")
        for token in ("--allow-dirty", ".claude/state/upgrade/", "3"):
            self.assertIn(token, init)
        guide = (ROOT / "docs/how-to/plugin.md").read_text(encoding="utf-8")
        update = self.section(guide, "## Update")
        for token in (".claude/state/upgrade/", "--allow-dirty", "template"):
            self.assertIn(token, update)
        self.assertIn("flow-history", self.section(guide, "## Publish a version (maintainers)"))
        self.assertEqual(json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))["version"], "2.4.0")


if __name__ == "__main__":
    unittest.main()
