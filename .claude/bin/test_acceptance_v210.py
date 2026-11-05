"""Acceptance tests of agentic-flow 2.10.0, part 1: AC-001 .. AC-010 of docs/architecture/0016 (maintainer mode
retired; a plan for the flow's own repository runs by hand).

Run: python3 -m unittest discover -s .claude/bin -p test_acceptance_v210.py
The commands run the live agentic.py against temporary git repositories; agents are a marker script. Nothing is spent.
"""
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

BIN = Path(__file__).resolve().parent
ROOT = BIN.parents[1]
sys.path.insert(0, str(BIN))
import agentic  # noqa: E402
import core  # noqa: E402
import launch  # noqa: E402
import manifest_check  # noqa: E402
import upgrade  # noqa: E402
from test_agentic import MANIFEST, Repo, write_payload  # noqa: E402
from test_pipeline import CONFORMANCE, run_scenario  # noqa: E402

RETIRED = "Bash(python3 .claude/state/guard/bin/agentic.py:*)"
BY_HAND = dict(MANIFEST, maintainer=True, work_packages=[
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": [".claude/bin/x.py", "src/a.py"]}])


class FlowRepo(Repo):
    """A temporary repository that is the flow's own: the plugin name and the README marker."""

    def __init__(self, manifest=BY_HAND):
        super().__init__(manifest)
        (self.dir / ".claude-plugin").mkdir()
        (self.dir / ".claude-plugin/plugin.json").write_text(json.dumps({"name": "agentic-flow"}), encoding="utf-8")
        (self.dir / "README.md").write_text("<!-- agentic-flow-template -->\n# flow\n", encoding="utf-8")


class Case(unittest.TestCase):
    def repo(self, cls=FlowRepo, *args):
        repo = cls(*args)
        self.addCleanup(repo.cleanup)
        return repo


def flow_repo(answer):
    """is_flow_repo patched where it is read: maintainer_mode (core) and the flag's rule (manifest_check)."""
    return mock.patch.multiple(core, is_flow_repo=lambda root: answer), \
        mock.patch.multiple(manifest_check, is_flow_repo=lambda root: answer)


class ValidateTests(Case):
    def test_ac_001_flag_rules_unchanged(self):
        a, b = flow_repo(True)
        with a, b:
            self.assertEqual(agentic.validate(BY_HAND), [])
            plain = {k: v for k, v in BY_HAND.items() if k != "maintainer"}
            self.assertIn("WP-01: cannot own '.claude/bin/x.py'.", agentic.validate(plain))
            settings = json.loads(json.dumps(BY_HAND))
            settings["work_packages"][0]["files"] = [".claude/settings.json"]
            self.assertTrue(any("is never owned" in e for e in agentic.validate(settings)))
        a, b = flow_repo(False)
        with a, b:
            self.assertTrue(any(e.startswith("maintainer:") for e in agentic.validate(BY_HAND)))


class RefusalTests(Case):
    def marker_env(self, repo):
        fake = repo.dir / "fake_claude.py"
        fake.write_text(f"open({str(repo.dir / 'MARKER')!r}, 'w').close()\nprint('{{}}')\n", encoding="utf-8")
        return {"AGENTIC_CLAUDE": f"{sys.executable} {fake}"}

    def test_ac_002_pipeline_plan_refuses(self):
        repo = self.repo()
        r = repo.run("pipeline-plan")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("executed by hand", r.stderr)
        self.assertFalse([line for line in r.stdout.splitlines() if line.startswith("{")])
        self.assertFalse((repo.dir / ".claude/state/guard").exists())

    def test_ac_003_launchers_refuse(self):
        repo = self.repo()
        env = self.marker_env(repo)
        for args in (["run-wave", "1"], ["run-review"], ["run-acceptance"], ["run-pipeline"]):
            with self.subTest(args=args):
                r = repo.run(*args, env=env)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("executed by hand", r.stderr)
        state = repo.dir / ".claude/state"
        self.assertFalse((repo.dir / "MARKER").exists(), "no agent was started")
        self.assertFalse((state / "briefs").exists())
        self.assertFalse((state / "runs").exists())
        self.assertFalse(list(state.glob("snapshot-*.json")) if state.exists() else [])


class CommandTests(Case):
    def test_ac_004_no_guard_left(self):
        repo = self.repo(Repo, MANIFEST)
        r = repo.run("pipeline-plan")
        self.assertEqual(r.returncode, 0, r.stderr)
        plan = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertNotIn("maintainer", plan)
        self.assertNotIn("agentic", plan)
        r = repo.run("pipeline-plan", "--keep-guard")
        self.assertEqual(r.returncode, 1)
        self.assertIn("Uso: pipeline-plan", r.stderr)
        self.assertEqual(repo.run("guard-release").returncode, 1)
        self.assertNotIn("guard-release", agentic.COMMANDS)
        self.assertNotRegex(agentic.__doc__, r"\n  guard-release")
        for module in (agentic, launch, core):
            for name in ("freeze_guard", "release_guard", "GUARD_DIR", "GUARD_CMD", "FROZEN"):
                with self.subTest(module=module.__name__, name=name):
                    self.assertFalse(hasattr(module, name))


class HookTests(Case):
    def test_ac_005_live_guard_only(self):
        repo = self.repo(Repo, MANIFEST)
        bin_dir = repo.dir / ".claude/bin"
        bin_dir.mkdir(parents=True)
        for f in BIN.glob("*.py"):
            if not f.name.startswith("test_"):
                shutil.copy(f, bin_dir / f.name)
        guard = repo.dir / ".claude/state/guard"
        (guard / "bin").mkdir(parents=True)
        (guard / "active.json").write_text("{}", encoding="utf-8")
        (guard / "bin/agentic.py").write_text("print('FROZEN')\n", encoding="utf-8")
        env = dict(repo.env, AGENTIC_WP="WP-01")
        r = subprocess.run([sys.executable, str(bin_dir / "hook.py")], cwd=repo.dir, capture_output=True, text=True,
                           input=json.dumps(write_payload("src/c.py")), env=env, encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertNotIn("FROZEN", r.stdout + r.stderr)


class OwnershipTests(unittest.TestCase):
    def test_ac_006_flow_paths_always_refused(self):
        self.assertTrue(core.flow_path_refused(".claude/bin/agentic.py"))
        self.assertTrue(core.flow_path_refused(".claude/settings.json"))
        self.assertFalse(core.flow_path_refused("src/a.py"))
        self.assertEqual(len(inspect.signature(core.flow_path_refused).parameters), 1)


class EngineTests(unittest.TestCase):
    def test_ac_007_live_only(self):
        for decl in CONFORMANCE["scenarios"]:
            with self.subTest(scenario=decl["name"]):
                self.assertNotIn("maintainer", decl["name"])
                self.assertFalse({"maintainer", "agentic"} & set(decl.get("plan", {})))
        resumed = next(d for d in CONFORMANCE["scenarios"]
                       if d["name"] == "start_wave skips the baseline, wave 0 and earlier waves")
        self.assertEqual(run_scenario(resumed)["gates"][1], "pipeline-plan")
        js = (ROOT / ".claude/workflows/agentic-implement.js").read_text(encoding="utf-8")
        py = (BIN / "pipeline.py").read_text(encoding="utf-8")
        self.assertIn("const AGENTIC = 'python3 .claude/bin/agentic.py'", js)
        self.assertEqual(len(re.findall(r"\bAGENTIC\s*=[^=]", js)), 1, "AGENTIC is assigned once")
        for text in (js, py):
            for needle in ("guard-release", "keep-guard", "plan.agentic", "self.agentic"):
                self.assertNotIn(needle, text)
        for f in BIN.iterdir():
            if f.suffix in (".py", ".mjs", ".json") and f.name != Path(__file__).name:
                with self.subTest(file=f.name):
                    self.assertNotRegex(f.read_text(encoding="utf-8"), r"gate_prefixes|gatePrefixes")


class InstallTests(Case):
    def test_ac_008_retired_permission_removed(self):
        repo = self.repo(Repo, MANIFEST)
        dst = repo.dir / "project-settings.json"
        dst.write_text(json.dumps({"permissions": {"allow": [RETIRED, "Bash(make:*)"]}}), encoding="utf-8")
        src = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
        if RETIRED not in src["permissions"]["allow"]:  # as before the maintainer's edit: the result must not change
            src["permissions"]["allow"].append(RETIRED)
        data, added = agentic.merge_settings(dst, src)
        self.assertNotIn(RETIRED, data["permissions"]["allow"])
        self.assertIn("Bash(make:*)", data["permissions"]["allow"])
        self.assertIn(f"removed allow {RETIRED}", added)
        self.assertNotIn(f"allow {RETIRED}", added)
        dst.write_text(json.dumps(data), encoding="utf-8")
        data, added = agentic.merge_settings(dst, src)
        self.assertFalse([a for a in added if a.startswith("removed")])
        self.assertIn("Bash(make:*)", data["permissions"]["allow"])


class DefinitionTests(unittest.TestCase):
    def test_ac_009_live_command_only(self):
        settings = (ROOT / ".claude/settings.json").read_text(encoding="utf-8")
        gatekeeper = (ROOT / ".claude/agents/gatekeeper.md").read_text(encoding="utf-8")
        self.assertNotIn("state/guard", settings)
        self.assertNotIn("state/guard", gatekeeper)
        self.assertIn("Bash(python3 .claude/bin/agentic.py:*)", json.loads(settings)["permissions"]["allow"])
        self.assertIn("python3 .claude/bin/agentic.py", gatekeeper)


class ReleaseTests(unittest.TestCase):
    def test_ac_010_version_notes_docs(self):
        self.assertEqual(json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))["version"],
                         "2.10.0")
        notes = " ".join(upgrade.NOTES.get("2.10.0", []))
        self.assertIn("guard-release", notes)
        self.assertIn("by hand", notes)
        how = (ROOT / "docs/how-it-works.md").read_text(encoding="utf-8")
        self.assertIn("Changing the flow itself", how)
        for text in (how, (ROOT / "docs/how-to/README.md").read_text(encoding="utf-8")):
            self.assertNotIn("guard-release", text)
            self.assertNotIn(".claude/state/guard", text)
        self.assertNotRegex(how, r"(?i)\bfrozen\b")
        self.assertFalse((BIN / "test_acceptance_v25.py").exists())


if __name__ == "__main__":
    unittest.main()
