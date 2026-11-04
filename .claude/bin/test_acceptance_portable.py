"""Acceptance tests of delivery A of the Windows design (portable internals, no visible change), AC-001..AC-012.

They run on every system of the CI matrix (Linux, Windows with Git for Windows); locally, on Linux.
Run: python3 -m unittest discover -s .claude/bin -p test_acceptance_portable.py
"""
import ast
import hashlib
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
SCRIPT = BIN / "agentic.py"
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.autocrlf=false"]
FLOW_MODULES = ["agentic.py", "upgrade.py", "pipeline.py", "brief.py", "compat.py", "core.py", "manifest_check.py",
                "repo_scan.py", "verification.py", "stage.py", "installer.py", "launch.py", "guardrail.py"]

def testutil():
    sys.path.insert(0, str(BIN))
    import testutil as module
    return module


def manifest(**extra):
    return dict({
        "allow_bash": ["Bash(python3 -m unittest:*)"],
        "acceptance": {"files": ["acceptance/"], "command": "faketool --ok"},
        "work_packages": [
            {"id": "WP-01", "wave": 1, "depends_on": [], "files": ["src/a.py"]},
            {"id": "WP-02", "wave": 1, "depends_on": [], "files": ["src/b.py"]},
        ]}, **extra)


class Project:
    """A temporary git repo with an architecture.md and the flow's workflows (the launcher's spec)."""

    def __init__(self, data, heading="# A"):
        self.dir = Path(tempfile.mkdtemp(prefix="portable-")).resolve()
        (self.dir / "architecture.md").write_text(
            f"{heading}\n\n```json wp-manifest\n{json.dumps(data, indent=2)}\n```\n", encoding="utf-8")
        shutil.copytree(ROOT / ".claude" / "workflows", self.dir / ".claude" / "workflows")
        shutil.copytree(ROOT / ".claude" / "agents", self.dir / ".claude" / "agents")
        shutil.copy(ROOT / ".claude" / "settings.json", self.dir / ".claude" / "settings.json")  # hooks-check reads it
        subprocess.run(["git", "init", "-q"], cwd=self.dir, check=True)
        # CLAUDECODE: inherited inside Claude Code, it would put hooks-check in live mode.
        self.env = {k: v for k, v in os.environ.items() if k not in ("AGENTIC_WP", "AGENTIC_CLAUDE", "CLAUDECODE")}
        self.env["CLAUDE_PROJECT_DIR"] = str(self.dir)

    def run(self, *args, stdin=None, env=None):
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=self.dir, input=stdin, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", env=dict(self.env, **(env or {})))

    def hook(self, payload, env=None):
        return self.run("hook", stdin=json.dumps(payload), env=env).returncode

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class Portable(unittest.TestCase):
    def project(self, data=None, **kw):
        p = Project(data or manifest(), **kw)
        self.addCleanup(p.cleanup)
        return p

    def tmpdir(self):
        d = Path(tempfile.mkdtemp(prefix="portable-")).resolve()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        return d

    def source(self, history):
        """A copy of this flow with a test-made flow-history.json."""
        src = self.tmpdir() / "source"
        for rel in (".claude/agents", ".claude/commands", ".claude/workflows", ".claude/rules-library"):
            shutil.copytree(ROOT / rel, src / rel)
        shutil.copytree(BIN, src / ".claude/bin", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy(ROOT / ".claude/settings.json", src / ".claude/settings.json")
        shutil.copytree(ROOT / ".claude-plugin", src / ".claude-plugin")
        (src / ".claude/flow-history.json").write_text(json.dumps({"generated_from": "test", "files": {
            rel: [hashlib.sha256(text.encode()).hexdigest()] for rel, text in history.items()}}), encoding="utf-8")
        return src

    def target(self, files):
        t = self.tmpdir() / "target"
        t.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=t, check=True)
        for rel, data in dict({"main.py": b"print(1)\n"}, **files).items():
            (t / rel).parent.mkdir(parents=True, exist_ok=True)
            (t / rel).write_bytes(data)
        subprocess.run(GIT + ["add", "-A"], cwd=t, check=True)
        subprocess.run(GIT + ["commit", "-qm", "old"], cwd=t, check=True, capture_output=True)
        return t

    def install(self, src, target):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
        return subprocess.run([sys.executable, str(src / ".claude/bin/agentic.py"), "install", str(target)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)

    @staticmethod
    def listed(out, kind):
        found, inside = [], False
        for line in out.splitlines():
            if line.strip().startswith(f"{kind}:"):
                inside = True
            elif inside and line.startswith("    "):
                found.append(line.strip())
            else:
                inside = False
        return found


class OsLayerTests(Portable):
    def test_ac_001_no_fcntl(self):
        data = self.tmpdir() / "data.json"
        code = ("import sys; from pathlib import Path; sys.modules['fcntl'] = None; "
                f"sys.path.insert(0, {str(BIN)!r}); import agentic; "
                "del sys.modules['fcntl']; "  # importing needs no fcntl; locking uses the system's own (compat.locked)
                f"agentic.locked_json(Path({str(data)!r}), lambda d: {{'a': 1}})")
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.tmpdir()))
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(data.read_text(encoding="utf-8")), {"a": 1})
        for name in FLOW_MODULES:
            if name == "compat.py":
                continue
            text = (BIN / name).read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"^\s*(?:import|from)\s+(?:fcntl|msvcrt)\b", text, re.M), name)

    def test_ac_002_resolve(self):
        p = self.project(manifest(verify={"tests": "faketool --ok"}))
        fake_bin = self.tmpdir()
        testutil().fake_exe(fake_bin, "faketool", "import sys\nsys.exit(0 if sys.argv[1:] == ['--ok'] else 1)\n")
        r = p.run("verify", env={"PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}"})
        out = json.loads(r.stdout.strip().splitlines()[-1])
        tests = next(ph for ph in out["phases"] if ph["name"] == "tests")
        self.assertTrue(tests["passed"], r.stdout + r.stderr)
        self.assertNotIn("command not found", r.stdout)

    def test_ac_003_utf8(self):
        p = self.project(heading="# Plan · € ñ")
        ascii_env = {"PYTHONIOENCODING": "ascii"}
        r = p.run("validate", env=ascii_env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(p.run("mark", "WP-01", "done", "nota · ñ").returncode, 0)
        r = p.run("status", env=ascii_env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("nota", r.stdout)
        self.assertNotIn("UnicodeEncodeError", r.stderr)
        self.assertNotIn("UnicodeDecodeError", r.stderr)

    def test_ac_004_encodings_declared(self):
        missing = []
        for name in FLOW_MODULES:
            path = BIN / name
            if not path.exists():
                missing.append(f"{name}: missing")
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                fname = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
                kws = {k.arg: k.value for k in node.keywords}
                if fname in ("open", "read_text", "write_text"):
                    mode = kws.get("mode")
                    if mode is None and fname == "open":
                        positional = node.args[1:2] if isinstance(func, ast.Name) else node.args[0:1]
                        mode = positional[0] if positional else None
                    binary = isinstance(mode, ast.Constant) and isinstance(mode.value, str) and "b" in mode.value
                    if "encoding" not in kws and not binary:
                        missing.append(f"{name}:{node.lineno} {fname}")
                elif fname in ("run", "Popen") and isinstance(func, ast.Attribute) and \
                        isinstance(func.value, ast.Name) and func.value.id == "subprocess":
                    text = kws.get("text")
                    if isinstance(text, ast.Constant) and text.value is True and "encoding" not in kws:
                        missing.append(f"{name}:{node.lineno} subprocess.{fname}")
        self.assertEqual(missing, [])


class HookTests(Portable):
    def test_ac_005_native_paths(self):
        p = self.project()
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(p.dir / "src" / "a.py")}}
        self.assertEqual(p.hook(payload, env={"AGENTIC_WP": "WP-01"}), 0)
        self.assertEqual(p.hook(payload, env={"AGENTIC_WP": "WP-02"}), 2)

    def test_ac_006_claims(self):
        p = self.project()
        self.assertEqual(p.run("snapshot", "1").returncode, 0)
        for command, agent in (("python3 .claude/bin/agentic.py claim WP-01", "a1"),
                               ("sh .claude/bin/agentic claim WP-02", "a2")):
            payload = {"tool_name": "Bash", "tool_input": {"command": command}, "agent_id": agent,
                       "agent_type": "implementer"}
            self.assertEqual(p.hook(payload), 0, command)
        claims = json.loads((p.dir / ".claude/state/claims.json").read_text(encoding="utf-8"))
        self.assertEqual(claims.get("a1"), "WP-01")
        self.assertEqual(claims.get("a2"), "WP-02")


class UpgradeTests(Portable):
    def test_ac_007_crlf_intact(self):
        rel = ".claude/agents/qa.md"
        src = self.source({rel: "OLD\n"})
        t = self.target({rel: b"OLD\r\n"})
        r = self.install(src, t)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(rel, self.listed(r.stdout, "updated"))
        self.assertNotIn(rel, self.listed(r.stdout, "modified by you (left alone)"))

    def test_ac_009_unreadable_ledger(self):
        src = self.source({})
        t = self.target({".claude/agents/qa.md": b"MINE\n"})
        (t / ".claude/state/ledger.json").mkdir(parents=True)
        before = sorted(p.relative_to(t).as_posix() for p in t.rglob("*") if ".git" not in p.parts)
        r = self.install(src, t)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("the run state cannot be read", r.stdout + r.stderr)
        after = sorted(p.relative_to(t).as_posix() for p in t.rglob("*") if ".git" not in p.parts)
        self.assertEqual(before, after)

    def test_ac_012_compat_installed(self):
        src = self.source({})
        t = self.target({})
        r = self.install(src, t)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((t / ".claude/bin/compat.py").is_file())
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(t))
        v = subprocess.run([sys.executable, str(t / ".claude/bin/agentic.py"), "validate"], cwd=t, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", env=env)
        self.assertNotIn("ModuleNotFoundError", v.stdout + v.stderr)


class LauncherTests(Portable):
    def test_ac_008_prompt_on_stdin(self):
        p = self.project()
        logs = self.tmpdir()
        r = p.run("run-wave", "1", env={"AGENTIC_CLAUDE": testutil().install_fake_claude(self.tmpdir()),
                                        "FAKE_LOG_DIR": str(logs)})
        calls = testutil().fake_calls(logs)
        self.assertEqual(sorted(c["id"] for c in calls), ["WP-01", "WP-02"], r.stdout + r.stderr)
        for call in calls:
            self.assertTrue(call["prompt"].startswith("Implement WP-0"), call["prompt"][:80])
            self.assertFalse(any("\n" in arg for arg in call["argv"]), call["argv"])
            self.assertIn("--json-schema", call["argv"])


class NoVisibleChangeTests(unittest.TestCase):
    def test_ac_010_no_visible_change(self):
        settings = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
        hooks = [(e.get("matcher"), h.get("command")) for e in settings["hooks"]["PreToolUse"] for h in e["hooks"]]
        # 2.5.0 moved the hook behind the launcher hook.py (maintainer mode); the matcher and python3 stay.
        self.assertIn(("Write|Edit|MultiEdit|NotebookEdit|Bash|StructuredOutput", 'python3 "$CLAUDE_PROJECT_DIR/.claude/bin/hook.py"'),
                      hooks)
        self.assertIn("Bash(python3 .claude/bin/agentic.py:*)", settings["permissions"]["allow"])
        workflow = (ROOT / ".claude/workflows/agentic-implement.js").read_text(encoding="utf-8")
        implementer = (ROOT / ".claude/agents/implementer.md").read_text(encoding="utf-8")
        self.assertIn("python3 .claude/bin/agentic.py", workflow)
        self.assertIn("python3 .claude/bin/agentic.py claim <WP-ID>", implementer)
        for text in (json.dumps(settings), workflow, implementer):
            self.assertNotIn("sh .claude/bin/agentic", text)


class CiTests(unittest.TestCase):
    def test_ac_011_ci_matrix(self):
        ci = (ROOT / ".github/workflows/agentic-flow-ci.yml").read_text(encoding="utf-8")
        self.assertRegex(ci, r"runs-on:\s*\$\{\{\s*matrix\.os\s*\}\}")
        # 2.7.1 dropped macOS from the matrix: nobody uses it, and its scarce runners queued past the time limit.
        for os_name in ("ubuntu-latest", "windows-latest"):
            self.assertIn(os_name, ci)
        for version in ('"3.9"', '"3.12"', '"3.14"'):
            self.assertIn(version, ci)
        self.assertRegex(ci, r"shell:\s*bash")


if __name__ == "__main__":
    unittest.main()
