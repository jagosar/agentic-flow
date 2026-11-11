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
from datetime import datetime
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
        old.write_text("---\nname: reviewer\n---\nan older auditor\n", encoding="utf-8")
        self.run_with(report("PASS", []), agent_file=old)
        self.assertEqual(self.call()["agent"], "---\nname: test-auditor\n---\nan older auditor\n",
                         "the name is rewritten, or --agent would not find it")
        self.run_with(report("PASS", []))
        self.assertIn("**Wrong:**", self.call()["agent"])


class CommandLineTests(Case):
    def main(self, *args):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            return scenario.main(list(args)), err.getvalue()

    def test_usage_errors_exit_1(self):
        bad = ([], [str(self.dir)], [str(SCENARIO), "--agent-file"], [str(SCENARIO), "--agent-file", "nope.md"],
               [str(SCENARIO), "--repeat", "0"], [str(SCENARIO), "--repeat", "x"],
               [str(SCENARIO), "--against", "no.md"])
        for args in bad:
            with self.subTest(args=args):
                code, err = self.main(*args)
                self.assertEqual(code, 1)
                self.assertIn("Uso: scenario.py TARGET [--agent-file PATH] [--repeat N] [--against PATH] [--save]", err)

    def test_a_scenario_file_is_a_target_and_names_its_results(self):
        self.assertEqual(scenario.locate(SCENARIO / "scenario.json"), (SCENARIO, SCENARIO / "scenario.json"))
        self.assertEqual(scenario.scenario_name(SCENARIO), "auditor-wrong-expected")
        style = HERE / "scenarios" / "review-style" / "standards.json"
        self.assertEqual(scenario.scenario_name(style), "review-style-standards")


class ExpectationTests(unittest.TestCase):
    """met(): every kind of expectation, on reports built here."""

    def test_status_mentions_and_tier(self):
        reflex = {"tier": "reflex", "rule": "No magic numbers", "file": "a.py", "problem": "0.85", "evidence": "e"}
        found = {"status": "FAIL", "findings": [reflex]}
        self.assertTrue(scenario.met(found, {"status": "FAIL", "tier": "reflex", "finding_mentions": ["MAGIC"]}))
        self.assertFalse(scenario.met(found, {"status": "FAIL", "tier": "floor", "finding_mentions": ["magic"]}))
        self.assertFalse(scenario.met(found, {"status": "PASS"}))
        finish = {"status": "FAIL", "findings": [dict(reflex, tier="finish")]}
        self.assertFalse(scenario.met(finish, {"finding_mentions": ["magic"]}), "a finish finding is not blocking")

    def test_no_blocking_equals_and_min(self):
        self.assertTrue(scenario.met({"status": "PASS", "findings": [{"tier": "finish"}]}, {"no_blocking": True}))
        self.assertFalse(scenario.met({"status": "PASS", "findings": [{"tier": "floor"}]}, {"no_blocking": True}))
        verdict = {"is_real": False, "confidence": 0.8}
        self.assertTrue(scenario.met(verdict, {"equals": {"is_real": False}, "min": {"confidence": 0.7}}))
        self.assertFalse(scenario.met(verdict, {"min": {"confidence": 0.9}}))
        self.assertFalse(scenario.met({"is_real": False}, {"min": {"confidence": 0.1}}))

    def test_text_mentions_need_the_text_answer(self):
        answer = "VERDICT: FIX ... parse() returns None"
        self.assertTrue(scenario.met(None, {"text_mentions": ["fix", "PARSE"]}, answer))
        self.assertFalse(scenario.met(None, {"text_mentions": ["fix"]}, None))
        self.assertFalse(scenario.met(None, {"status": "PASS"}, "PASS"))

    def test_all_verdicts_needs_one_and_every_one(self):
        both = {"status": "PASS", "verdicts": [{"fingerprint": "F1", "verdict": "ADDRESSED"},
                                               {"fingerprint": "F2", "verdict": "ADDRESSED"}]}
        self.assertTrue(scenario.met(both, {"status": "PASS", "all_verdicts": "ADDRESSED"}))
        mixed = dict(both, verdicts=[both["verdicts"][0], {"fingerprint": "F2", "verdict": "NOT_ADDRESSED"}])
        self.assertFalse(scenario.met(mixed, {"all_verdicts": "ADDRESSED"}))
        for verdicts in ([], None, "ADDRESSED", ["ADDRESSED"]):
            self.assertFalse(scenario.met({"verdicts": verdicts}, {"all_verdicts": "ADDRESSED"}), verdicts)

    def test_fisher(self):
        self.assertEqual(scenario.fisher_p(2, 5, 5, 5), 0.083)
        self.assertEqual(scenario.fisher_p(5, 5, 5, 5), 1.0)
        self.assertEqual(scenario.fisher_p(0, 3, 3, 3), 0.05)


class PromptTests(Case):
    """The prompt and the command a scenario file asks for."""

    def scenario_file(self, meta):
        folder = self.dir / "sc"
        (folder / "src").mkdir(parents=True)
        (folder / "src" / "a.py").write_text("a = 1\n", encoding="utf-8")
        (folder / "scenario.json").write_text(json.dumps(meta), encoding="utf-8")
        (folder / "other.json").write_text("{}", encoding="utf-8")
        return folder

    def test_rules_suffix_and_text_mode(self):
        folder = self.scenario_file({"agent": "plan-reviewer", "prompt_text": "Review it.{rules}", "rules": ["common"],
                                     "suffix": " SUFFIX", "schema": False, "model": "opus",
                                     "expect": {"text_mentions": ["fix"]}})
        script = self.dir / "text.py"
        script.write_text(FAKE.replace("print(OUTPUT)", "print(json.dumps({'result': 'VERDICT: FIX'}))")
                          .replace("'test-auditor.md'", "'plan-reviewer.md'"), encoding="utf-8")
        with unittest.mock.patch.dict("os.environ", FAKE_SCENARIO_LOG=str(self.log)):
            result = scenario.run(folder, claude=[sys.executable, str(script)])
        self.assertTrue(result["met"])
        self.assertEqual(result["text"], "VERDICT: FIX")
        call = self.call()
        self.assertNotIn("--json-schema", call["argv"])
        self.assertEqual(call["argv"][call["argv"].index("--model") + 1], "opus")
        self.assertIn("--- .claude/rules-library/common.md ---", call["prompt"])
        self.assertTrue(call["prompt"].startswith("Review it.\nRules you must follow"))
        self.assertTrue(call["prompt"].endswith(" SUFFIX"))
        self.assertEqual(call["cwd_files"], [".claude", "src"], "no scenario file reaches the agent")


class ScenarioSetTests(unittest.TestCase):
    """From test_acceptance_v213 ac_010 and ac_011: the saved scenarios name real agents and prompts, and an old
    definition can be run against a new one."""

    BASE = HERE / "scenarios"
    SPEC = json.loads((HERE.parent / ".claude/workflows/pipeline-spec.json").read_text(encoding="utf-8"))

    def test_every_scenario_names_a_real_agent_prompt_and_schema(self):
        files = sorted(p for d in self.BASE.iterdir() if d.is_dir() for p in d.glob("*.json"))
        self.assertGreaterEqual(len(files), 8)
        for path in files:
            with self.subTest(path=path.relative_to(self.BASE)):
                meta = json.loads(path.read_text(encoding="utf-8"))
                self.assertTrue((HERE.parent / ".claude/agents" / f"{meta['agent']}.md").is_file())
                self.assertTrue(meta.get("prompt") in self.SPEC["prompts"] or meta.get("prompt_text"))
                if meta.get("schema", True):
                    self.assertIn(meta.get("schema_name", meta["agent"]), self.SPEC["schemas"])
        self.assertFalse(list(self.BASE.rglob("__init__.py")))

    def test_the_expectations_of_the_review_scenarios(self):
        load = lambda rel: json.loads((self.BASE / rel).read_text(encoding="utf-8"))  # noqa: E731
        self.assertIn("0.85", (self.BASE / "review-style/src/pricing.py").read_text(encoding="utf-8"))
        self.assertEqual(load("review-style/standards.json")["expect"],
                         {"status": "FAIL", "tier": "reflex", "finding_mentions": ["magic"]})
        self.assertEqual(load("review-style/spec.json")["expect"], {"status": "PASS", "no_blocking": True})
        self.assertEqual(load("verifier-inferred/scenario.json")["expect"],
                         {"equals": {"is_real": False}, "min": {"confidence": 0.7}})
        plan = load("plan-inferred-row/scenario.json")
        self.assertEqual((plan["schema"], plan["model"]), (False, "opus"))
        self.assertEqual(plan["expect"], {"text_mentions": ["FIX", "parse"]})
        arch = (self.BASE / "plan-inferred-row/architecture.md").read_text(encoding="utf-8")
        self.assertRegex(arch, r"\|\s*inferred\s*\|")

    def test_the_re_review_scenario_carries_its_finding_and_both_fixes(self):
        sys.path.insert(0, str(HERE.parent / ".claude" / "bin"))
        import findings
        for name, verdict in (("fixed", "ADDRESSED"), ("unfixed", "NOT_ADDRESSED")):
            meta = json.loads((self.BASE / "re-review" / f"{name}.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["expect"]["all_verdicts"], verdict)
            [open_] = json.loads(meta["values"]["findings"])
            self.assertEqual(open_["fingerprint"], findings.fingerprint(open_))
            diff = self.BASE / "re-review" / meta["values"]["diffs"]
            self.assertTrue(diff.is_file(), diff)
            self.assertIn(f"+++ b/{name}/src/pricing.py", diff.read_text(encoding="utf-8"))
        fixed = (self.BASE / "re-review/fixed/src/pricing.py").read_text(encoding="utf-8")
        unfixed = (self.BASE / "re-review/unfixed/src/pricing.py").read_text(encoding="utf-8")
        self.assertIn(">= DISCOUNT_FROM_CENTS", fixed)
        self.assertIn("> DISCOUNT_FROM_CENTS", unfixed)
        self.assertNotIn(">= DISCOUNT_FROM_CENTS", unfixed)

    def fake(self, d):
        script = d / "fake.py"
        script.write_text(
            "import json, os, sys\nsys.stdin.read()\n"
            "text = open(os.path.join('.claude', 'agents', 'verifier.md'), encoding='utf-8').read()\n"
            "new = 'NEW-VERIFIER' in text\n"
            "report = {'is_real': not new, 'confidence': 0.9 if new else 0.5, 'reasoning': 'r'}\n"
            "print(json.dumps({'structured_output': report, 'result': 'done'}))\n", encoding="utf-8")
        return [sys.executable, str(script)]

    def test_an_old_definition_against_a_new_one_and_saved_results(self):
        d = Path(tempfile.mkdtemp(prefix="scenario-set-"))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        target = d / "refute-me"
        (target / "src").mkdir(parents=True)
        (target / "src" / "a.py").write_text("a = 1\n", encoding="utf-8")
        (target / "scenario.json").write_text(json.dumps({
            "agent": "verifier", "prompt": "verifier", "values": {"finding": "{}"},
            "expect": {"equals": {"is_real": False}, "min": {"confidence": 0.7}}}), encoding="utf-8")
        old, new = d / "old.md", d / "new.md"
        old.write_text("---\nname: verifier\nmodel: sonnet\n---\nOLD\n", encoding="utf-8")
        new.write_text("---\nname: verifier\nmodel: sonnet\n---\nNEW-VERIFIER\n", encoding="utf-8")
        claude = self.fake(d)
        result = scenario.compare(target, 2, against=old, claude=claude, agent_file=new)
        self.assertEqual((result["old"]["met"], result["new"]["met"]), (0, 2))
        self.assertEqual(set(scenario.run(target, claude=claude, agent_file=new)), {"report", "expect", "met", "text"})
        results = d / "results"
        code = scenario.main([str(target), "--repeat", "2", "--agent-file", str(new), "--save"],
                             now=datetime(2026, 1, 2, 3, 4, 5), results=results, claude=claude)
        self.assertEqual(code, 0)
        saved = results / "refute-me-20260102-030405.json"
        self.assertEqual(json.loads(saved.read_text(encoding="utf-8"))["met"], 2)


if __name__ == "__main__":
    unittest.main()
