"""Acceptance tests AC-001..AC-003: the A/B comparison is listed in the guides hub."""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_docs import FENCE, HOW_TO, HUB, VERSION_RE, read, sections, slugs, strip_fenced  # noqa: E402

AB_LINE_RE = re.compile(r"^python3 bench/bench\.py ab --a .*#", re.M)
AB_ANCHOR = "compare-two-versions-ab"
HUB_LINE_CAP = 260


def fenced_blocks(text):
    """Bodies of the fenced blocks of a section, one string per block."""
    blocks, current = [], None
    for line in text.splitlines():
        if line.lstrip().startswith(FENCE):
            if current is None:
                current = []
            else:
                blocks.append("\n".join(current))
                current = None
        elif current is not None:
            current.append(line)
    return blocks


class ScriptReferenceTests(unittest.TestCase):
    def setUp(self):
        self.secs = sections(read(HUB))

    def test_ac_001_script_reference_fence_lists_ab_command_with_comment(self):
        blocks = fenced_blocks(self.secs["Script reference"])
        self.assertTrue(any(AB_LINE_RE.search(b) for b in blocks))

    def test_ac_001_ab_command_appears_once(self):
        blocks = fenced_blocks(self.secs["Script reference"])
        found = [ln for b in blocks for ln in b.splitlines() if AB_LINE_RE.match(ln)]
        self.assertEqual(len(found), 1)

    def test_ac_001_ab_command_is_not_outside_the_script_reference_fence(self):
        for title, body in self.secs.items():
            if title == "Script reference":
                continue
            with self.subTest(section=title):
                self.assertIsNone(AB_LINE_RE.search(body))

    def test_ac_001_script_reference_stays_before_troubleshooting(self):
        titles = list(self.secs)
        self.assertLess(titles.index("Script reference"), titles.index("Troubleshooting"))

    def test_ac_001_ab_comment_column_matches_neighbours(self):
        block = next(b for b in fenced_blocks(self.secs["Script reference"]) if AB_LINE_RE.search(b))
        line = next(ln for ln in block.splitlines() if AB_LINE_RE.match(ln))
        neighbour = next(ln for ln in block.splitlines() if ln.startswith("python3 .claude/bin/agentic.py") and "#" in ln)
        self.assertEqual(line.index("#"), neighbour.index("#"))


class TestingSectionTests(unittest.TestCase):
    def setUp(self):
        self.text = read(HUB)
        self.body = strip_fenced(sections(self.text)["Testing the flow itself"])

    def test_ac_002_testing_section_links_to_ab_guide(self):
        self.assertIn(f"bench.md#{AB_ANCHOR}", self.body)

    def test_ac_002_anchor_exists_in_bench_guide(self):
        self.assertIn(AB_ANCHOR, slugs(read(HOW_TO / "bench.md")))

    def test_ac_002_every_bench_anchor_linked_in_hub_exists(self):
        bench_slugs = slugs(read(HOW_TO / "bench.md"))
        for anchor in re.findall(r"\(bench\.md#([^)]+)\)", self.text):
            with self.subTest(anchor=anchor):
                self.assertIn(anchor, bench_slugs)

    def test_ac_002_testing_section_hard_codes_no_version(self):
        self.assertIsNone(VERSION_RE.search(self.body))


class HubKeepsShapeTests(unittest.TestCase):
    def setUp(self):
        self.text = read(HUB)
        self.script = sections(self.text)["Script reference"]

    def test_ac_003_hub_is_at_most_260_lines(self):
        self.assertLessEqual(len(self.text.splitlines()), HUB_LINE_CAP)

    def test_ac_003_stop_line_keeps_both_meanings(self):
        for fragment in ("every running agent", "only the one named"):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.script)

    def test_ac_003_stop_commands_are_merged_into_one_line(self):
        stops = [ln for ln in self.script.splitlines() if ln.startswith("python3 .claude/bin/agentic.py stop")]
        self.assertEqual(len(stops), 1)


if __name__ == "__main__":
    unittest.main()
