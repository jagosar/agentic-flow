"""Acceptance tests of agentic-flow 2.4.1: AC-001 .. AC-004 of docs/architecture/0011.

Run: python3 -m unittest discover -s .claude/bin -p test_acceptance_v241.py
The fix prompt is read from the spec and rendered by both engines in the simulated conformance world. Nothing is spent.
"""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parent
ROOT = BIN.parents[1]
sys.path.insert(0, str(BIN))
import agentic  # noqa: E402
import upgrade  # noqa: E402
from test_pipeline import CONFORMANCE, run_scenario  # noqa: E402

SENTENCE = ("A defect in a file no package owns (for example, a caller your change broke) is fixed from your own files: "
            "keep that caller working with a compatible change, such as a default for a new parameter or a wrapper "
            "that keeps the old signature, unless section 6 explicitly forbids it. Return BLOCKED only when no "
            "compatible change exists in your files.")
OLD_FIX = ("Fix {wp}. Your brief is {brief}. The code already exists. These are the defects the judges (reviewer, QA "
           "and verification) attribute to your package, as JSON:\n{defects}\nStay within the contract, do not touch "
           "other packages' files or the acceptance tests, and keep the acceptance tests of your criteria green."
           "{retry}{rules}")
SCENARIO = "verification fails on a package: it is fixed and verified again"
FIX_KEY = "implementer:WP-02 (fix)#1"
OLD_NOTE_KEYS = ["1.1.0", "1.1.4", "2.0.0", "2.1.0", "2.2.0", "2.3.0", "2.4.0"]
PINNED = ["test_acceptance_v2.py", "test_acceptance_v21.py", "test_acceptance_v22.py", "test_acceptance_v23.py",
          "test_acceptance_v24.py"]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def fix_template():
    return json.loads(read(".claude/workflows/pipeline-spec.json"))["prompts"]["fix"]


class FixPromptTests(unittest.TestCase):
    def test_ac_001_the_sentence_sits_after_green_and_before_retry(self):
        template = fix_template()
        self.assertIn("criteria green. " + SENTENCE + "{retry}", template)
        rendered = agentic.render_prompt({}, "fix", "WP-01", defects="[]", retry="")
        self.assertIn(SENTENCE, rendered)

    def test_ac_001_nothing_else_changes(self):
        self.assertEqual(fix_template().replace(" " + SENTENCE, "", 1), OLD_FIX)


class EnginesTests(unittest.TestCase):
    def test_ac_002_python_engine_sends_it(self):
        by_name = {d["name"]: d for d in CONFORMANCE["scenarios"]}
        prompt = run_scenario(by_name[SCENARIO])["prompts"][FIX_KEY]
        self.assertIn(SENTENCE, prompt)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_ac_002_both_engines_send_the_same_prompt(self):
        r = subprocess.run(["node", str(BIN / "test_workflow.mjs"), "--dump"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        node = json.loads(r.stdout)[SCENARIO]["prompts"][FIX_KEY]
        by_name = {d["name"]: d for d in CONFORMANCE["scenarios"]}
        python = run_scenario(by_name[SCENARIO])["prompts"][FIX_KEY]
        self.assertIn(SENTENCE, node)
        self.assertEqual(node, python)


class ImplementerTests(unittest.TestCase):
    def setUp(self):
        self.text = read(".claude/agents/implementer.md")

    def test_ac_003_blocked_bullet(self):
        bullet = next(line for line in self.text.splitlines() if line.startswith("- `BLOCKED`:"))
        self.assertIn("not a reason to stop", bullet)
        self.assertIn("explicitly forbids", bullet)

    def test_ac_003_guardrails_paragraph(self):
        paragraph = next(line for line in self.text.splitlines() if line.startswith("A hook blocks any write"))
        self.assertIn("A hook blocks any write outside your WP's files", paragraph)
        self.assertIn("If a block stops you from finishing", paragraph)
        self.assertIn("never yours to edit", paragraph)
        self.assertIn("yours to keep working", paragraph)


class ReleaseTests(unittest.TestCase):
    def test_ac_004_version_note_roadmap(self):
        self.assertEqual(json.loads(read(".claude-plugin/plugin.json"))["version"], "2.5.0")
        notes = upgrade.NOTES["2.4.1"]
        self.assertEqual(len(notes), 1)
        self.assertIn("implementer.md", notes[0])
        self.assertIn("compatible", notes[0])
        self.assertEqual(sorted(upgrade.NOTES), OLD_NOTE_KEYS + ["2.4.1", "2.5.0"])
        self.assertEqual([len(upgrade.NOTES[v]) for v in ("2.4.0", "2.3.0", "2.2.0", "2.1.0", "2.0.0")],
                         [2, 2, 2, 4, 7])
        for name in PINNED + ["test_acceptance_upgrade.py"]:
            with self.subTest(pin=name):
                text = read(f".claude/bin/{name}")
                self.assertIn(', "2.5.0")', text)
                self.assertNotIn(', "2.4.1")', text)
        roadmap = read("docs/roadmap/repo-review-2026-11.md")
        entry = next(line for line in roadmap.splitlines()
                     if line.startswith("- A confirmed finding on a file nobody owns"))
        self.assertIn("Fixed in 2.4.1", entry)


if __name__ == "__main__":
    unittest.main()
