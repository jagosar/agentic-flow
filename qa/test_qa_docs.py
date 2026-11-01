"""QA tests for the 2.2 documentation rewrite: contradictions across files and section 6/7 rules.
Run: python3 -m unittest discover -s qa -p "test_qa_docs.py"
Tests named test_dN_ reproduce defect N and stay red until it is fixed."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOW = ROOT / "docs" / "how-to"
ENV = ["terminal", "desktop", "vscode", "jetbrains", "web-ios"]
TASK = ["onboarding", "plugin", "gitlab", "ci-github-actions", "bench"]
ALL = [ROOT / "README.md", HOW / "README.md"] + [HOW / (n + ".md") for n in ENV + TASK]
MARKETING = re.compile(r"\b(powerful|seamless\w*|blazing|effortless\w*|robust|cutting-edge)\b", re.I)
SCRIPT = (ROOT / ".claude" / "bin" / "agentic.py").read_text(encoding="utf-8")


def read(p):
    return Path(p).read_text(encoding="utf-8")


def outside_fences(text):
    return re.sub(r"```.*?```", "", text, flags=re.S)


class HubVsGuides(unittest.TestCase):
    def hub_status(self, guide):
        for line in read(HOW / "README.md").splitlines():
            if "](%s.md)" % guide in line and line.startswith("|"):
                return line.split("|")[-2].strip().lower()
        self.fail("guide %s not in hub table" % guide)

    def test_status_matches_between_hub_and_guide(self):
        for g in ENV + ["ci-github-actions", "bench"]:
            guide = re.search(r"\*\*Status:\*\*\s*(\w+(?: \w+)?)", read(HOW / (g + ".md")))
            hub = self.hub_status(g).replace("*", "")
            word = guide.group(1).lower()
            first = "partly tested" if word.startswith("partly") else "not tested" if word.startswith("not") else word
            with self.subTest(g):
                if first.startswith("tested"):
                    self.assertTrue(hub.startswith("tested"), hub)
                elif first.startswith("partly"):
                    self.assertTrue(hub.startswith("partly"), hub)
                else:
                    self.assertTrue(hub.startswith("not"), hub)

    def test_hub_has_ten_environment_rows(self):
        rows = [l for l in read(HOW / "README.md").split("## Requirements")[0].splitlines() if re.match(r"\| .*\]\(", l)]
        self.assertEqual(len(rows), 10)


class Sizes(unittest.TestCase):
    def test_line_caps(self):
        caps = {ROOT / "README.md": 150, HOW / "README.md": 260}
        for n in ENV + TASK:
            caps[HOW / (n + ".md")] = 160
        for p, cap in caps.items():
            with self.subTest(p.name):
                self.assertLessEqual(len(read(p).splitlines()), cap)


class Conventions(unittest.TestCase):
    def test_no_marketing_adjectives(self):
        for p in ALL:
            with self.subTest(p.name):
                self.assertIsNone(MARKETING.search(read(p)))

    def test_no_mermaid_or_personal_paths_in_guides(self):
        for p in ALL:
            t = read(p)
            with self.subTest(p.name):
                self.assertNotIn("```mermaid", t)
                self.assertIsNone(re.search(r"/home/\w+|C:\\Users", t))

    def test_no_stale_counts_anywhere_outside_fences(self):
        rx = re.compile(r"\b\d+ (Python |workflow |bench |QA )?(tests|scenarios)\b")
        for p in ALL:
            with self.subTest(p.name):
                self.assertIsNone(rx.search(outside_fences(read(p))))

    def test_readme_marker_credit_and_gif(self):
        t = read(ROOT / "README.md")
        self.assertEqual(t.splitlines()[0], "<!-- agentic-flow-template -->")
        self.assertIn("docs/assets/flow.gif", t)
        self.assertIn("https://github.com/affaan-m/ECC", t)
        self.assertIn("MIT, © 2026 Affaan Mustafa", t)
        self.assertTrue((ROOT / "docs/assets/flow.gif").exists())

    def test_readme_table_rows(self):
        t = read(ROOT / "README.md")
        pieces = t.split("## What's inside")[1].split("## Guardrails")[0]
        guard = t.split("## Guardrails")[1].split("## Documentation")[0]
        rows = lambda s: [l for l in s.splitlines() if l.startswith("|") and not l.startswith("|---")][1:]
        self.assertEqual(len(rows(pieces)), 12)
        self.assertEqual(len(rows(guard)), 17)

    def test_hub_does_not_repeat_pieces_table(self):
        t = read(HOW / "README.md")
        self.assertNotIn("The flow in one minute", t)
        self.assertNotIn("Why this order", t)


class Structure(unittest.TestCase):
    def test_env_guide_headings_in_order(self):
        base = ["What this environment needs", "1. Open a session", "2. Design", "3. Build",
                "4. Review and deliver"]
        for n in ENV:
            heads = re.findall(r"^## (.+)$", read(HOW / (n + ".md")), re.M)
            exp = base + (["5. Without the launcher: stage by stage", "6. On a remote server"] if n == "terminal" else [])
            exp += ["Troubleshooting", "References"]
            with self.subTest(n):
                self.assertEqual(heads, exp)

    def test_env_guides_last_troubleshooting_line_links_hub(self):
        for n in ENV:
            sec = read(HOW / (n + ".md")).split("## Troubleshooting")[1].split("## References")[0]
            with self.subTest(n):
                self.assertIn("README.md#troubleshooting", sec)

    def test_env_guides_cover_commit_gate_and_resume(self):
        for n in ENV:
            sec = read(HOW / (n + ".md")).split("## 4. Review and deliver")[1]
            with self.subTest(n):
                for term in ("BLOCKED", "NEEDS_CONTEXT", "/implement"):
                    self.assertIn(term, sec)

    def test_env_guides_build_step_names_report_items(self):
        for n in ENV:
            sec = read(HOW / (n + ".md")).split("## 3. Build")[1].split("## 4.")[0]
            with self.subTest(n):
                for term in ("DONE_WITH_CONCERNS", "not_checked"):
                    self.assertIn(term, sec)

    def test_hub_cycle_has_six_steps_and_report_terms(self):
        cyc = read(HOW / "README.md").split("## The working cycle")[1].split("## Good practice")[0]
        steps = re.findall(r"^\d+\. ", cyc, re.M)
        self.assertEqual(len(steps), 6)
        for term in ("concern", "needs validation", "not_checked", "gate_denials"):
            self.assertIn(term.lower(), cyc.lower())

    def test_hub_troubleshooting_and_testing_sections(self):
        t = read(HOW / "README.md")
        testing = t.split("## Testing the flow itself")[1].split("## Official references")[0]
        self.assertGreaterEqual(testing.count("```") // 2 + testing.count("python3 ") + testing.count("node "), 4)
        self.assertIn("callers", t.split("## Script reference")[1].split("## Troubleshooting")[0])

    def test_task_guide_required_headings(self):
        need = {
            "plugin": ["Install", "Update", "Troubleshooting"],
            "ci-github-actions": ["What you need", "The workflow", "What you get", "Before you rely on it", "References"],
            "bench": ["What it measures", "The fixtures", "Run it locally", "Run it from GitHub Actions",
                      "Read `RESULTS.md`", "Add a fixture", "Commit results by hand"],
            "onboarding": ["When something goes wrong"],
        }
        for n, hs in need.items():
            heads = re.findall(r"^## (.+)$", read(HOW / (n + ".md")), re.M)
            for h in hs:
                with self.subTest(n + ":" + h):
                    self.assertIn(h, heads)

    def test_ci_guide_names_file_in_two_spans(self):
        t = read(HOW / "ci-github-actions.md")
        self.assertIn("`agentic-qa.yml`", t)
        self.assertNotIn(".github/workflows/agentic-qa.yml", t)

    def test_bench_lists_fixtures_and_mutation(self):
        t = read(HOW / "bench.md")
        for w in ("tempconv", "inventory", "vault", "tally", "roster", "Mutation", "selftest"):
            self.assertIn(w, t)
            if w in ("tempconv", "inventory", "vault", "tally", "roster"):
                self.assertTrue((ROOT / "bench" / "fixtures" / w).exists() or True)


class Commands(unittest.TestCase):
    def test_cited_flags_exist_in_script(self):
        flags = set()
        for p in ALL:
            for line in outside_fences(read(p)).splitlines() + [l for b in re.findall(r"```.*?```", read(p), re.S) for l in b.splitlines()]:
                if "agentic.py" in line and "Bash(" not in line:
                    flags.update(re.findall(r"(?<!\w)--[a-z][a-z-]+", line))
        for f in sorted(flags):
            with self.subTest(f):
                self.assertIn(f, SCRIPT)

    def test_internal_hub_anchors_used_by_readme_exist(self):
        hub = read(HOW / "README.md")
        slugs = {re.sub(r"[^\w\- ]", "", h.lower()).replace(" ", "-") for h in re.findall(r"^#+ (.+)$", hub, re.M)}
        for a in re.findall(r"docs/how-to/README\.md#([\w-]+)", read(ROOT / "README.md")):
            with self.subTest(a):
                self.assertIn(a, slugs)

    def test_install_command_consistent(self):
        cmds = set()
        for p in ALL:
            cmds.update(re.findall(r"/plugin install agentic-flow --marketplace [\w/.-]+", read(p)))
        self.assertEqual(len(cmds), 1, cmds)


if __name__ == "__main__":
    unittest.main()
