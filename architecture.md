# Architecture: list the A/B comparison in the guides hub (issue 73)
Type: change · Size: small

## 1. Goal
`docs/how-to/bench.md` documents `bench.py ab` ("Compare two versions (A/B)"), but the hub `docs/how-to/README.md` does not mention it. A reader of the script reference or of "Testing the flow itself" cannot find that two versions of the flow can be compared. Two small edits in one file fix that without breaking the hub's 260-line cap, which the hub already sits at.

## 2. Scope
### Included
- One line in the hub's script reference for `bench.py ab`.
- One sentence in "Testing the flow itself" that links to the bench guide's A/B section.
- Merging the two `agentic.py stop` lines into one, to keep the hub at 260 lines.
### Excluded (non-goals)
- Any other file. No code, no `bench/`, no `README.md`, no `bench.md`.
- Rewording anything else in the hub.

## 3. Stack
Markdown. Python 3 `unittest` for the checks. Tests: `python3 -m unittest discover -s acceptance` and `python3 -m unittest discover -s qa -p "test_qa_docs.py"`.

## 4. Repository structure
```
docs/how-to/README.md          WP-01 (edited)
acceptance/test_docs_ab.py     AT (new)
```

## 4b. Existing code context
| What an implementer needs to know | Where it is | Pattern or rule |
|---|---|---|
| The hub is exactly 260 lines and the cap is 260 | `docs/how-to/README.md` (whole file); `acceptance/test_docs.py:158`; `qa/test_qa_docs.py:55` | A net line count above 260 fails two suites |
| The script reference is one fenced `bash` block of `agentic.py` commands, each with a `#` comment aligned at one column | `docs/how-to/README.md:169-206` | New line copies the alignment of its neighbours |
| The two `stop` lines to merge | `docs/how-to/README.md:185-186` | No test pins their text (grep found none) |
| "Testing the flow itself" is a fenced block, then one long paragraph on one line, then one line about the animation | `docs/how-to/README.md:239-249` | Append the sentence to the end of line 248, not a new line |
| The A/B section and its slug | `docs/how-to/bench.md:68` (`## Compare two versions (A/B)`) | Slug is `compare-two-versions-ab`; the acceptance tests check anchors |
| No hard-coded flow versions or test counts in the hub | `acceptance/test_docs.py:95-97` | Use `<ref>` placeholders, not `2.1.0` |
| Flags cited next to `agentic.py` must exist in the script | `qa/test_qa_docs.py:176-184` | The new line does not contain `agentic.py` |
| Paths cited in the docs must exist | `acceptance/test_docs.py:73` | `bench/bench.py` exists |

## 5. Data model
None.

## 6. Contracts between modules
None. One work package, one file.

## 7. Conventions
- English, plain voice, no marketing adjectives (`qa/test_qa_docs.py:15`).
- The new script-reference line, with its `#` in the same column as the other lines of the block (padded with spaces):
```
python3 bench/bench.py ab --a <ref> --b <ref>          # compares two versions of the flow (see the bench guide)
```
- The merged stop line, padded the same way:
```
python3 .claude/bin/agentic.py stop [WP-02]            # stops every running agent, or only the one named
```
- Acceptance tests match by regex and substring, never by exact whitespace: `^python3 bench/bench\.py ab --a .*#` and the substrings `every running agent` and `only the one named`.
- The new sentence ends line 248: `To compare two versions of the flow on the same fixtures, use the [A/B comparison](bench.md#compare-two-versions-ab).`
- No commit, no push: the flow's agents cannot.

## 8. Work packages and acceptance criteria
### Acceptance criteria
- AC-001 · The script reference lists the A/B command
  - Scenario: the hub as it is today.
  - Action: read the fenced block under `## Script reference`.
  - Expected: one line starts with `python3 bench/bench.py ab --a` and has a `#` comment.
  - Must not: put it in a different section, or outside the fence; it stays before `## Troubleshooting`, where `qa/test_qa_docs.py:146` cuts the section.
  - Check: `acceptance/test_docs_ab.py::ScriptReferenceTests`
  - WP: WP-01
- AC-002 · The testing section points to the A/B guide
  - Scenario: the hub as it is today.
  - Action: read the text under `## Testing the flow itself` outside fences.
  - Expected: it links to `bench.md#compare-two-versions-ab`, and that anchor exists as a heading in `docs/how-to/bench.md`.
  - Must not: link to an anchor that does not exist, or hard-code a flow version.
  - Check: `acceptance/test_docs_ab.py::TestingSectionTests`
  - WP: WP-01
- AC-003 · The hub keeps its size and its other commands
  - Scenario: the hub after the edit.
  - Action: count lines and read the script reference.
  - Expected: at most 260 lines; the `## Script reference` section still contains the substrings `every running agent` and `only the one named`.
  - Must not: drop a command from the script reference other than by merging the two `stop` lines.
  - Check: `acceptance/test_docs_ab.py::HubKeepsShapeTests`
  - WP: WP-01

### Work packages
#### WP-01 · Edit the hub
- Wave: 1.
- Files it owns: `docs/how-to/README.md`.
- Contracts: none.
- ACs: AC-001, AC-002, AC-003.
- **Patterns to mirror:** `docs/how-to/README.md:169-206` (comment alignment), `docs/how-to/README.md:248` (paragraph style).
- **Gotchas:** the file is at the 260-line cap, so the net change in lines must be zero or negative: one line added, two `stop` lines merged into one. The version rule forbids strings like `2.1.0`.
- **Exact imports and APIs:** none.
- **WP validation:** `python3 -m unittest discover -s acceptance`, `python3 -m unittest discover -s qa -p "test_qa_docs.py"`.

```json wp-manifest
{
  "stack": ["python"],
  "allow_bash": ["Bash(python3 -m unittest:*)"],
  "acceptance": {"files": ["acceptance/test_docs_ab.py"], "command": "python3 -m unittest discover -s acceptance -p test_docs_ab.py"},
  "verify": {"tests": "python3 -m unittest discover -s acceptance"},
  "docs": {"files": ["docs/roadmap/"], "codemap": null},
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": ["docs/how-to/README.md"],
     "acs": ["AC-001", "AC-002", "AC-003"], "mirror": ["docs/how-to/README.md:169-206", "docs/how-to/README.md:248"]}
  ]
}
```

## 9. Test strategy
- Unit: none (Markdown).
- Acceptance: `acceptance/test_docs_ab.py`, written first by the test-author, red today. It reads the hub and `bench.md` with a regex and splits sections by `##` headings; it imports the helpers (`sections`, `strip_fenced`, `slugs`, `read`) from `acceptance/test_docs.py:28-70` instead of copying them, so `slugs()` stays the same as the script's anchors.
- QA: the existing `qa/test_qa_docs.py` and `acceptance/test_docs.py` must stay green (cap, flags, anchors, no versions).

## 10. Decisions
- **D1 · Zero net lines:** the hub is at its cap. Raising the cap would mean editing two tests and hide a drift signal; merging two `stop` lines costs nothing. Discarded: raise the cap to 262.
- **D2 · The A/B command goes in the script reference even though it is not `agentic.py`:** the block is where readers look for commands; the line carries a pointer to the bench guide. Discarded: only the Testing paragraph.
- **D3 · The sentence is appended to the existing paragraph line:** a new line would break D1.
- **D4 · Docs zone is `docs/roadmap/` only:** the default zone would overlap the WP's file and `validate` rejects that. The issue's own text says to touch only the hub.

## 11. Risks and open questions
- `docs-check` only reads the manifest's `docs.files` (`agentic.py:1184-1188`), which here is `docs/roadmap/`, so it does not cover the hub. The anchor and the paths are covered by AC-002's test and by `acceptance/test_docs.py`.
- Nothing blocks the WP.
