"""Acceptance tests of the stop gate and the four implementer statuses (agentic-flow 2.1): AC-001 .. AC-008 of
docs/architecture/0003.

Run: python3 -m unittest discover -s .claude/bin -p test_acceptance_v21.py
The hook runs against a temporary repo with a fake acceptance script; the engines are driven with the simulated
world or the simulated `claude`, so nothing is spent.
"""
import json
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
from test_agentic import PY, Repo, testutil  # noqa: E402
from test_pipeline import CONFORMANCE, E2E_MANIFEST, SPEC, run_scenario  # noqa: E402

AGENTS = ROOT / ".claude" / "agents"
COMMANDS = ROOT / ".claude" / "commands"
WORKFLOW_JS = ROOT / ".claude" / "workflows" / "agentic-implement.js"
STATUSES = ["DONE", "DONE_WITH_CONCERNS", "NEEDS_CONTEXT", "BLOCKED"]
FAILED = "FAILED acceptance/test_x.py::test_ac_001_x - assert"

GATE_MANIFEST = {
    "allow_bash": ["Bash(python3 -m unittest:*)"],
    "acceptance": {"files": ["acceptance/"], "command": f"{PY} acc.py"},
    "work_packages": [
        {"id": "WP-01", "wave": 1, "depends_on": [], "files": ["src/a.py"], "acs": ["AC-001"]},
        {"id": "WP-02", "wave": 1, "depends_on": [], "files": ["src/b/"], "acs": ["AC-002"]},
    ],
}
SHARED_MANIFEST = {**GATE_MANIFEST, "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": ["src/a.py"], "acs": ["AC-001", "AC-003"]},
    {"id": "WP-02", "wave": 1, "depends_on": [], "files": ["src/b/"], "acs": ["AC-001", "AC-003"]},
]}


def text(path):
    return path.read_text(encoding="utf-8")


def report_payload(status, wp="WP-01"):
    return {"tool_name": "StructuredOutput", "agent_type": "implementer",
            "tool_input": {"status": status, "wp": wp, "files": [], "checks": [], "internal_decisions": [],
                           "blocker": None, "not_checked": [], "concerns": [], "missing_context": None}}


def acceptance_script(lines, code):
    body = "\n".join(f"print({line!r})" for line in lines)
    return f"import sys\nopen('ran', 'w').close()\n{body}\nsys.exit({code})\n"


def gate_state(repo):
    path = repo.dir / ".claude" / "state" / "gate.json"
    return json.loads(text(path) or "{}") if path.exists() else {}


def js_const(name):
    """A top-level `const NAME = {...}` of the workflow, evaluated by node, as JSON."""
    lines = text(WORKFLOW_JS).splitlines()
    blocks = []
    for const in ("SEVERITY", "NOT_CHECKED", name):
        start = next(i for i, line in enumerate(lines) if line.startswith(f"const {const} = "))
        end = start if not lines[start].endswith("{") else next(i for i in range(start, len(lines)) if lines[i] == "}")
        blocks.append("\n".join(lines[start:end + 1]))
    out = subprocess.run(["node", "-e", "\n".join(blocks) + f"\nconsole.log(JSON.stringify({name}))"],
                         capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(out.stdout)


def scenario(name):
    by_name = {d["name"]: d for d in CONFORMANCE["scenarios"]}
    return by_name[name]


class GateTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repo(GATE_MANIFEST)
        self.addCleanup(self.repo.cleanup)

    def hook(self, status, wp="WP-01"):
        r = self.repo.run("hook", stdin=json.dumps(report_payload(status, wp)), env={"AGENTIC_WP": wp})
        return r.returncode, r.stderr

    def ran(self):
        marker = self.repo.dir / "ran"
        if marker.exists():
            marker.unlink()
            return True
        return False

    def test_ac_001_red_acceptance_refuses_the_report(self):
        self.repo.write("acc.py", acceptance_script([FAILED, "1 failed"], 1))
        code, err = self.hook("DONE")
        self.assertEqual(code, 2, err)
        for word in ("WP-01", "denial 1 of 2", FAILED):
            self.assertIn(word, err)
        self.assertEqual(gate_state(self.repo)["WP-01"]["denials"], 1)
        self.assertTrue(self.ran())
        # Another package's failure never stops this one.
        code, err = self.hook("DONE", "WP-02")
        self.assertEqual(code, 0, err)
        self.assertNotIn("WP-02", gate_state(self.repo))
        # A report that is not finished does not run the command.
        for status in ("BLOCKED", "NEEDS_CONTEXT"):
            with self.subTest(status=status):
                self.ran()
                code, err = self.hook(status)
                self.assertEqual(code, 0, err)
                self.assertFalse(self.ran())
        # An AC shared with another package is not this one's own failure.
        shared = Repo(SHARED_MANIFEST)
        self.addCleanup(shared.cleanup)
        shared.write("acc.py", acceptance_script(["FAILED acceptance/test_x.py::test_ac_003_x - assert"], 1))
        r = shared.run("hook", stdin=json.dumps(report_payload("DONE")), env={"AGENTIC_WP": "WP-01"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(gate_state(shared), {})

    def test_ac_002_cap_and_reset(self):
        self.repo.write("acc.py", acceptance_script([FAILED], 1))
        self.repo.write(".claude/state/gate.json", json.dumps({"WP-01": {"denials": 2, "last": []}}))
        code, err = self.hook("DONE")
        self.assertEqual(code, 0, err)
        self.assertEqual(gate_state(self.repo)["WP-01"]["denials"], 2)
        self.repo.write(".claude/state/gate.json", json.dumps({"WP-01": {"denials": 1, "last": []}}))
        code, err = self.hook("DONE")
        self.assertEqual(code, 2, err)
        self.assertIn("denial 2 of 2", err)
        r = self.repo.run("open-stage", "1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("WP-01", gate_state(self.repo))
        code, err = self.hook("DONE")
        self.assertEqual(code, 2, err)
        self.assertIn("denial 1 of 2", err)

    def test_ac_003_close_stage_line(self):
        self.repo.write("acc.py", acceptance_script([], 0))
        self.assertEqual(self.repo.run("open-stage", "1").returncode, 0)
        self.repo.write(".claude/state/gate.json", json.dumps({"WP-01": {"denials": 1, "last": []}}))
        r = self.repo.run("close-stage", "1", "WP-01=done", "WP-02=done")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertLess(r.stdout.index("GATE: WP-01=1 WP-02=0"), r.stdout.index("RESULT: OK"))
        self.assertEqual(self.repo.run("open-stage", "qa").returncode, 0)
        r = self.repo.run("close-stage", "qa", "QA=pass")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("GATE:", r.stdout)


class InstallTests(unittest.TestCase):
    def test_ac_008_matcher_upgrade(self):
        src = json.loads(text(ROOT / ".claude" / "settings.json"))
        own = {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo mine"}]}
        old = {"matcher": "Write|Edit|Bash",
               "hooks": [{"type": "command", "command": 'python3 "$CLAUDE_PROJECT_DIR/.claude/bin/agentic.py" hook'}]}
        tmp = Path(tempfile.mkdtemp(prefix="agentic-settings-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        dst = tmp / "settings.json"
        dst.write_text(json.dumps({"hooks": {"PreToolUse": [own, old]}}), encoding="utf-8")
        settings, added = agentic.merge_settings(dst, src)
        self.assertIn("hook PreToolUse (StructuredOutput)", added)
        pre = settings["hooks"]["PreToolUse"]
        self.assertEqual(pre[0], own)
        agentic_entries = [e for e in pre if "agentic.py" in e["hooks"][0]["command"]]
        self.assertEqual(len(agentic_entries), 1)
        self.assertEqual(agentic_entries[0]["matcher"], "Write|Edit|Bash|StructuredOutput")
        self.assertEqual(agentic_entries[0]["hooks"][0]["timeout"], 900)
        dst.write_text(json.dumps(settings), encoding="utf-8")
        again, added = agentic.merge_settings(dst, src)
        self.assertEqual(added, [])
        self.assertEqual(again["hooks"]["PreToolUse"], pre)


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

    def test_ac_003_engines_sum(self):
        for summary in self.both("gate denials are summed from close-stage"):
            self.assertEqual(summary["gate_denials"], {"WP-01": 1})

    def test_ac_004_status_mapping(self):
        for summary in self.both("concerns go to pending and to the reviewer"):
            self.assertEqual(summary["result"], "OK")
            self.assertIn("concern", summary["pending"])
            self.assertIn("the retry loop in src/a.py may spin", summary["prompts"]["reviewer:reviewer#1"])
            self.assertTrue(any(g.startswith("close-stage 1 WP-01=done") for g in summary["gates"]), summary["gates"])
        for summary in self.both("needs context is re-dispatched once with the whole document"):
            self.assertEqual(summary["agents"].count("implementer:WP-02 (context)"), 1)
            prompt = summary["prompts"]["implementer:WP-02 (context)#1"]
            for word in ("architecture.md, whole", "the error type of the contract"):
                self.assertIn(word, prompt)
            self.assertTrue(any("WP-02=done" in g for g in summary["gates"]), summary["gates"])
            self.assertEqual(summary["result"], "OK")
        for summary in self.both("needs context twice is a blocker"):
            self.assertTrue(any("WP-02=blocker" in g for g in summary["gates"]), summary["gates"])
            self.assertEqual((summary["result"], summary["failed_stage"]), ("REVIEW", "wave 1"))
            self.assertEqual(summary["agents"].count("implementer:WP-02 (context)"), 1)
        for summary in self.both("needs context in a fix wave is a blocker"):
            self.assertTrue(any(g.startswith("close-stage 1 WP-01=done") for g in summary["gates"]), summary["gates"])
            self.assertTrue(any(g.startswith("close-stage 1 WP-01=blocker --fix") for g in summary["gates"]), summary["gates"])
            self.assertEqual((summary["result"], summary["failed_stage"]), ("REVIEW", "fix wave 1"))
            self.assertFalse([a for a in summary["agents"] if "(context)" in a])
        # A concern item never carries a severity.
        result = run_scenario_result("concerns go to pending and to the reviewer")
        concerns = [p for p in result["pending"] if p.get("type") == "concern"]
        self.assertEqual(len(concerns), 1)
        self.assertNotIn("severity", concerns[0])
        self.assertEqual(concerns[0]["wp"], "WP-01")


def run_scenario_result(name):
    import pipeline
    from test_pipeline import world
    state, gate, agent = world(scenario(name))
    return pipeline.Pipeline(SPEC, gate, agent, parallel=lambda ts: [t() for t in ts]).execute()


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class SchemaTests(unittest.TestCase):
    def test_ac_005_schema_in_both_engines_and_fake(self):
        spec = SPEC["schemas"]["implementer"]
        js = js_const("REPORT_SCHEMA")
        self.assertEqual(spec["properties"]["status"]["enum"], STATUSES)
        self.assertEqual(js["properties"]["status"]["enum"], STATUSES)
        self.assertEqual(spec["required"], js["required"])
        self.assertTrue({"concerns", "missing_context"} <= set(spec["required"]))
        self.assertEqual(spec, js)
        self.assertNotIn("BLOCKER", spec["properties"]["status"]["enum"])
        self.check_real_run()

    def check_real_run(self):
        repo = Repo(E2E_MANIFEST)
        self.addCleanup(repo.cleanup)
        fake_bin = Path(tempfile.mkdtemp(prefix="fake-claude-"))
        logs = Path(tempfile.mkdtemp(prefix="fake-logs-"))
        self.addCleanup(shutil.rmtree, fake_bin, ignore_errors=True)
        self.addCleanup(shutil.rmtree, logs, ignore_errors=True)
        repo.env.update(AGENTIC_CLAUDE=testutil.install_fake_claude(fake_bin), FAKE_LOG_DIR=str(logs), FAKE_WRITE="1",
                        FAKE_MODE="nousage", FAKE_CONCERNS="1")
        repo.write("acc.py", "import os, sys\nsys.exit(0 if all(os.path.exists(p) for p in ('src/a.py', 'src/b/x.py', 'src/c.py')) else 1)\n")
        subprocess.run(["git", "add", "-A"], cwd=repo.dir, check=True)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"], cwd=repo.dir, check=True)
        r = repo.run("run-pipeline")
        self.assertIn("RESULT: OK", r.stdout, r.stdout + r.stderr)
        saved = json.loads(text(repo.dir / ".claude/state/runs/workflow-result.json"))
        self.assertEqual(saved["result"], "OK")
        concerns = [p for p in saved["pending"] if p.get("type") == "concern"]
        self.assertEqual(sorted(c["wp"] for c in concerns), ["WP-01", "WP-02", "WP-03"])
        self.assertEqual(saved["gate_denials"], {})


class PromptTests(unittest.TestCase):
    def test_ac_006_prompts(self):
        implementer = text(AGENTS / "implementer.md")
        for word in STATUSES + ["one sentence per concern, with the file", "you will get the whole document once",
                                "a contract does not match",
                                "a report that says DONE while the acceptance tests of your criteria fail is refused, twice at most"]:
            self.assertIn(word, implementer)
        self.assertNotRegex(implementer, r"\bBLOCKER\b")
        implement = text(COMMANDS / "implement.md")
        for word in ("`concern`", "`gate_denials`"):
            self.assertIn(word, implement)


class ReleaseTests(unittest.TestCase):
    def test_ac_007_version_and_notes(self):
        version = json.loads(text(ROOT / ".claude-plugin" / "plugin.json"))["version"]
        self.assertEqual(version, "2.2.0")
        notes = upgrade.NOTES["2.1.0"]
        self.assertGreaterEqual(len(notes), 3)
        joined = " ".join(notes)
        for word in ("gate", "DONE_WITH_CONCERNS", "settings.json"):
            self.assertIn(word, joined)
        self.assertEqual(len(upgrade.NOTES["2.0.0"]), 7)
        self.assertTrue(upgrade.NOTES["2.0.0"][0].startswith("Review findings and QA defects have four parts"))
        roadmap = text(ROOT / "docs" / "roadmap" / "repo-review-2026-11.md")
        versioning = roadmap[roadmap.index("## Versioning"):roadmap.index("## Found while using the flow")]
        self.assertIn("2.1.0", versioning)
        for item in ("2.1", "2.2"):
            self.assertIn(item, versioning)


if __name__ == "__main__":
    unittest.main()
