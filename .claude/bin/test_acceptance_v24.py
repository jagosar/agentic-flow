"""Acceptance tests of agentic-flow 2.4: AC-001 .. AC-009 of docs/architecture/0009.

Run: python3 -m unittest discover -s .claude/bin -p test_acceptance_v24.py
The hook, hooks-check and the stages run against temporary repos; the engines in the simulated conformance world and
run-pipeline with the fake `claude`. Nothing is spent.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parent
ROOT = BIN.parents[1]
sys.path.insert(0, str(BIN))
import upgrade  # noqa: E402
from test_agentic import MANIFEST, Repo, bash_payload, testutil, write_payload  # noqa: E402
from test_pipeline import CONFORMANCE, E2E_MANIFEST, run_scenario  # noqa: E402

GIT_ID = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
SEEN = Path(".claude/state/hook-seen.json")
GUARD_MSG = "GUARDRAIL HOOK SAW NO FLOW AGENT"


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


class RepoCase(unittest.TestCase):
    manifest = MANIFEST

    def setUp(self):
        self.repo = Repo(self.manifest)
        self.repo.env.pop("CLAUDECODE", None)  # whatever Repo does, these tests decide the mode themselves
        settings = self.repo.dir / ".claude" / "settings.json"
        if not settings.exists():
            shutil.copy(ROOT / ".claude" / "settings.json", settings)

    def tearDown(self):
        self.repo.cleanup()

    def seen(self):
        return json.loads((self.repo.dir / SEEN).read_text(encoding="utf-8"))

    def put_seen(self, raw):
        path = self.repo.dir / SEEN
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(raw if isinstance(raw, str) else json.dumps(raw), encoding="utf-8")

    def hook(self, payload, wp=None):
        return self.repo.run("hook", stdin=json.dumps(payload), env={"AGENTIC_WP": wp} if wp else None)

    def check(self, live=False):
        env = {"CLAUDECODE": "1"} if live else None
        r = self.repo.run("hooks-check", env=env)
        lines = [line for line in r.stdout.splitlines() if line.strip().startswith("{")]
        return r, (json.loads(lines[-1]) if lines else None)


class HeartbeatTests(RepoCase):
    def test_ac_001_every_call_leaves_a_heartbeat(self):
        r = self.hook(bash_payload("ls", agent_id="a1", agent_type="implementer"))
        self.assertNotEqual(r.returncode, 0, "an implementer without a claim is still blocked")
        first = self.seen()
        self.assertEqual(first["tool"], "Bash")
        self.assertEqual(first["command"], "ls")
        self.assertEqual(first["agent_type"], "implementer")
        self.assertIsNotNone(first["guarded_ts"])
        self.assertLessEqual(abs(first["ts"] - time.time()), 60)
        r = self.hook(write_payload("src/a.py"))
        self.assertEqual(r.returncode, 0, r.stderr)
        second = self.seen()
        self.assertEqual(second["tool"], "Write")
        self.assertEqual(second["command"], "")
        self.assertIsNone(second["agent_type"])
        self.assertEqual(second["guarded_ts"], first["guarded_ts"], "the main thread never counts as a guard")

    def test_ac_001_fallback_agents_and_read_only_agents_count(self):
        self.hook(bash_payload("ls"), wp="WP-01")
        self.assertIsNotNone(self.seen()["guarded_ts"], "AGENTIC_WP marks a fallback agent")
        self.put_seen({"ts": 1, "tool": "Bash", "command": "", "agent_type": None, "guarded_ts": None})
        self.hook({"tool_name": "Bash", "tool_input": {"command": "ls"}, "agent_id": "v1", "agent_type": "verifier"})
        self.assertIsNotNone(self.seen()["guarded_ts"])
        self.put_seen({"ts": 1, "tool": "Bash", "command": "", "agent_type": None, "guarded_ts": None})
        self.hook({"tool_name": "Bash", "tool_input": {"command": "ls"}, "agent_id": "g1", "agent_type": "gatekeeper"})
        self.assertIsNone(self.seen()["guarded_ts"], "the gatekeeper runs whether or not the agents' hooks do")


class HooksCheckLiveTests(RepoCase):
    def assert_dead(self, r, out):
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertFalse(out["ok"])
        self.assertEqual(out["mode"], "live")
        self.assertIn("did not run for this call", r.stderr)
        self.assertIn("/implement fallback", r.stderr)

    def test_ac_002_a_fresh_heartbeat_passes(self):
        self.put_seen({"ts": time.time(), "tool": "Bash", "command": "anything", "agent_type": None, "guarded_ts": None})
        r, out = self.check(live=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((out["ok"], out["mode"]), (True, "live"))

    def test_ac_002_a_stale_heartbeat_fails(self):
        self.put_seen({"ts": time.time() - 1000, "tool": "Bash", "command": "hooks-check", "agent_type": None,
                       "guarded_ts": None})
        self.assert_dead(*self.check(live=True))

    def test_ac_002_no_heartbeat_fails(self):
        self.assert_dead(*self.check(live=True))

    def test_ac_002_a_corrupt_heartbeat_fails_cleanly(self):
        self.put_seen("{not json")
        r, out = self.check(live=True)
        self.assertNotIn("Traceback", r.stderr)
        self.assert_dead(r, out)


class HooksCheckStaticTests(RepoCase):
    def test_ac_003_the_installed_settings_pass(self):
        r, out = self.check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((out["ok"], out["mode"]), (True, "static"))
        self.assertFalse((self.repo.dir / SEEN).exists(), "static mode neither reads nor writes the heartbeat")

    def test_ac_003_no_hook_in_settings_fails(self):
        (self.repo.dir / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": []}}),
                                                                 encoding="utf-8")
        r, out = self.check()
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertEqual((out["ok"], out["mode"]), (False, "static"))
        self.assertIn("settings.json", out["reason"])

    def test_ac_003_disable_all_hooks_fails(self):
        (self.repo.dir / ".claude" / "settings.local.json").write_text(json.dumps({"disableAllHooks": True}),
                                                                       encoding="utf-8")
        r, out = self.check()
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("disableAllHooks", out["reason"])


class StageLivenessTests(RepoCase):
    def close(self):
        return self.repo.run("close-stage", "1", "WP-01=done")

    def test_ac_004_a_stage_written_with_no_hook_call_ends_in_review(self):
        self.repo.run("open-stage", "1")
        self.repo.write("src/a.py", "x = 1\n")
        r = self.close()
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn(GUARD_MSG, r.stdout)

    def test_ac_004_a_guarded_stage_closes(self):
        self.repo.run("open-stage", "1")
        self.hook(bash_payload("ls"), wp="WP-01")
        self.repo.write("src/a.py", "x = 1\n")
        r = self.close()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("all changes are within their owners", r.stdout)
        self.assertNotIn(GUARD_MSG, r.stdout)

    def test_ac_004_the_gatekeeper_is_not_a_guard(self):
        self.repo.run("open-stage", "1")
        self.hook({"tool_name": "Bash", "tool_input": {"command": "ls"}, "agent_id": "g1", "agent_type": "gatekeeper"})
        self.hook(write_payload("src/a.py"))  # the main thread
        self.repo.write("src/a.py", "x = 1\n")
        r = self.close()
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn(GUARD_MSG, r.stdout)

    def test_ac_004_a_guard_from_an_earlier_stage_does_not_count(self):
        self.hook(bash_payload("ls"), wp="WP-01")
        time.sleep(0.05)
        self.repo.run("open-stage", "1")
        self.repo.write("src/a.py", "x = 1\n")
        self.assertIn(GUARD_MSG, self.close().stdout)

    def test_ac_004_a_stage_that_changed_nothing_closes(self):
        self.repo.run("open-stage", "1")
        r = self.close()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn(GUARD_MSG, r.stdout)


class PreflightTests(unittest.TestCase):
    def test_ac_006_implement_checks_the_hook_first(self):
        text = read(".claude/commands/implement.md")
        pre = text.split("# 1. Pre-flight validation")[1].split("# 2.")[0]
        steps = [line for line in pre.splitlines() if re.match(r"\d+\. ", line)]
        self.assertTrue(steps, pre)
        self.assertIn("agentic.py hooks-check", steps[0])
        self.assertTrue(any("agentic.py validate" in s for s in steps[1:]))
        self.assertIn("/implement fallback", pre)
        numbers = [int(s.split(".")[0]) for s in steps]
        self.assertEqual(numbers, list(range(1, len(numbers) + 1)), "steps stay consecutive")


class FallbackGateTests(unittest.TestCase):
    """AC-009: /implement fallback, launched from a Bash tool whose hook is dead, still runs."""

    def setUp(self):
        self.repo = Repo(E2E_MANIFEST)
        settings = self.repo.dir / ".claude" / "settings.json"
        if not settings.exists():
            shutil.copy(ROOT / ".claude" / "settings.json", settings)
        self.bin = Path(tempfile.mkdtemp(prefix="fake-claude-"))
        self.logs = Path(tempfile.mkdtemp(prefix="fake-logs-"))
        self.repo.env.update(AGENTIC_CLAUDE=testutil.install_fake_claude(self.bin), FAKE_LOG_DIR=str(self.logs),
                             FAKE_WRITE="1", FAKE_MODE="nousage", CLAUDECODE="1")
        self.repo.write("acc.py", "import os, sys\nsys.exit(0 if all(os.path.exists(p) for p in "
                                  "('src/a.py', 'src/b/x.py', 'src/c.py')) else 1)\n")
        subprocess.run(["git", "add", "-A"], cwd=self.repo.dir, check=True)
        subprocess.run(["git", *GIT_ID, "commit", "-qm", "init"], cwd=self.repo.dir, check=True)

    def tearDown(self):
        self.repo.cleanup()
        shutil.rmtree(self.bin, ignore_errors=True)
        shutil.rmtree(self.logs, ignore_errors=True)

    def test_ac_009_the_fallback_checks_statically_and_runs(self):
        self.assertFalse((self.repo.dir / SEEN).exists())
        live = self.repo.run("hooks-check")
        self.assertEqual(live.returncode, 3, "the launcher's own session has no heartbeat: a live check would stop")
        r = self.repo.run("run-pipeline")
        result = json.loads((self.repo.dir / ".claude/state/runs/workflow-result.json").read_text(encoding="utf-8"))
        self.assertNotEqual(result.get("failed_stage"), "prepare", r.stdout + r.stderr)
        self.assertEqual(result["result"], "OK", r.stdout + r.stderr)
        calls = testutil.fake_calls(self.logs)
        self.assertTrue(calls, "agents ran")


class EnginesTests(unittest.TestCase):
    SCENARIO = "the guardrail hook is not running"

    def scenarios(self):
        return {d["name"]: d for d in CONFORMANCE["scenarios"]}

    def test_ac_005_python_engine_stops_at_prepare(self):
        by_name = self.scenarios()
        self.assertIn(self.SCENARIO, by_name)
        s = run_scenario(by_name[self.SCENARIO])
        self.assertEqual((s["result"], s["failed_stage"]), ("REVIEW", "prepare"))
        self.assertIn("guardrail hook is not running", s["detail"])
        self.assertEqual(s["gates"], ["hooks-check"])
        self.assertEqual(s["agents"], [])
        happy = run_scenario(by_name["happy path"])
        self.assertEqual(happy["gates"][:3], ["hooks-check", "pipeline-plan", "briefs"])

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_ac_005_both_engines_agree(self):
        r = subprocess.run(["node", str(BIN / "test_workflow.mjs"), "--dump"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        node = json.loads(r.stdout)
        by_name = self.scenarios()
        for name in (self.SCENARIO, "happy path"):
            with self.subTest(scenario=name):
                py = run_scenario(by_name[name])
                for key in ("result", "failed_stage", "detail", "gates", "agents"):
                    self.assertEqual(node[name][key], py[key], key)


class ReleaseTests(unittest.TestCase):
    def test_ac_007_version_notes_roadmap(self):
        version = json.loads(read(".claude-plugin/plugin.json"))["version"]
        self.assertEqual(version, "2.4.1")
        notes = upgrade.NOTES["2.4.0"]
        self.assertGreaterEqual(len(notes), 2)
        joined = " ".join(notes)
        for word in ("hooks-check", "close-stage"):
            self.assertIn(word, joined)
        self.assertEqual([len(upgrade.NOTES[v]) for v in ("2.3.0", "2.2.0", "2.1.0", "2.0.0")], [2, 2, 4, 7])
        roadmap = read("docs/roadmap/repo-review-2026-11.md")
        entry = next(line for line in roadmap.splitlines() if line.startswith("- Project hooks did not fire"))
        self.assertIn("Fixed in 2.4.0", entry)


class DocsTests(unittest.TestCase):
    def test_ac_008_three_layers_documented(self):
        readme = read("README.md")
        row = next(line for line in readme.splitlines() if line.startswith("| A failure in the guardrail itself"))
        self.assertIn("hooks-check", row)
        how = read("docs/how-it-works.md")
        guard = how.split("## 4. Guardrails")[1].split("\n## 5.")[0]
        self.assertIn("heartbeat", guard)
        self.assertIn("close-stage", guard)
        self.assertIn("hooks-check + pipeline-plan + briefs", how)
        hub = read("docs/how-to/README.md")
        self.assertLessEqual(len(hub.splitlines()), 260)
        ref = hub.split("## Script reference")[1].split("## Troubleshooting")[0]
        self.assertIn("agentic.py hooks-check", ref)
        trouble = hub.split("## Troubleshooting")[1].split("## Testing the flow itself")[0]
        self.assertTrue(any(line.startswith("|") and "hooks-check" in line for line in trouble.splitlines()))
        web = read("docs/how-to/web-ios.md")
        self.assertIn("two repositories", web)
        self.assertIn("hooks-check", web)


if __name__ == "__main__":
    unittest.main()
