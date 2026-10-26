"""Tests of the guardrails and the launcher.

Run: python3 -m unittest discover -s .claude/bin -p "test_*.py"
Each test works in a temporary git repo; the launcher uses a fake `claude`, with no real calls.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "agentic.py"
AGENTS_DIR = SCRIPT.parents[1] / "agents"
WORKFLOWS_DIR = SCRIPT.parents[1] / "workflows"
FINDING = {"severity": "high", "wp": "WP-02", "file": "src/b/x.py", "problem": "p", "evidence": "e"}

MANIFEST = {
    "allow_bash": ["Bash(python3 -m unittest:*)"],
    "ignore": ["dist/"],
    "acceptance": {"files": ["acceptance/"], "command": "python3 acc.py"},
    "work_packages": [
        {"id": "WP-01", "wave": 1, "depends_on": [], "files": ["src/a.py", "tests/test_a.py"]},
        {"id": "WP-02", "wave": 1, "depends_on": [], "files": ["src/b/"]},
        {"id": "WP-03", "wave": 2, "depends_on": ["WP-01"], "files": ["src/c.py"]},
    ],
}

FAKE_CLAUDE = textwrap.dedent("""\
    #!/usr/bin/env python3
    import json, os, sys, time
    argv = sys.argv[1:]
    wp = os.environ["AGENTIC_WP"]
    with open(os.path.join(os.environ["FAKE_LOG_DIR"], wp + ".args"), "w") as f:
        json.dump(argv, f)
    with open(os.path.join(os.environ["FAKE_LOG_DIR"], wp + ".env"), "w") as f:
        json.dump({k: os.environ.get(k) for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}, f)
    time.sleep(float(os.environ.get("FAKE_SLEEP", "0")))
    status = os.environ.get("FAKE_STATUS", "DONE" if wp != "QA" else "PASS")
    required = json.loads(argv[argv.index("--json-schema") + 1]).get("required", [])
    values = {"status": status, "wp": wp, "blocker": None}
    print(json.dumps({"structured_output": {k: values.get(k, []) for k in required}}))
""")


class Repo:
    def __init__(self, manifest=MANIFEST, raw_manifest=None):
        self.dir = Path(tempfile.mkdtemp(prefix="agentic-test-"))
        body = raw_manifest if raw_manifest is not None else json.dumps(manifest, indent=2)
        (self.dir / "architecture.md").write_text(f"# A\n\n```json wp-manifest\n{body}\n```\n")
        shutil.copytree(AGENTS_DIR, self.dir / ".claude" / "agents")
        shutil.copytree(WORKFLOWS_DIR, self.dir / ".claude" / "workflows")
        subprocess.run(["git", "init", "-q"], cwd=self.dir, check=True)
        self.env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.dir))
        self.env.pop("AGENTIC_WP", None)

    def run(self, *args, stdin=None, env=None):
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=self.dir, input=stdin,
                              capture_output=True, text=True, env=dict(self.env, **(env or {})))

    def hook(self, payload, wp=None):
        return self.run("hook", stdin=json.dumps(payload), env={"AGENTIC_WP": wp} if wp else None).returncode

    def write(self, rel, text="x"):
        p = self.dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def write_payload(path, agent_id=None, tool="Write"):
    data = {"tool_name": tool, "tool_input": {"file_path": path}}
    if agent_id:
        data.update(agent_id=agent_id, agent_type="implementer")
    return data


def bash_payload(command, agent_id=None):
    data = {"tool_name": "Bash", "tool_input": {"command": command}}
    if agent_id:
        data.update(agent_id=agent_id, agent_type="implementer")
    return data


class Base(unittest.TestCase):
    manifest = MANIFEST

    def setUp(self):
        self.repo = Repo(self.manifest)

    def tearDown(self):
        self.repo.cleanup()


class ValidateTests(unittest.TestCase):
    def errors(self, manifest):
        sys.path.insert(0, str(SCRIPT.parent))
        import agentic
        return agentic.validate(manifest)

    def test_valid_manifest(self):
        self.assertEqual(self.errors(MANIFEST), [])

    def test_overlapping_files(self):
        m = json.loads(json.dumps(MANIFEST))
        m["work_packages"][2]["files"] = ["src/b/x.py"]
        self.assertTrue(any("two owners" in e for e in self.errors(m)))

    def test_overlap_with_qa(self):
        m = dict(MANIFEST, qa={"files": ["src/"]})
        self.assertTrue(any("two owners" in e for e in self.errors(m)))

    def test_dependency_in_same_wave(self):
        m = json.loads(json.dumps(MANIFEST))
        m["work_packages"][1]["depends_on"] = ["WP-01"]
        self.assertTrue(any("earlier wave" in e for e in self.errors(m)))

    def test_broad_rules_rejected(self):
        for rule in ["Bash(*)", "Bash(python3:*)", "Bash(npm:*)", "Bash(bash:*)", "Bash(sh)", "Bash(git:*)", "Bash(np*)"]:
            with self.subTest(rule=rule):
                m = dict(MANIFEST, allow_bash=[rule])
                self.assertTrue(any("too broad" in e for e in self.errors(m)))

    def test_specific_rules_accepted(self):
        m = dict(MANIFEST, allow_bash=["Bash(npm test:*)", "Bash(python3 -m pytest:*)", "Bash(pytest:*)", "Bash(make test)"])
        self.assertEqual(self.errors(m), [])

    def test_cannot_own_claude_or_architecture(self):
        for f in [".claude/settings.json", "architecture.md"]:
            m = json.loads(json.dumps(MANIFEST))
            m["work_packages"][0]["files"] = [f]
            self.assertTrue(self.errors(m), f)

    def test_duplicate_and_reserved_ids(self):
        m = json.loads(json.dumps(MANIFEST))
        m["work_packages"][1]["id"] = "WP-01"
        self.assertTrue(any("duplicate" in e for e in self.errors(m)))
        m["work_packages"][1]["id"] = "QA"
        self.assertTrue(any("reserved" in e for e in self.errors(m)))


class HookWriteTests(Base):
    def test_main_thread_unrestricted(self):
        self.assertEqual(self.repo.hook(write_payload(str(self.repo.dir / "cualquiera.py"))), 0)

    def test_fallback_mode_own_and_foreign(self):
        self.assertEqual(self.repo.hook(write_payload(str(self.repo.dir / "src/a.py")), wp="WP-01"), 0)
        self.assertEqual(self.repo.hook(write_payload(str(self.repo.dir / "src/b/x.py")), wp="WP-01"), 2)
        self.assertEqual(self.repo.hook(write_payload(str(self.repo.dir / "src/b/x.py")), wp="WP-02"), 0)

    def test_relative_path_and_outside_the_repo(self):
        self.assertEqual(self.repo.hook({**write_payload("src/a.py"), "cwd": str(self.repo.dir)}, wp="WP-01"), 0)
        self.assertEqual(self.repo.hook(write_payload("/tmp/outside.py"), wp="WP-01"), 2)
        self.assertEqual(self.repo.hook(write_payload(str(self.repo.dir / "src/../src/b/x.py")), wp="WP-01"), 2)

    def test_qa_only_its_zone(self):
        self.assertEqual(self.repo.hook(write_payload(str(self.repo.dir / "qa/t.py")), wp="QA"), 0)
        self.assertEqual(self.repo.hook(write_payload(str(self.repo.dir / "src/a.py")), wp="QA"), 2)

    def test_workflow_mode_needs_claim(self):
        self.assertEqual(self.repo.hook(write_payload(str(self.repo.dir / "src/a.py"), agent_id="ag1")), 2)
        self.assertEqual(self.repo.hook(bash_payload("python3 .claude/bin/agentic.py claim WP-01", agent_id="ag1")), 0)
        self.assertEqual(self.repo.hook(write_payload(str(self.repo.dir / "src/a.py"), agent_id="ag1")), 0)
        self.assertEqual(self.repo.hook(write_payload(str(self.repo.dir / "src/c.py"), agent_id="ag1")), 2)

    def test_claim_is_exclusive(self):
        claim = "python3 .claude/bin/agentic.py claim WP-01"
        self.assertEqual(self.repo.hook(bash_payload(claim, agent_id="ag1")), 0)
        self.assertEqual(self.repo.hook(bash_payload(claim, agent_id="ag1")), 0, "claiming your own again is valid")
        self.assertEqual(self.repo.hook(bash_payload(claim, agent_id="ag2")), 2, "another agent cannot claim it")
        self.assertEqual(self.repo.hook(bash_payload("python3 .claude/bin/agentic.py claim WP-02", agent_id="ag1")), 2,
                         "an agent cannot claim two WPs")
        self.assertEqual(self.repo.hook(bash_payload("python3 .claude/bin/agentic.py claim WP-99", agent_id="ag3")), 2)

    def test_snapshot_resets_claims(self):
        claim = "python3 .claude/bin/agentic.py claim WP-01"
        self.assertEqual(self.repo.hook(bash_payload(claim, agent_id="ag1")), 0)
        self.repo.run("snapshot", "1")
        self.assertEqual(self.repo.hook(bash_payload(claim, agent_id="ag2")), 0)


class V2EntityTests(Base):
    """Wave 0 (AT), the read-only reviewer and the v2 flow validations."""

    def p(self, rel):
        return str(self.repo.dir / rel)

    def test_implementer_cannot_touch_acceptance(self):
        self.assertEqual(self.repo.hook(write_payload(self.p("acceptance/test_ac_001.py")), wp="WP-01"), 2)
        self.assertEqual(self.repo.hook(write_payload(self.p("acceptance/test_ac_001.py")), wp="AT"), 0)
        self.assertEqual(self.repo.hook(write_payload(self.p("src/a.py")), wp="AT"), 2, "the test-author does not implement")

    def test_reviewer_writes_nothing(self):
        for rel in ("src/a.py", "review.md", "acceptance/x.py", "qa/x.py"):
            with self.subTest(rel=rel):
                self.assertEqual(self.repo.hook(write_payload(self.p(rel)), wp="REVIEW"), 2)
        self.assertEqual(self.repo.hook(bash_payload("git diff"), wp="REVIEW"), 0)

    def test_claim_at_and_review_in_workflow_mode(self):
        for ident, agent in (("AT", "a1"), ("REVIEW", "a2")):
            self.assertEqual(self.repo.hook(bash_payload(f"python3 .claude/bin/agentic.py claim {ident}", agent_id=agent)), 0)
        self.assertEqual(self.repo.hook(write_payload(self.p("acceptance/t.py"), agent_id="a1")), 0)
        self.assertEqual(self.repo.hook(write_payload(self.p("src/a.py"), agent_id="a2")), 2)

    def write_manifest(self, m):
        (self.repo.dir / "architecture.md").write_text(f"```json wp-manifest\n{json.dumps(m)}\n```")

    def test_v2_validations(self):
        cases = {
            "reserved IDs": lambda m: m["work_packages"][0].update(id="AT"),
            "acceptance without command": lambda m: m.update(acceptance={"files": ["acceptance/"]}),
            "WP owning the decision archive": lambda m: m["work_packages"][0].update(files=["docs/architecture/x.md"]),
            "overlap with acceptance": lambda m: m["work_packages"][0].update(files=["acceptance/"]),
        }
        for name, mutate in cases.items():
            with self.subTest(name):
                m = json.loads(json.dumps(MANIFEST))
                mutate(m)
                self.write_manifest(m)
                self.assertEqual(self.repo.run("validate").returncode, 1)

    def test_v2_agent_models(self):
        agents = self.repo.dir / ".claude/agents"
        for name, wrong in (("test-author", "opus"), ("reviewer", "opus"), ("plan-reviewer", "sonnet")):
            with self.subTest(name):
                f = agents / f"{name}.md"
                original = f.read_text()
                good = "model: opus" if name == "plan-reviewer" else "model: sonnet"
                f.write_text(original.replace(good, f"model: {wrong}"))
                r = self.repo.run("validate")
                self.assertEqual(r.returncode, 1, r.stderr)
                self.assertIn(name, r.stderr)
                f.write_text(original)
        self.assertEqual(self.repo.run("validate").returncode, 0)

    def acc(self, code):
        (self.repo.dir / "acc.py").write_text(f"import sys\nprint('tests')\nsys.exit({code})\n")

    def test_acceptance_red_and_green(self):
        self.acc(1)
        self.assertEqual(self.repo.run("acceptance", "--expect", "red").returncode, 0)
        self.assertEqual(self.repo.run("acceptance", "--expect", "green").returncode, 3)
        self.acc(0)
        r = self.repo.run("acceptance", "--expect", "red")
        self.assertEqual(r.returncode, 3)
        self.assertIn("ALREADY PASS WITHOUT CODE", r.stdout)
        self.assertEqual(self.repo.run("acceptance", "--expect", "green").returncode, 0)
        self.assertIn("acceptance (green): OK", self.repo.run("status").stdout)

    def test_nonexistent_acceptance_command_is_not_red(self):
        m = json.loads(json.dumps(MANIFEST))
        m["acceptance"]["command"] = "command-that-does-not-exist --x"
        self.write_manifest(m)
        r = self.repo.run("acceptance", "--expect", "red")
        self.assertEqual(r.returncode, 3)
        self.assertIn("ERROR", r.stdout)


class ContentGuardTests(Base):
    """Content guardrails adapted from ECC: hook bypass, config, disabled tests and secrets."""
    manifest = dict(MANIFEST, work_packages=[
        {"id": "WP-01", "wave": 1, "depends_on": [], "files": ["src/a.py", "tests/test_a.py", "pyproject.toml", "setup.cfg"]},
        {"id": "WP-02", "wave": 1, "depends_on": [], "files": ["ruff.toml"], "config_edit": True},
    ])

    def w(self, rel, content, wp="WP-01", tool="Write", old=None):
        tinput = {"file_path": str(self.repo.dir / rel)}
        if tool == "Write":
            tinput["content"] = content
        else:
            tinput.update(new_string=content, old_string=old or "")
        return self.repo.hook({"tool_name": tool, "tool_input": tinput}, wp=wp)

    def test_no_verify_blocked_for_everyone(self):
        for cmd in ["git commit --no-verify -m x", "git commit -n -m x", "git -c core.hooksPath=/dev/null commit -m x", "sh -c 'git commit --no-verify'",
                    "git push --no-verify"]:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.repo.hook(bash_payload(cmd)), 2, "in the main session too")
        for cmd in ["git commit -m 'arregla -n'", "git log -n 5", "git commit -m x"]:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.repo.hook(bash_payload(cmd)), 0)

    def test_existing_config_is_protected(self):
        self.repo.write("pyproject.toml", "[tool.ruff]\nline-length = 88\n")
        self.assertEqual(self.w("pyproject.toml", "[tool.ruff]\nline-length = 300\n"), 2)
        self.assertEqual(self.w("setup.cfg", "x"), 0, "creating new configuration is allowed")
        self.repo.write("ruff.toml", "a")
        self.assertEqual(self.w("ruff.toml", "b", wp="WP-02"), 0, "config_edit: true lo permite")

    def test_tests_cannot_be_disabled(self):
        self.assertEqual(self.w("tests/test_a.py", "import unittest\n@unittest.skip('x')\ndef test(): pass\n"), 2)
        self.assertEqual(self.w("tests/test_a.py", "import pytest\n@pytest.mark.xfail\ndef test(): pass\n"), 2)
        self.assertEqual(self.w("tests/test_a.py", "it.only('x', () => {})", tool="Edit"), 2)
        self.assertEqual(self.w("tests/test_a.py", "@unittest.skipIf(os.geteuid() == 0, 'root')\ndef test(): pass\n"), 0)
        self.assertEqual(self.w("src/a.py", "# pytest.mark.skip in a code comment\n"), 0, "only in test files")
        self.assertEqual(self.w("tests/test_a.py", "@unittest.skip('was already there')\nX", tool="Edit",
                                old="@unittest.skip('was already there')\n"), 0, "what already existed does not count")

    def test_secrets(self):
        for secret in ["AKIA" + "A" * 16, "ghp_" + "a" * 36, "sk-ant-" + "a" * 30,
                       "-----BEGIN RSA PRIVATE KEY-----", "xoxb-" + "1" * 12]:
            with self.subTest(secret=secret[:8]):
                self.assertEqual(self.w("src/a.py", f"TOKEN = '{secret}'\n"), 2)
        self.assertEqual(self.w("src/a.py", "TOKEN = os.environ['API_TOKEN']\n"), 0)


class WorkflowCommandTests(Base):
    """Deterministic commands the native workflow uses through the gatekeeper agent."""

    def test_open_stage_resets_the_previous_stages_claims(self):
        self.repo.hook(bash_payload("python3 .claude/bin/agentic.py claim WP-01", agent_id="old"))
        self.assertEqual(self.repo.run("open-stage", "1").returncode, 0)
        self.assertEqual(self.repo.hook(bash_payload("python3 .claude/bin/agentic.py claim WP-01", agent_id="new")), 0)


class LauncherTests(Base):
    def setUp(self):
        super().setUp()
        self.bin = Path(tempfile.mkdtemp(prefix="fake-claude-"))
        fake = self.bin / "claude"
        fake.write_text(FAKE_CLAUDE)
        fake.chmod(0o755)
        self.logs = Path(tempfile.mkdtemp(prefix="fake-logs-"))
        self.repo.env.update(PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}", FAKE_LOG_DIR=str(self.logs))

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.bin, ignore_errors=True)
        shutil.rmtree(self.logs, ignore_errors=True)

    def args(self, wp):
        return json.loads((self.logs / f"{wp}.args").read_text())

    def test_wave_runs_in_parallel(self):
        start = time.time()
        r = self.repo.run("run-wave", "1", env={"FAKE_SLEEP": "1.5"})
        elapsed = time.time() - start
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertLess(elapsed, 2.8, "the two WPs should run at the same time")
        self.assertNotIn("USD", r.stdout, "no cost information")

    def test_flags_of_each_agent(self):
        self.repo.run("run-wave", "1")
        a = self.args("WP-01")
        self.assertEqual(a[a.index("--agent") + 1], "implementer")
        self.assertEqual(a[a.index("--model") + 1], "sonnet")
        self.assertNotIn("--max-budget-usd", a)
        self.assertIn("--strict-mcp-config", a)
        self.assertIn("Bash(python3 -m unittest:*)", a)
        self.assertNotIn("Bash", a, "never unrestricted Bash")
        self.assertFalse((self.logs / "WP-03.args").exists(), "WP-03 belongs to wave 2")

    def test_model_cannot_be_changed(self):
        (self.repo.dir / ".claude/agentic.json").write_text(json.dumps({"models": {"qa": "claude-opus-5-5"}}))
        self.repo.run("run-qa", env={"AGENTIC_QA_MODEL": "opus", "AGENTIC_IMPLEMENTER_MODEL": "opus"})
        a = self.args("QA")
        self.assertEqual(a[a.index("--model") + 1], "sonnet")
        self.assertEqual(a[a.index("--agent") + 1], "qa")

    def test_agent_with_another_model_does_not_validate(self):
        f = self.repo.dir / ".claude/agents/qa.md"
        f.write_text(f.read_text().replace("model: sonnet", "model: claude-opus-5-5"))
        r = self.repo.run("run-wave", "1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("model: sonnet", r.stderr)
        self.assertFalse((self.logs / "WP-01.args").exists())

    def test_architect_must_be_opus(self):
        cmds = self.repo.dir / ".claude/commands"
        cmds.mkdir(parents=True, exist_ok=True)
        (cmds / "architect.md").write_text("---\ndescription: x\nmodel: opus\n---\nx")
        self.assertEqual(self.repo.run("validate").returncode, 0)
        (cmds / "architect.md").write_text("---\ndescription: x\nmodel: claude-opus-5-5\n---\nx")
        r = self.repo.run("validate")
        self.assertEqual(r.returncode, 1)
        self.assertIn("latest Opus", r.stderr)

    def test_real_definitions_use_aliases(self):
        sys.path.insert(0, str(SCRIPT.parent))
        import agentic
        root = SCRIPT.parents[2]
        self.assertEqual(agentic.frontmatter_model(root / ".claude/commands/architect.md"), "opus")
        for name in ("implementer", "qa"):
            self.assertEqual(agentic.frontmatter_model(root / f".claude/agents/{name}.md"), "sonnet")
        for name in ("implement",):
            self.assertEqual(agentic.frontmatter_model(root / f".claude/commands/{name}.md"), "sonnet")

    def test_launcher_must_be_sonnet(self):
        cmds = self.repo.dir / ".claude/commands"
        cmds.mkdir(parents=True, exist_ok=True)
        (cmds / "implement.md").write_text("---\ndescription: x\nmodel: opus\n---\nx")
        r = self.repo.run("validate")
        self.assertEqual(r.returncode, 1)
        self.assertIn("/implement", r.stderr)

    def test_specialised_agent_must_exist_and_be_sonnet(self):
        m = json.loads(json.dumps(MANIFEST))
        m["work_packages"][0]["agent"] = "frontend"
        (self.repo.dir / "architecture.md").write_text(f"```json wp-manifest\n{json.dumps(m)}\n```")
        r = self.repo.run("validate")
        self.assertIn("does not exist", r.stderr)
        (self.repo.dir / ".claude/agents/frontend.md").write_text("---\nname: frontend\nmodel: haiku\n---\nx")
        self.assertIn("not 'haiku'", self.repo.run("validate").stderr)
        (self.repo.dir / ".claude/agents/frontend.md").write_text("---\nname: frontend\nmodel: sonnet\n---\nx")
        self.assertEqual(self.repo.run("validate").returncode, 0)

    def env_of(self, wp):
        return json.loads((self.logs / f"{wp}.env").read_text())

    def test_subscription_does_not_inherit_api_key(self):
        self.repo.run("run-wave", "1", env={"ANTHROPIC_API_KEY": "sk-test", "ANTHROPIC_AUTH_TOKEN": "tok"})
        self.assertEqual(self.env_of("WP-01"), {"ANTHROPIC_API_KEY": None, "ANTHROPIC_AUTH_TOKEN": None})

    def test_auth_inherit_keeps_api_key(self):
        (self.repo.dir / ".claude").mkdir(exist_ok=True)
        (self.repo.dir / ".claude/agentic.json").write_text(json.dumps({"auth": "inherit"}))
        self.repo.run("run-wave", "1", env={"ANTHROPIC_API_KEY": "sk-test"})
        self.assertEqual(self.env_of("WP-01")["ANTHROPIC_API_KEY"], "sk-test")

    def test_only_one_wp(self):
        r = self.repo.run("run-wave", "1", "WP-02")
        self.assertEqual(r.returncode, 0)
        self.assertFalse((self.logs / "WP-01.args").exists())
        self.assertEqual(self.repo.run("run-wave", "1", "WP-03").returncode, 1)

    def prompt_of(self, wp):
        return self.args(wp)[1]

    def test_fix_only_when_requested(self):
        runs = self.repo.dir / ".claude/state/runs"
        runs.mkdir(parents=True, exist_ok=True)
        (runs / "REVIEW.json").write_text(json.dumps({"structured_output": {"status": "FAIL", "findings": [FINDING]}}))
        self.repo.run("run-wave", "1", "WP-02")
        self.assertNotIn('"problem"', self.prompt_of("WP-02"), "without --fix it must not use an old report")
        self.repo.run("run-wave", "1", "WP-02", "--fix")
        self.assertIn('"problem":"p"', self.prompt_of("WP-02"))

    def test_fix_without_report_fails(self):
        r = self.repo.run("run-wave", "1", "WP-01", "--fix")
        self.assertEqual(r.returncode, 1)
        self.assertIn("run-review or run-qa", r.stderr)

    # ---------- ledger, mark y stop ----------

    def status(self):
        return self.repo.run("status").stdout

    def test_ledger_after_a_wave(self):
        self.assertEqual(self.repo.run("run-wave", "1").returncode, 0)
        st = self.status()
        self.assertIn("[done]", st)
        self.assertIn("WP-01 (sonnet)", st)
        self.assertIn("mode fallback", st)
        self.assertIn("wave 1: OK", st)
        self.assertNotIn("WP-03", st, "WP-03 belongs to wave 2 and was not launched")

    def test_mark(self):
        r = self.repo.run("mark", "WP-02", "blocker", "missing", "the", "contract")
        self.assertEqual(r.returncode, 0, r.stderr)
        st = self.status()
        self.assertIn("[blocker]", st)
        self.assertIn("missing the contract", st)
        self.assertEqual(self.repo.run("mark", "WP-02", "raro").returncode, 1)
        self.assertEqual(self.repo.run("mark", "WP-99", "done").returncode, 1)

    def test_claim_records_workflow_mode(self):
        self.repo.hook(bash_payload("python3 .claude/bin/agentic.py claim WP-01", agent_id="ag1"))
        st = self.status()
        self.assertIn("[running]", st)
        self.assertIn("WP-01 (sonnet)", st)
        self.assertIn("mode workflow", st)

    def test_stop_stops_the_wave(self):
        proc = subprocess.Popen([sys.executable, str(SCRIPT), "run-wave", "1"], cwd=self.repo.dir,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                env=dict(self.repo.env, FAKE_SLEEP="30"))
        ledger = self.repo.dir / ".claude/state/ledger.json"
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                d = json.loads(ledger.read_text())
                if all(d.get(w, {}).get("pid") for w in ("WP-01", "WP-02")):
                    break
            except (OSError, json.JSONDecodeError):
                pass
            time.sleep(0.1)
        start = time.time()
        r = self.repo.run("stop")
        self.assertIn("stopped", r.stdout)
        out, _ = proc.communicate(timeout=15)
        self.assertLess(time.time() - start, 10, "stop must cut the wave without waiting for the agents")
        self.assertEqual(proc.returncode, 3)
        self.assertIn("STOPPED", out)
        self.assertIn("[stopped]", self.status())
        self.assertIn("No agents are running", self.repo.run("stop").stdout)

    def test_wave_0_launches_test_author(self):
        self.assertEqual(self.repo.run("run-acceptance").returncode, 0)
        a = self.args("AT")
        self.assertEqual(a[a.index("--agent") + 1], "test-author")
        self.assertEqual(a[a.index("--model") + 1], "sonnet")

    def test_review_without_write_tools(self):
        (self.logs / "x").write_text("")
        r = self.repo.run("run-review", env={"FAKE_STATUS": "PASS"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        a = self.args("REVIEW")
        self.assertEqual(a[a.index("--agent") + 1], "reviewer")
        for tool in ("Write", "Edit"):
            self.assertNotIn(tool, a)

    def test_implementers_may_run_acceptance(self):
        self.repo.run("run-wave", "1")
        self.assertIn("Bash(python3 acc.py:*)", self.args("WP-01"))

    def test_fix_limit(self):
        runs = self.repo.dir / ".claude/state/runs"
        runs.mkdir(parents=True, exist_ok=True)
        findings = [FINDING, dict(FINDING, wp="WP-01")]
        (runs / "REVIEW.json").write_text(json.dumps({"structured_output": {"status": "FAIL", "findings": findings}}))
        for _ in range(2):
            self.assertEqual(self.repo.run("run-wave", "1", "WP-02", "--fix").returncode, 0)
            self.assertTrue(self.prompt_of("WP-02").startswith("Fix WP-02."))
        r = self.repo.run("run-wave", "1", "WP-02", "--fix")
        self.assertEqual(r.returncode, 4)
        self.assertIn("used up", r.stderr)
        self.assertEqual(self.repo.run("run-wave", "1", "WP-01", "--fix").returncode, 0, "the limit is per WP")

    def test_timeout(self):
        start = time.time()
        r = self.repo.run("run-wave", "1", env={"FAKE_SLEEP": "30", "AGENTIC_TIMEOUT_S": "1"})
        self.assertLess(time.time() - start, 10)
        self.assertEqual(r.returncode, 3)
        self.assertIn("TIMEOUT", r.stdout)

    def test_blocker_marks_review(self):
        r = self.repo.run("run-wave", "1", env={"FAKE_STATUS": "BLOCKER"})
        self.assertEqual(r.returncode, 3)
        self.assertIn("RESULT: REVIEW", r.stdout)

    def test_invalid_manifest_does_not_launch(self):
        m = json.loads(json.dumps(MANIFEST))
        m["allow_bash"] = ["Bash(*)"]
        (self.repo.dir / "architecture.md").write_text(f"```json wp-manifest\n{json.dumps(m)}\n```")
        self.assertEqual(self.repo.run("run-wave", "1").returncode, 1)
        self.assertFalse((self.logs / "WP-01.args").exists())


if __name__ == "__main__":
    unittest.main()
