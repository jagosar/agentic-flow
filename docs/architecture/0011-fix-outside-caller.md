# Architecture: a broken caller outside every package is fixed from the changed package (issue 83, agentic-flow 2.4.1)
Type: fix · Size: small

## 1. Goal
In the `pricing` A/B (`bench/results/ab-2.1.0-vs-2.4.0-20261102-210456.md`), 2.4.0's reviewer confirmed in 3 of 3 sessions that `shop/receipt.py`, a caller no package owns, broke when `parse_price` gained a required parameter. Every fix cycle then ended `BLOCKED`: the implementer asked for ownership of the caller instead of keeping it working from its own files with a default for the new parameter. The prompts told it to return `BLOCKED` when a guardrail stops it, and nothing told it that a caller outside every package is kept working from the changed package's side. This change says so in the fix-cycle prompt (both engines and the one-off `run-wave --fix`) and in `implementer.md`. It is a prompt change: its effect on real agents is not measured here.

## 2. Scope
### Included
- The `fix` prompt in `.claude/workflows/pipeline-spec.json` and its hand-kept copy in `.claude/workflows/agentic-implement.js`.
- `implementer.md`: the `BLOCKED` status and the guardrails paragraph.
- Version 2.4.1, its upgrade note, the version pins, the roadmap entry.
### Excluded (non-goals)
- The reviewer's `fix` field, a deterministic "outside every package" marker on defects, a plan-reviewer check (not chosen).
- An A/B to measure the effect (not now, by the user's choice).
- Any change to the hook, which keeps blocking writes outside the package's files.

## 3. Stack
Python 3.9+ standard library and Node 20 for the workflow tests.
- Tests: `python3 -m unittest discover -s .claude/bin -p "test_*.py"`, `node .claude/bin/test_workflow.mjs`; docs: `python3 -m unittest discover -s acceptance`, `python3 -m unittest discover -s qa`.

## 4. Repository structure
```
.claude/workflows/pipeline-spec.json        WP-01 (the fix prompt)
.claude/workflows/agentic-implement.js      WP-01 (its copy)
.claude/agents/implementer.md               WP-01
.claude-plugin/plugin.json                  WP-02 (2.4.1)
.claude/bin/upgrade.py                      WP-02 (NOTES["2.4.1"])
.claude/bin/test_acceptance_upgrade.py    WP-02 (version pin)
.claude/bin/test_acceptance_v2.py         WP-02 (version pin)
.claude/bin/test_acceptance_v21.py        WP-02 (version pin)
.claude/bin/test_acceptance_v22.py        WP-02 (version pin)
.claude/bin/test_acceptance_v23.py        WP-02 (version pin)
.claude/bin/test_acceptance_v24.py        WP-02 (version pin)
docs/roadmap/repo-review-2026-11.md         WP-02
.claude/bin/test_acceptance_v241.py         AT (new)
```

## 4b. Existing code context
| What an implementer needs to know | Where it is | Pattern or rule |
|---|---|---|
| The fix prompt, as the fallback engine and the one-off command render it | `.claude/workflows/pipeline-spec.json:13` (`prompts.fix`: "... Stay within the contract, do not touch other packages' files or the acceptance tests, and keep the acceptance tests of your criteria green.{retry}{rules}") | The new sentence goes after "green." and before `{retry}` |
| Its copy in the native workflow | `.claude/workflows/agentic-implement.js:298-299` (the template literal that starts "Fix ${wp}.") | Same sentence, same place: the conformance tests compare both engines' prompts verbatim (`.claude/bin/test_pipeline.py:115-130`, key `prompts`) |
| How both engines render it | `.claude/bin/pipeline.py:336-337` (`render(self.prompts["fix"], ...)`); `.claude/bin/agentic.py:819-821` (`render_prompt`, used by `run-wave --fix`) | No code change: both read the spec |
| Scenarios that run a fix cycle | `.claude/bin/conformance.json`, scenario "verification fails on a package: it is fixed and verified again" | Its prompts include a `(fix)` call in both engines |
| The implementer's statuses and guardrails | `.claude/agents/implementer.md:38` (shared-code rule), `:47` (`BLOCKED` bullet), `:55` (guardrails paragraph: "If a block stops you from finishing ... return `BLOCKED`") | The two places that sent the agent to `BLOCKED` |
| Upgrade notes and version pins | `.claude/bin/upgrade.py:58-67` (`NOTES["2.4.0"]`), `plugin.json:4`, pins at `test_acceptance_upgrade.py:258`, `_v2.py:177`, `_v21.py:283`, `_v22.py:171`, `_v23.py:256`, `_v24.py:270` | Every pin becomes `"2.4.1"`; `_v24.py:271-276` keeps reading `NOTES["2.4.0"]` |
| The roadmap entry | `docs/roadmap/repo-review-2026-11.md:110` ("A confirmed finding on a file nobody owns cannot be fixed ...") | Gains "Fixed in 2.4.1 (prompts only; not measured)" |

## 5. Data model
None.

## 6. Contracts between modules
The sentence, identical in `pipeline-spec.json` (`prompts.fix`) and in `agentic-implement.js`, inserted after "keep the acceptance tests of your criteria green." with one space before it:
```
A defect in a file no package owns (for example, a caller your change broke) is fixed from your own files: keep that caller working with a compatible change, such as a default for a new parameter or a wrapper that keeps the old signature, unless section 6 explicitly forbids it. Return BLOCKED only when no compatible change exists in your files.
```
`implementer.md`:
- The `BLOCKED` bullet ends with: "A caller outside every package that your change breaks is not a reason to stop: keep it working from your own files (a default, a wrapper), unless section 6 explicitly forbids that; then `BLOCKED`, naming the caller."
- The guardrails paragraph's sentence "If a block stops you from finishing, do not try to get around it (for example, by writing with Bash): return `BLOCKED`." gains, after it: "A file no package owns is never yours to edit, but a caller in it that your change breaks is yours to keep working, from your own files."

`upgrade.NOTES["2.4.1"]`, one note: "The fix-cycle prompt and implementer.md say that a caller outside every package that a change breaks is kept working from the changed package's files (a default for a new parameter, a wrapper), and that BLOCKED is only for when no compatible change exists or section 6 explicitly forbids it. A customised implementer.md keeps the old wording: merge the two sentences."

## 7. Conventions
- English; one sentence per rule; the spec and the JS copy must be byte-identical in the rendered prompt.
- No hard-coded version in the docs (`acceptance/test_docs.py:95-97`).
- One commit per WP; no model names.

## 8. Work packages and acceptance criteria
### Acceptance criteria
- AC-001 · The fix prompt says how to handle a caller nobody owns
  - Scenario: the spec after the change.
  - Action: read `pipeline-spec.json`'s `prompts.fix`; render it with `agentic.render_prompt({}, "fix", "WP-01", defects="[]", retry="")`.
  - Expected: both contain the section-6 sentence exactly; in the template it sits after "criteria green." and before `{retry}`.
  - Must not: change anything else: the template with the new sentence (and its leading space) removed equals the template before the change, byte for byte (the test keeps that old template as a constant).
  - Check: `.claude/bin/test_acceptance_v241.py::FixPromptTests`
  - WP: WP-01
- AC-002 · Both engines send the same fix prompt
  - Scenario: the conformance scenario "verification fails on a package: it is fixed and verified again".
  - Action: run it through `test_pipeline.run_scenario` and through `node .claude/bin/test_workflow.mjs --dump`.
  - Expected: in both summaries, the prompt under the key `implementer:WP-02 (fix)#1` (as `test_pipeline.summarize` names it, `test_pipeline.py:115-129`) contains the section-6 sentence, and the two prompts are equal.
  - Must not: differ between engines.
  - Check: `.claude/bin/test_acceptance_v241.py::EnginesTests`
  - WP: WP-01
- AC-003 · `implementer.md` no longer sends a broken outside caller to `BLOCKED`
  - Scenario: `implementer.md` after the change.
  - Action: read the `BLOCKED` bullet and the guardrails paragraph.
  - Expected: the bullet contains "not a reason to stop" and "explicitly forbids"; the paragraph contains "never yours to edit" and "yours to keep working"; the old sentence "If a block stops you from finishing" is still there.
  - Must not: loosen the hook rule: the sentence "A hook blocks any write outside your WP's files" is still present, unchanged.
  - Check: `.claude/bin/test_acceptance_v241.py::ImplementerTests`
  - WP: WP-01
- AC-004 · Release 2.4.1
  - Scenario: the repository after the change.
  - Action: read `plugin.json`, `upgrade.NOTES` and the roadmap.
  - Expected: version `2.4.1`; `NOTES["2.4.1"]` has one note mentioning `implementer.md` and `compatible`; the note counts of 2.4.0/2.3.0/2.2.0/2.1.0/2.0.0 are `[2, 2, 2, 4, 7]`; the roadmap line starting "- A confirmed finding on a file nobody owns" contains "Fixed in 2.4.1".
  - Must not: change the other notes: `NOTES`' keys are exactly the old ones plus `"2.4.1"`, with the counts above; the six pins read `"2.4.1"`.
  - Check: `.claude/bin/test_acceptance_v241.py::ReleaseTests`
  - WP: WP-02

### Work packages
#### WP-01 · The rule in the prompts
- Wave: 1.
- Files: `.claude/workflows/pipeline-spec.json`, `.claude/workflows/agentic-implement.js`, `.claude/agents/implementer.md`.
- ACs: AC-001, AC-002, AC-003.
- **Patterns to mirror:** `.claude/workflows/pipeline-spec.json:13`, `.claude/workflows/agentic-implement.js:298-299`, `.claude/agents/implementer.md:44-55`.
- **Gotchas:** the JS copy is a template literal: keep the sentence on the same line as "criteria green." so the rendered strings match. `test_definitions.py` checks the agent files' required sections; do not rename any heading. The sentence has no `{` or `}` (`pipeline.render`, `.claude/bin/pipeline.py:31-35`, replaces `{key}` placeholders), no backtick and no `${`, so it can sit inside the second template literal of `agentic-implement.js:299`, before its closing backtick.
- **WP validation:** `node .claude/bin/test_workflow.mjs`, `python3 -m unittest discover -s .claude/bin -p "test_pipeline.py"`, `python3 -m unittest discover -s .claude/bin -p "test_definitions.py"`, and the AC-001…AC-003 classes of `test_acceptance_v241.py`.

#### WP-02 · Version 2.4.1, note and roadmap
- Wave: 1.
- Files: `.claude-plugin/plugin.json`, `.claude/bin/upgrade.py`, the six `test_acceptance_*.py` version pins, `docs/roadmap/repo-review-2026-11.md`.
- ACs: AC-004.
- **Patterns to mirror:** `.claude/bin/upgrade.py:58-67`, `.claude/bin/test_acceptance_v24.py:267-280`.
- **WP validation:** the six pinned files and the upgrade tests, not the whole `test_acceptance_*.py` pattern (it also matches `test_acceptance_v241.py`, whose other classes check WP-01's text and stay red until WP-01 lands, not yours): `python3 -m unittest discover -s .claude/bin -p "test_acceptance_v2.py"`, the same with `test_acceptance_v21.py`, `test_acceptance_v22.py`, `test_acceptance_v23.py`, `test_acceptance_v24.py`, `test_acceptance_upgrade.py`, `test_upgrade.py`, and from `.claude/bin` `python3 -m unittest test_acceptance_v241.ReleaseTests`.

```json wp-manifest
{
  "stack": ["python", "typescript"],
  "allow_bash": ["Bash(python3 -m unittest:*)", "Bash(node .claude/bin/test_workflow.mjs)"],
  "acceptance": {"files": [".claude/bin/test_acceptance_v241.py"], "command": "python3 -m unittest discover -s .claude/bin -p test_acceptance_v241.py"},
  "verify": {"build": "python3 -m compileall -q .claude/bin", "lint": "node .claude/bin/test_workflow.mjs", "types": "python3 -m unittest discover -s acceptance", "tests": "python3 -m unittest discover -s .claude/bin -p \"test_*.py\""},
  "docs": {"files": ["docs/how-it-works.md"], "codemap": null},
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": [".claude/workflows/pipeline-spec.json", ".claude/workflows/agentic-implement.js", ".claude/agents/implementer.md"],
     "acs": ["AC-001", "AC-002", "AC-003"], "mirror": [".claude/workflows/pipeline-spec.json:13", ".claude/workflows/agentic-implement.js:298-299", ".claude/agents/implementer.md:44-55"]},
    {"id": "WP-02", "wave": 1, "depends_on": [], "files": [".claude-plugin/plugin.json", ".claude/bin/upgrade.py", ".claude/bin/test_acceptance_upgrade.py", ".claude/bin/test_acceptance_v2.py", ".claude/bin/test_acceptance_v21.py", ".claude/bin/test_acceptance_v22.py", ".claude/bin/test_acceptance_v23.py", ".claude/bin/test_acceptance_v24.py", "docs/roadmap/repo-review-2026-11.md"],
     "acs": ["AC-004"], "mirror": [".claude/bin/upgrade.py:58-67", ".claude/bin/test_acceptance_v24.py:267-280"]}
  ]
}
```

## 9. Test strategy
- Acceptance: `.claude/bin/test_acceptance_v241.py`, AC-001…AC-004, written first and red (today the sentence is absent everywhere and the version is 2.4.0). AC-002 reuses `run_scenario` and `CONFORMANCE` from `test_pipeline.py` and the Node dump, as `test_acceptance_v24.py:EnginesTests` does.
- Regression: the whole `.claude/bin` suite, `test_workflow.mjs` (conformance prompts compared verbatim), the docs suites.
- Not measured: whether real agents now keep the caller working. The `pricing` fixture can tell (`test_ctx_*` passing, sessions ending OK) with an A/B of 2.4.0 against 2.4.1, when the user wants it.
- After merging, by hand: `agentic.py flow-history`, release `agentic-flow--v2.4.1`, `install` in the projects.

## 10. Decisions
- **D1 · Prompts only (user's choice):** the fix prompt and `implementer.md`. A deterministic marker and a reviewer or plan-reviewer change were not chosen.
- **D2 · "Unless section 6 explicitly forbids it":** a plan that deliberately removes the old signature keeps `BLOCKED` as the right answer; a silent plan does not.
- **D3 · 2.4.1 (user's choice):** a prompt fix. Projects with a customised `implementer.md` keep their copy (install leaves edited files alone); the note tells them to merge.
- **D4 · Executed by hand:** every file is under `.claude/` or pins the version; acceptance tests first and red, one commit per WP.

## 11. Risks and open questions
- **Not measured:** a prompt sentence may not change what an agent does. Without the A/B, 2.4.1 is a reasoned fix, not a proven one.
- **Over-reach:** an implementer could read the rule as permission to add compatibility shims everywhere. The sentence limits it to a caller the change broke, and the reviewer still reviews the fix.
