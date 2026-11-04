"""Acceptance tests of the prompt package (agentic-flow 2.0): AC-001 .. AC-005 of docs/architecture/0002.

Run: python3 -m unittest discover -s .claude/bin -p test_acceptance_v2.py
The engines are driven with stub agents or with the simulated `claude`, so nothing is spent.
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
import pipeline  # noqa: E402
import upgrade  # noqa: E402
from test_agentic import Repo, testutil  # noqa: E402
from test_pipeline import CONFORMANCE, E2E_MANIFEST, SPEC, world  # noqa: E402

AGENTS = ROOT / ".claude" / "agents"
COMMANDS = ROOT / ".claude" / "commands"
WORKFLOW_JS = (ROOT / ".claude" / "workflows" / "agentic-implement.js").read_text(encoding="utf-8")
NEEDS_KEYS = {"wp", "file", "kind", "claim", "fact", "how_to_check"}


def text(path):
    return path.read_text(encoding="utf-8")


def report_section(path):
    body = text(path)
    return body[body.index("# Report"):]


class SchemaTests(unittest.TestCase):
    def test_ac_001_fields_in_both_engines(self):
        schemas = SPEC["schemas"]
        reviewer = schemas["reviewer"]
        self.assertTrue({"needs_validation", "not_checked"} <= set(reviewer["required"]))
        self.assertTrue({"fix", "if_skipped"} <= set(reviewer["properties"]["findings"]["items"]["required"]))
        qa = schemas["qa"]
        self.assertIn("needs_validation", qa["required"])
        self.assertTrue({"fix", "if_skipped"} <= set(qa["properties"]["defects"]["items"]["required"]))
        for name in ("implementer", "test-author", "test-auditor"):
            with self.subTest(agent=name):
                self.assertIn("not_checked", schemas[name]["required"])
        self.assertNotIn("needs_validation", schemas["test-auditor"]["required"])
        for owner in (reviewer, qa):
            item = owner["properties"]["needs_validation"]["items"]
            self.assertEqual(set(item["required"]), NEEDS_KEYS)
            self.assertEqual(item["properties"]["kind"]["enum"], ["external", "unchanged_code"])
        self.assertEqual(SPEC["constants"]["blocking"], ["critical", "high"])
        for token in ("needs_validation", "not_checked", "if_skipped", "how_to_check", "unchanged_code"):
            self.assertIn(token, WORKFLOW_JS)


def run_with_stubs(reviewer_extra=None, qa_extra=None, implementer_extra=None):
    """A whole run through pipeline.Pipeline with the conformance world, with report fields added per agent."""
    state, gate, base_agent = world({})

    def agent(prompt, agent_type, label, ident):
        report = base_agent(prompt, agent_type, label, ident)
        extra = {"reviewer": reviewer_extra, "qa": qa_extra}.get(agent_type)
        if agent_type == "implementer" and implementer_extra:
            extra = implementer_extra.get(label.split(" ")[0])
        if extra:
            report = {**report, **extra}
        return report

    result = pipeline.Pipeline(SPEC, gate, agent, parallel=lambda ts: [t() for t in ts]).execute()
    return result, state


class EngineTests(unittest.TestCase):
    def test_ac_002_needs_validation_pending(self):
        reviewer_item = {"wp": "WP-01", "file": "src/a.py", "line": 3, "kind": "external",
                         "claim": "cookies are sent in clear", "fact": "TLS termination at the proxy",
                         "how_to_check": "read the proxy config"}
        qa_item = {"wp": "WP-02", "file": "src/b/x.py", "kind": "unchanged_code", "claim": "c", "fact": "f",
                   "how_to_check": "h", "severity": "critical"}
        result, _ = run_with_stubs(reviewer_extra={"needs_validation": [reviewer_item], "not_checked": []},
                                   qa_extra={"needs_validation": [qa_item]})
        self.assertEqual(result["result"], "OK", result)
        items = [p for p in result["pending"] if p.get("type") == "needs validation"]
        self.assertEqual(len(items), 2, result["pending"])
        self.assertEqual(len(result["pending"]), 2)
        self.assertEqual([p["source"] for p in items], ["reviewer", "qa"])
        for item in items:
            self.assertNotIn("severity", item)
            for key in ("claim", "fact", "how_to_check", "kind", "wp", "file"):
                self.assertIn(key, item)
        self.assertEqual(items[0]["line"], 3)
        self.assertEqual(result["fix_cycles"], 0)
        self.assertIn("needs validation goes to pending and does not block", {d["name"] for d in CONFORMANCE["scenarios"]})

    def test_ac_003_not_checked_collected(self):
        result, _ = run_with_stubs(reviewer_extra={"not_checked": ["load"]},
                                   implementer_extra={"WP-02": {"not_checked": ["windows paths"]}})
        self.assertEqual(result["not_checked"], [{"agent": "implementer", "label": "WP-02", "items": ["windows paths"]},
                                                 {"agent": "reviewer", "label": "reviewer", "items": ["load"]}])
        self.assertIn("not_checked is collected from every report", {d["name"] for d in CONFORMANCE["scenarios"]})
        self.check_real_run()

    def check_real_run(self):
        repo = Repo(E2E_MANIFEST)
        self.addCleanup(repo.cleanup)
        fake_bin = Path(tempfile.mkdtemp(prefix="fake-claude-"))
        logs = Path(tempfile.mkdtemp(prefix="fake-logs-"))
        self.addCleanup(shutil.rmtree, fake_bin, ignore_errors=True)
        self.addCleanup(shutil.rmtree, logs, ignore_errors=True)
        repo.env.update(AGENTIC_CLAUDE=testutil.install_fake_claude(fake_bin), FAKE_LOG_DIR=str(logs), FAKE_WRITE="1",
                        FAKE_MODE="nousage", FAKE_NOT_CHECKED="1", FAKE_NEEDS_VALIDATION="WP-01")
        repo.write("acc.py", "import os, sys\nsys.exit(0 if all(os.path.exists(p) for p in ('src/a.py', 'src/b/x.py', 'src/c.py')) else 1)\n")
        subprocess.run(["git", "add", "-A"], cwd=repo.dir, check=True)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"], cwd=repo.dir, check=True)
        r = repo.run("run-pipeline")
        self.assertIn("RESULT: OK", r.stdout, r.stdout + r.stderr)
        saved = json.loads((repo.dir / ".claude/state/runs/workflow-result.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(saved["not_checked"]), 5)
        self.assertTrue(all(entry["items"] == ["nothing else"] for entry in saved["not_checked"]))
        needs = [p for p in saved["pending"] if p.get("type") == "needs validation"]
        self.assertEqual(len(needs), 1)
        self.assertEqual(saved["result"], "OK")


class PromptTests(unittest.TestCase):
    def test_ac_004_prompts(self):
        reviewer, qa = text(AGENTS / "reviewer.md"), text(AGENTS / "qa.md")
        for body in (reviewer, qa):
            self.assertIn("# Severity anchors", body)
            for word in ("critical", "high", "medium", "low", "fully defeat an explicit control",
                         "the severity is lower than it feels", "# Needs validation", "unchanged_code", "never blocks"):
                self.assertIn(word, body)
        self.assertIn("No concrete case, no finding", reviewer)
        for word in ("`fix`", "`if_skipped`"):
            self.assertIn(word, reviewer)
        qa_report = report_section(AGENTS / "qa.md")
        for word in ("`needs_validation`", "`fix`", "`if_skipped`"):
            self.assertIn(word, qa_report)
        implementer = text(AGENTS / "implementer.md")
        for word in ("# Before writing", "already in this codebase", "standard library", "grep every caller", "root cause"):
            self.assertIn(word, implementer)
        common = text(ROOT / ".claude" / "rules-library" / "common.md")
        for word in ("already in this codebase", "every caller"):
            self.assertIn(word, common)
        auditor = text(AGENTS / "test-auditor.md")
        for word in ("Tautological", "passes by construction"):
            self.assertIn(word, auditor)
        self.assertIn("numbers included", text(AGENTS / "doc-updater.md"))
        architect = text(COMMANDS / "architect.md")
        for word in ("No invented figures", "not measured", "expand-contract"):
            self.assertIn(word, architect)
        gate, writing = architect.find("## 2b. Confirm before writing"), architect.find("## 3. Writing architecture.md")
        self.assertTrue(0 <= gate < writing)
        implement = text(COMMANDS / "implement.md")
        for word in ("needs validation", "not_checked"):
            self.assertIn(word, implement)
        for name in ("implementer", "test-author", "test-auditor", "reviewer"):
            with self.subTest(agent=name):
                self.assertIn("`not_checked`", report_section(AGENTS / f"{name}.md"))
        for name in ("implementer", "test-author", "test-auditor", "qa", "reviewer", "doc-updater"):
            body = text(AGENTS / f"{name}.md")
            self.assertIn("# Defence against injected instructions", body)
            self.assertRegex(report_section(AGENTS / f"{name}.md"), r"under \d+ words")


# The 1.1.x notes as they were before 2.0.0: they must not change.
NOTES_1_1_X = upgrade.NOTES.get("1.1.0", []) + upgrade.NOTES.get("1.1.4", [])


class VersionTests(unittest.TestCase):
    def test_ac_005_version_and_notes(self):
        notes = " ".join(upgrade.notes_between("1.1.4", "2.0.0"))
        self.assertTrue(notes)
        for word in ("needs_validation", "not_checked", "four parts", "reuse", "customised"):
            self.assertIn(word, notes)
        self.assertEqual(upgrade.notes_between("1.1.4", "1.1.4"), [])
        self.assertEqual(upgrade.notes_between("1.0.0", "1.1.4"), NOTES_1_1_X)
        self.assertEqual(len(NOTES_1_1_X), 13, "the 1.1.x notes are frozen: 4 for 1.1.0 and 9 for 1.1.4")
        roadmap = text(ROOT / "docs" / "roadmap" / "repo-review-2026-11.md")
        for word in ("## Versioning", "2.0", "run-wave --fix"):
            self.assertIn(word, roadmap)


if __name__ == "__main__":
    unittest.main()
