# Architecture: the reviewer reads beyond the diff (agentic-flow 2.2)
Type: feature · Size: standard

## 1. Goal
Roadmap item 3.1 (`docs/roadmap/repo-review-2026-11.md:49`). The reviewer reads the integrated diff and, by its own rule, reports no problems in code that was not touched; a change that breaks an untouched caller therefore slips through. A new deterministic step, `agentic.py callers`, lists the callers of every public symbol defined in a changed file: for each symbol, the lines of tracked code files outside the diff that use it as a whole word, tests included. The list joins the gatekeeper call that already runs `verify + open-stage review`, both engines render it into the reviewer's prompt, and `reviewer.md` says that a change which breaks one of those callers is a finding on the package that owns the change. The reviewer prompt and the engines change, so projects upgrade: version 2.2.0 with notes.

## 2. Scope
### Included
- `agentic.py callers`: changed files (`git diff --name-only HEAD` plus untracked files), their public symbols (the codemap's `SYMBOL_RES`), the word-boundary matches in code files outside the diff, caps and a `truncated` flag, one JSON line; in `SEQ_COMMANDS`.
- Both engines: `WAVE_TAIL` gains `callers`; its JSON is rendered into the reviewer prompt; a missing or failed step renders nothing. Conformance scenario and the Node assertions that pin the gate sequence.
- `reviewer.md`: the callers list in the process and in the false-positive rule; definition tests.
- `plugin.json` 2.2.0, `NOTES["2.2.0"]`, the version pins, roadmap item 3.1 marked shipped; acceptance tests in `.claude/bin/test_acceptance_v22.py`.
### Excluded (non-goals)
- `graphify` or any dependency: plain grep (decision D2).
- Callers of symbols that are not public by the codemap's regexes (methods, private helpers, variables): the list is about signatures a plan exposes.
- Changing what the reviewer reads beyond the list (it still reads `git diff`, `architecture.md` and the files), the verifier, QA, or the test-auditor.
- Snapshot-based change detection (decision D1).

## 3. Stack
Python 3.9+ standard library (`agentic.py`, `pipeline.py`, tests with `unittest`, no type annotations in `agentic.py`); Node 22 for the native workflow and its scenario runner. No new dependency.
- Build: `python3 -m compileall -q .claude/bin`
- Lint (the conformance scenarios, both engines must agree): `node .claude/bin/test_workflow.mjs`
- Tests: `python3 -m unittest discover -s .claude/bin -p "test_*.py"` (about 90 s)
- Acceptance: `python3 -m unittest discover -s .claude/bin -p test_acceptance_v22.py`

## 4. Repository structure
```
.claude/bin/agentic.py                      WP-01  callers command, constants, SEQ_COMMANDS
.claude/bin/test_agentic.py                 WP-01
.claude/workflows/pipeline-spec.json        WP-02  reviewer prompt gains {callers}
.claude/workflows/agentic-implement.js      WP-02  WAVE_TAIL, post[2], the prompt text
.claude/bin/pipeline.py                     WP-02  the same, in Python
.claude/bin/conformance.json                WP-02  one new scenario
.claude/bin/test_pipeline.py                WP-02  world answers `callers`; scenario assertion
.claude/bin/test_workflow.mjs               WP-02  simulate answers `callers`; the gate-sequence assertions
.claude/agents/reviewer.md                  WP-03
.claude/bin/test_definitions.py             WP-03
.claude-plugin/plugin.json                  WP-04  2.2.0
.claude/bin/upgrade.py                      WP-04  NOTES["2.2.0"]
.claude/bin/test_upgrade.py                 WP-04
.claude/bin/test_acceptance_upgrade.py      WP-04  pin at :258
.claude/bin/test_acceptance_v2.py           WP-04  pin at :177
.claude/bin/test_acceptance_v21.py          WP-04  pin at :283
docs/roadmap/repo-review-2026-11.md         WP-04  3.1 shipped
.claude/bin/test_acceptance_v22.py          AT
README.md, docs/how-it-works.md, docs/how-to/   docs (doc-updater)
```

## 4b. Existing code context
| What an implementer needs to know | Where it is | Pattern or rule |
|---|---|---|
| The public-symbol regexes per language and their lookup | `.claude/bin/agentic.py:113-123` (`SYMBOL_RES`), `:952-953` (`symbol_re(name)`: the regex for a file name or `None` for a non-code file) | `callers` reuses both: a changed file with no regex yields no symbols; a tracked file with no regex is never searched |
| How the codemap extracts symbols from a file | `:956-970` (`codemap`: `symbols = [m.group(1) for line in text.splitlines() if (m := rx.match(line))]`, `read_text(encoding="utf-8", errors="replace")`) | Copy that line for the changed files |
| The repo's files | `:877-890` (`source_files()`: `git ls-files -co --exclude-standard`, with a non-git fallback), `:548-551` (`tracked_files()`: the same without `.claude/state/`) | Search candidates: `source_files()` minus the changed set minus `.claude/state/`, filtered by `symbol_re` |
| How the script calls git and tolerates no repo | `:572-590` (`git_tree`: `subprocess.run(["git", ...], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)`, catching `(subprocess.CalledProcessError, FileNotFoundError, OSError)` and returning `None`) | The same call shape for `git diff --name-only HEAD` and `git ls-files --others --exclude-standard`; no repo or no `HEAD` (an empty repo) gives an empty list, never a failure |
| The commands the gatekeeper may batch and how a batch runs | `:1278-1279` (`SEQ_COMMANDS`), `:1294-1308` (`run_steps`: each step its own process, stops at the first that fails), `:1310-1327` (`seq`), `:1282-1292` (`cap_output`: the last JSON line survives truncation) | Add `"callers"`; its output is one JSON line, so it survives `cap_output` |
| Command dispatch | `:2098-2112` (`main()`: `elif cmd == "codemap":` at `:2180` is the model) | `elif cmd == "callers": callers()` |
| Where the review tail is launched and consumed, JS | `.claude/workflows/agentic-implement.js:167` (`WAVE_TAIL = ['verify', 'open-stage review']`), `:342` and `:365` (`seq(WAVE_TAIL, 'verify')`), `:460` (`post[0]` verify), `:476-480` (the review prompt with `concerns`), `:490` (`opened: ok(post[1])`), `:144-147` (`lastJson`) | `callers` is `post[2]`; `lastJson(post[2].output)` or `null` |
| The same in Python | `.claude/bin/pipeline.py:51` (`WAVE_TAIL`), `:346` and `:372`, `:395` (`post[0]`), `:413-415` (the review prompt, `render(self.prompts["reviewer"], concerns=..., rules=...)`), `:431` (`opened`), `:17-23` (`lines_json`), `:26-28` (`compact`) | `post[2]` likewise |
| The reviewer prompt in the spec | `.claude/workflows/pipeline-spec.json` `prompts.reviewer` = `Review the integrated code according to architecture.md.{concerns}{rules}`; the JS builds the same text inline (`:480`) | Becomes `...architecture.md.{callers}{concerns}{rules}`; the JS mirrors |
| Conformance simulators and their answers to unknown commands | `.claude/bin/test_workflow.mjs:24-36` (`respond`: known commands answer JSON, the rest `RESULTADO: OK`), `:449-470` (`fromDecl`, `gate_fail`), `:300-309` (the exact gate sequence of the happy path), `:320` (`'seq verify + open-stage review'`), `:349`; `.claude/bin/test_pipeline.py:39-60` (`respond` in `world`), `:115-123` (`summarize`), `:150` (compared keys) | Both simulators answer `callers` with the empty JSON of section 5; the two Node assertions gain `callers`; a scenario forces a caller through `gate_fail` with `exit_code` 0 |
| `reviewer.md` today | `.claude/agents/reviewer.md`: "# Process" step 2 (`git diff`, `git status`, each WP's files); "Common false positives" ends with "nor problems in code that was not touched, unless they are critical security issues" | Step 2 adds the callers list; the exception gains "or a caller your prompt lists that the change breaks" |
| Definition tests of the reviewer | `.claude/bin/test_definitions.py:128-146` (phrases pinned per agent) | One test for the new phrases |
| Version pins | `.claude-plugin/plugin.json:4`; `test_acceptance_upgrade.py:258`; `test_acceptance_v2.py:177`; `test_acceptance_v21.py:283` (`"2.1.0"`), `:284` (`NOTES["2.1.0"]` by key, unaffected) | All four become `2.2.0`; `NOTES["2.2.0"]` goes before `"2.1.0"` in `upgrade.py:50` |
| Docs the doc-updater touches | `docs/how-it-works.md:128` (`verify + open-stage review` in the sequence diagram), `:248` (the reviewer row of the permission matrix), `:327+` (glossary), `README.md:76` (the guardrails table), `docs/roadmap/repo-review-2026-11.md:49` (WP-04 marks it) | |

**What must NOT change:** the hook, `close-stage`, the other agents' prompts and schemas, the gatekeeper call count (the new step joins an existing call), `SCHEMA` of the results and the bench.

## 5. Data model
The JSON line `agentic.py callers` prints (exit 0 always):
```json
{"changed": ["src/money.py", "src/new.py"],
 "symbols": {"src/money.py": ["parse_amount", "split"], "src/new.py": ["Thing"]},
 "callers": [{"symbol": "split", "defined_in": "src/money.py", "file": "src/ledger.py", "line": 41, "text": "shares = split(cents, len(names))"}],
 "truncated": false}
```
- `changed`: code files (those with a `symbol_re`) modified since `HEAD` or untracked, sorted, filtered exactly like `source_files()` (`SKIP_DIRS`, `agentic.py:110` and `:886`: `.claude`, `vendor`, `build`, `node_modules`…), so the flow's own files under `.claude/` are never "changed" and never searched. A deleted file stays out (nothing to extract). Without a repo or without `HEAD`: the untracked files only, or `[]`.
- `symbols`: per changed file, the codemap regex matches in file order; files with none are omitted.
- `callers`: symbol-major: for each symbol in `symbols` order (files sorted, symbols in file order), the matching lines in file order then line order; `text` is the stripped line cut to `CALLER_TEXT_MAX` characters. A line in a changed file is never a caller (the diff is what the reviewer already reads). At most `CALLERS_PER_SYMBOL` items per symbol and `CALLERS_MAX` in total; past either cap the later items (later symbols first to go) are dropped and `truncated` is `true`.
- On any `OSError` while reading a file, that file is skipped; the command still exits 0 (the step must not stop the review).

## 6. Contracts between modules
`.claude/bin/agentic.py` (WP-01):
```python
CALLERS_PER_SYMBOL = 10
CALLERS_MAX = 80
CALLER_TEXT_MAX = 160
CALLER_RE_TEMPLATE = r"(?<![\w$])%s(?![\w$])"   # the symbol as a whole word; $ for JS identifiers

def changed_code_files():      # sorted list of section 5's "changed" (git diff --name-only -z HEAD + git ls-files --others --exclude-standard -z, SKIP_DIRS filtered)
def file_symbols(rel):         # the codemap's public symbols of one file, in order; [] for a non-code file
def find_callers(changed, symbols):   # section 5's "callers" and "truncated", as (list, bool), over source_files() minus changed; one alternation regex per file, tried only on files whose text contains some symbol as plain text
def callers():                 # prints the JSON line of section 5 and exits 0
```
`SEQ_COMMANDS` gains `"callers"`.

Engines (WP-02): `WAVE_TAIL = ['verify', 'open-stage review', 'callers']` in both. After the review stage is opened, `const found = post[2] ? lastJson(post[2].output) : null` (JS; `post` is the `steps` list of the tail call, as at `:460` and `:490`) / `found = lines_json(post[2]["output"]) if len(post) > 2 and post[2] else None` (Python); anything that is not a dict whose `callers` is a non-empty list counts as none (`not json`, a missing step, `{}`). In Python, `render(self.prompts["reviewer"], concerns=..., rules=..., callers=...)` passes `callers` **last**, so a caller line that contains a literal `{rules}` or `{concerns}` is not expanded (the JS concatenates and never expands). The reviewer prompt becomes `Review the integrated code according to architecture.md.{callers}{concerns}{rules}` where `{callers}` is `""` when there are no callers, else:
```
\nCallers, outside the diff, of the public symbols this change defines or modifies (the reviewer must read them), as JSON:\n<compact JSON of the "callers" list>\nA change that breaks one of them is a finding on the package that owns the changed symbol, even though the caller's file was not touched.<" The list is truncated." when truncated is true>
```
The JS builds the same text with `JSON.stringify`; the Python uses `compact`. `run["review"]` gains `"callers": <count or 0>` (both engines) so the run record says how many callers the reviewer was given.

`.claude/agents/reviewer.md` (WP-03): process step 2 becomes "Review the integrated diff (`git diff`, `git status`), each WP's files, and **the callers your prompt lists**: the lines outside the diff that use a changed public symbol. Read each one and check that the change keeps it working." The false-positive exception becomes "nor problems in code that was not touched, unless they are critical security issues or **a caller your prompt lists that the change breaks**: that one is a finding on the package that owns the change."

## 7. Conventions
- The flow's existing style: English, short flat functions, UPPER_CASE constants next to their siblings (`SEQ_OUTPUT_CAP` `:1277`), **no type annotations in `agentic.py`** (an explicit override of the python rules: the file has none and must import on 3.9), git through `subprocess.run` with the shape of `git_tree`, failures of an instrument never stop the run.
- Both engines mirror each other; the conformance suite is the proof.
- Prompt text pinned by tests: the new reviewer phrases are asserted in `test_definitions.py` and in the acceptance tests; a later rewording updates them.
- Tests: `unittest`, one behaviour per test, temp git repos through `test_agentic.Repo` (which runs `git init`), commits with `-c user.name=t -c user.email=t@t` as `test_agentic.py:1274-1290` does.
- Forbidden: a dependency for the search, searching `.claude/state/`, a caller step that can exit non-zero, changing the gatekeeper call count.

## 8. Work packages and acceptance criteria
### Acceptance criteria
- AC-001 · The callers of a changed symbol are listed, from tracked code outside the diff
  - Scenario: a `Repo` with `src/money.py` (`def split(cents, parts):` and `def parse_amount(text):`), `src/ledger.py` (line 3 `shares = split(100, 3)`, line 4 `total = parse_amount("1")`), `tests/test_ledger.py` (line 2 `from src.money import split`, line 5 `assert split(1, 1) == [1]`), `notes.md` mentioning `split`, everything committed with `git add -A` (the `.claude/` copies the `Repo` helper makes included); then `src/money.py` modified (a new line inside `split`).
  - Action: `agentic.py callers`.
  - Expected: exit 0; the JSON's `changed == ["src/money.py"]`; `symbols == {"src/money.py": ["split", "parse_amount"]}`; `callers` holds, in this order, `src/ledger.py:3` and `tests/test_ledger.py:2` and `:5` for `split`, then `src/ledger.py:4` for `parse_amount`; each item has `symbol`, `defined_in`, `file`, `line`, `text`; `truncated` is `false`.
  - Must not: list `notes.md` (no `symbol_re`); list any line of `src/money.py` itself; match `splitter` or `my_split` (whole word only).
  - Check: `test_acceptance_v22.py::CallersTests::test_ac_001_callers_outside_the_diff`
  - WP: WP-01
- AC-002 · New files count as changed, caps truncate, and no repo is no failure
  - Scenario: the same repo with an untracked `src/new.py` defining `class Thing:` used once in `src/ledger.py`; a second repo where a committed `src/a.py` defines `def f():` and `def g():`, a tracked `src/b.py` calls `f()` on 12 lines, and a tracked `src/c.py` calls `g()` on 75 lines, then `src/a.py` is modified; a third directory with files but no git repo.
  - Action: `agentic.py callers` in each.
  - Expected: first: `src/new.py` in `changed`, `Thing` in `symbols`, its caller listed; second: exactly 10 callers for `f`, 70 for `g` (the total cap of 80), `truncated == true`; third: exit 0 with `changed == []`, `callers == []`.
  - Must not: exit non-zero in any of the three; list `.claude/state/` files.
  - Check: `test_acceptance_v22.py::CallersTests::test_ac_002_new_files_caps_and_no_repo`
  - WP: WP-01
- AC-003 · The step joins the review call and reaches the reviewer in both engines
  - Scenario: two conformance scenarios: `callers reach the reviewer`, whose `gate_fail` answers `callers` with `exit_code` 0 and the JSON of section 5 holding one caller `{"symbol": "split", "defined_in": "src/a.py", "file": "src/b/x.py", "line": 7, "text": "split(1, 2)"}`; and `callers that are not JSON are ignored`, whose `gate_fail` answers `callers` with `exit_code` 0 and output `not json`.
  - Action: both conformance runners, through their summaries (`run_scenario` and the `--dump`).
  - Expected: in both engines: the first scenario's `gates` has `callers` right after `open-stage review` and its reviewer prompt (`prompts["reviewer:reviewer#1"]`) contains `src/b/x.py`, `"line":7` and `the package that owns the changed symbol`; the second scenario's reviewer prompt equals the happy path's (`a happy path...` scenario), which contains none of those; the happy path's `gate_calls` is still 10 and its `gates` list `verify`, `open-stage review`, `callers` consecutively.
  - Must not: a second gatekeeper call for `callers`; a reviewer prompt that mentions callers when the step returned none or garbage.
  - Check: `test_acceptance_v22.py::EngineTests::test_ac_003_callers_in_the_review_call_and_prompt`
  - WP: WP-02
- AC-004 · The reviewer's instructions say it
  - Scenario: the merged `reviewer.md`.
  - Action: read it.
  - Expected: it contains `the callers your prompt lists`, `Read each one and check that the change keeps it working`, and `a caller your prompt lists that the change breaks`; the old sentence `nor problems in code that was not touched, unless they are critical security issues.` (with the full stop right after `issues`) is gone.
  - Must not: remove `No concrete case, no finding` or the `# Needs validation` section (pinned by `test_definitions.py:128-146`).
  - Check: `test_acceptance_v22.py::PromptTests::test_ac_004_reviewer_reads_callers`
  - WP: WP-03
- AC-005 · Version and notes
  - Scenario: the merged repo.
  - Action: read `plugin.json`, `upgrade.NOTES`, the roadmap.
  - Expected: version `2.2.0`; `NOTES["2.2.0"]` has at least two strings mentioning `callers` and `reviewer`; `NOTES["2.1.0"]` has 4 strings and `NOTES["2.0.0"]` 7; roadmap item 3.1 contains `Shipped in 2.2.0`.
  - Must not: change the older notes.
  - Check: `test_acceptance_v22.py::ReleaseTests::test_ac_005_version_and_notes`
  - WP: WP-04

### Work packages
#### WP-01 · The callers command
- Wave 1.
- Files: `.claude/bin/agentic.py`, `.claude/bin/test_agentic.py`.
- Implements the constants, `changed_code_files`, `file_symbols`, `find_callers`, `callers`, the `SEQ_COMMANDS` entry and the dispatch (section 6). Consumes nothing.
- ACs: AC-001, AC-002.
- Patterns to mirror: `agentic.py:956-970` (symbol extraction), `:572-590` (git calls that tolerate no repo), `:877-890` (`source_files`), `:1278-1279` (`SEQ_COMMANDS`), `:2180` (dispatch); `test_agentic.py:907-930` (`test_codemap_deterministic_with_public_symbols`: a repo with code files and committed state), `:1274-1290` (commits inside a test repo).
- Gotchas: use `-z` on both git commands (`source_files` does), so a non-ASCII path is not quoted; `git diff --name-only -z HEAD` fails in a repo with no commit (`fatal: bad revision 'HEAD'`): catch `CalledProcessError` and treat as no changes, but still list untracked files from `git ls-files --others --exclude-standard`; a deleted file appears in the diff but has no content: skip it. Search files with `read_text(encoding="utf-8", errors="replace")`; a binary or unreadable file is skipped. Build one compiled regex per symbol (`re.escape`). Python 3.9: no `str | None`, no `match`. The output is a single `print(json.dumps(...))` and nothing else on stdout (the engines parse the last JSON line). Exit 0 always, also on an exception caught at the top of `callers()` (print the empty JSON with an `"error"` key and a stderr line).
- Exact imports and APIs: `json`, `re`, `subprocess`, already imported; `source_files()`, `symbol_re()`, `ROOT`.
- WP validation: `python3 -m unittest discover -s .claude/bin -p test_agentic.py`; `python3 -m compileall -q .claude/bin`.

#### WP-02 · The step in both engines and the reviewer prompt
- Wave 1.
- Files: `.claude/workflows/pipeline-spec.json`, `.claude/workflows/agentic-implement.js`, `.claude/bin/pipeline.py`, `.claude/bin/conformance.json`, `.claude/bin/test_pipeline.py`, `.claude/bin/test_workflow.mjs`.
- Implements `WAVE_TAIL`, the `post[2]` parsing, the `{callers}` text, `run["review"]["callers"]` (section 6). Consumes the JSON of section 5 by signature (WP-01, same wave).
- ACs: AC-003.
- Patterns to mirror: the `{concerns}` rendering (JS `:476-480`, Python `:413-415`, `CONCERNS_PROMPT` in `pipeline.py`), `lastJson`/`lines_json`, the simulators' `respond` (`test_workflow.mjs:24-36`, `test_pipeline.py:39-60`), the 2.1.0 conformance scenarios and their named assertions (`test_pipeline.py:160-180`, `test_workflow.mjs:525-540`).
- Gotchas: `post` may be shorter than 3 when the gatekeeper lost the tail or `callers` failed: guard the index as the contract shows (`post` is a plain list of steps, shorter when a step failed or was lost); the second scenario needs the simulator to pass a `gate_fail` with exit 0 and non-JSON output through unchanged; the prompt text must be byte-identical in both (the conformance comparison of `prompts` catches a space); the two Node assertions at `test_workflow.mjs:300-309` and `:320` pin the gate sequence and must be updated to include `callers`; the simulators' default answer for `callers` is the empty JSON of section 5 so every existing scenario still yields the plain reviewer prompt; `run["review"]["callers"]` is the count, not the list (the list is in the prompt and the record stays small).
- WP validation: `node .claude/bin/test_workflow.mjs`; `python3 -m unittest discover -s .claude/bin -p test_pipeline.py`; `python3 -m compileall -q .claude/bin`.

#### WP-03 · The reviewer's instructions
- Wave 1.
- Files: `.claude/agents/reviewer.md`, `.claude/bin/test_definitions.py`.
- Implements the two text changes of section 6. Consumes nothing.
- ACs: AC-004.
- Patterns to mirror: `reviewer.md` "# Process" and "Common false positives"; `test_definitions.py:128-146`.
- Gotchas: keep every phrase the existing tests pin (`No concrete case, no finding`, the severity anchors, `# Needs validation`, `unchanged_code`, `never blocks`); do not change the report section.
- WP validation: `python3 -m unittest discover -s .claude/bin -p test_definitions.py`.

#### WP-04 · Version, notes, pins, roadmap
- Wave 1.
- Files: `.claude-plugin/plugin.json`, `.claude/bin/upgrade.py`, `.claude/bin/test_upgrade.py`, `.claude/bin/test_acceptance_upgrade.py`, `.claude/bin/test_acceptance_v2.py`, `.claude/bin/test_acceptance_v21.py`, `docs/roadmap/repo-review-2026-11.md`.
- ACs: AC-005.
- Patterns to mirror: `upgrade.py:50-67` (`NOTES["2.1.0"]`), `test_upgrade.py` (the `test_the_2_1_notes_name_the_gate_and_the_statuses` test).
- Notes to write: the reviewer receives the callers of every changed public symbol (how they are found, the caps) and must report a caller the change breaks; `install` refreshes `reviewer.md` unless the project edited it, in which case merge; nothing else changes for projects. Roadmap: item 3.1 ends with "Shipped in 2.2.0 (plain grep; no `graphify`)."
- WP validation: `python3 -m unittest discover -s .claude/bin -p "test_*upgrade.py"`; `python3 -m unittest discover -s .claude/bin -p "test_acceptance_v2*.py"`.

```json wp-manifest
{
  "stack": ["python", "typescript"],
  "allow_bash": ["Bash(python3 -m unittest:*)", "Bash(python3 -m compileall:*)", "Bash(node .claude/bin/test_workflow.mjs)"],
  "acceptance": {"files": [".claude/bin/test_acceptance_v22.py"], "command": "python3 -m unittest discover -s .claude/bin -p test_acceptance_v22.py"},
  "verify": {"build": "python3 -m compileall -q .claude/bin", "lint": "node .claude/bin/test_workflow.mjs", "tests": "python3 -m unittest discover -s .claude/bin -p test_*.py"},
  "docs": {"files": ["README.md", "docs/how-it-works.md", "docs/how-to/"], "codemap": null},
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": [".claude/bin/agentic.py", ".claude/bin/test_agentic.py"],
     "acs": ["AC-001", "AC-002"], "mirror": [".claude/bin/agentic.py:956-970", ".claude/bin/agentic.py:572-590", ".claude/bin/agentic.py:877-890", ".claude/bin/test_agentic.py:907-930"]},
    {"id": "WP-02", "wave": 1, "depends_on": [], "files": [".claude/workflows/pipeline-spec.json", ".claude/workflows/agentic-implement.js", ".claude/bin/pipeline.py", ".claude/bin/conformance.json", ".claude/bin/test_pipeline.py", ".claude/bin/test_workflow.mjs"],
     "acs": ["AC-003"], "mirror": [".claude/workflows/agentic-implement.js:476-490", ".claude/bin/pipeline.py:393-431", ".claude/bin/test_workflow.mjs:24-36", ".claude/bin/test_pipeline.py:39-60"]},
    {"id": "WP-03", "wave": 1, "depends_on": [], "files": [".claude/agents/reviewer.md", ".claude/bin/test_definitions.py"],
     "acs": ["AC-004"], "mirror": [".claude/agents/reviewer.md", ".claude/bin/test_definitions.py:128-146"]},
    {"id": "WP-04", "wave": 1, "depends_on": [], "files": [".claude-plugin/plugin.json", ".claude/bin/upgrade.py", ".claude/bin/test_upgrade.py", ".claude/bin/test_acceptance_upgrade.py", ".claude/bin/test_acceptance_v2.py", ".claude/bin/test_acceptance_v21.py", "docs/roadmap/repo-review-2026-11.md"],
     "acs": ["AC-005"], "mirror": [".claude/bin/upgrade.py:50-67"]}
  ]
}
```

## 9. Test strategy
- Unit: WP-01 in `test_agentic.py` (a changed file with no symbols; a symbol used only in the changed file; two changed files sharing a caller; a deleted file; `$` identifiers in a `.js` file; `.claude/state/` never searched; caps per symbol and total; no git; `callers` through `seq verify + open-stage review + callers` yields three steps); WP-02 through the conformance scenario and the Node assertions; WP-03 in `test_definitions.py`; WP-04 in `test_upgrade.py`.
- Acceptance: `.claude/bin/test_acceptance_v22.py`, AC-001…AC-005, written first and red. No real `claude`; the engines run in the simulated world.
- QA: exploratory over `callers` (a symbol named like a keyword or a common word such as `run`, hitting the cap; a file with CRLF; a very long line; a repo whose `HEAD` is a merge; a symbol defined twice in one file) and over the prompt (`truncated` text present only when true).
- After merging, by hand: release 2.2.0, `install` in finanzas-familiares, and a bench run (five fixtures, three sessions) against the 2.1.0 rows of `bench/RESULTS.md`: the signal is review findings and fix cycles; cost may rise with the prompt.

## 10. Decisions
- **D1 · `git diff HEAD` plus untracked files define the change (user's choice):** what the reviewer already reads; no new state. Discarded: a baseline snapshot (state and a failure mode when the baseline is skipped).
- **D2 · Whole-word grep over tracked code outside the diff, tests included, capped (user's choice):** deterministic and dependency-free; tests that call a changed signature are exactly what breaks. Discarded: `graphify` (an optional dependency path for little gain); production code only (misses breakage visible through tests).
- **D3 · Inline in the reviewer prompt, version 2.2.0 (user's choice):** a printed line is followed where an extra read gets skipped (roadmap 4.4); the prompt changes, so projects upgrade with notes. Discarded: a brief file; a 2.1.1 patch (the notes are needed anyway).
- **D4 · The step rides the existing `verify + open-stage review` call:** no new gatekeeper round trip; it runs after the review stage opens so the snapshot is unaffected. It always exits 0: an instrument never stops the review.
- **D5 · Only codemap-public symbols:** the regexes already define "public" for ten languages; methods and private helpers would multiply noise and the caps would hide the signatures that matter.
- **D6 · Caps of 10 per symbol and 80 total, with a `truncated` flag:** a common name (`run`, `main`) must not flood the prompt; the flag tells the reviewer the list is partial.
- **D7 · This plan is executed by hand:** `validate` refuses `.claude/` ownership (`agentic.py:403`); the manifest stays truthful, the acceptance tests go first and red, one commit per WP, as with 0002 and 0003.

## 11. Risks and open questions
- **Noise for common symbol names:** a changed file defining `run` lists ten unrelated lines; the reviewer may spend attention there. The cap bounds it; if the bench shows more cost and no findings, a stop-list of names is the next step.
- **Regex-level "callers":** a whole-word match is not a call: a comment or a string mentioning the symbol is listed. The reviewer is told to read each one; false callers cost reading, not findings.
- **Scan time inside the verify call:** `callers` runs in the same Bash call as `verify`, the whole suite. The scan is symbols × files × lines; the plain-text pre-filter and one alternation regex per file keep it to a pass over the tracked code (not measured; the flow's own repo has about 60 code files). A huge monorepo would pay more; the step has no timeout of its own because `seq` runs each step as a process under the gatekeeper's Bash limit.
- **Nothing to see on the flow's own repo:** `SKIP_DIRS` drops `.claude/`, so a change to the flow itself lists no callers; by design, since those files are not a project's code.
- **Prompt size:** 80 items of about 200 characters add about 16 KB to the reviewer prompt in the worst case (not measured); typical runs on the fixtures change a handful of files with few external callers.
- **Executed by hand, native workflow hooks:** the previous run on this repo showed project hooks not firing for Workflow subagents in this cloud session; this plan does not depend on hooks (it is run by hand), but the open question from 0004 remains.
- **Rollback:** revert the PR; a project on 2.2.0 keeps a reviewer prompt that mentions callers the engines no longer send, harmless; the downgrade guard refuses `install` from an older flow, so a bad 2.2.0 needs a 2.2.1.
