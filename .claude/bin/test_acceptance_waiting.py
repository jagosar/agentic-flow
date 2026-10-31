"""Acceptance tests of the waiting notice (design "notice of agents waiting for a permission or an answer", AC-001..AC-007).

Each test runs the real waiting.py hook (stdin JSON) and agentic.py against a temporary git repo.
Run: python3 -m unittest discover -s .claude/bin -p test_acceptance_waiting.py
"""
import ast
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
AGENTIC = BIN / "agentic.py"
WAITING = BIN / "waiting.py"
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
MANIFEST = {"acceptance": {"files": ["acceptance/"], "command": "python3 -m unittest discover -s acceptance"},
            "work_packages": [{"id": "WP-01", "wave": 1, "depends_on": [], "files": ["src/a.py"]}]}
LINE = re.compile(r"^- WP-01 \(implementer\) needs your permission for Bash: npm run e2e — waiting 0 min \(since \d\d:\d\d\)$",
                  re.M)


def permission(agent_id, agent_type="implementer", tool="Bash", tool_input=None):
    return {"hook_event_name": "PermissionRequest", "session_id": "s", "agent_id": agent_id, "agent_type": agent_type,
            "tool_name": tool, "tool_input": {"command": "npm run e2e"} if tool_input is None else tool_input}


def event(name, agent_id):
    return {"hook_event_name": name, "session_id": "s", "agent_id": agent_id, "tool_name": "Bash"}


class Waiting(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="waiting-")).resolve()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        (self.dir / "architecture.md").write_text(f"# A\n\n```json wp-manifest\n{json.dumps(MANIFEST)}\n```\n",
                                                  encoding="utf-8")
        for rel in (".claude/workflows", ".claude/agents"):
            shutil.copytree(ROOT / rel, self.dir / rel)
        subprocess.run(["git", "init", "-q"], cwd=self.dir, check=True)
        self.env = {k: v for k, v in os.environ.items() if k not in ("AGENTIC_WP", "AGENTIC_CLAUDE")}
        self.env["CLAUDE_PROJECT_DIR"] = str(self.dir)

    def hook(self, payload):
        stdin = payload if isinstance(payload, str) else json.dumps(payload)
        return subprocess.run([sys.executable, str(WAITING)], cwd=self.dir, input=stdin, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=self.env)

    def agentic(self, *args):
        return subprocess.run([sys.executable, str(AGENTIC), *args], cwd=self.dir, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=self.env)

    def status(self):
        r = self.agentic("status")
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def claim(self, agent_id, ident):
        state = self.dir / ".claude/state"
        state.mkdir(parents=True, exist_ok=True)
        claims = state / "claims.json"
        data = json.loads(claims.read_text(encoding="utf-8")) if claims.exists() else {}
        claims.write_text(json.dumps(dict(data, **{agent_id: ident})), encoding="utf-8")

    @staticmethod
    def section(text):
        """The lines under '## Waiting for you', or None when the section is absent."""
        if "## Waiting for you" not in text:
            return None
        body = text.split("## Waiting for you", 1)[1].split("\n## ", 1)[0]
        return [line for line in body.splitlines() if line.startswith("- ")]


class ShownTests(Waiting):
    def test_ac_001_permission_shown(self):
        self.claim("ag1", "WP-01")
        r = self.hook(permission("ag1"))
        self.assertEqual((r.returncode, r.stdout), (0, ""), r.stderr)
        out = self.status()
        self.assertIsNotNone(self.section(out))
        self.assertLess(out.index("## Waiting for you"), out.index("## Stages"))
        self.assertRegex(out, LINE)

    def test_ac_002_cleared(self):
        self.claim("ag1", "WP-01")
        for ending in ("PostToolUse", "PostToolUseFailure", "SubagentStop"):
            with self.subTest(ending=ending):
                self.hook(permission("ag1"))
                self.hook(permission("ag2", agent_type="qa"))
                self.assertEqual(self.hook(event(ending, "ag1")).returncode, 0)
                lines = self.section(self.status())
                self.assertEqual(len(lines or []), 1, "only ag2 is still waiting")
                self.assertIn("qa agent", lines[0])
                self.hook(event(ending, "ag2"))
                self.assertIsNone(self.section(self.status()))

    def test_ac_003_kinds(self):
        self.hook(permission("q1", agent_type="qa", tool="AskUserQuestion", tool_input={"questions": []}))
        self.hook(permission("x1", tool="WebFetch", tool_input={"url": "https://example.com"}))
        main = permission("ignored")
        del main["agent_id"]
        self.hook(main)
        lines = self.section(self.status())
        self.assertEqual(len(lines), 2, lines)
        self.assertTrue(any("qa agent has a question for you" in line for line in lines), lines)
        self.assertTrue(any("implementer agent needs your permission for WebFetch: https://example.com" in line
                            for line in lines), lines)


class RobustTests(Waiting):
    def test_ac_004_never_blocks(self):
        r = self.hook(event("PostToolUse", "a"))
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertFalse((self.dir / ".claude/state").exists(), "a removal creates nothing")
        for payload in ("not json", permission("b", tool_input="a string")):
            with self.subTest(payload=str(payload)[:20]):
                r = self.hook(payload)
                self.assertEqual((r.returncode, r.stdout), (0, ""))
        tree = ast.parse(WAITING.read_text(encoding="utf-8"))
        imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        imported |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        self.assertFalse(imported & {"agentic", "pipeline", "brief", "upgrade"}, imported)

    def test_ac_005_stage_resets(self):
        self.claim("ag1", "WP-01")
        self.hook(permission("ag1"))
        self.assertIsNotNone(self.section(self.status()))
        self.assertEqual(self.agentic("snapshot", "1").returncode, 0)
        self.assertIsNone(self.section(self.status()))


class InstallTests(unittest.TestCase):
    def test_ac_006_install(self):
        target = Path(tempfile.mkdtemp(prefix="waiting-install-")).resolve()
        self.addCleanup(shutil.rmtree, target, ignore_errors=True)
        subprocess.run(["git", "init", "-q"], cwd=target, check=True)
        (target / ".claude").mkdir()
        mine = {"matcher": "Write", "hooks": [{"type": "command", "command": "echo mine"}]}
        (target / ".claude/settings.json").write_text(json.dumps({"hooks": {"PostToolUse": [mine]}}), encoding="utf-8")
        (target / "main.py").write_text("print(1)\n", encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}

        def install():
            r = subprocess.run([sys.executable, str(AGENTIC), "install", str(target)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", env=env)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            subprocess.run(["git", "add", "-A"], cwd=target, check=True)
            subprocess.run(GIT + ["commit", "-qm", "i", "--allow-empty"], cwd=target, check=True)
            return r.stdout

        def ours(settings, ev):
            return [h for e in settings["hooks"].get(ev, []) for h in e.get("hooks", []) if "waiting.py" in h.get("command", "")]

        subprocess.run(["git", "add", "-A"], cwd=target, check=True)
        subprocess.run(GIT + ["commit", "-qm", "base"], cwd=target, check=True)
        first = install()
        settings = json.loads((target / ".claude/settings.json").read_text(encoding="utf-8"))
        for ev in ("PermissionRequest", "PostToolUse", "PostToolUseFailure", "SubagentStop"):
            self.assertEqual(len(ours(settings, ev)), 1, ev)
        self.assertIn(mine, settings["hooks"]["PostToolUse"], "the project's own hook is kept")
        self.assertIn("hook PermissionRequest", first)
        self.assertTrue((target / ".claude/bin/waiting.py").is_file())
        second = install()
        settings = json.loads((target / ".claude/settings.json").read_text(encoding="utf-8"))
        for ev in ("PermissionRequest", "PostToolUse", "PostToolUseFailure", "SubagentStop"):
            self.assertEqual(len(ours(settings, ev)), 1, f"{ev} after a second install")
        self.assertNotIn("hook PermissionRequest", second)


class ValidateTests(unittest.TestCase):
    def errors(self, **fields):
        sys.path.insert(0, str(BIN))
        import agentic
        return agentic.validate(dict(MANIFEST, **fields))

    def test_ac_007_glob_arguments(self):
        good = self.errors(verify={"tests": "python3 -m unittest discover -s .claude/bin -p test_*.py"},
                           acceptance={"files": ["acceptance/"], "command": "python3 -m pytest tests/*_acceptance.py"})
        self.assertEqual(good, [])
        for cmd in ("python3", "bash", "*", "bash -c *", "python3 -c *", "npm *"):
            with self.subTest(cmd=cmd):
                self.assertTrue(any("too broad" in e for e in self.errors(verify={"tests": cmd})), cmd)
        self.assertTrue(self.errors(allow_bash=["Bash(npm:*)"]), "allow_bash keeps its rule")


if __name__ == "__main__":
    unittest.main()
