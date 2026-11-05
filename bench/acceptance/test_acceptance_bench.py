"""Acceptance tests of the measurement bench (AC-001 ... AC-010). Black box: they load bench/bench.py and run its
command line; every run uses the simulated `claude` of .claude/bin/testutil.py, so they never spend money."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
BENCH_PY = REPO / "bench" / "bench.py"
AGENTIC = REPO / ".claude" / "bin" / "agentic.py"
sys.path.insert(0, str(REPO / ".claude" / "bin"))
import testutil  # noqa: E402

FIXTURE_NAME = "benchfix"
ACC_PY = ("import os, sys\n"
          "if os.path.exists('.bench_oracle'):\n    sys.exit(1)\n"
          "files = ('src/a.py', 'src/b/x.py', 'src/c.py')\n"
          "sys.exit(0 if all(os.path.exists(f) for f in files) else 1)\n")
ORACLE_PY = ("import os\nimport unittest\n\n\nclass Oracle(unittest.TestCase):\n"
             "    def test_a(self):\n        self.assertTrue(os.path.exists('src/a.py'))\n\n"
             "    def test_b(self):\n        self.assertTrue(os.path.exists('src/b/x.py'))\n\n"
             "    def test_c(self):\n        self.assertTrue(os.path.exists('src/c.py'))\n\n"
             "    def test_d(self):\n        self.assertTrue(os.path.exists('src/d.py'))\n")
GOOD_FILES = ("src/a.py", "src/b/x.py", "src/c.py", "src/d.py")  # reference/good passes the whole oracle
BAD_FILES = ("src/a.py", "src/b/x.py")                            # reference/bad fails part of it
ISOLATION_ENV = {"CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1", "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}
ISOLATION_FLAGS = ["--setting-sources", "project,local"]


def load_bench():
    spec = importlib.util.spec_from_file_location("bench_module", BENCH_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_fixture(root: Path) -> Path:
    fixture = root / FIXTURE_NAME
    (fixture / "repo").mkdir(parents=True)
    (fixture / "oracle").mkdir()
    (fixture / "fixture.json").write_text(
        json.dumps({"name": FIXTURE_NAME, "description": "test fixture", "difficulty": "simple"}), encoding="utf-8")
    manifest = {
        "allow_bash": ["Bash(python3 -m unittest:*)"],
        "acceptance": {"files": ["acceptance/"], "command": shlex.join([sys.executable, "acc.py"])},
        "work_packages": [
            {"id": "WP-01", "wave": 1, "depends_on": [], "files": ["src/a.py"], "acs": ["AC-001"]},
            {"id": "WP-02", "wave": 1, "depends_on": [], "files": ["src/b/"]},
            {"id": "WP-03", "wave": 2, "depends_on": ["WP-01"], "files": ["src/c.py"]},
        ],
    }
    plan = f"# Plan\n\n```json wp-manifest\n{json.dumps(manifest, indent=2)}\n```\n"
    (fixture / "repo" / "architecture.md").write_text(plan, encoding="utf-8")
    (fixture / "repo" / "acc.py").write_text(ACC_PY, encoding="utf-8")
    (fixture / "oracle" / "test_oracle.py").write_text(ORACLE_PY, encoding="utf-8")
    write_reference(fixture, "good", GOOD_FILES)
    write_reference(fixture, "bad", BAD_FILES)
    return fixture


def write_reference(fixture: Path, name: str, files: tuple) -> None:
    for rel in files:
        target = fixture / "reference" / name / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x = 1\n", encoding="utf-8")


class Sandbox:
    """A private temp dir with the fixture, the simulated claude, its log and the environment to run bench.py."""

    def __init__(self, **extra_env: str):
        self.root = Path(tempfile.mkdtemp(prefix="bench-acc-"))
        self.tmp = self.root / "tmp"
        self.tmp.mkdir()
        self.logs = self.root / "logs"
        self.logs.mkdir()
        self.results = self.root / "results"
        self.fixture = make_fixture(self.root)
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PROJECT_DIR", "AGENTIC_WP")}
        env.update(TMPDIR=str(self.tmp), TEMP=str(self.tmp), TMP=str(self.tmp), FAKE_LOG_DIR=str(self.logs),
                   AGENTIC_CLAUDE=testutil.install_fake_claude(bin_dir), FAKE_WRITE="1")
        env.update(extra_env)
        self.env = env

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def bench(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(BENCH_PY), *args], cwd=self.root, env=self.env,
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)

    def run_args(self, *extra: str) -> list:
        return ["run", "--fixture", str(self.fixture), "--out", str(self.results), "--source", str(REPO), *extra]

    def result_files(self) -> list:
        return sorted(p for p in self.results.glob("*.json") if p.name not in ("old.json", "bad.json"))

    def load_result(self) -> dict:
        files = self.result_files()
        self.assertion_one(files)
        return json.loads(files[0].read_text(encoding="utf-8"))

    @staticmethod
    def assertion_one(files: list) -> None:
        if len(files) != 1:
            raise AssertionError(f"expected exactly one results file, found {files}")

    def leftovers(self) -> list:
        return sorted(p.name for p in self.tmp.glob("bench-run-*"))


def plugin_version() -> str:
    return json.loads((REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]


def is_alive(pid: int) -> bool:
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True).stdout
        return str(pid) in out
    stat = Path(f"/proc/{pid}/stat")
    if stat.exists():
        return stat.read_text(encoding="utf-8", errors="replace").rsplit(")", 1)[1].split()[0] != "Z"
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class SharedRunTests(unittest.TestCase):
    """AC-001 and AC-002 share one bench run."""

    @classmethod
    def setUpClass(cls):
        cls.box = Sandbox()
        cls.bench_results = REPO / "bench" / "RESULTS.md"
        cls.results_before = cls.bench_results.stat().st_mtime_ns if cls.bench_results.exists() else None
        cls.proc = cls.box.bench(*cls.box.run_args("--repeat", "1"))

    @classmethod
    def tearDownClass(cls):
        cls.box.cleanup()

    def test_ac_001_one_run(self):
        box = self.box
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)
        data = box.load_result()
        self.assertEqual(data["schema"], 1)
        self.assertEqual(len(data["runs"]), 1)
        run = data["runs"][0]
        self.assertEqual(run["result"], "OK")
        self.assertEqual(run["fix_cycles"], 0)
        self.assertEqual(run["oracle"], {"passed": 3, "total": 4})
        self.assertGreater(run["usage"]["output"], 0)
        self.assertGreater(run["agents"], 0)
        self.assertGreater(run["seconds"], 0)
        self.assertEqual(data["flow_version"], plugin_version())
        self.assertRegex(data["flow_commit"], r"^[0-9a-f]{7,}$")
        self.assertEqual(data["summary"][FIXTURE_NAME]["runs"], 1)
        self.assertTrue((box.root / "RESULTS.md").exists())

    def test_ac_001_leaves_nothing_behind(self):
        self.assertEqual(self.box.leftovers(), [])
        after = self.bench_results.stat().st_mtime_ns if self.bench_results.exists() else None
        self.assertEqual(after, self.results_before)

    def test_ac_002_oracle_hidden(self):
        data = self.box.load_result()
        run = data["runs"][0]
        self.assertEqual(run["result"], "OK")
        self.assertEqual(run["oracle"]["total"], 4)
        calls = testutil.fake_calls(self.box.logs)
        self.assertGreater(len(calls), 0)
        for call in calls:
            self.assertNotIn(".bench_oracle", call["prompt"])
            self.assertNotIn("test_oracle", call["prompt"])


    def test_ac_011_each_session_result_is_kept(self):
        """Next to the results file, a folder with every session's workflow-result.json: what the agents really reported."""
        results = self.box.result_files()[0]
        kept = results.with_suffix("")  # <out>/<results stem>/
        self.assertTrue(kept.is_dir(), kept)
        files = sorted(p.name for p in kept.glob("*.json"))
        self.assertEqual(files, [f"{FIXTURE_NAME}-1.json"])
        session = json.loads((kept / files[0]).read_text(encoding="utf-8"))
        for key in ("result", "pending", "not_checked", "usage", "work_packages"):
            self.assertIn(key, session)
        self.assertEqual(session["result"], "OK")

    def test_ac_009_sessions_are_isolated(self):
        """Every simulated claude call ran without the user's settings, CLAUDE.md files or auto memory."""
        calls = testutil.fake_calls(self.box.logs)
        self.assertGreater(len(calls), 0)
        for call in calls:
            argv = call["argv"]
            self.assertLess(argv.index("--setting-sources"), argv.index("-p"), argv)
            self.assertEqual(argv[argv.index("--setting-sources") + 1], "project,local", argv)
            for var, value in ISOLATION_ENV.items():
                self.assertEqual(call["env"].get(var), value, (var, call["env"]))


class RepeatAndReportTests(unittest.TestCase):
    def test_ac_003_repeat_and_report(self):
        box = Sandbox()
        self.addCleanup(box.cleanup)
        box.results.mkdir()
        (box.results / "old.json").write_text('{"schema": 99}', encoding="utf-8")
        (box.results / "bad.json").write_text("not json", encoding="utf-8")
        proc = box.bench(*box.run_args("--repeat", "3"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = box.load_result()
        self.assertEqual([r["index"] for r in data["runs"]], [1, 2, 3])
        summary = data["summary"][FIXTURE_NAME]
        self.assertEqual((summary["runs"], summary["ok"], summary["oracle_rate_median"]), (3, 3, 0.75))
        report = box.bench("report", "--out", str(box.results))
        self.assertEqual(report.returncode, 0, report.stderr)
        text = (box.root / "RESULTS.md").read_text(encoding="utf-8")
        rows = [line for line in text.splitlines() if line.startswith("|") and FIXTURE_NAME in line]
        self.assertEqual(len(rows), 1, text)
        for expected in (plugin_version(), "3/3", "0.75 (0.75–0.75)"):
            self.assertIn(expected, rows[0])
        self.assertEqual(box.leftovers(), [])


class FailureTests(unittest.TestCase):
    def test_ac_004_failures_recorded(self):
        self.check_rogue_run()
        self.check_stuck_runs()

    def check_rogue_run(self):
        box = Sandbox(FAKE_ROGUE="1")
        self.addCleanup(box.cleanup)
        proc = box.bench(*box.run_args("--repeat", "1"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        run = box.load_result()["runs"][0]
        self.assertEqual(run["result"], "REVIEW")
        self.assertIsNotNone(run["failed_stage"])
        self.assertEqual(box.leftovers(), [])

    def check_stuck_runs(self):
        box = Sandbox()
        self.addCleanup(box.cleanup)
        bench = load_bench()
        env = dict(box.env, FAKE_SLEEP="30")
        started = time.monotonic()
        with mock.patch.object(tempfile, "tempdir", str(box.tmp)):
            path = bench.run([box.fixture], REPO, 2, box.results, timeout_s=5, env=env)
        self.assertLess(time.monotonic() - started, 60)
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.assertEqual([r["result"] for r in data["runs"]], ["timeout", "timeout"])
        for run in data["runs"]:
            self.assertEqual(run["oracle"]["total"], 4)
        logged = len(testutil.fake_calls(box.logs))
        self.assertGreater(logged, 0)
        time.sleep(10)
        self.assertEqual(len(testutil.fake_calls(box.logs)), logged)
        pids = [int(p.stem.rsplit("-", 1)[1]) for p in box.logs.glob("call-*.json")]
        self.assertEqual([pid for pid in pids if is_alive(pid)], [])
        self.assertEqual(box.leftovers(), [])


class BadInputTests(unittest.TestCase):
    def test_ac_005_bad_input(self):
        box = Sandbox()
        self.addCleanup(box.cleanup)
        box.results.mkdir()
        empty_source = box.root / "empty-source"
        empty_source.mkdir()
        cases = [
            box.run_args("--repeat", "0"),
            ["run", "--fixture", "does-not-exist", "--out", str(box.results), "--source", str(REPO)],
            box.run_args("--auth", "other"),
            ["run", "--fixture", str(box.fixture), "--out", str(box.results), "--source", str(empty_source)],
        ]
        for args in cases:
            with self.subTest(args=args):
                proc = box.bench(*args)
                self.assertEqual(proc.returncode, 1, proc.stderr)
                self.assertTrue(proc.stderr.strip())
                self.assertNotIn("Traceback", proc.stderr)
                self.assertEqual(list(box.results.iterdir()), [])
                self.assertEqual(testutil.fake_calls(box.logs), [])


def run_in(cwd: Path, args: list, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300)


class FixtureReady:
    """Shared checks of a shipped fixture (AC-006, AC-008)."""

    def prepare(self, name: str):
        fixture = REPO / "bench" / "fixtures" / name
        self.assertTrue(fixture.is_dir(), f"missing {fixture}")
        info = json.loads((fixture / "fixture.json").read_text(encoding="utf-8"))
        copy = Path(tempfile.mkdtemp(prefix="bench-ready-"))
        self.addCleanup(shutil.rmtree, copy, ignore_errors=True)
        shutil.copytree(fixture / "repo", copy, dirs_exist_ok=True)
        env = {k: v for k, v in os.environ.items() if k != "AGENTIC_WP"}
        env["CLAUDE_PROJECT_DIR"] = str(copy)
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
        for cmd in (["git", "init", "-q"], ["git", "add", "-A"], [*git, "commit", "-qm", "init"]):
            self.assertEqual(run_in(copy, cmd, env).returncode, 0)
        install = run_in(copy, [sys.executable, str(AGENTIC), "install", str(copy)], env)
        self.assertEqual(install.returncode, 0, install.stderr + install.stdout)
        for cmd in (["git", "add", "-A"], [*git, "commit", "-qm", "install"]):
            run_in(copy, cmd, env)
        validate = run_in(copy, [sys.executable, str(AGENTIC), "validate"], env)
        self.assertEqual(validate.returncode, 0, validate.stderr + validate.stdout)
        self.assertIn("Manifest valid", validate.stdout + validate.stderr)
        return fixture, info, copy, env

    def check_oracle_and_tests(self, fixture: Path, copy: Path, env: dict, minimum: int) -> dict:
        oracle = fixture / "oracle"
        proc = run_in(copy, [sys.executable, "-m", "unittest", "discover", "-s", str(oracle), "-t", str(oracle)],
                      dict(env, PYTHONPATH=str(copy)))
        summary = proc.stderr
        found = re.search(r"Ran (\d+) tests?", summary)
        self.assertIsNotNone(found, summary)
        total = int(found.group(1))
        self.assertGreaterEqual(total, minimum)
        failed = sum(int(n) for n in re.findall(r"(?:failures|errors)=(\d+)", summary))
        self.assertEqual(failed, total, summary)
        text = (copy / "architecture.md").read_text(encoding="utf-8")
        self.assertNotIn("oracle", text.lower())
        match = re.search(r"```json\s+wp-manifest\s*\n(.*?)\n```", text, re.S)
        manifest = json.loads(match.group(1))
        tests = shlex.split(manifest["verify"]["tests"])
        self.assertEqual(tests[0], "python3")
        existing = run_in(copy, [sys.executable, *tests[1:]], dict(env, PYTHONPATH=str(copy)))
        self.assertEqual(existing.returncode, 0, existing.stderr)
        return manifest


class TempconvReadyTests(FixtureReady, unittest.TestCase):
    def test_ac_006_tempconv_ready(self):
        fixture, info, copy, env = self.prepare("tempconv")
        self.assertEqual(info["name"], "tempconv")
        self.assertEqual(info["difficulty"], "simple")
        self.check_oracle_and_tests(fixture, copy, env, 10)


class InventoryReadyTests(FixtureReady, unittest.TestCase):
    def test_ac_008_inventory_ready(self):
        fixture, info, copy, env = self.prepare("inventory")
        self.assertEqual(info["name"], "inventory")
        self.assertEqual(info["difficulty"], "trap")
        manifest = self.check_oracle_and_tests(fixture, copy, env, 12)
        waves = {wp["id"]: wp for wp in manifest["work_packages"]}
        self.assertEqual(len({wp["wave"] for wp in waves.values()}), 2)
        self.assertEqual(waves["WP-02"]["wave"], 2)
        self.assertIn("WP-01", waves["WP-02"]["depends_on"])


def top_level_block(text: str, key: str) -> str:
    match = re.search(rf"^{key}:(.*?)(?=^\S|\Z)", text, re.S | re.M)
    return match.group(1) if match else ""


class CiTests(unittest.TestCase):
    def test_ac_007_ci(self):
        workflows = REPO / ".github" / "workflows"
        bench_file = workflows / "agentic-bench.yml"
        self.assertTrue(bench_file.exists())
        text = bench_file.read_text(encoding="utf-8")
        triggers = top_level_block(text, "on") or top_level_block(text, '"on"')
        self.assertIn("workflow_dispatch", triggers)
        self.assertIn("repeat", triggers)
        for forbidden in ("push", "pull_request", "schedule"):
            self.assertNotIn(forbidden, triggers)
        self.assertIn("secrets.ANTHROPIC_API_KEY", text)
        self.assertIn("bench/bench.py run", text)
        self.assertIn("--auth inherit", text)
        self.assertIn("actions/upload-artifact", text)
        self.assertIn("bench/results", text)
        permissions = top_level_block(text, "permissions")
        self.assertIn("contents: read", permissions)
        self.assertNotIn("write", permissions)
        uses = re.findall(r"^\s*-?\s*uses:\s*(\S+)", text, re.M)
        self.assertTrue(uses)
        for ref in uses:
            self.assertRegex(ref, r"@[0-9a-f]{40}$")
        ci = (workflows / "agentic-flow-ci.yml").read_text(encoding="utf-8")
        paths = re.findall(r"^\s*paths:\s*\[(.*)\]", ci, re.M)
        self.assertGreaterEqual(len(paths), 2)
        for line in paths:
            self.assertIn('"bench/**"', line)
            self.assertIn('".github/workflows/agentic-bench.yml"', line)
        self.assertIn('unittest discover -s bench -p "test_*.py"', ci)
        self.assertIn("unittest discover -s bench/acceptance", ci)
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
        proc = run_in(REPO / ".claude" / "bin",
                      [sys.executable, "-m", "unittest", "test_definitions", "test_ci"], env)
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])



class SelftestTests(unittest.TestCase):
    """AC-010: the instruments are checked before any spend."""

    def break_bad_reference(self, box: Sandbox) -> None:
        shutil.rmtree(box.fixture / "reference" / "bad")
        write_reference(box.fixture, "bad", GOOD_FILES)  # a "bad" reference that passes the oracle

    def test_ac_010_selftest_passes_for_sound_fixtures(self):
        box = Sandbox()
        self.addCleanup(box.cleanup)
        proc = box.bench("selftest", "--fixture", str(box.fixture))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn(f"{FIXTURE_NAME}: ok", proc.stdout)
        real = box.bench("selftest", "--source", str(REPO))
        self.assertEqual(real.returncode, 0, real.stdout + real.stderr)
        for name in ("tempconv", "inventory"):
            self.assertIn(f"{name}: ok", real.stdout)
        self.assertEqual(testutil.fake_calls(box.logs), [])
        self.assertEqual(box.leftovers(), [])

    def test_ac_010_broken_instruments_stop_before_any_spend(self):
        box = Sandbox()
        self.addCleanup(box.cleanup)
        self.break_bad_reference(box)
        proc = box.bench("selftest", "--fixture", str(box.fixture))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("bad", proc.stdout + proc.stderr)
        run = box.bench(*box.run_args("--repeat", "1"))
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertNotIn("Traceback", run.stderr)
        self.assertEqual(testutil.fake_calls(box.logs), [], "no claude call before the instruments pass")
        self.assertEqual(box.result_files(), [])
        oracle = box.fixture / "oracle" / "test_oracle.py"
        oracle.write_text(oracle.read_text(encoding="utf-8") + "\n    def test_free(self):\n        pass\n",
                          encoding="utf-8")
        shutil.rmtree(box.fixture / "reference" / "bad")
        write_reference(box.fixture, "bad", BAD_FILES)
        proc = box.bench("selftest", "--fixture", str(box.fixture))
        self.assertEqual(proc.returncode, 1, "an oracle test that passes with no code is a broken instrument")
        shutil.rmtree(box.fixture / "reference" / "good")
        missing = box.bench(*box.run_args("--repeat", "1"))
        self.assertEqual(missing.returncode, 1)
        self.assertIn("reference", missing.stderr)

if __name__ == "__main__":
    unittest.main()
