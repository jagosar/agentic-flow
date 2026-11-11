"""Unit tests of variant.py: a variant is built in a copy, applied whole or not at all, and the checkout is untouched.
No agent runs."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("bench_variant", HERE / "variant.py")
variant = importlib.util.module_from_spec(spec)
spec.loader.exec_module(variant)

IMPLEMENTER = """---
name: implementer
---

# Rules

4. **Conventions.** Follow section 7, the style of the existing code and the rules printed in your prompt.
5. **No new dependencies.**

# Before writing

Is it already in this codebase? Does the standard library do it? Then grep every caller.

# Statuses

DONE.
"""


class Case(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="variant-test-"))
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def source(self, implementer=IMPLEMENTER, constants=None):
        src = self.dir / "src"
        (src / ".claude/agents").mkdir(parents=True)
        (src / ".claude/workflows").mkdir(parents=True)
        (src / ".claude/agents/implementer.md").write_text(implementer, encoding="utf-8")
        (src / ".claude/workflows/pipeline-spec.json").write_text(
            json.dumps({"constants": constants or {"implementer_rules": True, "escalation_model": "opus",
                                                   "advisor_model": None}}), encoding="utf-8")
        (src / ".gitignore").write_text(".claude/state/\n", encoding="utf-8")
        (src / ".claude/state").mkdir()
        (src / ".claude/state/ledger.json").write_text("{}", encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=src, check=True)
        subprocess.run(["git", "add", ".claude/agents", ".gitignore"], cwd=src, check=True)
        return src


class BuildTests(Case):
    def test_the_variant_is_applied_to_a_copy(self):
        src = self.source()
        out = variant.build("implementer-no-standards", self.dir / "v", src=src)
        spec_json = json.loads((out / ".claude/workflows/pipeline-spec.json").read_text(encoding="utf-8"))
        self.assertIs(spec_json["constants"]["implementer_rules"], False, "an untracked new file is copied too")
        text = (out / ".claude/agents/implementer.md").read_text(encoding="utf-8")
        self.assertNotIn("# Before writing", text)
        self.assertNotIn("grep every caller", text)
        self.assertIn(variant.CONVENTIONS, text)
        self.assertIn("5. **No new dependencies.**", text)
        self.assertIn("# Statuses", text)
        self.assertFalse((out / ".claude/state").exists(), "ignored state is never copied")
        self.assertEqual((src / ".claude/agents/implementer.md").read_text(encoding="utf-8"), IMPLEMENTER)

    def test_a_definition_without_what_the_variant_removes_is_refused(self):
        src = self.source(IMPLEMENTER.replace("# Before writing", "# Something else"))
        with self.assertRaises(ValueError):
            variant.build("implementer-no-standards", self.dir / "v", src=src)

    def test_the_advisor_variant_sets_the_advisor_and_turns_escalation_off(self):
        src = self.source()
        out = variant.build("advisor-opus", self.dir / "v", src=src)
        constants = json.loads((out / ".claude/workflows/pipeline-spec.json").read_text(encoding="utf-8"))["constants"]
        self.assertEqual(constants, {"implementer_rules": True, "escalation_model": None, "advisor_model": "opus"})
        self.assertEqual((out / ".claude/agents/implementer.md").read_text(encoding="utf-8"), IMPLEMENTER)
        mine = json.loads((src / ".claude/workflows/pipeline-spec.json").read_text(encoding="utf-8"))["constants"]
        self.assertIsNone(mine["advisor_model"], "the source is untouched")

    def test_a_spec_without_the_model_constants_is_refused(self):
        src = self.source(constants={"implementer_rules": True})
        with self.assertRaises(ValueError):
            variant.build("advisor-opus", self.dir / "v", src=src)

    def test_this_checkout_builds_both_variants(self):
        for name in sorted(variant.VARIANTS):
            with self.subTest(name=name):
                out = variant.build(name, self.dir / name)
                self.assertTrue((out / ".claude/bin/agentic.py").is_file())

    def test_an_existing_folder_or_an_unknown_name_is_refused(self):
        src = self.source()
        (self.dir / "taken").mkdir()
        with self.assertRaises(ValueError):
            variant.build("implementer-no-standards", self.dir / "taken", src=src)
        with self.assertRaises(ValueError):
            variant.build("no-such-variant", self.dir / "w", src=src)


class CommandLineTests(Case):
    def test_usage_errors_exit_1(self):
        for args in ([], ["implementer-no-standards"], ["no-such-variant", str(self.dir / "x")]):
            with self.subTest(args=args):
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    self.assertEqual(variant.main(args), 1)
                self.assertIn("Uso: variant.py NAME DST", err.getvalue())


if __name__ == "__main__":
    unittest.main()
