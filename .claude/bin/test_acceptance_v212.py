"""Acceptance tests of agentic-flow 2.12.0: AC-001 .. AC-007 of docs/architecture/0019 (doctor, plan-picture, the
test-auditor's wrong expected values, test_acceptance_v211.py retired).

Run: python3 -m unittest discover -s .claude/bin -p test_acceptance_v212.py
doctor and plan-picture run against temporary repositories; the scenario runner gets a fake `claude` script.
Nothing is spent.
"""
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parent
ROOT = BIN.parents[1]
sys.path.insert(0, str(BIN))
from test_agentic import MANIFEST, Repo  # noqa: E402

RETIRED = "Bash(python3 .claude/state/guard/bin/agentic.py:*)"
STOP = "python3 .claude/bin/agentic.py stop"


def last_json(text):
    return json.loads([line for line in text.splitlines() if line.startswith("{")][-1])


def snapshot(folder):
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(Path(folder).rglob("*"))
            if p.is_file() and ".git" not in p.parts}


class DoctorCase(unittest.TestCase):
    def repo(self):
        repo = Repo()
        self.addCleanup(repo.cleanup)
        return repo

    def stale(self):
        repo = self.repo()
        repo.write(".claude/state/guard/x", "old")
        settings = json.loads((repo.dir / ".claude/settings.json").read_text(encoding="utf-8"))
        settings["permissions"]["allow"].append(RETIRED)
        repo.write(".claude/settings.json", json.dumps(settings, indent=2) + "\n")
        repo.write(".claude/state/ledger.json", json.dumps({"WP-01": {"state": "running"}}))
        repo.write(".claude/state/upgrade/.claude/agents/qa.md", "new")
        return repo

    def clean(self):
        repo = self.repo()
        shutil.copytree(ROOT / ".claude/rules-library", repo.dir / ".claude/rules-library")
        version = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))["version"]
        repo.write(".claude/agentic-install.json", json.dumps({"version": version, "files": {}}))
        repo.write(".claude/quality-baseline.json", json.dumps({"version": 1, "flow_repo": False, "limits": {},
                                                                "exclude": [], "files": {}, "functions": {}}))
        self.assertEqual(repo.run("rules-sync").returncode, 0)
        return repo

    def doctor(self, repo, *args):
        r = repo.run("doctor", *args)
        return r.returncode, last_json(r.stdout)


class DoctorTests(DoctorCase):
    def test_ac_001_findings(self):
        repo = self.stale()
        before = snapshot(repo.dir)
        code, out = self.doctor(repo)
        self.assertEqual(code, 3)
        self.assertFalse(out["ok"])
        got = [(f["code"], f["severity"]) for f in out["findings"]]
        self.assertEqual(got, [("guard-leftover", "auto"), ("retired-permission", "auto"), ("install-record", "route"),
                               ("quality-baseline", "route"), ("agents-running", "route"),
                               ("upgrade-pending", "mention")])
        routes = {f["code"]: f["route"] for f in out["findings"] if f["severity"] == "route"}
        self.assertEqual(routes["install-record"], "/agentic-flow:init")
        self.assertEqual(routes["quality-baseline"], "python3 .claude/bin/agentic.py quality --init")
        self.assertEqual(routes["agents-running"], STOP)
        self.assertEqual(snapshot(repo.dir), before, "doctor without --fix writes nothing")

    def test_ac_002_fix(self):
        repo = self.stale()
        ledger = (repo.dir / ".claude/state/ledger.json").read_bytes()
        code, out = self.doctor(repo, "--fix")
        self.assertEqual(code, 3)
        self.assertEqual(out["fixed"], ["guard-leftover", "retired-permission"])
        self.assertFalse((repo.dir / ".claude/state/guard").exists())
        settings = json.loads((repo.dir / ".claude/settings.json").read_text(encoding="utf-8"))
        self.assertNotIn(RETIRED, settings["permissions"]["allow"])
        self.assertIn("Bash(python3 .claude/bin/agentic.py:*)", settings["permissions"]["allow"])
        self.assertIn("PreToolUse", settings["hooks"])
        self.assertEqual((repo.dir / ".claude/state/ledger.json").read_bytes(), ledger)
        self.assertTrue((repo.dir / ".claude/state/upgrade/.claude/agents/qa.md").exists())
        code, out = self.doctor(repo)
        self.assertEqual(code, 3)
        self.assertFalse([f for f in out["findings"] if f["severity"] == "auto"])

    def test_ac_003_clean(self):
        repo = self.clean()
        had_state = (repo.dir / ".claude/state").exists()
        code, out = self.doctor(repo)
        self.assertEqual((code, out["ok"], out["findings"]), (0, True, []), out)
        self.assertEqual((repo.dir / ".claude/state").exists(), had_state, "doctor creates nothing under state")
        self.assertFalse((repo.dir / ".claude/state/ledger.json").exists())
        repo.write(".claude/state/upgrade/a.md", "x")
        code, out = self.doctor(repo)
        self.assertEqual((code, out["ok"]), (0, True))
        self.assertEqual([f["code"] for f in out["findings"]], ["upgrade-pending"])
        flow = self.repo()
        (flow.dir / ".claude-plugin").mkdir()
        shutil.copy(ROOT / ".claude-plugin/plugin.json", flow.dir / ".claude-plugin/plugin.json")
        shutil.copy(ROOT / "README.md", flow.dir / "README.md")
        self.assertNotIn("install-record", [f["code"] for f in self.doctor(flow)[1]["findings"]])

    def test_ac_004_rules(self):
        repo = self.clean()
        common = repo.dir / ".claude/rules/agentic/common.md"
        common.write_text(common.read_text(encoding="utf-8") + "\nlocal edit\n", encoding="utf-8")
        repo.write(".claude/rules/agentic/ruby.md", "x")
        rules_before = snapshot(repo.dir / ".claude/rules")
        code, out = self.doctor(repo)
        found = [f for f in out["findings"] if f["code"] == "rules"]
        self.assertEqual(len(found), 1, out)
        self.assertIn("extra: ruby", found[0]["message"])
        self.assertIn("changed: common", found[0]["message"])
        self.assertEqual(found[0]["route"], "python3 .claude/bin/agentic.py rules-sync")
        self.assertEqual(snapshot(repo.dir / ".claude/rules"), rules_before)
        self.assertEqual(repo.run("rules-sync").returncode, 0)
        self.assertEqual(self.doctor(repo)[1]["findings"], [])


class PictureTests(unittest.TestCase):
    def test_ac_005_picture(self):
        manifest = dict(MANIFEST, work_packages=[
            {"id": "WP-01", "wave": 1, "depends_on": [], "files": ["src/a.py"], "acs": ["AC-001"]},
            {"id": "WP-02", "wave": 1, "depends_on": [], "files": ["src/<b>.py"], "acs": ["AC-002"]},
            {"id": "WP-03", "wave": 2, "depends_on": ["WP-01"], "files": ["src/c.py"], "acs": ["AC-003"]}])
        repo = Repo(manifest)
        self.addCleanup(repo.cleanup)
        r = repo.run("plan-picture")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(last_json(r.stdout), {"path": ".claude/state/plan.html", "packages": 3, "waves": 2})
        page = (repo.dir / ".claude/state/plan.html").read_bytes()
        self.assertEqual(repo.run("plan-picture").returncode, 0)
        self.assertEqual((repo.dir / ".claude/state/plan.html").read_bytes(), page, "deterministic")
        html = page.decode("utf-8")
        self.assertEqual(html.count("<svg"), 1)
        for wp in ("WP-01", "WP-02", "WP-03"):
            self.assertIn(f'<g id="wp-{wp}"', html)
            self.assertIn(f"<td>{wp}</td>", html)
        self.assertEqual(html.count('<line class="dep" data-from="WP-01" data-to="WP-03"'), 1)
        self.assertEqual(html.count('<line class="dep"'), 1)
        self.assertIn("src/&lt;b&gt;.py", html)
        self.assertNotIn("<script", html)
        self.assertNotIn("http", html)
        bad = Repo(dict(MANIFEST, work_packages=[{"id": "WP-01", "wave": 1, "files": ["architecture.md"]}]))
        self.addCleanup(bad.cleanup)
        self.assertEqual(bad.run("plan-picture").returncode, 1)
        self.assertFalse((bad.dir / ".claude/state/plan.html").exists())


def load_scenario():
    spec = importlib.util.spec_from_file_location("bench_scenario", ROOT / "bench" / "scenario.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AuditorTests(unittest.TestCase):
    def fake(self, report):
        d = Path(tempfile.mkdtemp(prefix="fake-auditor-"))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        script = d / "fake.py"
        script.write_text("import json, sys\nsys.stdin.read()\nprint(json.dumps(" + repr({"structured_output": report})
                          + "))\n", encoding="utf-8")
        return [sys.executable, str(script)]

    def test_ac_006_auditor_and_scenario(self):
        auditor = (ROOT / ".claude/agents/test-auditor.md").read_text(encoding="utf-8")
        for phrase in ("**Wrong:**", "contradicts the criterion's Expected", "wrong expected value"):
            self.assertIn(phrase, auditor)
        scenario = ROOT / "bench/scenarios/auditor-wrong-expected"
        self.assertIn("960", (scenario / "brief.md").read_text(encoding="utf-8"))
        self.assertIn("960 + 480", (scenario / "acceptance/test_schedule.py").read_text(encoding="utf-8"))
        meta = json.loads((scenario / "scenario.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["expect"], {"status": "FAIL", "finding_mentions": ["AC-009", "960"]})
        self.assertFalse((ROOT / "bench/scenarios/__init__.py").exists())
        runner = load_scenario()
        finding = {"severity": "critical", "wp": "AT", "file": "acceptance/test_schedule.py",
                   "problem": "AC-009 expects 960", "evidence": "the test asserts 1440"}
        hit = {"status": "FAIL", "findings": [finding], "not_checked": []}
        miss = {"status": "PASS", "findings": [], "not_checked": []}
        result = runner.run(scenario, claude=self.fake(hit))
        self.assertEqual(set(result), {"report", "expect", "met"})
        self.assertTrue(result["met"])
        self.assertFalse(runner.run(scenario, claude=self.fake(miss))["met"])


class ReleaseTests(unittest.TestCase):
    def test_ac_007_release(self):
        import agentic
        import installer
        import upgrade
        for module in (".claude/bin/doctor.py", ".claude/bin/plan_picture.py"):
            self.assertIn(module, installer.INSTALL_GLOBS)
        for command in ("doctor", "plan-picture"):
            self.assertIn(command, agentic.COMMANDS)
            self.assertIn(f"\n  {command}", agentic.__doc__)
        tree = (ROOT / "docs/how-it-works.md").read_text(encoding="utf-8")
        self.assertIn("doctor.py", tree)
        self.assertIn("plan_picture.py", tree)
        self.assertEqual(json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))["version"],
                         "2.12.0")
        notes = " ".join(upgrade.NOTES.get("2.12.0", []))
        for word in ("doctor", "plan-picture", "test-auditor"):
            self.assertIn(word, notes)
        self.assertEqual(sorted(p.name for p in BIN.glob("test_acceptance*.py")), ["test_acceptance_v212.py"])


if __name__ == "__main__":
    unittest.main()
