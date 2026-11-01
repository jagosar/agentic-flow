# Architecture: the stop gate and the four implementer statuses (agentic-flow 2.1)
Type: feature · Size: large

## 1. Goal
Two roadmap items (`docs/roadmap/repo-review-2026-11.md`, 2.1 and 2.2) that should cut fix cycles. First, a **stop gate**: when an implementer submits a report that says it is finished, the hook runs the acceptance command before the report is accepted; if a failure is attributed to that package, the report is refused with the failing lines and the agent keeps working, at most twice per package per stage. Second, **four implementer statuses** instead of two: `DONE`, `DONE_WITH_CONCERNS` (done, with doubts the reviewer must weigh), `NEEDS_CONTEXT` (the brief was not enough: one re-dispatch with the whole `architecture.md`, then blocked) and `BLOCKED` (as `BLOCKER` today). Both engines handle the statuses deterministically; the plugin becomes 2.1.0 with upgrade notes. The bench (4 fixtures × 3 sessions) measures the result against the 2.0.0 rows of `bench/RESULTS.md`.

## 2. Scope
### Included
- The gate in `agentic.py hook`, on the `StructuredOutput` tool: identity, conditions, attribution, the denial cap, its state file, and the `GATE:` line of `close-stage`.
- `settings.json`: the hook matcher gains `StructuredOutput` and a `timeout`; `install` upgrades an already-installed matcher.
- The implementer report schema (statuses, `concerns`, `missing_context`) in `pipeline-spec.json` and in `agentic-implement.js`; the engines' handling of each status; the reviewer prompt carries the concerns; conformance scenarios for both engines.
- The implementer and `/implement` prompts; definition tests.
- `plugin.json` 2.1.0, `NOTES["2.1.0"]`, roadmap note; acceptance tests in `.claude/bin/test_acceptance_v21.py`.
### Excluded (non-goals)
- A `SubagentStop` or `Stop` gate: measured in this session, a `Stop` block does not alter a `--json-schema` structured answer, so the gate lives on the tool call that delivers the report (decision D1).
- Resuming the same implementer in fix cycles, a model per WP, scoped re-review (roadmap 2.3, 2.4): later packages.
- Statuses of the test-author, QA and doc-updater: they keep `DONE`/`BLOCKER` and `PASS`/`FAIL`.
- A gate on the `verify.*` commands: only the acceptance command is run, because only it is attributable to a package by `acs`.
- The release and the bench run: by hand after merging (section 9).

## 3. Stack
Python 3.9+ standard library (`agentic.py`, `pipeline.py`, tests with `unittest`; no type annotations in `agentic.py`, which has none); Node 22 for the native workflow and its scenario runner (`typescript` in `stack` for its rules). No new dependency.
- Build: `python3 -m compileall -q .claude/bin`
- Lint (the conformance scenarios, both engines must agree): `node .claude/bin/test_workflow.mjs`
- Tests: `python3 -m unittest discover -s .claude/bin -p "test_*.py"` (about 90 s)
- Acceptance: `python3 -m unittest discover -s .claude/bin -p test_acceptance_v21.py`

## 4. Repository structure
```
.claude/bin/agentic.py                      WP-01  the gate in guard(), gate.json, GATE: line, status_to_state, merge_settings
.claude/settings.json                       WP-01  matcher with StructuredOutput and timeout
.claude/bin/test_agentic.py                 WP-01  hook, close-stage and install tests
.claude/bin/test_acceptance_portable.py     WP-01  pins the hook matcher at :256
.claude/workflows/pipeline-spec.json        WP-02  implementer schema and prompts (implement_full, reviewer {concerns})
.claude/workflows/agentic-implement.js      WP-02  REPORT_SCHEMA, status handling, GATE: parsing, concerns to pending and reviewer
.claude/bin/pipeline.py                     WP-02  the same, in Python
.claude/bin/conformance.json                WP-02  four new scenarios
.claude/bin/test_pipeline.py                WP-02  summary gains gate_denials; scenario assertions
.claude/bin/test_workflow.mjs               WP-02  the same, in Node
.claude/bin/testutil.py                     WP-02  fake claude: FAKE_CONCERNS, FAKE_NEEDS_CONTEXT
.claude/agents/implementer.md               WP-03  the four statuses and the gate
.claude/commands/implement.md               WP-03  presents concerns and gate denials
.claude/bin/test_definitions.py             WP-03
.claude-plugin/plugin.json                  WP-04  version 2.1.0
.claude/bin/upgrade.py                      WP-04  NOTES["2.1.0"]
.claude/bin/test_upgrade.py                 WP-04
.claude/bin/test_acceptance_upgrade.py      WP-04  pins the plugin version at :258
.claude/bin/test_acceptance_v2.py           WP-04  pins the plugin version at :177
docs/roadmap/repo-review-2026-11.md         WP-04  2.1 and 2.2 shipped in 2.1.0; 2.1 corrected (not SubagentStop)
.claude/bin/test_acceptance_v21.py          AT
README.md, docs/how-it-works.md, docs/how-to/   docs (doc-updater)
```

## 4b. Existing code context
| What an implementer needs to know | Where it is | Pattern or rule |
|---|---|---|
| The hook's entry and its fail-closed wrapper | `.claude/bin/agentic.py:1985-1998` (`hook()`), `:1929-1983` (`guard(data)`) | `guard` returns to allow, calls `block(msg)` (`:1812`: prints `[agentic guard] msg` to stderr, exit 2) to deny. Any exception inside a restricted agent blocks |
| How the hook knows who is acting | `guard` `:1932-1952`: `AGENTIC_WP` env (fallback engine, set at `:745`) or `claims.json` through `data["agent_id"]` (native workflow) | The gate uses `owner_id` after that block, exactly like the write rules; an owner that does not match `^WP-\d+$` is never gated |
| What a `StructuredOutput` call looks like to the hook | Measured in this session with CLI 2.1.316: `tool_name` is `StructuredOutput`, `tool_input` is the report object itself (`status`, `wp`, `files`…); `agent_type` is present; exit 2 with a stderr reason denies it and the agent re-submits a corrected report (3 turns in the probe) | `tinput.get("status")` is the status. Nothing else of the report is trusted |
| The `Stop` hook does not work for this | Measured: with `--json-schema`, `{"decision":"block"}` on `Stop` left the structured answer unchanged and the second `Stop` never fired | Decision D1 |
| Running the acceptance command without a shell | `run_command(cmd, timeout=900, scan=None)` `:1208-1228`: returns `(code, tail)`; with a list in `scan` the last 200 lines are appended to it. `acceptance_check` `:1230-1249` wraps it but also writes a ledger line (`ledger_stage`) and prints | The gate calls `run_command` directly (no ledger line, no stdout) and takes the command from `at_entity(manifest)["command"]` (`:1232`) |
| Exit codes that mean "could not run" | `acceptance_check` `:1240`: `code in (124, 126, 127)` | The gate lets through in that case: it cannot judge |
| Attributing failures to packages | `attribute(manifest, lines)` `:1557-1574`: `{wp_id: {"files": [...], "acs": [...]}}` by whole path or `AC-NNN` in the text | The gate denies only on the WP's own failure (section 6): its files mentioned, or an AC that only it owns. A shared AC or another package's failure never stops this one |
| Which lines to show the agent | `failure_lines(lines)` `:1539-1543` and `normal_failure` `:1534` pick the lines that matter | Show the lines that mention the WP's files or ACs (`attribute`'s `mentioned` logic), then the command's last 3 lines, at most `GATE_MAX_LINES` |
| State files under `.claude/state/` with a lock | `locked_json(path, fn)` `:1673-1690` (used by `with_claims` `:1693`); constants `STATE`, `CLAIMS`, `LEDGER_JSON` `:72-77` | `GATE = STATE / "gate.json"`; `gate_denials(fn)` is `locked_json(GATE, fn)` |
| Where a stage starts and ends | `open_stage` `:1459-1469` (snapshot, prints `{"stage","owners"}`), `close_stage` `:1472-1508` (marks `ID=state`, `--fix`, acceptance, `RESULT:` line, exit 3 on REVIEW) | `open_stage` resets the gate counters of its owners; `close_stage` prints one `GATE:` line before `RESULT:` |
| Ledger states and the status mapping | `LEDGER_STATES` `:78`; `status_to_state(status)` `:1723-1726` (first word of the status) | Extend the mapping; `LEDGER_STATES` does not change |
| The fallback engine launches one `claude -p` per agent | `:736-776`: `--json-schema` from `spec["schemas"][agent_type]`, `--allowedTools` from `pipeline_tools` `:1320`, `AGENTIC_WP` in the env | No change needed there: the hook sees `AGENTIC_WP` |
| The pipeline-spec and its hand-mirrored JS twin | `.claude/workflows/pipeline-spec.json` (`schemas.implementer`, `prompts.implement`, `prompts.fix`, `prompts.fix_retry`, `prompts.reviewer`); `.claude/workflows/agentic-implement.js:56-66` (`REPORT_SCHEMA`), `:269-287` (`launchWave`), `:430` (the reviewer prompt, a literal string) | A field added to one must be added to the other identically; `test_workflow.mjs` compares them (`required` order matters: `deepEqual`) |
| Where the wave states are decided | JS `:285`; Python `pipeline.py:285`: `error` if no report, `done` if `status == 'DONE'`, else `blocker` | Replace with `wave_states` (section 6) |
| Where pending items are built and what blocks | JS `:258` and `:264` (`run.pending.push({type, severity, problem})`), `:465` (`run.result` is `REVIEW` if a pending item's `severity` is in `BLOCKING`); Python `:455`, `:399` | A concern item has no `severity`, so it never blocks, like the `needs validation` items (`needsItem` JS `:188`, `Pipeline.needs_item` `pipeline.py:119-125`) |
| The run record both engines return | JS `:180` (`const run = {...}`); Python `Pipeline.__init__` (`self.run`), the same keys | Add `gate_denials: {}` next to `not_checked` |
| Report helper and `call` | JS `report(prompt, opts)` `:182-186`; Python `Pipeline.call` `pipeline.py:106-116` | A re-dispatch is a second `report`/`call` with label `WP-01 (context)` |
| Prompt rendering | Python `render(template, **values)` `pipeline.py:31-35`, `{key}` placeholders; `compact(value)` `pipeline.py:26` for JSON in prompts; the JS writes prompt strings inline | New placeholders: `{missing}` in `implement_full`, `{concerns}` in `reviewer` |
| Fix counters | JS `fixCount` `:193`, incremented in `fixCycle` `:330`; Python `self.fix_count` `pipeline.py:331` | A `(context)` call is not a fix attempt and must not touch them |
| Conformance: the shared world and the summaries | `test_pipeline.py:28-70` (`world`), `:108-119` (`summarize`), `:144` (the compared keys); `test_workflow.mjs:449-470` (`fromDecl`), `:486` (summary), `:491` (every scenario), `:518-529` (named assertions). Scenarios override reports with `reports.implementer[wp]` (`test_workflow.mjs:66`) and gatekeeper answers with `gate_fail` (`test_pipeline.py:41-43`) | New scenarios use `reports` for statuses and `gate_fail` (exit 0 is allowed there) for a `GATE:` line in a close-stage output. A `reports.implementer[wp]` override that must differ between the first and second call takes a list: first element for the first call, last element afterwards (extend `world` and `fromDecl` the same way) |
| The simulated `claude` | `.claude/bin/testutil.py:36-95`: env knobs; the "first call only" marker-file pattern at `:78-81` | Add `FAKE_CONCERNS` and `FAKE_NEEDS_CONTEXT=<WP>` |
| Hook tests | `test_agentic.py:57-58` (`Repo.hook(payload, wp)` returns the exit code), `:69-80` (`write_payload`, `bash_payload`) | Add `report_payload(status, wp, agent_id=None)` next to them; the fake acceptance command is a Python script written into the temp repo, as the acceptance-command tests of that file do |
| Install tests | `test_agentic.py:933-1012` (`InstallTests`: a project `settings.json` with its own entries, `install` twice, "settings.json: unchanged") | Mirror `test_installs_the_flow_and_keeps_project_configuration` `:970` |
| Installing settings | `merge_settings(dst, src)` `:1051-1085`: adds the flow's `PreToolUse` entry only if none ends with `hook`; `install` `:1153-1160` writes it | Extend: when the agentic entry exists but its `matcher` lacks `StructuredOutput`, append `\|StructuredOutput` to the project's matcher (never replace it: a project may have trimmed it), set the hook's `timeout` from `src` when absent, and add `"hook PreToolUse (StructuredOutput)"` to `added` |
| Upgrade notes | `.claude/bin/upgrade.py:50-62` (`NOTES["2.0.0"]`, a list of strings); `test_acceptance_upgrade.py:258` and `test_acceptance_v2.py:177` pin the version | `NOTES["2.1.0"]`, pin `2.1.0` in both |
| The matcher is pinned by a test | `test_acceptance_portable.py:254-258` asserts the exact matcher `Write|Edit|MultiEdit|NotebookEdit|Bash` | Update it to the new matcher (WP-01) |
| The hook's messages say "return BLOCKER" | `agentic.py:1906`, `:1915`, `:1978`, `:1981` | They become "return the blocked status your schema allows (BLOCKED for an implementer, BLOCKER for the others)"; the rules themselves do not change |
| Definition tests of prompts | `.claude/bin/test_definitions.py:179` reads `implement.md`; the 2.0.0 tests near the end pin phrases | One test per rule, asserting the exact phrase |
| What `/implement` presents | `.claude/commands/implement.md:60-64` (pending, needs validation, not_checked) | Add concerns and gate denials there |
| Docs the doc-updater touches | `docs/how-it-works.md:187-224` (hook diagram and text), `:226-244` (permission matrix), `:327` (glossary); `docs/how-to/README.md:278` (testing the flow: test counts) | The diagram gains a `StructuredOutput` branch |

**What must NOT change:** `validate`'s refusal of `.claude/` ownership (`:403`), the write rules of `guard` (their wording may), `LEDGER_STATES`, the schemas of the other agents, `constants.blocking`, `close-stage`'s exit codes and its `RESULT:` line.

## 5. Data model
Report of an implementer (both engines, identical):
```json
{"status": "DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED",
 "wp": "WP-01", "files": [], "checks": [{"command": "", "passed": true, "detail": ""}],
 "internal_decisions": [], "not_checked": [],
 "concerns": ["<a doubt about the result, one sentence, with the file>"],
 "missing_context": {"what": "<what the brief lacked>", "section": "<section of architecture.md that should have it>"},
 "blocker": {"missing": "", "section": "", "options": []}}
```
`required`: `["status", "wp", "files", "checks", "internal_decisions", "blocker", "not_checked", "concerns", "missing_context"]`, in that order in both files. `concerns` is `[]` unless the status is `DONE_WITH_CONCERNS`; `missing_context` is `null` (type `["object", "null"]`, `required: ["what", "section"]`) unless `NEEDS_CONTEXT`; `blocker` is `null` unless `BLOCKED`.

Gate state, `.claude/state/gate.json`: `{"WP-01": {"denials": 1, "last": ["FAILED acceptance/test_ac_001.py::test_ac_001_x"]}}`. Reset per WP when its stage opens.

Pending item of a concern: `{"type": "concern", "source": "WP-01", "wp": "WP-01", "problem": "<the sentence>"}`. No `severity`.

Run record: `gate_denials: {"WP-01": 1}` (only WPs with at least one denial), summed from the `GATE:` lines of every close-stage, fix cycles included.

## 6. Contracts between modules
Python, `.claude/bin/agentic.py` (WP-01):
```python
GATE = STATE / "gate.json"
GATE_MAX_DENIALS = 2        # per WP and stage; afterwards the report is let through
GATE_MAX_LINES = 40         # lines shown to the agent in a denial
GATE_STATUSES = ("DONE", "DONE_WITH_CONCERNS")

GATE_TIMEOUT_S = 840        # below the hook's 900 s, so the gate times out before the CLI kills the hook

def gate_denials(fn):        # locked_json(GATE, fn); fn(data) -> dict or None
def gate_reset(owners):      # drops the counters of those WPs (a list of IDs); called by open_stage
def gate_check(owner_id, status):
    """The stop gate. Returns None to let the report through, or a list of lines to show (the report is refused).
    Loads the manifest itself, inside its own try (see "fails open"). Lets through when: status is not in
    GATE_STATUSES (or not a string); the manifest has no acceptance command;
    the WP already has GATE_MAX_DENIALS denials; the command cannot run (exit 124/126/127) or times out
    (run_command(cmd, timeout=GATE_TIMEOUT_S, scan=lines)); it passes; or the failure is not the WP's own (below).
    On a refusal, increments gate.json for owner_id and stores the lines."""
```
No type annotations in `agentic.py` (the file has none and must import on Python 3.9: `list[str] | None` is a `TypeError` there).

**The WP's own failure:** `found = attribute(manifest, lines).get(owner_id)`; the failure is the WP's own if `found["files"]` is non-empty, or if any of `found["acs"]` is owned by `owner_id` alone (listed in no other WP's `acs`). An AC shared with another package, or a package in a later wave, never refuses this one's report.

**The gate fails open:** `gate_check` catches `ManifestError` (from its own `load_manifest()`), `OSError` and `ValueError` itself, prints `[agentic guard] gate skipped: <error>` to stderr and returns None. The hook's fail-closed wrapper stays for everything else; a broken gate must not refuse reports forever (the cap is only raised on a real denial).
`guard(data)` handles `tool == "StructuredOutput"` right after `owner_id` is resolved from the env or from `claims.json` (`:1949`) and **before** the identity block that demands a claim (`:1950-1952`): a report is never refused for a missing claim (a reviewer or QA that never claimed still delivers its report). If `owner_id` matches `^WP-\d+$` it calls `gate_check(owner_id, status)`; otherwise it returns. On a list it calls `block(...)` with:
```
WP-01: the report says DONE but the acceptance tests of your package fail (denial 1 of 2). Failing lines:
  <line>
  ...
Run `<acceptance.command>`, fix your files and submit the report again. If a test contradicts architecture.md, return BLOCKED and say which.
```
`close_stage` prints, before `RESULT:`, one line `GATE: WP-01=1 WP-02=0` listing every WP in `marks` in that order (judge IDs `QA`, `AT`, `REVIEW`, `DOCS` are not listed; no line when no mark is a WP).
`status_to_state` maps `DONE`→`done`, `DONE_WITH_CONCERNS`→`done`, `NEEDS_CONTEXT`→`blocker`, `BLOCKED`→`blocker`, `BLOCKER`→`blocker` (kept for the test-author and doc-updater), the others as today.
`merge_settings(dst, src)` also appends `"hook PreToolUse (StructuredOutput)"` to `added` when it upgraded an existing agentic entry's `matcher` and `timeout`; a second call adds nothing.

`.claude/settings.json` (WP-01): the agentic `PreToolUse` entry becomes
```json
{"matcher": "Write|Edit|MultiEdit|NotebookEdit|Bash|StructuredOutput",
 "hooks": [{"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/bin/agentic.py\" hook", "timeout": 900}]}
```
(`timeout` is in seconds; the CLI's default is 60; the acceptance command can take minutes.)

Engines (WP-02), the same in `pipeline.py` (module-level functions) and `agentic-implement.js` (consts):
```python
def wave_states(wp_ids, reports) -> list[str]        # "WP-01=done" | "WP-01=blocker" | "WP-01=error" per the mapping above
def gate_line(output) -> dict[str, int]               # parses "GATE: WP-01=1 WP-02=0" from a close-stage output; {} if absent
def concern_item(wp, text) -> dict                    # the pending item of section 5
```
Behaviour per status in `launch_wave`/`launchWave`, before the states are computed:
- `DONE_WITH_CONCERNS`: each string of `concerns` → `concern_item` appended to `concern_pending` (`self.concern_pending` / `const concernPending = []`), a list of its own like `limit_pending`; the report stays in `run["work_packages"][wp]`. Both engines rebuild `run["pending"]` after QA (JS `:421`, `:463`; Python `:348`, `:397`): those assignments become `qa_pending + limit_pending + concern_pending`, so concerns survive to the result. Every review (the first and each one after a fix cycle) gets all concerns gathered so far, and a concern stays in `pending` even when the reviewer confirms it as a finding (the finding carries the severity; the concern records who raised it).
- `NEEDS_CONTEXT` in an implement wave (`defects_by_wp` empty), first time for that WP in this run: one more call with prompt `implement_full` (label `f"{wp} (context)"`, same agent type); the second report replaces the first in `run["work_packages"][wp]` and is mapped like any other (a second `NEEDS_CONTEXT` is `blocker`). In a fix wave `NEEDS_CONTEXT` is `blocker` with no re-dispatch.
- `BLOCKED`, and any status outside the four (a legacy `BLOCKER` from a custom agent): `blocker` state, the wave stops, as today.
After every close-stage of a wave (implement or fix), `gate_line(close.output)` is summed into `run["gate_denials"]` (keys with 0 are not stored) right after `run["stages"]` is appended and **before** the `if not good` stop (JS `:310`, Python `:308`), so a wave that ends in REVIEW still reports its denials.
Reviewer prompt: `prompts.reviewer` becomes `Review the integrated code according to architecture.md.{concerns}{rules}`, built from `concern_pending` (never from `run["pending"]`, which is rebuilt only after QA), where `{concerns}` is `""` when `concern_pending` is empty, else `"\nThe implementers finished with these concerns about their own code, as JSON:\n" + compact([{"wp", "problem"}...]) + "\nCheck each one: confirm it as a finding with its severity, or leave it out if the code is right."`. The JS builds the same string.
New prompt `prompts.implement_full`: `Implement {wp}. Your first attempt returned NEEDS_CONTEXT: {missing}. This time your brief is architecture.md, whole: read it and implement. If the document does not settle it, return BLOCKED with the section that should.{rules}`, where `{missing}` is `missing_context.what` followed by ` (section <section>)`. If `missing_context` is not an object with a string `what`, there is no re-dispatch: the status maps to `blocker` (a malformed report is not a request for context).
Conformance summary (both runners) gains `"gate_denials": result["gate_denials"]`, and the comparison tuple at `test_pipeline.py:144` includes it.

Fake `claude` (WP-02, `testutil.py`): every implementer report now carries `concerns: []` and `missing_context: null`. `FAKE_CONCERNS=1` → every implementer answers `DONE_WITH_CONCERNS` with `concerns: ["the retry loop in src/<wp>.py may spin"]`. `FAKE_NEEDS_CONTEXT=<WP>` → that WP answers `NEEDS_CONTEXT` with `missing_context: {"what": "the error type of the contract", "section": "6"}` on its first call only (the marker-file pattern), `DONE` afterwards.

## 7. Conventions
- The flow's existing style: English identifiers and messages; short flat functions; constants in UPPER_CASE next to their siblings (`MAX_CHECKED_COMMAND` `:185`); no new dependency; every hook path fails closed (the wrapper at `:1985` already does that for exceptions).
- The hook writes nothing to stdout (the CLI does not show it); the agent sees stderr only on exit 2.
- Messages to agents name the WP first, then what was refused, then what to do (`block` messages at `:1974-1981`).
- The JS and Python engines mirror each other in behaviour; a change in one is a change in the other before any test runs.
- Tests: `unittest`, one behaviour per test, named after it; the fake acceptance command is a script in the temp repo, never the real suite.
- Commit format: the repo's history (`Short imperative summary (#PR)` after squash).
- Forbidden: relaxing `validate`, touching the other agents' schemas, a `Stop`/`SubagentStop` hook, gating any owner that is not a `WP-NN`.

## 8. Work packages and acceptance criteria
### Acceptance criteria
- AC-001 · A finished report with the package's acceptance tests red is refused
  - Scenario: a temp repo (`test_agentic.Repo`) whose manifest has `acceptance.command` pointing at a script that exits 1 and prints `FAILED acceptance/test_x.py::test_ac_001_x - assert`, with `WP-01` (`acs: ["AC-001"]`) and `WP-02` (`acs: ["AC-002"]`). The script also creates a marker file when it runs.
  - Action: `agentic.py hook` with `AGENTIC_WP=WP-01` and stdin `{"tool_name": "StructuredOutput", "tool_input": {"status": "DONE", "wp": "WP-01", ...}}`.
  - Expected: exit 2; stderr contains `WP-01`, `denial 1 of 2` and the `FAILED` line; `.claude/state/gate.json` has `WP-01.denials == 1`.
  - Must not: deny with `AGENTIC_WP=WP-02` (exit 0, no counter for `WP-02`); deny `WP-01` when the failing test names only an AC that `WP-01` shares with `WP-02` (`acs: ["AC-001", "AC-003"]` on both); run the command when the status is `BLOCKED` or `NEEDS_CONTEXT` (exit 0, no marker file).
  - Check: `test_acceptance_v21.py::GateTests::test_ac_001_red_acceptance_refuses_the_report`
  - WP: WP-01
- AC-002 · The gate gives up after two denials and resets when the stage opens
  - Scenario: AC-001's repo, with `gate.json` at `{"WP-01": {"denials": 2, "last": []}}`.
  - Action: the same hook call; then `agentic.py open-stage 1` and the hook call again.
  - Expected: first call exit 0 (let through, counter stays 2); after `open-stage 1` the counter for `WP-01` is gone and the call is denied again (exit 2, `denial 1 of 2`).
  - Must not: let a `DONE` through on a red suite when the counter is below 2; count a denial for a WP other than the owner.
  - Check: `test_acceptance_v21.py::GateTests::test_ac_002_cap_and_reset`
  - WP: WP-01
- AC-003 · close-stage reports the denials and the engines sum them
  - Scenario: AC-001's repo with `gate.json` `{"WP-01": {"denials": 1, "last": []}}` and a green acceptance script; the conformance scenario `gate denials are summed from close-stage`, whose `gate_fail` answers `close-stage 1` with exit 0 and output `WP-01: 1 file(s) changed: src/a.py\nWP-02: 1 file(s) changed: src/b/x.py\nGATE: WP-01=1 WP-02=0\nRESULT: OK`.
  - Action: `agentic.py open-stage 1` (the gate reset leaves `WP-01` at 0, so `gate.json` is written after it), then `agentic.py close-stage 1 WP-01=done WP-02=done`; then both conformance runners on the scenario.
  - Expected: the close-stage output has the line `GATE: WP-01=1 WP-02=0` before `RESULT: OK`; both runners' summary has `gate_denials == {"WP-01": 1}`.
  - Must not: list `QA`, `AT`, `REVIEW` or `DOCS` in the `GATE:` line (`close-stage qa QA=pass` prints no `GATE:` line); store a WP with 0 denials in `gate_denials`.
  - Check: `test_acceptance_v21.py::GateTests::test_ac_003_close_stage_line` (WP-01's half) and `test_acceptance_v21.py::EngineTests::test_ac_003_engines_sum` (WP-02's half)
  - WP: WP-01, WP-02
- AC-004 · The four statuses map deterministically in both engines
  - Scenario: the conformance scenarios `concerns go to pending and to the reviewer` (`reports.implementer["WP-01"] = {"status": "DONE_WITH_CONCERNS", "concerns": ["the retry loop in src/a.py may spin"]}`), `needs context is re-dispatched once with the whole document` (`WP-02`: `[{"status": "NEEDS_CONTEXT", "missing_context": {...}}, {"status": "DONE"}]`), `needs context twice is a blocker` (`WP-02` answers `NEEDS_CONTEXT` on both calls, and `gate_fail: [{"prefix": "close-stage 1 ", "exit_code": 3, "output": "RESULT: REVIEW"}]`, as the scenario "a wave in REVIEW stops before the next" does, because the simulated gatekeeper answers exit 0 otherwise) and `needs context in a fix wave is a blocker` (`review: [{"status": "FAIL", "findings": [<one high finding on WP-01>]}]`; `reports.implementer["WP-01"] = [{"status": "DONE"}, {"status": "NEEDS_CONTEXT", "missing_context": {...}}]`, because the implement and the `(fix)` call share the key `WP-01`; and `gate_fail` on `close-stage 1 ` exit 3 with `--fix` in the prefix: `{"prefix": "close-stage 1 WP-01=blocker", "exit_code": 3, "output": "RESULT: REVIEW"}`).
  - Action: both conformance runners.
  - Expected: scenario 1: result `OK`, `pending` contains `concern`, the reviewer prompt (`prompts["reviewer:reviewer#1"]`) contains `the retry loop in src/a.py may spin`, the close-stage of wave 1 carries `WP-01=done`. Scenario 2: `agents` contains `implementer:WP-02 (context)` once, its prompt contains `architecture.md, whole` and `the error type of the contract`, the wave closes `WP-02=done`, result `OK`. Scenario 3: the wave closes `WP-02=blocker`, result `REVIEW`, `failed_stage` `wave 1`, `implementer:WP-02 (context)` exactly once. Scenario 4: the first wave closes `WP-01=done`, the fix wave closes `WP-01=blocker --fix`, result `REVIEW`, `failed_stage` `fix wave 1`, no `(context)` call.
  - Must not: a concern item with a `severity`; a third dispatch of `WP-02`; a `(context)` call counted as a fix attempt.
  - Check: `test_acceptance_v21.py::EngineTests::test_ac_004_status_mapping`
  - WP: WP-02
- AC-005 · Both engines carry the same implementer schema and the simulated claude speaks it
  - Scenario: `pipeline-spec.json` and `agentic-implement.js` as merged; a temp project with the fake `claude` and `FAKE_CONCERNS=1`.
  - Action: compare `schemas.implementer` of the spec with `REPORT_SCHEMA` extracted from the JS (as `test_acceptance_v2.py::SchemaTests` does); run `agentic.py run-pipeline` in the temp project.
  - Expected: `status.enum == ["DONE", "DONE_WITH_CONCERNS", "NEEDS_CONTEXT", "BLOCKED"]`, `required` identical in both and containing `concerns` and `missing_context`; `workflow-result.json` has `result == "OK"`, one `concern` pending item per WP and `gate_denials == {}`.
  - Must not: `BLOCKER` in the implementer enum; a difference in `required` order between the two files.
  - Check: `test_acceptance_v21.py::SchemaTests::test_ac_005_schema_in_both_engines_and_fake`
  - WP: WP-02
- AC-006 · The prompts say it
  - Scenario: the merged `implementer.md` and `implement.md`.
  - Action: read them.
  - Expected: `implementer.md` names the four statuses, one line each, containing these phrases: `DONE_WITH_CONCERNS` with "one sentence per concern, with the file"; `NEEDS_CONTEXT` with "you will get the whole document once"; `BLOCKED` with "a contract does not match"; and the gate: "a report that says DONE while the acceptance tests of your criteria fail is refused, twice at most". `implement.md` has a bullet for `concern` items and one for `gate_denials`.
  - Must not: the token `BLOCKER` anywhere in `implementer.md`.
  - Check: `test_acceptance_v21.py::PromptTests::test_ac_006_prompts`
  - WP: WP-03
- AC-007 · Version and notes
  - Scenario: the merged repo.
  - Action: read `plugin.json`, `upgrade.NOTES`, the roadmap.
  - Expected: version `2.1.0`; `NOTES["2.1.0"]` has at least three strings, mentioning `gate`, `DONE_WITH_CONCERNS` and `settings.json` between them; the roadmap's "Versioning" section names 2.1.0 for items 2.1 and 2.2.
  - Must not: `NOTES["2.0.0"]` changed (seven strings, same first sentence).
  - Check: `test_acceptance_v21.py::ReleaseTests::test_ac_007_version_and_notes`
  - WP: WP-04
- AC-008 · install upgrades the hook matcher of a 2.0 project
  - Scenario: a temp `settings.json` with the 2.0.0 agentic entry whose matcher the project trimmed to `Write|Edit|Bash` (no `timeout`) and a project-owned `PreToolUse` entry (`matcher: "Bash"`, another command).
  - Action: `agentic.merge_settings(dst, src)` with the repo's `settings.json` as `src`, twice.
  - Expected: the agentic entry's matcher is exactly `Write|Edit|Bash|StructuredOutput`, its hook has `timeout == 900`, `added` contains `hook PreToolUse (StructuredOutput)`; the project's entry is unchanged; the second call's `added` is empty.
  - Must not: duplicate the agentic entry; alter the project's entry.
  - Check: `test_acceptance_v21.py::InstallTests::test_ac_008_matcher_upgrade`
  - WP: WP-01

### Work packages
#### WP-01 · The gate in the hook, the GATE: line, the settings
- Wave 1.
- Files: `.claude/bin/agentic.py`, `.claude/settings.json`, `.claude/bin/test_agentic.py`, `.claude/bin/test_acceptance_portable.py`.
- Implements `gate_check`, `gate_reset`, `gate_denials`, the `GATE:` line, `status_to_state`, `merge_settings` (section 6). Consumes nothing.
- ACs: AC-001, AC-002, AC-003 (the close-stage half), AC-008.
- Patterns to mirror: `guard` write rules `:1961-1983` (message shape, `block`), `with_claims`/`locked_json` `:1673-1696` (state file), `acceptance_check` `:1230-1249` (exit codes), `attribute` `:1557-1574`, `failure_lines` `:1539-1543`, `open_stage` `:1459-1469`, `close_stage` `:1472-1508`, `merge_settings` `:1051-1085`; tests `test_agentic.py:57-80` and `InstallTests` `:933-1012`.
- Gotchas: WP-02 lands before WP-01 (the `run-wave` tests of `test_agentic.py` need the fake `claude` to emit the new required fields), and every WP's checks run on the merged tree; the hook's `cwd` may be a subdirectory, use `ROOT`; the gate's `run_command` timeout is `GATE_TIMEOUT_S`, below the hook's 900 s; a shared AC (`acs` in two WPs) never counts against either; `gate.json` is written by parallel implementers, always through `locked_json`; a WP with neither `acs` nor mentioned files is never attributed (let through); the gate must not print to stdout; `status` may be missing or not a string in a malformed report: not in `GATE_STATUSES`, let through (the schema refuses it anyway); `open_stage` takes the label of a wave, `gate_reset` receives that wave's `owners`.
- Exact imports and APIs: none new; `json`, `re`, `Path` are already imported.
- WP validation: `python3 -m unittest discover -s .claude/bin -p test_agentic.py`; `python3 -m unittest discover -s .claude/bin -p test_acceptance_portable.py`; `python3 -m compileall -q .claude/bin`.

#### WP-02 · Statuses, concerns and gate_denials in both engines
- Wave 1.
- Files: `.claude/workflows/pipeline-spec.json`, `.claude/workflows/agentic-implement.js`, `.claude/bin/pipeline.py`, `.claude/bin/conformance.json`, `.claude/bin/test_pipeline.py`, `.claude/bin/test_workflow.mjs`, `.claude/bin/testutil.py`.
- Implements `wave_states`, `gate_line`, `concern_item`, the re-dispatch, the reviewer `{concerns}`, the schema (section 5), the fake knobs. Consumes the `GATE:` line format by signature (WP-01, same wave).
- ACs: AC-003 (the engines' half), AC-004, AC-005.
- Patterns to mirror: `needsItem`/`needs_item` and the `needs validation` routing (JS `:188`, `pipeline.py:119-125`), `report`/`call` (JS `:182-186`, `pipeline.py:106-116`), `launchWave`/`launch_wave` (JS `:269-287`, `pipeline.py:262-287`), `changedBy` parsing (JS `:169-173`, `pipeline.py:128-131`), the 2.0.0 conformance scenarios (last two of `conformance.json`) and their assertions (`test_pipeline.py:160-166`, `test_workflow.mjs:525-529`), fake knobs `testutil.py:78-95`.
- Gotchas: `concern_pending` must be added wherever `run["pending"]` is rebuilt (two places per engine) or the concerns vanish; `required` order identical in the spec and the JS (`deepEqual`); the engines record the *second* report of a re-dispatched WP; `fixCount`/`fix_count` must not count a `(context)` call; the reviewer prompt is built once per review from `concern_pending`; `summarize` in both runners must add `gate_denials` or the conformance comparison fails; the fake must emit `concerns: []` and `missing_context: null` in every implementer report or `structured_report` refuses it; `world`/`fromDecl` must accept a list override per WP (first call, then last element).
- Exact imports and APIs: `render` (`pipeline.py:31`), `compact` (`pipeline.py:26`), `self.seq`/`seq`, `self.step`/`step`.
- WP validation: `node .claude/bin/test_workflow.mjs`; `python3 -m unittest discover -s .claude/bin -p test_pipeline.py`; `python3 -m compileall -q .claude/bin`.

#### WP-03 · The prompts
- Wave 1.
- Files: `.claude/agents/implementer.md`, `.claude/commands/implement.md`, `.claude/bin/test_definitions.py`.
- Implements the texts of AC-006. Consumes the schema of section 5 by signature.
- ACs: AC-006.
- Patterns to mirror: the "# Report" section of `implementer.md` (last paragraph); the "Ambiguity" and "Active guardrails" sections (`NEEDS_CONTEXT` replaces "stop and return BLOCKER" for a missing decision; `BLOCKED` for contradictions, mismatched contracts and guardrails); `implement.md:60-64` (one bullet per pending type); the 2.0.0 tests at the end of `test_definitions.py`.
- Gotchas: `test_definitions.py` already pins phrases of `implementer.md` ("not_checked", the reuse ladder): keep them; `BLOCKER` must disappear from `implementer.md` but stays in `test-author.md` and `doc-updater.md`; the report paragraph must list `concerns` and `missing_context` with when each is non-empty.
- WP validation: `python3 -m unittest discover -s .claude/bin -p test_definitions.py`.

#### WP-04 · Version, notes, roadmap
- Wave 1.
- Files: `.claude-plugin/plugin.json`, `.claude/bin/upgrade.py`, `.claude/bin/test_upgrade.py`, `.claude/bin/test_acceptance_upgrade.py`, `.claude/bin/test_acceptance_v2.py`, `docs/roadmap/repo-review-2026-11.md`.
- ACs: AC-007.
- Patterns to mirror: `NOTES["2.0.0"]` `upgrade.py:50-62` (tone: what changed, what the project must do); `test_acceptance_upgrade.py:258` and `test_acceptance_v2.py:177` (the version pins: both become `2.1.0`).
- Notes to write (at least): the gate and its two denials; the four statuses and that a customised `implementer.md` from 2.0 must be merged (`BLOCKER` is no longer in the schema); `settings.json` matcher and timeout upgraded by `install` (a hand-edited agentic entry must be checked); `gate_denials` and `concern` items in `workflow-result.json`. Roadmap: item 2.1 corrected (`PreToolUse` on `StructuredOutput`, measured; not `SubagentStop`), "Versioning" names 2.1.0, "Recommended order" step 3 marked shipped.
- WP validation: `python3 -m unittest discover -s .claude/bin -p "test_*upgrade.py"`; `python3 -m unittest discover -s .claude/bin -p test_acceptance_v2.py`.

```json wp-manifest
{
  "stack": ["python", "typescript"],
  "allow_bash": ["Bash(python3 -m unittest:*)", "Bash(python3 -m compileall:*)", "Bash(node .claude/bin/test_workflow.mjs)"],
  "acceptance": {"files": [".claude/bin/test_acceptance_v21.py"], "command": "python3 -m unittest discover -s .claude/bin -p test_acceptance_v21.py"},
  "verify": {"build": "python3 -m compileall -q .claude/bin", "lint": "node .claude/bin/test_workflow.mjs", "tests": "python3 -m unittest discover -s .claude/bin -p test_*.py"},
  "docs": {"files": ["README.md", "docs/how-it-works.md", "docs/how-to/"], "codemap": null},
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": [".claude/bin/agentic.py", ".claude/settings.json", ".claude/bin/test_agentic.py", ".claude/bin/test_acceptance_portable.py"],
     "acs": ["AC-001", "AC-002", "AC-003", "AC-008"], "mirror": [".claude/bin/agentic.py:1929-1983", ".claude/bin/agentic.py:1557-1574", ".claude/bin/agentic.py:1459-1508", ".claude/bin/agentic.py:1051-1085"]},
    {"id": "WP-02", "wave": 1, "depends_on": [], "files": [".claude/workflows/pipeline-spec.json", ".claude/workflows/agentic-implement.js", ".claude/bin/pipeline.py", ".claude/bin/conformance.json", ".claude/bin/test_pipeline.py", ".claude/bin/test_workflow.mjs", ".claude/bin/testutil.py"],
     "acs": ["AC-003", "AC-004", "AC-005"], "mirror": [".claude/bin/pipeline.py:106-131", ".claude/bin/pipeline.py:262-287", ".claude/workflows/agentic-implement.js:169-193", ".claude/workflows/agentic-implement.js:269-287"]},
    {"id": "WP-03", "wave": 1, "depends_on": [], "files": [".claude/agents/implementer.md", ".claude/commands/implement.md", ".claude/bin/test_definitions.py"],
     "acs": ["AC-006"], "mirror": [".claude/agents/implementer.md", ".claude/commands/implement.md:60-64"]},
    {"id": "WP-04", "wave": 1, "depends_on": [], "files": [".claude-plugin/plugin.json", ".claude/bin/upgrade.py", ".claude/bin/test_upgrade.py", ".claude/bin/test_acceptance_upgrade.py", ".claude/bin/test_acceptance_v2.py", "docs/roadmap/repo-review-2026-11.md"],
     "acs": ["AC-007"], "mirror": [".claude/bin/upgrade.py:50-62"]}
  ]
}
```

## 9. Test strategy
- Unit: WP-01 in `test_agentic.py` (gate: each let-through condition, a report from a reviewer that never claimed is let through, the denial message, the counter, the reset, the `GATE:` line, `status_to_state`, the matcher upgrade and its idempotence); WP-02 through the five new conformance scenarios in both runners plus the fake knobs; WP-03 in `test_definitions.py`; WP-04 in `test_upgrade.py`.
- Acceptance: `.claude/bin/test_acceptance_v21.py`, AC-001…AC-008, written first and red (the gate, the statuses, the version do not exist yet). AC-005's end-to-end part uses the simulated `claude`, so nothing is spent. No acceptance test re-runs the whole suites.
- QA: exploratory over the gate (a non-string status; a WP with no `acs` and unmentioned files; a corrupt `gate.json`; a `StructuredOutput` call from QA or the test-author, never gated; a report whose `wp` differs from the owner: the owner wins) and over the engines (`concerns` with non-strings; `NEEDS_CONTEXT` from a custom agent; a `GATE:` line with an unknown WP; a `GATE:` line in a fix wave summed with the implement wave's).
- After merging, by hand: release 2.1.0, then `python3 bench/bench.py run --sessions 3` on the four fixtures, compared with the 2.0.0 rows of `bench/RESULTS.md`; the metrics are fix cycles, gate denials (new, from the kept session results), cost and minutes.

## 10. Decisions
- **D1 · The gate is a `PreToolUse` hook on `StructuredOutput`, not `Stop`/`SubagentStop` (measured):** with `--json-schema` the structured answer is delivered before `Stop` fires and a block does not change it; a denied `StructuredOutput` makes the agent correct and re-submit in the same context. Roadmap item 2.1 said `SubagentStop`; the roadmap is corrected. Discarded: a check inside the engines after the report (would need a new dispatch, losing the agent's context, which is the whole point).
- **D2 · Acceptance attributed to the WP, nothing else (user's choice):** only the acceptance tests have a deterministic owner (`acs` and paths); a `verify.*` failure would blame the wrong package in a parallel wave.
- **D3 · Two denials per WP and stage (user's choice):** a third attempt in the same context rarely helps and the fix cycles already exist; the count resets when the stage opens so a fix wave gets its own two.
- **D4 · Deterministic status mapping (user's choice):** `DONE_WITH_CONCERNS` is `done` plus pending items without severity, handed to the reviewer who can promote them to findings; `NEEDS_CONTEXT` buys one re-dispatch with the whole document, only in implement waves (in a fix wave the agent already has the code and the defects; a second miss is a plan problem, so `blocker`); `BLOCKED` is the old `BLOCKER`. Discarded: letting the launcher model decide (not reproducible, not measurable).
- **D5 · `BLOCKER` is removed from the implementer enum**, kept for the test-author and doc-updater, and kept in `status_to_state` so their fallback runs still map. A hard rename rather than an alias: an alias would let a 2.0 customised `implementer.md` keep working while its prompt lies about the statuses.
- **D6 · `gate_denials` reach the run through `close-stage` output**, not by the engines reading `gate.json`: the engines have no disk (the native workflow runs inside the Workflow tool) and every state fact already travels in gatekeeper output.
- **D7 · Version 2.1.0, not 3.0:** the implementer schema and the settings change, so projects upgrade with `install` and read the notes, but no plan, manifest or command changes; the roadmap's "Versioning" section already said 2.x for sections 2-7.
- **D8 · The hook `timeout` is set in `settings.json` and upgraded by `install`:** without it the CLI kills the hook at 60 s and a killed hook is read as allowed by the CLI. 900 s matches `run_command`'s cap.
- **D9 · The gate fails open on its own errors and only on the WP's own failure:** a hook that refused every report because the manifest did not parse would stall a run with no cap; a shared AC would make the first finisher pay for the other's unfinished work. The write rules keep failing closed.
- **D10 · The gate runs the whole acceptance command, not only the WP's tests:** the manifest has one command and no per-WP selection; attribution filters the result. Discarded: deriving a `-k AC-001` filter (framework-specific; the flow is language-agnostic).

## 11. Risks and open questions
- **This plan cannot be run by `/implement` in this repo:** `validate` refuses any WP that owns a path under `.claude/` (`agentic.py:403`) and the hook blocks agents' writes there; both are security rules, not to be relaxed. The WPs are executed by hand in this session, with the acceptance tests written and red first, the WP validation commands and the verify phases run as the manifest states, and one commit per WP. The manifest stays truthful rather than valid.
- **The native workflow is untested here:** the `StructuredOutput` denial was measured with `claude -p --agent` (the fallback engine's shape). Whether the Workflow tool's subagents fire `PreToolUse` on `StructuredOutput` with an `agent_id` that `claims.json` knows is assumed, not measured; the bench runs `run-pipeline`, so the measurement covers the fallback only. If the native workflow does not fire it, the gate is simply absent there (no hook call, no denial) and the statuses still work.
- **Cost:** each gated report runs the acceptance suite once more (the implementer should have run it already); on the fixtures that is seconds. A denial costs one more agent turn, cheaper than a fix cycle. The bench decides; a null or negative result is still a result.
- **Hook timeout:** a project whose `settings.json` was hand-edited may keep the 60 s default; the upgrade note says so and `install` fixes the standard entry. The gate's 840 s also count against the fallback engine's per-agent `timeout_s` (`agentic.json`); on the fixtures the acceptance suites take seconds, but a project with a slow suite should raise `timeout_s` or expect a `TIMEOUT` status; the note says so.
- **False denials in a parallel wave:** a half-written file of WP-02 can break an import in WP-01's acceptance test; the output names `AC-001` and WP-01 is refused for a failure that is not its own. The cap of two bounds the damage and the report then goes through. A deterministic rule ("an import or collection error never counts") was considered and left out: the markers differ per framework and language. If the bench shows denials without a later fix, revisit.
- **Customised implementers:** a project with an edited `implementer.md` from 2.0 keeps a prompt that says `BLOCKER` while the schema refuses it; the CLI forces one of the four values. The note tells them to merge.
- **Rollback:** revert the PR; projects on 2.1.0 are refused by the downgrade guard, so a bad 2.1.0 needs a 2.1.1.
