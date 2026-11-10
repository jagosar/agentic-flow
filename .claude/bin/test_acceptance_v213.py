"""Acceptance tests of agentic-flow 2.13.0: AC-001 .. AC-012 of docs/architecture/0020 (two review axes, tiers and
waivers, the provenance of section 4b, printed rules, the bench's prompt tests, 2.12.0's acceptance file retired).

Run: python3 -m unittest discover -s .claude/bin -p test_acceptance_v213.py
Engines run on conformance scenarios with simulated agents; commands run in temporary projects with a fake `claude`.
Nothing is spent.
"""
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

BIN = Path(__file__).resolve().parent
ROOT = BIN.parents[1]
sys.path.insert(0, str(BIN))
from test_agentic import MANIFEST, Repo, testutil  # noqa: E402

CONFORMANCE = json.loads((BIN / "conformance.json").read_text(encoding="utf-8"))
RULE = "No magic numbers"
WAIVER = {"rule": "No magic numbers", "scope": "src/b/x.py", "reason": "ana: tax table constants are the spec"}


def scenario(name):
    import test_pipeline
    decl = next(d for d in CONFORMANCE["scenarios"] if d["name"] == name)
    return test_pipeline.run_scenario(decl)


def node_agrees(test):
    if not shutil.which("node"):
        test.skipTest("node is not installed")
    r = subprocess.run(["node", str(BIN / "test_workflow.mjs")], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    test.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-3000:])


def prompts_of(summary, agent):
    return [p for k, p in summary["prompts"].items() if k.startswith(agent + ":")]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AxesTests(unittest.TestCase):
    def test_ac_001_two_axes(self):
        s = scenario("the two axes keep separate lists")
        self.assertEqual((s["result"], s["fix_cycles"]), ("OK", 1))
        self.assertIn("reviewer:reviewer", s["agents"])
        self.assertIn("standards-reviewer:standards-reviewer", s["agents"])
        fix1 = [p for k, p in s["prompts"].items() if k.startswith("implementer:WP-01") and "Fix WP-01" in p]
        fix2 = [p for k, p in s["prompts"].items() if k.startswith("implementer:WP-02") and "Fix WP-02" in p]
        self.assertTrue(fix1 and fix2, s["prompts"].keys())
        self.assertIn('"axis":"spec"', fix1[0])
        self.assertNotIn('"axis":"standards"', fix1[0])
        self.assertIn('"axis":"standards"', fix2[0])
        self.assertNotIn('"axis":"spec"', fix2[0])
        node_agrees(self)

    def test_ac_002_tiers(self):
        reflex = scenario("a reflex finding blocks until it is fixed")
        self.assertEqual((reflex["result"], reflex["fix_cycles"]), ("OK", 1))
        waived = scenario("a waived reflex finding does not block and is recorded")
        self.assertEqual((waived["result"], waived["fix_cycles"]), ("OK", 0))
        self.assertFalse([a for a in waived["agents"] if a.startswith("verifier:")])
        self.assertEqual(waived["review_axes"]["standards"], [0, 0, 0, 1])
        finish = scenario("a finish finding never blocks")
        self.assertEqual(finish["result"], "OK")
        self.assertFalse([a for a in finish["agents"] if a.startswith("verifier:")])
        self.assertEqual(finish["review_axes"]["spec"], [0, 0, 1])
        missing = scenario("the standards reviewer returned no report")
        self.assertEqual((missing["result"], missing["failed_stage"]), ("REVIEW", "review"))


class TierTests(unittest.TestCase):
    def test_ac_003_fallback_and_fix_sources(self):
        import findings
        blocking = ["critical", "high"]
        waiver = {"rule": "magic numbers", "scope": "src/", "reason": "ana: constants of the tax table"}
        reflex = {"tier": "reflex", "rule": RULE, "file": "src/a.py"}
        self.assertTrue(findings.blocks({"severity": "high"}, blocking, [waiver]))
        self.assertFalse(findings.blocks({"severity": "low"}, blocking, [waiver]))
        self.assertFalse(findings.blocks({"tier": "finish", "severity": "critical"}, blocking, [waiver]))
        self.assertTrue(findings.blocks(reflex, blocking))
        self.assertFalse(findings.blocks(reflex, blocking, [waiver]))

        repo = Repo()
        self.addCleanup(repo.cleanup)
        logs = Path(tempfile.mkdtemp(prefix="fake-logs-"))
        bindir = Path(tempfile.mkdtemp(prefix="fake-claude-"))
        self.addCleanup(shutil.rmtree, logs, ignore_errors=True)
        self.addCleanup(shutil.rmtree, bindir, ignore_errors=True)
        repo.env.update(AGENTIC_CLAUDE=testutil.install_fake_claude(bindir), FAKE_LOG_DIR=str(logs))
        floor = {"tier": "floor", "severity": "high", "wp": "WP-02", "file": "src/b/x.py", "problem": "FLOOR-ONE",
                 "evidence": "e", "fix": "f", "if_skipped": "s", "provenance": "read"}
        rule_hit = {"tier": "reflex", "rule": RULE, "wp": "WP-02", "file": "src/b/x.py", "problem": "REFLEX-ONE",
                    "evidence": "e", "fix": "f", "if_skipped": "s", "provenance": "read"}
        note = dict(rule_hit, tier="finish", problem="FINISH-ONE")
        repo.write(".claude/state/runs/REVIEW.json", json.dumps({"structured_output": {
            "status": "FAIL", "findings": [floor], "needs_validation": [], "not_checked": []}}))
        repo.write(".claude/state/runs/STANDARDS.json", json.dumps({"structured_output": {
            "status": "FAIL", "axis": "standards", "findings": [rule_hit, note], "not_checked": []}}))
        r = repo.run("run-wave", "1", "WP-02", "--fix")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        prompt = testutil.fake_calls(logs, "WP-02")[-1]["prompt"]
        self.assertIn("FLOOR-ONE", prompt)
        self.assertIn("REFLEX-ONE", prompt)
        self.assertNotIn("FINISH-ONE", prompt)

        manifest = json.loads(json.dumps(MANIFEST))
        manifest["waivers"] = [{"rule": RULE, "scope": "src/b/", "reason": "ana: constants of the tax table"}]
        waived = Repo(manifest)
        self.addCleanup(waived.cleanup)
        shutil.copytree(ROOT / ".claude/rules-library", waived.dir / ".claude/rules-library")
        waived.env.update(repo.env, CLAUDE_PROJECT_DIR=str(waived.dir))
        for name in ("REVIEW.json", "STANDARDS.json"):
            text = (repo.dir / ".claude/state/runs" / name).read_text(encoding="utf-8")
            waived.write(f".claude/state/runs/{name}", text)
        for args in (["--fix"], ["--fix", "--all"]):
            r = waived.run("run-wave", "1", "WP-02", *args)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            prompt = testutil.fake_calls(logs, "WP-02")[-1]["prompt"]
            self.assertIn("FLOOR-ONE", prompt)
            self.assertNotIn("REFLEX-ONE", prompt, args)


class PlanTests(unittest.TestCase):
    def project(self, waivers=None, arch=None):
        manifest = json.loads(json.dumps(MANIFEST))
        if waivers is not None:
            manifest["waivers"] = waivers
        repo = Repo(manifest)
        self.addCleanup(repo.cleanup)
        shutil.copytree(ROOT / ".claude/rules-library", repo.dir / ".claude/rules-library")
        if arch is not None:
            text = (repo.dir / "architecture.md").read_text(encoding="utf-8")
            repo.write("architecture.md", text.replace("# A\n", "# A\n\n" + arch + "\n", 1))
        return repo

    def test_ac_004_waivers(self):
        for waivers in (None, [WAIVER]):
            r = self.project(waivers).run("validate")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        bad = [([dict(WAIVER, scope="src/")], 'waivers[0]: scope "src/" is wider than any package\'s files'),
               ([dict(WAIVER, scope="**")], 'waivers[0]: scope "**" must be one file or one folder ending in "/"'),
               ([dict(WAIVER, reason="because")], 'waivers[0]: reason must be "<who decided>: <evidence>"'),
               ([dict(WAIVER, rule="no such rule at all")],
                'waivers[0]: rule "no such rule at all" is not in the installed rules'),
               ([WAIVER, WAIVER], "waivers[1]: repeats waivers[0]")]
        for waivers, message in bad:
            with self.subTest(message=message):
                r = self.project(waivers).run("validate")
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn(message, r.stderr)

    def table(self, *rows, source=True):
        head = "| What | Where | Rule |" + (" Source |" if source else "")
        sep = "|---|---|---|" + ("---|" if source else "")
        return "## 4b. Existing code context\n" + "\n".join([head, sep, *rows]) + "\n\n## 5. Data model\n"

    def test_ac_005_provenance(self):
        cases = [(self.table("| a | `src/a.py:1-3` | r |", source=False), 0,
                  "warning: section 4b has no Source column: mark each row read or inferred"),
                 (self.table("| a | `src/a.py:1-3` | r | read |", "| b | nowhere | r | inferred |"), 0, None),
                 (self.table("| a | `src/a.py:1-9` | r | read |"), 1,
                  "section 4b, row 1: src/a.py:1-9 does not exist or is out of range"),
                 (self.table("| a | nowhere | r | read |"), 1, "section 4b, row 1: read needs a file:line"),
                 (self.table("| a | `src/a.py:1-3` | r | seen |"), 1,
                  "section 4b, row 1: Source must be read or inferred")]
        for arch, code, message in cases:
            with self.subTest(message=message):
                repo = self.project(arch=arch)
                repo.write("src/a.py", "a = 1\nb = 2\nc = 3\n")
                r = repo.run("validate")
                self.assertEqual(r.returncode, code, r.stdout + r.stderr)
                if message:
                    self.assertIn(message, r.stdout + r.stderr)
                elif code == 0:
                    self.assertNotIn("section 4b", r.stdout)
                if "1-9" in arch:
                    plan = repo.run("pipeline-plan")
                    self.assertEqual(plan.returncode, 1)
                    self.assertIn(message, plan.stderr)
                    self.assertEqual(repo.run("briefs").returncode, 0, "only validate and pipeline-plan check it")
        for arch in ("", "## 4b. Existing code context\nNo table here.\n\n## 5. Data model\n"):
            self.assertEqual(self.project(arch=arch).run("validate").returncode, 0)


class RulesTests(unittest.TestCase):
    def test_ac_006_printed_rules(self):
        import findings
        manifest = dict(MANIFEST, stack=["python"])
        repo = Repo(manifest)
        self.addCleanup(repo.cleanup)
        shutil.copytree(ROOT / ".claude/rules-library", repo.dir / ".claude/rules-library")
        self.assertEqual(repo.run("rules-sync").returncode, 0)
        plan = json.loads(repo.run("pipeline-plan").stdout.splitlines()[-1])
        text = plan["rules_text"]
        self.assertTrue(text.startswith("\nRules you must follow (common and language). They are printed here, "
                                        "so do not read them from disk:"), text[:200])
        self.assertIn("--- .claude/rules/agentic/common.md ---", text)
        self.assertIn(RULE, text)
        self.assertNotIn("paths:", text)
        self.assertEqual(plan["rules_sum"], findings.text_sum(text))
        logs = Path(tempfile.mkdtemp(prefix="fake-logs-"))
        bindir = Path(tempfile.mkdtemp(prefix="fake-claude-"))
        self.addCleanup(shutil.rmtree, logs, ignore_errors=True)
        self.addCleanup(shutil.rmtree, bindir, ignore_errors=True)
        repo.env.update(AGENTIC_CLAUDE=testutil.install_fake_claude(bindir), FAKE_LOG_DIR=str(logs))
        self.assertEqual(repo.run("run-wave", "1").returncode, 0)
        self.assertIn(RULE, testutil.fake_calls(logs, "WP-01")[-1]["prompt"])
        bare = Repo()
        self.addCleanup(bare.cleanup)
        self.assertEqual(json.loads(bare.run("pipeline-plan").stdout.splitlines()[-1])["rules_text"], "")

        printed = scenario("printed rules reach the agents")
        self.assertEqual(printed["rules"], "printed")
        for agent in ("implementer", "reviewer", "standards-reviewer"):
            self.assertTrue(all("RULE-TEXT" in p for p in prompts_of(printed, agent)), agent)
        for agent in ("gatekeeper", "verifier"):
            self.assertFalse([p for p in prompts_of(printed, agent) if "RULE-TEXT" in p or "Rules you must" in p])
        damaged = scenario("rules text that arrives damaged falls back to the paths")
        self.assertEqual(damaged["rules"], "pointed")
        for agent in ("implementer", "reviewer", "standards-reviewer"):
            for p in prompts_of(damaged, agent):
                self.assertIn("Rules you must follow (language and common): .claude/rules/agentic/common.md", p)
                self.assertNotIn("RULE-TEXT", p)
        node_agrees(self)


class StandardsAgentTests(unittest.TestCase):
    def test_ac_007_agent(self):
        text = (ROOT / ".claude/agents/standards-reviewer.md").read_text(encoding="utf-8")
        head = text.split("---")[1]
        self.assertIn("model: sonnet", head)
        tools = {t.strip() for t in head.split("tools:")[1].splitlines()[0].split(",")}
        self.assertEqual(tools, {"Read", "Glob", "Grep", "Bash", "StructuredOutput"})

        repo = Repo()
        self.addCleanup(repo.cleanup)
        claim = "python3 .claude/bin/agentic.py claim "

        def hook(payload, agent_id, agent_type):
            return repo.run("hook", stdin=json.dumps(dict(payload, agent_id=agent_id, agent_type=agent_type)))
        bash = lambda cmd: {"tool_name": "Bash", "tool_input": {"command": cmd}}  # noqa: E731
        self.assertEqual(hook(bash(claim + "REVIEW"), "r1", "reviewer").returncode, 0)
        self.assertEqual(hook(bash(claim + "REVIEW"), "s1", "standards-reviewer").returncode, 0)
        write = {"tool_name": "Write", "tool_input": {"file_path": str(repo.dir / "src/a.py"), "content": "x = 1\n"}}
        self.assertEqual(hook(write, "s1", "standards-reviewer").returncode, 2)
        self.assertEqual(hook(bash(claim + "WP-01"), "i1", "implementer").returncode, 0)
        second = hook(bash(claim + "WP-01"), "i2", "implementer")
        self.assertEqual(second.returncode, 2)
        self.assertIn("was already claimed", second.stderr)

        logs = Path(tempfile.mkdtemp(prefix="fake-logs-"))
        bindir = Path(tempfile.mkdtemp(prefix="fake-claude-"))
        self.addCleanup(shutil.rmtree, logs, ignore_errors=True)
        self.addCleanup(shutil.rmtree, bindir, ignore_errors=True)
        project = Repo()
        self.addCleanup(project.cleanup)
        project.env.update(AGENTIC_CLAUDE=testutil.install_fake_claude(bindir), FAKE_LOG_DIR=str(logs))
        r = project.run("run-review")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        agents = sorted(c["argv"][c["argv"].index("--agent") + 1] for c in testutil.fake_calls(logs))
        self.assertEqual(agents, ["reviewer", "standards-reviewer"])
        for name in ("REVIEW.json", "STANDARDS.json"):
            self.assertTrue((project.dir / ".claude/state/runs" / name).is_file(), name)
        self.assertIn("REVIEW:", r.stdout)
        self.assertIn("STANDARDS:", r.stdout)
        ledger = json.loads((project.dir / ".claude/state/ledger.json").read_text(encoding="utf-8"))
        self.assertIn("REVIEW", ledger)
        self.assertIn("STANDARDS", ledger)


class DefinitionTests(unittest.TestCase):
    def read(self, rel):
        return (ROOT / ".claude" / rel).read_text(encoding="utf-8")

    def test_ac_008_definitions(self):
        reviewer = self.read("agents/reviewer.md")
        for phrase in ("# Tiers", "`tier`", "`provenance`", "the Standards axis"):
            self.assertIn(phrase, reviewer)
        self.assertNotIn("breaches of section 7", reviewer)
        standards = self.read("agents/standards-reviewer.md")
        for phrase in ("# Tiers", "reflex", "`rule`", "the rule's opening words", "Never report a floor",
                       "No concrete case, no finding"):
            self.assertIn(phrase, standards)
        for name in ("qa.md", "test-auditor.md"):
            text = self.read("agents/" + name)
            for phrase in ("`tier`", "floor", "finish"):
                self.assertIn(phrase, text, name)
        verifier = self.read("agents/verifier.md")
        self.assertIn("inferred", verifier)
        self.assertIn("Uncertainty never downgrades a blocker", verifier)
        plan_reviewer = self.read("agents/plan-reviewer.md")
        self.assertLess(plan_reviewer.index("inferred"), plan_reviewer.index("blind implementer"))
        self.assertIn("waivers", plan_reviewer)
        architect = self.read("commands/architect.md")
        for phrase in ("| Source |", "read", "inferred", "`waivers`"):
            self.assertIn(phrase, architect)
        implement = self.read("commands/implement.md")
        for phrase in ("Spec", "Standards", "waived"):
            self.assertIn(phrase, implement)
        for name in ("implementer.md", "test-author.md", "qa.md"):
            self.assertIn("the rules printed in your prompt", self.read("agents/" + name), name)
        for path in sorted((ROOT / ".claude/agents").glob("*.md")):
            self.assertNotIn("the rules your prompt points to", path.read_text(encoding="utf-8"), path.name)
        r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(BIN), "-p", "test_definitions.py"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 0, r.stderr[-3000:])


class MeasureTests(unittest.TestCase):
    def test_ac_009_variant(self):
        s = scenario("the implementer can be left without the rules")
        self.assertTrue(prompts_of(s, "implementer"))
        self.assertFalse([p for p in prompts_of(s, "implementer") if "RULE-TEXT" in p])
        for agent in ("reviewer", "standards-reviewer"):
            self.assertTrue(all("RULE-TEXT" in p for p in prompts_of(s, agent)), agent)
        variant = load("bench_variant", ROOT / "bench" / "variant.py")
        tmp = Path(tempfile.mkdtemp(prefix="variant-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        before = (ROOT / ".claude/agents/implementer.md").read_text(encoding="utf-8")
        out = variant.build("implementer-no-standards", tmp / "v")
        self.assertTrue((out / ".claude/bin/agentic.py").is_file())
        spec = json.loads((out / ".claude/workflows/pipeline-spec.json").read_text(encoding="utf-8"))
        self.assertIs(spec["constants"]["implementer_rules"], False)
        impl = (out / ".claude/agents/implementer.md").read_text(encoding="utf-8")
        for gone in ("# Before writing", "standard library", "grep every caller"):
            self.assertNotIn(gone, impl)
        self.assertIn("4. **Conventions.** Follow section 7 and the style of the existing code.", impl)
        self.assertIn("# Statuses", impl)
        mine = json.loads((ROOT / ".claude/workflows/pipeline-spec.json").read_text(encoding="utf-8"))
        self.assertIs(mine["constants"]["implementer_rules"], True)
        self.assertEqual((ROOT / ".claude/agents/implementer.md").read_text(encoding="utf-8"), before)
        with self.assertRaises(ValueError):
            variant.build("implementer-no-standards", tmp / "v")
        with self.assertRaises(ValueError):
            variant.build("no-such-variant", tmp / "w")

    def fake(self, d):
        script = d / "fake.py"
        script.write_text(
            "import json, os, sys\nsys.stdin.read()\n"
            "text = open(os.path.join('.claude', 'agents', 'verifier.md'), encoding='utf-8').read()\n"
            "new = 'NEW-VERIFIER' in text\n"
            "report = {'is_real': not new, 'confidence': 0.9 if new else 0.5, 'reasoning': 'r'}\n"
            "print(json.dumps({'structured_output': report, 'result': 'done'}))\n", encoding="utf-8")
        return [sys.executable, str(script)]

    def test_ac_010_old_against_new(self):
        runner = load("bench_scenario_v213", ROOT / "bench" / "scenario.py")
        d = Path(tempfile.mkdtemp(prefix="scenario-v213-"))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        target = d / "refute-me"
        (target / "src").mkdir(parents=True)
        (target / "src" / "a.py").write_text("a = 1\n", encoding="utf-8")
        (target / "scenario.json").write_text(json.dumps({
            "agent": "verifier", "prompt": "verifier", "values": {"finding": "{}"},
            "expect": {"equals": {"is_real": False}, "min": {"confidence": 0.7}}}), encoding="utf-8")
        old = d / "old.md"
        old.write_text("---\nname: verifier\nmodel: sonnet\n---\nOLD\n", encoding="utf-8")
        new = d / "new.md"
        new.write_text("---\nname: verifier\nmodel: sonnet\n---\nNEW-VERIFIER\n", encoding="utf-8")
        claude = self.fake(d)
        result = runner.compare(target, 2, against=old, claude=claude, agent_file=new)
        self.assertEqual((result["old"]["met"], result["old"]["total"]), (0, 2))
        self.assertEqual((result["new"]["met"], result["new"]["total"]), (2, 2))
        self.assertEqual(runner.fisher_p(2, 5, 5, 5), 0.083)
        single = runner.run(target, claude=claude, agent_file=new)
        self.assertEqual(set(single), {"report", "expect", "met", "text"})
        results = d / "results"
        code = runner.main([str(target), "--repeat", "2", "--agent-file", str(new), "--save"],
                           now=datetime(2026, 1, 2, 3, 4, 5), results=results, claude=claude)
        self.assertEqual(code, 0)
        saved = results / "refute-me-20260102-030405.json"
        self.assertTrue(saved.is_file())
        self.assertEqual(json.loads(saved.read_text(encoding="utf-8"))["met"], 2)

    def test_ac_011_scenarios(self):
        base = ROOT / "bench" / "scenarios"
        files = ["auditor-wrong-expected/scenario.json", "review-style/standards.json", "review-style/spec.json",
                 "review-contract/scenario.json", "verifier-inferred/scenario.json", "plan-inferred-row/scenario.json"]
        spec = json.loads((ROOT / ".claude/workflows/pipeline-spec.json").read_text(encoding="utf-8"))
        loaded = {}
        for rel in files:
            meta = json.loads((base / rel).read_text(encoding="utf-8"))
            loaded[rel] = meta
            self.assertTrue((ROOT / ".claude/agents" / f"{meta['agent']}.md").is_file(), rel)
            self.assertTrue(meta.get("prompt") in spec["prompts"] or meta.get("prompt_text"), rel)
        self.assertIn("0.85", (base / "review-style/src/pricing.py").read_text(encoding="utf-8"))
        self.assertEqual(loaded["review-style/standards.json"]["expect"],
                         {"status": "FAIL", "tier": "reflex", "finding_mentions": ["magic"]})
        self.assertEqual(loaded["review-style/spec.json"]["expect"], {"status": "PASS", "no_blocking": True})
        self.assertEqual(loaded["verifier-inferred/scenario.json"]["expect"],
                         {"equals": {"is_real": False}, "min": {"confidence": 0.7}})
        plan = loaded["plan-inferred-row/scenario.json"]
        self.assertEqual((plan["schema"], plan["model"]), (False, "opus"))
        self.assertEqual(plan["expect"], {"text_mentions": ["FIX", "parse"]})
        arch = (base / "plan-inferred-row/architecture.md").read_text(encoding="utf-8")
        self.assertRegex(arch, r"\|\s*inferred\s*\|")
        self.assertFalse(list(base.rglob("__init__.py")))


class ReleaseTests(unittest.TestCase):
    def test_ac_012_release(self):
        import installer
        import upgrade
        self.assertIn(".claude/bin/findings.py", installer.INSTALL_GLOBS)
        self.assertEqual(json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))["version"],
                         "2.13.0")
        notes = " ".join(upgrade.NOTES.get("2.13.0", []))
        for word in ("standards-reviewer", "tier", "waivers", "Source", "printed"):
            self.assertIn(word, notes)
        self.assertIn("standards-reviewer", (ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn("findings.py", (ROOT / "docs/how-it-works.md").read_text(encoding="utf-8"))
        bench_md = (ROOT / "docs/how-to/bench.md").read_text(encoding="utf-8")
        for word in ("scenario.py", "--against", "variant.py"):
            self.assertIn(word, bench_md)
        self.assertEqual(sorted(p.name for p in BIN.glob("test_acceptance*.py")), ["test_acceptance_v213.py"])
        import test_doctor
        import test_plan_picture
        self.assertTrue(hasattr(test_doctor, "ProjectStateTests"))
        self.assertTrue(hasattr(test_plan_picture, "CommandTests"))


if __name__ == "__main__":
    unittest.main()
