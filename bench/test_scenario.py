"""Unit tests of scenario.py with a fake `claude` written per test: what reaches the agent, how a report is judged,
and the command line. No real agent session."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("bench_scenario", HERE / "scenario.py")
scenario = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scenario)

SCENARIO = HERE / "scenarios" / "auditor-wrong-expected"
FAKE = """import json, os, sys
prompt = sys.stdin.read()
log = os.environ.get("FAKE_SCENARIO_LOG")
if log:
    agent = os.path.join(".claude", "agents", "test-auditor.md")
    with open(log, "w", encoding="utf-8") as f:
        json.dump({"argv": sys.argv[1:], "prompt": prompt, "cwd_files": sorted(os.listdir(".")),
                   "agent": open(agent, encoding="utf-8").read()}, f)
print(OUTPUT)
"""


def blocking(problem, evidence, severity="critical"):
    return {"severity": severity, "wp": "AT", "file": "acceptance/test_schedule.py", "problem": problem,
            "evidence": evidence}


def report(status, findings):
    return {"status": status, "findings": findings, "not_checked": []}


class Case(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="fake-scenario-"))
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.log = self.dir / "log.json"

    def fake(self, output):
        script = self.dir / "fake.py"
        script.write_text(FAKE.replace("OUTPUT", repr(output)), encoding="utf-8")
        return [sys.executable, str(script)]

    def run_with(self, rep, **kwargs):
        output = json.dumps({"structured_output": rep}) if isinstance(rep, dict) else rep
        with unittest.mock.patch.dict("os.environ", FAKE_SCENARIO_LOG=str(self.log)):
            return scenario.run(SCENARIO, claude=self.fake(output), **kwargs)

    def call(self):
        return json.loads(self.log.read_text(encoding="utf-8"))


class RunTests(Case):
    def test_a_blocking_finding_naming_the_criterion_and_value_meets_the_expectation(self):
        result = self.run_with(report("FAIL", [blocking("AC-009 expects 960", "the test asserts 1440")]))
        self.assertTrue(result["met"])
        self.assertEqual(result["expect"], {"status": "FAIL", "finding_mentions": ["AC-009", "960"]})

    def test_a_pass_does_not_meet_it(self):
        self.assertFalse(self.run_with(report("PASS", []))["met"])

    def test_a_medium_finding_or_one_missing_a_mention_does_not_meet_it(self):
        self.assertFalse(self.run_with(report("FAIL", [blocking("AC-009 expects 960", "x", "medium")]))["met"])
        self.assertFalse(self.run_with(report("FAIL", [blocking("AC-009 is weak", "a stub passes")]))["met"])

    def test_a_bad_answer_gives_no_report_and_never_raises(self):
        for output in ("not json", json.dumps({"structured_output": {"status": "FAIL"}}), json.dumps({"x": 1})):
            with self.subTest(output=output):
                result = self.run_with(output)
                self.assertEqual((result["report"], result["met"]), (None, False))

    def test_the_agent_runs_read_only_and_isolated_with_the_rendered_prompt(self):
        self.run_with(report("PASS", []))
        call = self.call()
        argv = call["argv"]
        self.assertEqual(argv[:2], ["--setting-sources", "project,local"])
        self.assertEqual(argv[argv.index("--agent") + 1], "test-auditor")
        self.assertEqual(argv[argv.index("--allowedTools") + 1:], ["Read", "Glob", "Grep", "StructuredOutput"])
        self.assertNotIn("acceptEdits", argv)
        self.assertNotIn("{brief}", call["prompt"])
        self.assertIn("brief.md", call["prompt"])
        self.assertIn("acceptance/test_schedule.py::test_minutes_worked", call["prompt"])
        self.assertEqual(call["cwd_files"], [".claude", "acceptance", "brief.md"], "scenario.json never reaches it")

    def test_an_agent_file_replaces_the_definition_the_agent_reads(self):
        old = self.dir / "old.md"
        old.write_text("an older auditor\n", encoding="utf-8")
        self.run_with(report("PASS", []), agent_file=old)
        self.assertEqual(self.call()["agent"], "an older auditor\n")
        self.run_with(report("PASS", []))
        self.assertIn("**Wrong:**", self.call()["agent"])


class CommandLineTests(Case):
    def main(self, *args):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            return scenario.main(list(args)), err.getvalue()

    def test_usage_errors_exit_1(self):
        for args in ([], [str(self.dir)], [str(SCENARIO), "--agent-file"], [str(SCENARIO), "--agent-file", "nope.md"]):
            with self.subTest(args=args):
                code, err = self.main(*args)
                self.assertEqual(code, 1)
                self.assertIn("Uso: scenario.py DIR [--agent-file PATH]", err)


if __name__ == "__main__":
    unittest.main()
