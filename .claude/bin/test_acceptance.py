"""Acceptance tests of design 0001 (lean agents): briefs, one report format, telemetry.

They come from the AC-001..AC-013 criteria of docs/architecture/0001-lean-agents-briefs.md.
Run: python3 -m unittest discover -s .claude/bin -p test_acceptance.py
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
from test_agentic import PY, Repo, testutil  # noqa: E402

SPEC = json.loads((ROOT / ".claude" / "workflows" / "pipeline-spec.json").read_text(encoding="utf-8"))


def manifest(wps=2, wave2=False):
    items = [
        {"id": "WP-01", "wave": 1, "depends_on": [], "files": ["src/a.py"], "acs": ["AC-001"]},
        {"id": "WP-02", "wave": 1, "depends_on": [], "files": ["src/b/"], "acs": ["AC-002"]},
    ]
    if wps == 3:
        items.append({"id": "WP-03", "wave": 2, "depends_on": ["WP-01"], "files": ["src/c.py"], "acs": ["AC-003"]})
    return {"allow_bash": ["Bash(python3 -m unittest:*)"],
            "acceptance": {"files": ["acceptance/"], "command": f"{PY} acc.py"}, "work_packages": items}


def document(m, contract_extra=""):
    """An architecture.md with the template's sections, a block per AC and per WP, and the manifest."""
    acs = [a for wp in m["work_packages"] for a in wp["acs"]]
    ac_blocks = "".join(f"- {a} · title {a}\n  - Scenario: body of {a}\n  - Must not: nothing {a}\n" for a in acs)
    wp_blocks = "".join(f"#### {wp['id']} · goal {wp['id']}\nbody of {wp['id']}\n\n" for wp in m["work_packages"])
    return (
        "# Architecture: demo\nType: feature · Size: standard\n\n"
        "## 1. Goal\nTEXT-GOAL\n\n## 2. Scope\nTEXT-SCOPE\n\n## 3. Stack\nTEXT-STACK\n\n"
        "## 4. Repository structure\nTEXT-TREE\n\n## 4b. Existing code context\nTEXT-CONTEXT\n\n"
        "## 5. Data model\nTEXT-MODEL\n\n"
        f"## 6. Contracts between modules\nTEXT-CONTRACTS\n{contract_extra}\n"
        "## 7. Conventions\nTEXT-CONVENTIONS\n\n"
        f"## 8. Work packages and acceptance criteria\n### Acceptance criteria\n{ac_blocks}\n### Work packages\n{wp_blocks}"
        f"```json wp-manifest\n{json.dumps(m, indent=2)}\n```\n\n"
        "## 9. Test strategy\nTEXT-TESTS\n\n## 10. Decisions\nTEXT-DECISIONS\n\n## 11. Risks and open questions\nTEXT-RISKS\n")


FENCED = "```text\n## 10. Decisions\n#### WP-02 · fake\nFENCED-LINE\n```\n"

class Project(Repo):
    """A temporary git repo with an architecture.md, the workflows folder (the spec) and a fake `claude` (AGENTIC_CLAUDE)."""

    def __init__(self, m=None, doc=None):
        m = m or manifest()
        super().__init__(m)
        (self.dir / "architecture.md").write_text(doc if doc is not None else document(m), encoding="utf-8")
        shutil.copytree(ROOT / ".claude" / "workflows", self.dir / ".claude" / "workflows", dirs_exist_ok=True)
        self.fake_bin = Path(tempfile.mkdtemp(prefix="fake-claude-"))
        self.logs = Path(tempfile.mkdtemp(prefix="fake-logs-"))
        self.env.update(AGENTIC_CLAUDE=testutil.install_fake_claude(self.fake_bin), FAKE_LOG_DIR=str(self.logs))

    def calls(self):
        return testutil.fake_calls(self.logs)

    def files(self):
        return {p.relative_to(self.dir).as_posix() for p in self.dir.rglob("*")
                if p.is_file() and ".git/" not in p.as_posix() + "/"}

    def cleanup(self):
        super().cleanup()
        shutil.rmtree(self.fake_bin, ignore_errors=True)
        shutil.rmtree(self.logs, ignore_errors=True)


def slicer():
    import brief
    return brief.slice_architecture


class SlicerTests(unittest.TestCase):
    def setUp(self):
        self.m = manifest()
        self.text = document(self.m)

    def test_ac_001_wp_brief(self):
        brief, sliced = slicer()(self.text, "WP-01", self.m)
        self.assertTrue(sliced)
        self.assertTrue(brief.startswith("> Brief for WP-01:"))
        for token in ("TEXT-GOAL", "TEXT-SCOPE", "TEXT-STACK", "TEXT-CONTEXT", "TEXT-MODEL", "TEXT-CONTRACTS",
                      "TEXT-CONVENTIONS", "TEXT-TESTS", "TEXT-RISKS", "- AC-001 · title", "#### WP-01 · goal"):
            self.assertIn(token, brief)
        entry = json.dumps(self.m["work_packages"][0], indent=2)
        self.assertIn("```json\n" + entry + "\n```", brief)
        for token in ("AC-002", "WP-02", "TEXT-TREE", "TEXT-DECISIONS", "wp-manifest"):
            self.assertNotIn(token, brief)

    def test_ac_002_at_brief(self):
        brief, sliced = slicer()(self.text, "AT", self.m)
        self.assertTrue(sliced)
        for token in ("TEXT-GOAL", "TEXT-SCOPE", "TEXT-STACK", "TEXT-CONTEXT", "TEXT-MODEL", "TEXT-CONTRACTS",
                      "TEXT-CONVENTIONS", "TEXT-TESTS", "- AC-001 · title", "- AC-002 · title"):
            self.assertIn(token, brief)
        self.assertIn("```json\n" + json.dumps({"acceptance": self.m["acceptance"]}, indent=2) + "\n```", brief)
        for token in ("#### WP-", "TEXT-TREE", "TEXT-DECISIONS", "TEXT-RISKS", "wp-manifest"):
            self.assertNotIn(token, brief)

    def test_ac_003_fallback(self):
        variants = {
            "no heading": (self.text.replace("#### WP-01 · goal WP-01", "WP-01 · goal WP-01"), self.m, "WP-01"),
            "empty acs": (self.text, json.loads(json.dumps(self.m)), "WP-01"),
            "unknown ac": (self.text, json.loads(json.dumps(self.m)), "WP-01"),
            "unknown id": (self.text, self.m, "WP-77"),
        }
        variants["empty acs"][1]["work_packages"][0]["acs"] = []
        variants["unknown ac"][1]["work_packages"][0]["acs"] = ["AC-009"]
        for name, (text, m, ident) in variants.items():
            with self.subTest(name):
                self.assertEqual(slicer()(text, ident, m), (text, False))

    def test_ac_004_fences(self):
        text = document(self.m, contract_extra=FENCED)
        brief, sliced = slicer()(text, "WP-01", self.m)
        self.assertTrue(sliced)
        self.assertIn(FENCED, brief)
        self.assertNotIn("TEXT-DECISIONS", brief)
        self.assertNotIn("#### WP-02", brief.replace(FENCED, ""))


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.p = Project()

    def tearDown(self):
        self.p.cleanup()

    def test_ac_005_briefs_command(self):
        before = self.p.files()
        r = self.p.run("briefs")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        info = json.loads(r.stdout.strip().splitlines()[-1])
        text = (self.p.dir / "architecture.md").read_text(encoding="utf-8")
        m = manifest()
        for ident in ("WP-01", "WP-02", "AT"):
            expected, sliced = slicer()(text, ident, m)
            self.assertEqual((self.p.dir / ".claude/state/briefs" / f"{ident}.md").read_text(encoding="utf-8"), expected)
            self.assertEqual(info["briefs"][ident]["sliced"], sliced)
        self.assertTrue(info["briefs"]["WP-01"]["sliced"])
        self.assertLess(info["briefs"]["WP-01"]["words"], info["full_words"])
        written = self.p.files() - before
        self.assertTrue(all(f.startswith(".claude/state/briefs/") for f in written), written)
        r = self.p.run("seq", "pipeline-plan", "+", "briefs")
        steps = json.loads(r.stdout)["steps"]
        self.assertEqual([s["exit_code"] for s in steps], [0, 0])
        (self.p.dir / "architecture.md").write_text("# no manifest\n", encoding="utf-8")
        self.assertEqual(self.p.run("briefs").returncode, 1)

    def test_ac_007_single_report_format(self):
        r = self.p.run("run-wave", "1", env={"FAKE_MODE": "structured"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for call in self.p.calls():
            argv = call["argv"]
            self.assertEqual(json.loads(argv[argv.index("--json-schema") + 1]), SPEC["schemas"]["implementer"])
        r = self.p.run("run-wave", "1", env={"FAKE_MODE": "text"})
        self.assertEqual(r.returncode, 3, r.stdout)
        ledger = json.loads((self.p.dir / ".claude/state/ledger.json").read_text(encoding="utf-8"))
        self.assertEqual(ledger["WP-01"]["state"], "error")
        self.assertIn("NO REPORT", ledger["WP-01"]["note"])

    def test_ac_008_fix_defects(self):
        runs = self.p.dir / ".claude/state/runs"
        runs.mkdir(parents=True)
        finding = {"severity": "high", "wp": "WP-02", "file": "src/b/x.py", "problem": "p", "evidence": "e"}
        (runs / "REVIEW.json").write_text(json.dumps({"structured_output": {"status": "FAIL", "findings": [finding]}}), encoding="utf-8")
        r = self.p.run("run-wave", "1", "WP-02", "--fix")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        prompt = self.p.calls()[-1]["prompt"]
        self.assertTrue(prompt.startswith("Fix WP-02."), prompt)
        self.assertIn('"problem":"p"', prompt)
        n = len(self.p.calls())
        r = self.p.run("run-wave", "1", "WP-01", "--fix")
        self.assertEqual(r.returncode, 1)
        self.assertIn("WP-01: no blocking defect from review or QA is attributed to it.", r.stderr)
        self.assertEqual(len(self.p.calls()), n, "no agent is launched for WP-01")

    def test_ac_009_dead_commands(self):
        for args in (["wave-plan", "1"], ["open-wave", "1"], ["close-wave", "1", "WP-01=done"]):
            with self.subTest(args):
                r = self.p.run(*args)
                self.assertEqual(r.returncode, 1)
                self.assertIn("Subcommands", r.stderr)
        self.assertFalse((self.p.dir / ".claude/state/snapshot-1.json").exists())

    def test_ac_010_usage(self):
        r = self.p.run("run-wave", "1", env={"FAKE_MODE": "structured"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        records = [json.loads(x) for x in (self.p.dir / ".claude/state/usage.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(records), 2)
        self.assertIn({"id": "WP-01", "agent": "implementer", "label": "WP-01", "input": 120, "cache_read": 300,
                       "output": 50, "cost_usd": 0.01, "turns": 3}, records)
        out = self.p.run("status").stdout
        self.assertIn("## Usage", out)
        self.assertIn("Total: in 240", out)

    def test_ac_010_usage_missing_fields(self):
        r = self.p.run("run-wave", "1", env={"FAKE_MODE": "nousage"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rec = json.loads((self.p.dir / ".claude/state/usage.jsonl").read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual((rec["input"], rec["cache_read"], rec["output"], rec["cost_usd"]), (0, 0, 0, None))
        self.assertIn("$?", self.p.run("status").stdout)


class PipelineUsageTests(unittest.TestCase):
    def test_ac_010_run_pipeline_reports_usage(self):
        m = manifest(3)
        p = Project(m)
        self.addCleanup(p.cleanup)
        p.write("acc.py", "import os, sys\nsys.exit(0 if all(os.path.exists(f) for f in ('src/a.py', 'src/b/x.py', 'src/c.py')) else 1)\n")
        subprocess.run(["git", "add", "-A"], cwd=p.dir, check=True)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"], cwd=p.dir, check=True)
        r = p.run("run-pipeline", env={"FAKE_MODE": "structured", "FAKE_WRITE": "1"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        result = json.loads((p.dir / ".claude/state/runs/workflow-result.json").read_text(encoding="utf-8"))
        usage = result["usage"]
        self.assertEqual(len(usage["by_agent"]), 7, "test-author, auditor, 3 implementers, reviewer, qa")
        self.assertEqual(usage["total"]["output"], 50 * 7)
        for call in p.calls():
            if call["agent"] != "implementer":
                continue
            prompt = call["prompt"]
            self.assertIn(f".claude/state/briefs/{call['id']}.md", prompt)


class PromptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r = subprocess.run(["node", str(BIN / "test_workflow.mjs"), "--dump"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert r.returncode == 0, r.stdout + r.stderr
        cls.dump = json.loads(r.stdout)

    def test_ac_006_prompts_use_briefs(self):
        happy = self.dump["happy path"]
        self.assertIn(".claude/state/briefs/WP-01.md", happy["prompts"]["implementer:WP-01#1"])
        for key in ("test-author:test-author#1", "test-auditor:test-auditor#1"):
            self.assertIn(".claude/state/briefs/AT.md", happy["prompts"][key])
        self.assertEqual(happy["gates"][:4], ["hooks-check", "pipeline-plan", "briefs", "baseline"])
        resumed = self.dump["start_wave skips the baseline, wave 0 and earlier waves"]
        # 2.10.0: a resumed run plans like a fresh one (the frozen guard of 2.5.0 is gone).
        self.assertEqual(resumed["gates"][:3], ["hooks-check", "pipeline-plan", "briefs"])
        judges = ("reviewer", "qa", "verifier", "doc-updater")
        seen = 0
        for scenario in self.dump.values():
            for key, prompt in scenario["prompts"].items():
                if key.split(":")[0] in judges:
                    seen += 1
                    self.assertNotIn("briefs/", prompt, key)
        self.assertGreater(seen, 0)


def section(text, heading):
    """The section whose heading starts with `# <heading>`, heading line included (it carries the word cap)."""
    m = re.search(rf"^# {heading}.*?(?=^# |\Z)", text, re.S | re.M)
    return m.group(0) if m else ""


class DefinitionTests(unittest.TestCase):
    AGENTS = ROOT / ".claude" / "agents"

    def test_ac_011_agents_json_only(self):
        for name in ("implementer", "test-author", "test-auditor", "qa", "reviewer", "doc-updater"):
            with self.subTest(name):
                text = (self.AGENTS / f"{name}.md").read_text(encoding="utf-8")
                self.assertNotIn("STATUS:", text)
                body = section(text, "Report")
                self.assertIn("schema", body)
                self.assertIn("words", body)
        for name in ("implementer", "test-author", "test-auditor"):
            with self.subTest(brief=name):
                self.assertIn("brief", (self.AGENTS / f"{name}.md").read_text(encoding="utf-8").lower())

    def test_ac_012_architect_template(self):
        architect = (ROOT / ".claude/commands/architect.md").read_text(encoding="utf-8")
        self.assertIn("#### WP-NN · ", architect)
        self.assertIn("brief", architect.lower())
        self.assertIn("`acs`", architect)
        reviewer = (self.AGENTS / "plan-reviewer.md").read_text(encoding="utf-8")
        self.assertIn("#### WP-", reviewer)
        self.assertIn("- AC-NNN ·", reviewer)

    def test_ac_013_docs(self):
        how = (ROOT / "docs/how-it-works.md").read_text(encoding="utf-8")
        for token in ("**Brief:**", "briefs/", "usage.jsonl"):
            self.assertIn(token, how)
        skip = {ROOT / "architecture.md"}
        for path in list(ROOT.glob("*.md")) + list((ROOT / "docs").rglob("*.md")) + list((ROOT / ".claude").rglob("*.md")):
            if path in skip or "fixtures" in path.parts:  # a fixture is a test input, not documentation
                continue
            text = path.read_text(encoding="utf-8")
            for dead in ("wave-plan", "open-wave", "close-wave"):
                self.assertNotIn(dead, text, f"{path.relative_to(ROOT)} cites {dead}")
        paragraph = next(p for p in (ROOT / "README.md").read_text(encoding="utf-8").split("\n\n")
                         if p.startswith("Not confirmed with real agents"))
        self.assertIn("brief", paragraph.lower())
        self.assertIn("telemetry", paragraph.lower())


if __name__ == "__main__":
    unittest.main()
