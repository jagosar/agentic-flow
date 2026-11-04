"""Acceptance tests of agentic-flow 2.7.0: AC-001 .. AC-008 of docs/architecture/0013 (the clean-code ratchet).

Run: python3 -m unittest discover -s .claude/bin -p test_acceptance_v27.py
Measurement and the ratchet are pure functions of quality.py; the command, the verify phase, the hook and install run
the live agentic.py against temporary git repositories. Nothing is spent.
"""
import json
import os
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
from test_agentic import PY, SCRIPT, Repo, bash_payload  # noqa: E402

BASELINE = ".claude/quality-baseline.json"
LIMITS = {"function_lines": 60, "test_function_lines": 100, "nesting": 4,
          "file_lines": 800, "file_growth": 30, "line_chars": 120}

PY_SOURCE = '''def f():
    a = 1
    b = 2
    return a + b


class C:
    def g(self):
        if self:
            for i in range(3):
                while i:
                    i -= 1


def chain(x):
    if x == 1:
        return 1
    elif x == 2:
        return 2
    elif x == 3:
        return 3
    else:
        return 0


def outer():
    def inner():
        if True:
            return 1
    return inner


LONG = "''' + "x" * 120 + '''"
'''

JS_SOURCE = '''function a(x, y) {
  if (x) {
    return 1
  } else if (y) {
    return 2
  } else {
    return 3
  }
}
const b = async (p) => {
  const s = `template { with } braces ${p}`
  // a comment with { braces } and }
  for (const i of p) {
    try {
      if (i) {
        items.map(j => { return j })
      }
    } catch (e) {
      throw e
    }
  }
}
class C {
  m() {
    return '{'
  }
}
'''


def quality():
    import quality as module
    return module


def function_source(name, lines):
    return f"def {name}():\n" + "    x = 1\n" * (lines - 1)


def baseline(**extra):
    data = {"version": 1, "flow_repo": False, "limits": dict(LIMITS), "exclude": [],
            "files": {"p.py": {"lines": 900, "long_lines": 2}},
            "functions": {"p.py::big": {"lines": 90, "nesting": 5}}}
    data.update(extra)
    return data


def current(big=(90, 5), file=(900, 2), functions=None, files=None):
    funcs = {"p.py::big": {"lines": big[0], "nesting": big[1], "test": False}}
    funcs.update(functions or {})
    all_files = {"p.py": {"lines": file[0], "long_lines": file[1]}}
    all_files.update(files or {})
    return {"files": all_files, "functions": funcs}


def last_json(text):
    return json.loads([line for line in text.splitlines() if line.strip().startswith("{")][-1])


class MeasureTests(unittest.TestCase):
    def test_ac_001_python(self):
        m = quality().measure_file("m.py", PY_SOURCE)
        fns = m["functions"]
        self.assertEqual(fns["f"]["lines"], 4)
        self.assertEqual(fns["C.g"]["nesting"], 3)
        self.assertEqual(fns["chain"]["nesting"], 1, "an elif chain is one level")
        self.assertEqual(fns["outer"]["nesting"], 0, "a nested def does not add to its parent")
        self.assertEqual(fns["outer.inner"]["nesting"], 1)
        self.assertEqual(m["long_lines"], 1)
        self.assertEqual(m["lines"], len(PY_SOURCE.splitlines()))

    def test_ac_001_syntax_error_does_not_raise(self):
        m = quality().measure_file("broken.py", "def f(:\n    pass\n")
        self.assertEqual(m["functions"], {})
        self.assertEqual(m["lines"], 2)

    def test_ac_002_javascript(self):
        m = quality().measure_file("w.js", JS_SOURCE)
        fns = m["functions"]
        self.assertIn("a", fns)
        self.assertIn("b", fns)
        self.assertIn("C.m", fns)
        self.assertEqual(fns["a"]["nesting"], 1, "else if is not a deeper level")
        self.assertEqual(fns["a"]["lines"], 9)
        self.assertEqual(fns["b"]["nesting"], 3, "braces in strings, templates and comments do not count")
        self.assertEqual(fns["b"]["lines"], 13)
        self.assertEqual(fns["C.m"]["lines"], 3)
        self.assertFalse([k for k in fns if k not in ("a", "b", "C", "C.m")], fns)


class RatchetTests(unittest.TestCase):
    def assert_fails(self, cur, path="p.py"):
        result = quality().check(baseline(), cur)
        self.assertFalse(result["ok"], cur)
        self.assertTrue(result["violations"])
        for line in result["violations"]:
            self.assertTrue(line.startswith("FAIL "), line)
            self.assertIn(path, line)
            self.assertIsNone(re.search(r"\b\d+\b", line.replace(path, "")), f"no values or line numbers: {line}")

    def assert_passes(self, cur):
        result = quality().check(baseline(), cur)
        self.assertTrue(result["ok"], result["violations"])
        return result

    def test_ac_003_worse_fails(self):
        self.assert_fails(current(big=(91, 5)))
        self.assert_fails(current(big=(90, 6)))
        self.assert_fails(current(functions={"p.py::new": {"lines": 61, "nesting": 1, "test": False}}))
        self.assert_fails(current(functions={"p.py::new": {"lines": 10, "nesting": 5, "test": False}}))
        self.assert_fails(current(functions={"test_x.py::test_a": {"lines": 101, "nesting": 1, "test": True}},
                                  files={"test_x.py": {"lines": 120, "long_lines": 0}}), path="test_x.py")
        self.assert_fails(current(file=(931, 2)))
        self.assert_fails(current(file=(900, 3)))
        self.assert_fails(current(files={"n.py": {"lines": 801, "long_lines": 0}}), path="n.py")
        self.assert_fails(current(files={"n.py": {"lines": 10, "long_lines": 1}}), path="n.py")

    def test_ac_003_same_or_better_passes(self):
        self.assert_passes(current())
        improved = self.assert_passes(current(big=(50, 3)))
        self.assertTrue(any("p.py::big" in item for item in improved["improvable"]), improved)
        self.assert_passes(current(file=(930, 2)))
        self.assert_passes(current(functions={"test_x.py::test_a": {"lines": 100, "nesting": 9, "test": True}},
                                   files={"test_x.py": {"lines": 120, "long_lines": 0}}))

    def test_ac_003_a_partial_improvement_reads_the_same(self):
        worse = quality().check(baseline(), current(big=(95, 5)))["violations"]
        less_worse = quality().check(baseline(), current(big=(92, 5)))["violations"]
        self.assertEqual(worse, less_worse)

    def test_ac_003_tighten_only_lowers(self):
        q = quality()
        lowered = q.tighten(baseline(), current(big=(80, 5)))
        self.assertEqual(lowered["functions"]["p.py::big"], {"lines": 80, "nesting": 5})
        within = q.tighten(baseline(), current(big=(50, 3)))
        self.assertNotIn("p.py::big", within["functions"])
        never_raised = q.tighten(baseline(), current(big=(95, 6), file=(920, 4)))
        self.assertEqual(never_raised["functions"]["p.py::big"], {"lines": 90, "nesting": 5})
        self.assertEqual(never_raised["files"]["p.py"], {"lines": 900, "long_lines": 2})
        none_added = q.tighten(baseline(), current(functions={"p.py::new": {"lines": 70, "nesting": 1, "test": False}}))
        self.assertNotIn("p.py::new", none_added["functions"])
        self.assertEqual(none_added["limits"], LIMITS)


class Case(unittest.TestCase):
    def repo(self, manifest=None):
        from test_agentic import MANIFEST
        r = Repo(manifest or MANIFEST)
        self.addCleanup(r.cleanup)
        return r


class CommandTests(Case):
    def test_ac_004_init_check_update(self):
        r = self.repo()
        r.write("src/a.py", function_source("big", 80) + "\n\n" + function_source("small", 5))
        first = r.run("quality")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertIn("skipped", last_json(first.stdout))
        init = r.run("quality", "--init")
        self.assertEqual(init.returncode, 0, init.stdout + init.stderr)
        path = r.dir / BASELINE
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIs(data["flow_repo"], False)
        self.assertEqual(data["functions"]["src/a.py::big"]["lines"], 80)
        before = path.read_bytes()
        again = r.run("quality", "--init")
        self.assertEqual(again.returncode, 1)
        self.assertEqual(path.read_bytes(), before)
        r.write("src/a.py", function_source("big", 90) + "\n\n" + function_source("small", 5))
        worse = r.run("quality")
        self.assertEqual(worse.returncode, 3, worse.stdout)
        self.assertTrue([line for line in worse.stdout.splitlines() if line.startswith("FAIL") and "src/a.py" in line])
        self.assertIs(last_json(worse.stdout)["ok"], False)
        self.assertEqual(path.read_bytes(), before, "a plain check never writes the baseline")
        r.write("src/a.py", function_source("big", 70) + "\n\n" + function_source("small", 5))
        update = r.run("quality", "--update")
        self.assertEqual(update.returncode, 0, update.stdout + update.stderr)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["functions"]["src/a.py::big"]["lines"], 70)

    def test_ac_004_flow_files_are_not_measured_in_a_project(self):
        r = self.repo()
        r.write("src/a.py", function_source("small", 5))
        r.write(".claude/bin/tool.py", function_source("huge", 200))
        self.assertEqual(r.run("quality", "--init").returncode, 0)
        data = json.loads((r.dir / BASELINE).read_text(encoding="utf-8"))
        self.assertFalse([k for k in list(data["functions"]) + list(data["files"]) if k.startswith(".claude/")], data)

    def test_ac_004_a_foreign_baseline_is_ignored(self):
        r = self.repo()
        r.write("src/a.py", function_source("big", 80))
        r.write(BASELINE, json.dumps(dict(baseline(), flow_repo=True)))
        result = r.run("quality")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("skipped", last_json(result.stdout))


def verify_manifest(with_verify=True):
    m = {"allow_bash": ["Bash(python3 -m unittest:*)"],
         "acceptance": {"files": ["acceptance/"], "command": f"{PY} acc.py"},
         "work_packages": [{"id": "WP-01", "wave": 1, "depends_on": [], "files": ["src/a.py"], "acs": ["AC-001"]}]}
    if with_verify:
        m["verify"] = {"tests": f"{PY} -c pass"}
    return m


class VerifyTests(Case):
    def prepared(self, with_verify=True):
        r = self.repo(verify_manifest(with_verify))
        r.write("acc.py", "")
        r.write("src/a.py", function_source("small", 5))
        self.assertEqual(r.run("quality", "--init").returncode, 0)
        return r

    def phase(self, out):
        return next((p for p in last_json(out)["phases"] if p["name"] == "quality"), None)

    def test_ac_005_a_worse_package_blocks_and_is_named(self):
        r = self.prepared()
        self.assertEqual(r.run("baseline").returncode, 0)
        r.write("src/a.py", function_source("small", 70))
        out = r.run("verify")
        self.assertEqual(out.returncode, 3, out.stdout + out.stderr)
        report = last_json(out.stdout)
        self.assertIn(self.phase(out.stdout)["status"], ("regression", "fails"))
        self.assertIn("quality", report["blocking"])
        self.assertIn("src/a.py", report["suspects"]["WP-01"]["files"])

    def test_ac_005_a_pre_existing_violation_does_not_block(self):
        r = self.prepared()
        r.write("src/a.py", function_source("small", 70))
        r.run("baseline")
        out = r.run("verify")
        self.assertEqual(self.phase(out.stdout)["status"], "pre-existing failure", out.stdout)
        self.assertNotIn("quality", last_json(out.stdout)["blocking"])

    def test_ac_005_baseline_runs_quality_without_verify_commands(self):
        r = self.prepared(with_verify=False)
        out = r.run("baseline")
        report = last_json(out.stdout)
        self.assertNotIn("skipped", report)
        self.assertTrue([p for p in report["phases"] if p["name"] == "quality"], report)

    def test_ac_005_no_baseline_no_phase(self):
        r = self.repo(verify_manifest())
        r.write("acc.py", "")
        r.write("src/a.py", function_source("small", 70))
        r.run("baseline")
        self.assertIsNone(self.phase(r.run("verify").stdout))


class GuardTests(Case):
    def test_ac_006_never_owned(self):
        import agentic
        self.assertIsNotNone(agentic.never_owned_problem(BASELINE))
        manifest = {"maintainer": True, "acceptance": {"files": ["acceptance/"], "command": "x"},
                    "work_packages": [{"id": "WP-01", "wave": 1, "depends_on": [], "files": [BASELINE]}]}
        self.assertTrue([e for e in agentic.validate(manifest) if "quality-baseline" in e])

    def test_ac_006_agents_cannot_write_the_baseline(self):
        r = self.repo()
        for cmd, agent_code in (("python3 .claude/bin/agentic.py quality --update", 2),
                                ("python3 .claude/bin/agentic.py quality --init", 2),
                                ("python3 .claude/bin/agentic.py quality", 0)):
            with self.subTest(cmd=cmd):
                self.assertEqual(r.hook(bash_payload(cmd), wp="WP-01"), agent_code)
                self.assertEqual(r.hook(bash_payload(cmd)), 0, "the main session may")


class InstallTests(unittest.TestCase):
    def target(self, files):
        d = Path(tempfile.mkdtemp(prefix="quality-install-"))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        for rel, text in files.items():
            (d / rel).parent.mkdir(parents=True, exist_ok=True)
            (d / rel).write_text(text, encoding="utf-8")
        for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                    ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"]):
            subprocess.run(cmd, cwd=d, check=True)
        return d

    def install(self, target, *flags):
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PROJECT_DIR", "CLAUDECODE", "AGENTIC_WP")}
        return subprocess.run([sys.executable, str(SCRIPT), "install", str(target), *flags], capture_output=True,
                              text=True, env=env, encoding="utf-8", errors="replace")

    def test_ac_007_install_creates_the_baseline(self):
        t = self.target({"main.py": function_source("main", 5)})
        r = self.install(t)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("quality baseline: created", r.stdout + r.stderr)
        self.assertTrue((t / ".claude/bin/quality.py").is_file())
        self.assertIs(json.loads((t / BASELINE).read_text(encoding="utf-8"))["flow_repo"], False)
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "AGENTIC_WP")}
        env["CLAUDE_PROJECT_DIR"] = str(t)
        check = subprocess.run([sys.executable, str(t / ".claude/bin/agentic.py"), "quality"], cwd=t, env=env,
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

    def test_ac_007_an_existing_baseline_is_kept(self):
        own = json.dumps(baseline(files={}, functions={}), indent=2) + "\n"
        t = self.target({"main.py": "x = 1\n", BASELINE: own})
        r = self.install(t)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("quality baseline: kept", r.stdout + r.stderr)
        self.assertEqual((t / BASELINE).read_text(encoding="utf-8"), own)

    def test_ac_007_a_template_baseline_is_replaced(self):
        t = self.target({"main.py": "x = 1\n", BASELINE: json.dumps(dict(baseline(), flow_repo=True))})
        r = self.install(t)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("quality baseline: replaced", r.stdout + r.stderr)
        self.assertIs(json.loads((t / BASELINE).read_text(encoding="utf-8"))["flow_repo"], False)

    def test_ac_007_dry_run_writes_nothing(self):
        t = self.target({"main.py": "x = 1\n"})
        r = self.install(t, "--dry-run")
        self.assertIn("quality baseline: would be created", r.stdout + r.stderr)
        self.assertFalse((t / BASELINE).exists())


class ReleaseTests(unittest.TestCase):
    def read(self, rel):
        return (ROOT / rel).read_text(encoding="utf-8")

    def test_ac_008_ci_release_and_docs(self):
        import upgrade
        self.assertIn("python .claude/bin/agentic.py quality", self.read(".github/workflows/agentic-flow-ci.yml"))
        notes = upgrade.NOTES.get("2.7.0")
        self.assertTrue(notes)
        joined = " ".join(notes)
        self.assertIn("quality-baseline.json", joined)
        self.assertIn("verify", joined)
        readme = self.read("README.md")
        guard = readme.split("## Guardrails")[1].split("## Documentation")[0]
        self.assertTrue([line for line in guard.splitlines() if line.startswith("|") and "quality" in line])
        hub = self.read("docs/how-to/README.md")
        self.assertIn("quality --init", hub.split("## Script reference")[1].split("## Troubleshooting")[0])
        self.assertLessEqual(len(hub.splitlines()), 260)


if __name__ == "__main__":
    unittest.main()
