"""Acceptance tests AC-001..AC-005: the rewritten README and guides, read as Markdown."""
import re
import sys
import unittest
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / ".claude" / "bin"
sys.path.insert(0, str(BIN))

import agentic  # noqa: E402
from test_definitions import agentic_subcommands  # noqa: E402

HOW_TO = ROOT / "docs" / "how-to"
README = ROOT / "README.md"
HUB = HOW_TO / "README.md"
ENV_GUIDES = ["terminal.md", "desktop.md", "vscode.md", "jetbrains.md", "web-ios.md"]
TASK_GUIDES = ["onboarding.md", "plugin.md", "gitlab.md", "ci-github-actions.md", "bench.md"]
ALL_GUIDES = ENV_GUIDES + TASK_GUIDES
ELEVEN = [README, HUB] + [HOW_TO / n for n in ALL_GUIDES]

COUNT_RE = re.compile(r"\b\d+ (Python |workflow |bench |QA )?(tests|scenarios)\b")
VERSION_RE = re.compile(r"(?<!Claude Code )(?<!claude-code@)\b[12]\.\d+\.\d+\b")
FENCE = "```"


def read(path):
    return path.read_text(encoding="utf-8")


def strip_fenced(text):
    out, fenced = [], False
    for line in text.splitlines():
        if line.lstrip().startswith(FENCE):
            fenced = not fenced
            continue
        if not fenced:
            out.append(line)
    return "\n".join(out)


def headings(text, level):
    """Headings of one level, outside fenced blocks."""
    prefix = "#" * level + " "
    return [ln[len(prefix):].strip() for ln in strip_fenced(text).splitlines() if ln.startswith(prefix)]


def sections(text):
    """Map of H2 title to the body below it (H3 included), outside fenced-block confusion."""
    result, current, fenced = {}, None, False
    for line in text.splitlines():
        if line.lstrip().startswith(FENCE):
            fenced = not fenced
        if not fenced and line.startswith("## "):
            current = line[3:].strip()
            result[current] = []
            continue
        if current is not None:
            result[current].append(line)
    return {k: "\n".join(v) for k, v in result.items()}


def slugs(text):
    found, seen = set(), {}
    for h in re.findall(r"^#+ (.+)$", text, re.M):
        slug = re.sub(r"[^\w\s-]", "", h.strip().lower(), flags=re.U).replace(" ", "-")
        found.add(f"{slug}-{seen[slug]}" if slug in seen else slug)
        seen[slug] = seen.get(slug, 0) + 1
    return found


def missing_paths(text):
    top_dirs = {p.name for p in ROOT.iterdir() if p.is_dir()}
    missing = []
    for cited in agentic.PATH_RE.findall(strip_fenced(text)):
        first = cited.split("/", 1)[0]
        if first in top_dirs and first not in agentic.SKIP_DIRS and not (ROOT / cited).exists():
            missing.append(cited)
    return missing


def line_count(text):
    return len(text.splitlines())


class DocCase(unittest.TestCase):
    def assertContainsAll(self, text, terms, where):
        lowered = text.lower()
        for term in terms:
            with self.subTest(file=where, term=term):
                self.assertIn(term.lower(), lowered)

    def assertNoCountsOrVersions(self, text, where):
        self.assertIsNone(COUNT_RE.search(text), f"{where}: hard-coded test count")
        self.assertIsNone(VERSION_RE.search(text), f"{where}: hard-coded flow version")


class ReadmeTests(DocCase):
    H2 = ["What you get", "What it costs you", "Proof", "Quick start", "What's inside",
          "Guardrails", "Documentation", "Credits"]

    def test_ac_001_readme_order_and_terms(self):
        text = read(README)
        lines = text.splitlines()
        self.assertEqual(lines[0], "<!-- agentic-flow-template -->")
        self.assertEqual(lines[1], "# agentic-flow")
        self.assertEqual(headings(text, 2), self.H2)
        before_quick = text.split("## Quick start", 1)[0]
        self.assertNotIn(FENCE, before_quick, "fenced block before Quick start")
        self.assertLessEqual(len(lines), 150)
        self.assertContainsAll(text, ["stop gate", "DONE_WITH_CONCERNS", "NEEDS_CONTEXT", "needs validation",
                                      "not_checked", "callers", "mutation"], "README.md")
        for target in ["bench/RESULTS.md", "docs/how-it-works.md", "docs/how-to/README.md",
                       "docs/how-to/bench.md"]:
            with self.subTest(link=target):
                self.assertRegex(text, r"\]\(" + re.escape(target) + r"[^)]*\)")
        credits = sections(text)["Credits"]
        self.assertIn("ECC", credits)
        self.assertIn("MIT", credits)
        self.assertIn("flow.gif", text)
        self.assertNoCountsOrVersions(text, "README.md")


class HubTests(DocCase):
    H2 = ["Pick your environment", "Requirements", "Install the flow in a project", "The working cycle",
          "Good practice", "Language rules", "Follow and stop the work", "Configuration", "Script reference",
          "Troubleshooting", "Testing the flow itself", "Official references"]

    def table_rows(self, body):
        rows = [ln for ln in body.splitlines() if ln.startswith("|")]
        return [r for r in rows[2:]]

    def test_ac_002_hub_order_tables_and_terms(self):
        text = read(HUB)
        self.assertEqual(headings(text, 2), self.H2)
        secs = sections(text)
        self.assertIn("Windows", headings(secs["Requirements"], 3))
        self.assertIn("Two ways to run", headings(secs["The working cycle"], 3))
        rows = self.table_rows(secs["Pick your environment"])
        linked = set()
        for row in rows:
            for target in re.findall(r"\]\(([^)\s#]+)(?:#[^)\s]*)?\)", row):
                linked.add(target)
        self.assertEqual(linked, set(ALL_GUIDES))
        script = secs["Script reference"]
        for cmd in ["callers", "run-pipeline", "validate", "status", "stop", "install"]:
            with self.subTest(command=cmd):
                self.assertIn("agentic.py " + cmd, script)
        self.assertContainsAll(secs["The working cycle"], ["DONE_WITH_CONCERNS", "NEEDS_CONTEXT",
                                                           "needs validation", "not_checked", "gate_denials"],
                               "hub working cycle")
        trouble = secs["Troubleshooting"]
        for fragment in ["the report says DONE but the acceptance tests", "about its acceptance tests", "twice"]:
            with self.subTest(row=fragment):
                self.assertTrue(any(ln.startswith("|") and fragment in ln for ln in trouble.splitlines()))
        self.assertLessEqual(line_count(text), 260)
        self.assertFalse(any(ln.startswith("| Architect |") for ln in text.splitlines()),
                         "the pieces table must not be repeated")
        self.assertNoCountsOrVersions(text, "docs/how-to/README.md")


class EnvironmentGuideTests(DocCase):
    BASE = ["What this environment needs", "1. Open a session", "2. Design", "3. Build",
            "4. Review and deliver"]
    TAIL = ["Troubleshooting", "References"]
    UNTESTED = ["vscode.md", "jetbrains.md", "web-ios.md"]

    def expected_h2(self, name):
        extra = ["5. Without the launcher: stage by stage", "6. On a remote server"] if name == "terminal.md" else []
        return self.BASE + extra + self.TAIL

    def test_ac_003_same_skeleton(self):
        for name in ENV_GUIDES:
            with self.subTest(file=name):
                text = read(HOW_TO / name)
                lines = text.splitlines()
                self.assertTrue(lines[0].startswith("# Guide: "))
                head = lines[:6]
                self.assertTrue(any(ln.startswith("**Goal:**") for ln in head))
                status = [ln for ln in head if ln.startswith("**Status:**")]
                self.assertTrue(status)
                before = [ln for ln in lines if "Before you start" in ln]
                self.assertTrue(before, "missing Before you start line")
                self.assertRegex(before[0], r"\]\(README\.md#requirements\)")
                self.assertRegex(before[0], r"\]\(README\.md#install-the-flow-in-a-project\)")
                self.assertEqual(headings(text, 2), self.expected_h2(name))
                secs = sections(text)
                self.assertIn("/implement", secs["3. Build"])
                self.assertTrue("DONE_WITH_CONCERNS" in secs["3. Build"] or "gate" in secs["3. Build"])
                self.assertIn("/implement <wave>", secs["4. Review and deliver"])
                self.assertLessEqual(len(lines), 160)
                last = [ln for ln in secs["Troubleshooting"].splitlines() if ln.strip()][-1]
                self.assertRegex(last, r"\]\(README\.md#troubleshooting\)")
                self.assertNotIn("```mermaid", text.lower())
                self.assertNoCountsOrVersions(text, name)
                if name in self.UNTESTED:
                    low = status[0].lower()
                    self.assertIn("not tested", low)
                    for m in re.finditer(r"tested", low):
                        self.assertRegex(low[:m.start()], r"\bnot\b")


class TaskGuideTests(DocCase):
    BENCH_H2 = ["What it measures", "The fixtures", "Run it locally", "Run it from GitHub Actions",
                "Read `RESULTS.md`", "Add a fixture", "Commit results by hand"]
    CI_H2 = ["What you need", "The workflow", "What you get", "Before you rely on it", "References"]
    FIXTURES = ["tempconv", "inventory", "vault", "tally", "roster"]

    def test_ac_004_current_and_paths_exist(self):
        texts = {n: read(HOW_TO / n) for n in TASK_GUIDES}
        for name, text in texts.items():
            with self.subTest(file=name):
                self.assertEqual(missing_paths(text), [])
                self.assertLessEqual(line_count(text), 160)
                prose = strip_fenced(text) if name in ("onboarding.md", "plugin.md") else text
                self.assertNoCountsOrVersions(prose, name)

        bench = texts["bench.md"]
        for term in ["Mutation", "mutation score", "roster", "selftest"]:
            with self.subTest(bench=term):
                self.assertIn(term, bench)
        for fixture in self.FIXTURES:
            with self.subTest(fixture=fixture):
                self.assertTrue(any(ln.startswith("|") and fixture in ln for ln in bench.splitlines()))
        self.assertEqual([h for h in headings(bench, 2) if h in self.BENCH_H2], self.BENCH_H2)

        ci = texts["ci-github-actions.md"]
        self.assertIn("agentic-qa.yml", ci)
        self.assertNotIn(".github/workflows/agentic-qa.yml", ci)
        self.assertIn("`agentic-qa.yml`", ci)
        self.assertIn("`.github/workflows/`", ci)
        self.assertEqual([h for h in headings(ci, 2) if h in self.CI_H2], self.CI_H2)

        plugin = texts["plugin.md"]
        self.assertIn(".claude/state/upgrade/", plugin)
        self.assertIn("/agentic-flow:init", plugin)
        for h in ["Install", "Update", "Troubleshooting"]:
            with self.subTest(plugin=h):
                self.assertIn(h, headings(plugin, 2))

        h2 = headings(texts["onboarding.md"], 2)
        self.assertTrue(any(h.startswith("A.") for h in h2))
        self.assertTrue(any(h.startswith("B.") for h in h2))
        self.assertIn("When something goes wrong", h2)

        gitlab = headings(texts["gitlab.md"], 2)
        self.assertTrue(any(h.startswith("A.") for h in gitlab))
        self.assertTrue(any(h.startswith("B.") for h in gitlab))
        self.assertIn("Where Claude Code runs", gitlab)


class LinkTests(DocCase):
    CMD_RE = re.compile(r"(?:python3 \.claude/bin/|`)agentic\.py ([a-z][\w-]*)(\*?)")

    def test_ac_005_links_anchors_and_commands(self):
        valid = agentic_subcommands()
        for path in ELEVEN:
            rel = path.relative_to(ROOT).as_posix()
            text = read(path)
            with self.subTest(file=rel):
                broken = []
                for link in re.findall(r"\]\(([^)\s]+)\)", text):
                    if link.startswith(("http://", "https://", "mailto:")):
                        continue
                    target_rel, _, frag = link.partition("#")
                    target_rel = urllib.parse.unquote(target_rel)
                    if not target_rel:
                        target = path
                    elif target_rel.startswith("/"):
                        target = ROOT / target_rel.lstrip("/")
                    else:
                        target = path.parent / target_rel
                    if not target.exists():
                        broken.append(("link", link))
                    elif frag and target.suffix == ".md" and frag not in slugs(read(target)):
                        broken.append(("anchor", link))
                for cmd, star in self.CMD_RE.findall(text):
                    if not star and cmd not in valid:
                        broken.append(("command", cmd))
                broken += [("path", p) for p in missing_paths(text)]
                self.assertEqual(broken, [])

        hub_links = set(re.findall(r"\]\(([^)\s#]+)", sections(read(HUB))["Pick your environment"]))
        self.assertEqual(hub_links & set(ALL_GUIDES), set(ALL_GUIDES))
        self.assertRegex(sections(read(README))["Documentation"], r"\]\(docs/how-to/README\.md[^)]*\)")


if __name__ == "__main__":
    unittest.main()
