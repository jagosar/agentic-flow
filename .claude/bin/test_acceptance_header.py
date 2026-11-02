"""Acceptance tests of the README header (agentic-flow 2.4): AC-001 .. AC-009 of docs/architecture/0010.

Run: python3 -m unittest discover -s .claude/bin -p test_acceptance_header.py
Every readme-header call runs this repo's agentic.py against a temporary repo with CLAUDE_PROJECT_DIR set to it:
without it, ROOT falls back to this repository and the command would rewrite the flow's own README.
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
SCRIPT = BIN / "agentic.py"
sys.path.insert(0, str(BIN))
import upgrade  # noqa: E402

START = "<!-- agentic-flow:header:start -->"
END = "<!-- agentic-flow:header:end -->"
MARKER = "<!-- agentic-flow-template -->"
GIT_ID = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
MIT = "MIT License\n\nCopyright (c) 2026 someone\n"
APACHE = "\n                                 Apache License\n                           Version 2.0, January 2004\n"
VERSION_RE = re.compile(r"\b[12]\.\d+\.\d+\b")


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def block(text):
    return text.split(START, 1)[1].split(END, 1)[0]


class HeaderCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="header-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.dir = self.tmp / "demo"
        self.dir.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.dir, check=True)
        self.env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "AGENTIC_WP")}
        self.env["CLAUDE_PROJECT_DIR"] = str(self.dir)

    def write(self, rel, text):
        path = self.dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def readme(self):
        return (self.dir / "README.md").read_text(encoding="utf-8")

    def header(self, *flags):
        r = subprocess.run([sys.executable, str(SCRIPT), "readme-header", *flags], cwd=self.dir, env=self.env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        lines = [line for line in r.stdout.splitlines() if line.strip().startswith("{")]
        state = json.loads(lines[-1]).get("readme_header") if lines else None
        return r, state

    def project(self, readme="# Demo\n\nA small tool.\n\n## Usage\n\nrun it\n"):
        self.write("LICENSE", MIT)
        self.write("src/a.py", "x = 1\n")
        self.write("src/b.py", "y = 2\n")
        if readme is not None:
            self.write("README.md", readme)


class FirstHeaderTests(HeaderCase):
    def test_ac_001_title_and_description_move_into_the_block_once(self):
        self.project()
        r, state = self.header()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(state, "added")
        text = self.readme()
        self.assertTrue(text.startswith(START), text[:200])
        inside = block(text)
        self.assertIn("# Demo", inside)
        self.assertIn("A small tool.", inside)
        self.assertIn("licence-MIT", inside)
        self.assertIn("python", inside)
        self.assertIn("built%20with-agentic--flow", inside)
        self.assertTrue(text.split(END, 1)[1].startswith("\n\n## Usage"), text.split(END, 1)[1][:40])
        self.assertEqual(text.count("# Demo"), 1)
        self.assertEqual(text.count("A small tool."), 1)
        before = (self.dir / "README.md").read_bytes()
        r, state = self.header()
        self.assertEqual((r.returncode, state), (0, "unchanged"), r.stdout + r.stderr)
        self.assertEqual((self.dir / "README.md").read_bytes(), before)


class UpdateTests(HeaderCase):
    def test_ac_002_edits_are_kept_and_only_badges_change(self):
        self.project()
        self.header()
        text = self.readme().replace("# Demo\n", "# Demo Tool\n").replace("A small tool.", "Edited.")
        text = text.replace(END + "\n", END + "\nextra text\n")
        (self.dir / "README.md").write_text(text, encoding="utf-8")
        self.write("LICENSE", APACHE)
        r, state = self.header()
        self.assertEqual((r.returncode, state), (0, "updated"), r.stdout + r.stderr)
        text = self.readme()
        inside = block(text)
        self.assertIn("# Demo Tool", inside)
        self.assertIn("Edited.", inside)
        self.assertNotIn("A small tool.", text)
        self.assertIn("Apache--2.0", inside)
        self.assertNotIn("licence-MIT", inside)
        self.assertEqual(text.count("extra text"), 1)


class EdgeTests(HeaderCase):
    def test_ac_003_no_leading_title(self):
        self.project("Some intro\n\n# Later\n")
        r, state = self.header()
        self.assertEqual((r.returncode, state), (0, "added"), r.stdout + r.stderr)
        text = self.readme()
        inside = block(text)
        self.assertIn("# demo", inside)
        self.assertNotIn("Some intro", inside, "no description without a leading H1")
        after = text.split(END, 1)[1]
        self.assertIn("Some intro", after)
        self.assertIn("# Later", after)

    def test_ac_003_no_readme(self):
        self.project(readme=None)
        r, state = self.header()
        self.assertEqual((r.returncode, state), (0, "added"), r.stdout + r.stderr)
        text = self.readme()
        self.assertTrue(text.startswith(START))
        self.assertEqual(text.split(END, 1)[1].strip(), "")

    def test_ac_003_the_template_marker_stays_first(self):
        self.project(f"{MARKER}\n# agentic-flow\n\nA team.\n")
        r, state = self.header()
        self.assertEqual((r.returncode, state), (0, "added"), r.stdout + r.stderr)
        lines = self.readme().splitlines()
        self.assertEqual(lines[0], MARKER)
        self.assertEqual(lines[1], START)
        inside = block(self.readme())
        self.assertIn("# agentic-flow", inside)
        self.assertIn("A team.", inside)
        self.assertIn("agentic--flow", inside)
        self.assertIsNone(VERSION_RE.search(inside), "the flow's own badge has no version")


class SponsorTests(HeaderCase):
    def config(self, readme):
        self.write(".claude/agentic.json", json.dumps({"readme": readme}))

    def test_ac_004_valid_sponsors_and_skipped_ones(self):
        self.project()
        self.config({"sponsors": [
            {"label": "GitHub Sponsors", "url": "https://github.com/sponsors/someone"},
            {"label": "Plain", "url": "http://example.com/x"},
            {"label": "Paren", "url": "https://example.com/a)b"},
            {"label": "x](javascript:alert(1)", "url": "https://example.com/ok"},
        ]})
        r, state = self.header()
        self.assertEqual((r.returncode, state), (0, "added"), r.stdout + r.stderr)
        text = self.readme()
        self.assertIn("https://github.com/sponsors/someone", text)
        for bad in ("http://example.com", "a)b", "javascript", "Plain", "Paren"):
            self.assertNotIn(bad, text)
        for i, reason in ((1, "url must start with https://"), (2, "url has a character that is not allowed"),
                          (3, "label must be 1-40 characters without [ ] < >")):
            self.assertIn(f"readme.sponsors[{i}] skipped: {reason}", r.stderr)

    def test_ac_004_header_can_be_turned_off(self):
        self.project()
        self.config({"header": False})
        r, state = self.header()
        self.assertEqual((r.returncode, state), (0, "disabled"), r.stdout + r.stderr)
        self.assertNotIn(START, self.readme())


class CheckTests(HeaderCase):
    def test_ac_006_check_never_writes(self):
        self.project()
        self.header()
        before = self.readme()
        r, state = self.header("--check")
        self.assertEqual((r.returncode, state), (0, "unchanged"), r.stdout + r.stderr)
        self.write("LICENSE", APACHE)
        r, state = self.header("--check")
        self.assertEqual((r.returncode, state), (3, "updated"), r.stdout + r.stderr)
        self.assertEqual(self.readme(), before)

    def test_ac_006_a_damaged_block_is_an_error(self):
        self.project(f"{START}\n<div align=\"center\">\n\n# Demo\n\nno end marker\n")
        before = self.readme()
        r, _ = self.header()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("README.md: start marker without an end marker", r.stderr)
        self.assertEqual(self.readme(), before)

    def test_ac_006_a_bad_config_is_an_error(self):
        self.project()
        self.write(".claude/agentic.json", json.dumps({"readme": True}))
        before = self.readme()
        r, _ = self.header()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("readme in .claude/agentic.json must be an object", r.stderr)
        self.assertEqual(self.readme(), before)


class InstallHeaderTests(HeaderCase):
    def install(self, *flags):
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PROJECT_DIR", "CLAUDECODE", "AGENTIC_WP")}
        return subprocess.run([sys.executable, str(SCRIPT), "install", str(self.dir), *flags], cwd=self.tmp, env=env,
                              capture_output=True, text=True, encoding="utf-8", errors="replace")

    def commit(self):
        subprocess.run(["git", "add", "-A"], cwd=self.dir, check=True)
        subprocess.run(["git", *GIT_ID, "commit", "-qm", "c"], cwd=self.dir, check=True)

    def test_ac_005_install_writes_reports_and_guards(self):
        self.write("README.md", "# Target\n\nText.\n")
        self.commit()
        r = self.install("--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("README header: would be added", r.stdout)
        self.assertEqual(self.readme(), "# Target\n\nText.\n")
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("README header: added", r.stdout)
        version = json.loads((self.dir / ".claude/agentic-install.json").read_text(encoding="utf-8"))["version"]
        self.assertIn("agentic--flow%20" + version, block(self.readme()))
        self.commit()
        self.write("README.md", self.readme() + "\nlocal edit\n")
        r = self.install()
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("README.md", r.stderr)
        self.assertEqual(self.readme().count("local edit"), 1)


class TemplateTests(unittest.TestCase):
    def test_ac_007_the_stub_gets_the_header(self):
        workflow = read(".github/workflows/reset-readme.yml")
        stub = workflow.index("printf")
        header = workflow.index("python3 .claude/bin/agentic.py readme-header")
        add = workflow.index("git add README.md")
        self.assertLess(stub, header)
        self.assertLess(header, add)
        self.assertLess(workflow.index("agentic-flow-template"), stub, "it still runs only while the marker is there")


class DocsTests(unittest.TestCase):
    def test_ac_008_docs_and_note(self):
        hub = read("docs/how-to/README.md")
        self.assertLessEqual(len(hub.splitlines()), 260)
        ref = hub.split("## Script reference")[1].split("## Troubleshooting")[0]
        self.assertIn("agentic.py readme-header", ref)
        config = hub.split("## Configuration")[1].split("## Script reference")[0]
        for word in ('"readme"', '"header"', '"sponsors"'):
            self.assertIn(word, config)
        plugin = read("docs/how-to/plugin.md")
        self.assertIn("README", plugin)
        self.assertIn("readme.header", plugin)
        self.assertIn("readme-header", read("docs/how-it-works.md"))
        notes = " ".join(upgrade.NOTES["2.4.0"])
        self.assertIn("README", notes)
        self.assertIn("readme.header", notes)


class FlowReadmeTests(unittest.TestCase):
    def test_ac_009_the_flows_readme_is_current(self):
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "AGENTIC_WP")}
        env["CLAUDE_PROJECT_DIR"] = str(ROOT)
        r = subprocess.run([sys.executable, str(SCRIPT), "readme-header", "--check"], cwd=ROOT, env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        text = read("README.md")
        lines = text.splitlines()
        self.assertEqual(lines[0], MARKER)
        self.assertEqual(lines[1], START)
        self.assertIn("\n# agentic-flow\n", block(text))
        self.assertIsNone(VERSION_RE.search(text))
        self.assertLessEqual(len(lines), 150)


if __name__ == "__main__":
    unittest.main()
