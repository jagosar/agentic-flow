"""Acceptance tests of agentic-flow 2.5.0: AC-001 .. AC-009 of docs/architecture/0012 (maintainer mode).

Run: python3 -m unittest discover -s .claude/bin -p test_acceptance_v25.py
Temporary repos stand in for the flow's own repo (plugin.json named agentic-flow, the template marker on README line 1)
and carry a copy of this tree's .claude/bin, so the guard can be frozen and the launcher run there. Nothing is spent.
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

BIN = Path(__file__).resolve().parent
ROOT = BIN.parents[1]
sys.path.insert(0, str(BIN))
import upgrade  # noqa: E402
from test_pipeline import CONFORMANCE, run_scenario  # noqa: E402

MARKER = "<!-- agentic-flow-template -->"
GUARD_CMD = "python3 .claude/state/guard/bin/agentic.py"
LIVE_CMD = "python3 .claude/bin/agentic.py"
NEVER = [".claude/settings.json", ".claude/settings.local.json", ".claude/state/x", ".claude/bin/hook.py",
         ".claude/bin/waiting.py", ".claude/", ".claude/bin/"]
FROZEN_NAMES = sorted(p.name for p in BIN.glob("*.py") if not p.name.startswith("test_") and p.name != "testutil.py")


def manifest(maintainer=None, wp_files=(".claude/bin/x.py", "src/a.py")):
    m = {"stack": ["python"], "allow_bash": ["Bash(python3 -m unittest:*)"],
         "acceptance": {"files": ["acceptance/"], "command": f"{sys.executable} acc.py"},
         "work_packages": [{"id": "WP-01", "wave": 1, "depends_on": [], "files": list(wp_files), "acs": ["AC-001"]},
                           {"id": "WP-02", "wave": 1, "depends_on": [], "files": ["src/b.py"], "acs": ["AC-002"]}]}
    if maintainer is not None:
        m["maintainer"] = maintainer
    return m


class FlowRepo:
    """A temp repo with a copy of this tree's flow scripts; optionally made to look like the flow's own repo."""

    def __init__(self, data, flow_repo=True):
        self.dir = Path(tempfile.mkdtemp(prefix="maint-")).resolve()
        shutil.copytree(ROOT / ".claude" / "agents", self.dir / ".claude" / "agents")
        shutil.copytree(ROOT / ".claude" / "workflows", self.dir / ".claude" / "workflows")
        shutil.copy(ROOT / ".claude" / "settings.json", self.dir / ".claude" / "settings.json")
        (self.dir / ".claude" / "bin").mkdir(parents=True)
        for p in BIN.glob("*.py"):
            shutil.copy(p, self.dir / ".claude" / "bin" / p.name)
        (self.dir / ".claude-plugin").mkdir()
        (self.dir / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "agentic-flow"}), encoding="utf-8")
        (self.dir / "README.md").write_text((MARKER + "\n" if flow_repo else "") + "# x\n", encoding="utf-8")
        self.write_plan(data)
        for rel in ("src/a.py", "src/b.py", ".claude/bin/x.py"):
            self.write(rel, "x = 1\n")
        subprocess.run(["git", "init", "-q"], cwd=self.dir, check=True)
        subprocess.run(["git", "add", "-A"], cwd=self.dir, check=True)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"], cwd=self.dir,
                       check=True)
        self.env = {k: v for k, v in os.environ.items() if k not in ("AGENTIC_WP", "AGENTIC_CLAUDE", "CLAUDECODE")}
        self.env["CLAUDE_PROJECT_DIR"] = str(self.dir)

    def write_plan(self, data):
        (self.dir / "architecture.md").write_text(f"# A\n\n```json wp-manifest\n{json.dumps(data, indent=2)}\n```\n",
                                                  encoding="utf-8")

    def write(self, rel, text):
        p = self.dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def run(self, *args, script=None, stdin=None, env=None):
        script = script or self.dir / ".claude" / "bin" / "agentic.py"
        return subprocess.run([sys.executable, str(script), *args], cwd=self.dir, input=stdin, capture_output=True,
                              text=True, env=dict(self.env, **(env or {})), encoding="utf-8", errors="replace")

    def hook(self, payload, wp=None, launcher=False):
        script = self.dir / ".claude" / "bin" / ("hook.py" if launcher else "agentic.py")
        args = () if launcher else ("hook",)
        return self.run(*args, script=script, stdin=json.dumps(payload), env={"AGENTIC_WP": wp} if wp else None)

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def write_payload(rel):
    return {"tool_name": "Write", "tool_input": {"file_path": rel, "content": "y = 2\n"}}


def plan_line(r):
    lines = [line for line in r.stdout.splitlines() if line.strip()]
    return lines, (json.loads(lines[-1]) if lines else None)


class Case(unittest.TestCase):
    def repo(self, data, flow_repo=True):
        r = FlowRepo(data, flow_repo)
        self.addCleanup(r.cleanup)
        return r


class ValidateTests(Case):
    def test_ac_001_accepted_in_the_flow_repo(self):
        r = self.repo(manifest(True)).run("validate")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_ac_001_refused_elsewhere(self):
        r = self.repo(manifest(True), flow_repo=False).run("validate")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("only for the agentic-flow repository", r.stderr + r.stdout)

    def test_ac_001_without_the_flag_nothing_changes(self):
        for flow in (True, False):
            with self.subTest(flow_repo=flow):
                r = self.repo(manifest(), flow_repo=flow).run("validate")
                self.assertIn("cannot own '.claude/bin/x.py'", r.stderr + r.stdout)

    def test_ac_001_flag_must_be_boolean(self):
        r = self.repo(manifest("yes")).run("validate")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("maintainer", r.stderr + r.stdout)


class NeverOwnedTests(Case):
    def test_ac_002_never_owned_paths_are_refused(self):
        for path in NEVER:
            with self.subTest(path=path):
                r = self.repo(manifest(True, wp_files=(path,))).run("validate")
                self.assertNotEqual(r.returncode, 0, r.stdout)
                out = r.stderr + r.stdout
                self.assertTrue(any(n in out for n in (".claude/settings.json", ".claude/settings.local.json",
                                                       ".claude/state/", ".claude/bin/hook.py",
                                                       ".claude/bin/waiting.py")), out)

    def test_ac_002_plan_and_archive_stay_refused(self):
        for path in ("architecture.md", "docs/architecture/x.md"):
            with self.subTest(path=path):
                r = self.repo(manifest(True, wp_files=(path,))).run("validate")
                self.assertIn(f"cannot own '{path}'", r.stderr + r.stdout)


class FreezeTests(Case):
    def guard(self, repo):
        return repo.dir / ".claude" / "state" / "guard"

    def test_ac_003_maintainer_plan_freezes_the_guard(self):
        repo = self.repo(manifest(True))
        r = repo.run("pipeline-plan")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lines, plan = plan_line(r)
        self.assertEqual(len(lines), 1, r.stdout)
        self.assertIs(plan["maintainer"], True)
        self.assertEqual(plan["agentic"], GUARD_CMD)
        guard = self.guard(repo)
        self.assertEqual(sorted(p.name for p in (guard / "bin").glob("*.py")), sorted(FROZEN_NAMES + ["x.py"]))
        self.assertTrue((guard / "workflows" / "pipeline-spec.json").is_file())
        active = json.loads((guard / "active.json").read_text(encoding="utf-8"))
        digest = hashlib.sha256((guard / "bin" / "agentic.py").read_bytes()).hexdigest()
        self.assertEqual(active["files"]["bin/agentic.py"], digest)

    def test_ac_003_keep_guard_does_not_refreeze(self):
        repo = self.repo(manifest(True))
        repo.run("pipeline-plan")
        before = (self.guard(repo) / "active.json").read_text(encoding="utf-8")
        live = repo.dir / ".claude" / "bin" / "agentic.py"
        live.write_text(live.read_text(encoding="utf-8") + "\n# changed by an agent\n", encoding="utf-8")
        r = repo.run("pipeline-plan", "--keep-guard")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.guard(repo) / "active.json").read_text(encoding="utf-8"), before)
        self.assertNotIn("changed by an agent", (self.guard(repo) / "bin" / "agentic.py").read_text(encoding="utf-8"))

    def test_ac_003_a_normal_plan_releases_a_leftover_guard(self):
        repo = self.repo(manifest(True))
        repo.run("pipeline-plan")
        repo.write_plan({**manifest(), "work_packages": [
            {"id": "WP-01", "wave": 1, "depends_on": [], "files": ["src/a.py"], "acs": ["AC-001"]}]})
        r = repo.run("pipeline-plan")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        _, plan = plan_line(r)
        self.assertIs(plan["maintainer"], False)
        self.assertEqual(plan["agentic"], LIVE_CMD)
        self.assertFalse((self.guard(repo) / "active.json").exists())


PERMISSIVE = "def guard(data):\n    return\n"


class HookTests(Case):
    def test_ac_004_the_frozen_guard_decides_while_active(self):
        repo = self.repo(manifest(True))
        self.assertEqual(repo.run("pipeline-plan").returncode, 0)
        live = repo.dir / ".claude" / "bin" / "agentic.py"
        text = live.read_text(encoding="utf-8")
        self.assertIn("def guard(data):\n", text)
        live.write_text(text.replace("def guard(data):\n", PERMISSIVE + "\n\ndef _old_guard(data):\n", 1),
                        encoding="utf-8")
        blocked = repo.hook(write_payload("src/b.py"), wp="WP-01", launcher=True)
        self.assertEqual(blocked.returncode, 2, blocked.stdout + blocked.stderr)
        self.assertEqual(repo.run("guard-release").returncode, 0)
        allowed = repo.hook(write_payload("src/b.py"), wp="WP-01", launcher=True)
        self.assertEqual(allowed.returncode, 0, allowed.stdout + allowed.stderr)

    def test_ac_004_without_a_guard_the_launcher_runs_the_live_hook(self):
        repo = self.repo(manifest())
        r = repo.hook(write_payload("src/b.py"), wp="WP-01", launcher=True)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(repo.hook(write_payload("src/a.py"), wp="WP-01", launcher=True).returncode, 0)


class OwnershipTests(Case):
    def test_ac_005_owned_flow_paths_in_maintainer_mode(self):
        repo = self.repo(manifest(True))
        self.assertEqual(repo.hook(write_payload(".claude/bin/x.py"), wp="WP-01").returncode, 0)
        r = repo.hook(write_payload(".claude/settings.json"), wp="WP-01")
        self.assertEqual(r.returncode, 2)
        self.assertIn(".claude/settings.json", r.stderr + r.stdout)

    def test_ac_005_without_the_flag_both_are_blocked(self):
        repo = self.repo(manifest())
        for rel in (".claude/bin/x.py", ".claude/settings.json"):
            with self.subTest(rel=rel):
                self.assertEqual(repo.hook(write_payload(rel), wp="WP-01").returncode, 2)

    def test_ac_005_close_stage_accepts_an_owned_flow_path(self):
        repo = self.repo(manifest(True))
        self.assertEqual(repo.run("open-stage", "1").returncode, 0)
        repo.hook({"tool_name": "Bash", "tool_input": {"command": "true"}}, wp="WP-01")
        repo.write(".claude/bin/x.py", "x = 2\n")
        r = repo.run("close-stage", "1", "WP-01=done", "WP-02=done")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class FrozenCopyTests(Case):
    def test_ac_006_frozen_copy_finds_the_repo_and_keeps_its_spec(self):
        repo = self.repo(manifest(True))
        self.assertEqual(repo.run("pipeline-plan").returncode, 0)
        spec = repo.dir / ".claude" / "workflows" / "pipeline-spec.json"
        data = json.loads(spec.read_text(encoding="utf-8"))
        frozen_fix = data["prompts"]["fix"]
        data["prompts"]["fix"] = "CHANGED BY AN AGENT"
        spec.write_text(json.dumps(data), encoding="utf-8")
        frozen = repo.dir / ".claude" / "state" / "guard" / "bin" / "agentic.py"
        env = {k: v for k, v in repo.env.items() if k != "CLAUDE_PROJECT_DIR"}
        r = subprocess.run([sys.executable, str(frozen), "validate"], cwd=repo.dir, env=env, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        code = ("import importlib.util, json, sys\n"
                "s = importlib.util.spec_from_file_location('frozen_agentic', sys.argv[1])\n"
                "m = importlib.util.module_from_spec(s); s.loader.exec_module(m)\n"
                "print(json.dumps(m.load_spec()['prompts']['fix']))\n")
        r = subprocess.run([sys.executable, "-c", code, str(frozen)], cwd=repo.dir, env=env, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout.strip().splitlines()[-1]), frozen_fix)


class EnginesTests(unittest.TestCase):
    SCENARIOS = ("maintainer run uses the frozen guard", "maintainer run whose briefs fail still releases the guard",
                 "a resumed maintainer run keeps the guard", "happy path")

    @classmethod
    def setUpClass(cls):
        cls.by_name = {d["name"]: d for d in CONFORMANCE["scenarios"]}
        cls.node = None
        if shutil.which("node"):
            r = subprocess.run(["node", str(BIN / "test_workflow.mjs"), "--dump"], capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            cls.node = json.loads(r.stdout) if r.returncode == 0 else {"_error": r.stdout + r.stderr}

    def summary(self, name):
        self.assertIn(name, self.by_name)
        return run_scenario(self.by_name[name])

    def test_ac_007_maintainer_run(self):
        s = self.summary(self.SCENARIOS[0])
        self.assertEqual(s["gate_prefixes"], [GUARD_CMD])
        self.assertEqual(s["gates"][-1], "guard-release")

    def test_ac_007_briefs_failure_still_releases(self):
        s = self.summary(self.SCENARIOS[1])
        self.assertEqual(s["gates"][-1], "guard-release")
        self.assertEqual(s["gates"].count("guard-release"), 1)

    def test_ac_007_resume_keeps_the_guard(self):
        s = self.summary(self.SCENARIOS[2])
        self.assertIn("pipeline-plan --keep-guard", s["gates"][:3])

    def test_ac_007_happy_path_unchanged(self):
        s = self.summary(self.SCENARIOS[3])
        self.assertEqual(s["gate_prefixes"], [LIVE_CMD])
        self.assertNotIn("guard-release", s["gates"])

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_ac_007_both_engines_agree(self):
        self.assertNotIn("_error", self.node or {}, (self.node or {}).get("_error"))
        for name in self.SCENARIOS:
            with self.subTest(scenario=name):
                py = self.summary(name)
                for key in ("gates", "gate_prefixes", "result"):
                    self.assertEqual(self.node[name][key], py[key], key)


class InstallTests(Case):
    def test_ac_008_install_ships_the_launcher_and_migrates_the_hook(self):
        target = Path(tempfile.mkdtemp(prefix="maint-target-")).resolve()
        self.addCleanup(shutil.rmtree, target, ignore_errors=True)
        (target / ".claude").mkdir()
        old = {"hooks": {"PreToolUse": [{"matcher": "Write|Edit|Bash|StructuredOutput", "hooks": [
            {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/bin/agentic.py\" hook",
             "timeout": 900}]}]}}
        (target / ".claude" / "settings.json").write_text(json.dumps(old), encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=target, check=True)
        subprocess.run(["git", "add", "-A"], cwd=target, check=True)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"], cwd=target,
                       check=True)
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PROJECT_DIR", "CLAUDECODE", "AGENTIC_WP")}
        r = subprocess.run([sys.executable, str(BIN / "agentic.py"), "install", str(target)], cwd=target, env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((target / ".claude" / "bin" / "hook.py").is_file())
        settings = json.loads((target / ".claude" / "settings.json").read_text(encoding="utf-8"))
        flow = [(e, h) for e in settings["hooks"]["PreToolUse"] for h in e["hooks"]
                if "hook.py" in h["command"] or ("agentic.py" in h["command"] and h["command"].endswith("hook"))]
        self.assertEqual(len(flow), 1, settings["hooks"]["PreToolUse"])
        entry, hook = flow[0]
        self.assertEqual(hook["command"], 'python3 "$CLAUDE_PROJECT_DIR/.claude/bin/hook.py"')
        self.assertEqual(hook["timeout"], 900)
        self.assertIn("Bash", entry["matcher"])
        self.assertIn("Bash(python3 .claude/state/guard/bin/agentic.py:*)", settings["permissions"]["allow"])
        env["CLAUDE_PROJECT_DIR"] = str(target)
        r = subprocess.run([sys.executable, str(target / ".claude" / "bin" / "agentic.py"), "hooks-check"], cwd=target,
                           env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        gatekeeper = (ROOT / ".claude" / "agents" / "gatekeeper.md").read_text(encoding="utf-8")
        self.assertIn("python3 .claude/bin/agentic.py", gatekeeper)
        self.assertIn("python3 .claude/state/guard/bin/agentic.py", gatekeeper)


class ReleaseTests(unittest.TestCase):
    def test_ac_009_version_notes_docs(self):
        read = lambda rel: (ROOT / rel).read_text(encoding="utf-8")  # noqa: E731
        self.assertEqual(json.loads(read(".claude-plugin/plugin.json"))["version"], "2.6.0")
        notes = upgrade.NOTES["2.5.0"]
        self.assertGreaterEqual(len(notes), 2)
        joined = " ".join(notes)
        for word in ("hook.py", "settings.json", "maintainer"):
            self.assertIn(word, joined)
        self.assertEqual([len(upgrade.NOTES[v]) for v in ("2.4.1", "2.4.0", "2.3.0", "2.2.0", "2.1.0", "2.0.0")],
                         [1, 2, 2, 2, 4, 7])
        how = read("docs/how-it-works.md")
        self.assertIn("frozen", how.split("## 4. Guardrails")[1].split("\n## 5.")[0])
        hub = read("docs/how-to/README.md")
        self.assertIn("guard-release", hub.split("## Script reference")[1].split("## Troubleshooting")[0])
        self.assertLessEqual(len(hub.splitlines()), 260)
        entry = next(line for line in read("docs/roadmap/repo-review-2026-11.md").splitlines()
                     if line.startswith("- The flow cannot implement itself"))
        self.assertIn("Shipped in 2.5.0", entry)


if __name__ == "__main__":
    unittest.main()
