# Architecture: clean-code ratchet (`agentic.py quality`)
Type: feature · Size: standard

## 1. Goal
The code is growing coarser: `agentic.py` grew from 2,145 to 2,652 lines between 1.1.4 and 2.6.1, five functions exceed 60 lines, and no check stops it. This design adds a deterministic, stdlib-only command, `agentic.py quality`, that measures function length, nesting depth, file size and long lines (Python with `ast`, JavaScript/TypeScript with a heuristic scanner) and compares them with a committed baseline. It works as a ratchet: nothing may get worse, a new function or file must respect the limits, and improvements lower the baseline. It runs in agentic-flow's CI, and in projects as an extra phase of `verify`, so the flow sends back a package that makes the code worse. The same pull request carries the already-written `claude/less-brittle-tests` changes.

## 2. Scope
### Included
- `.claude/bin/quality.py`: measurement and ratchet comparison, pure functions.
- `agentic.py quality [--init | --update]`.
- A `quality` phase in `baseline`/`verify` when the repo has a baseline.
- Guardrails so that agents cannot loosen the baseline:
  - never owned, even in maintainer mode;
  - `quality --init/--update` blocked for flow agents.
- `install`:
  - ships `quality.py`;
  - creates the baseline when it is missing, or when it was copied from the template.
- agentic-flow's own baseline, a CI step, docs and version 2.7.0.
- The `claude/less-brittle-tests` changes, already in the working tree:
  - version pins removed from 8 frozen acceptance files, replaced by `test_definitions.PluginTests.test_the_version_has_its_upgrade_note`;
  - exact doc-table row counts replaced by meaning checks.

  They are not a work package; section 4 lists their files as "done".

### Excluded (non-goals)
- Test-hygiene, dead-code and duplication checks (the user chose size and complexity only).
- Refactoring the five long functions (`main`, `install`, `judge`, `validate`, `guard`); the ratchet freezes them.
- Languages other than Python and JS/TS for function and nesting metrics. Other code files get only the file-size and long-line checks.
- Formatting and lint (ruff, eslint): projects keep their own `verify.lint`.

## 3. Stack
- Python ≥ 3.9, standard library only (`ast`, `json`, `re`, `pathlib`, `fnmatch`). No type annotations in `quality.py` or `agentic.py` (Python 3.9, and both are frozen into the maintainer guard).
- Node 22 only for the existing `test_workflow.mjs`; nothing new in JS.
- Commands:
  - compile: `python3 -m compileall -q .claude/bin` (run by hand: the four `verify` slots hold the suites below)
  - tests: `python3 -m unittest discover -s .claude/bin -p "test_*.py"`
  - workflow: `node .claude/bin/test_workflow.mjs`
  - docs: `python3 -m unittest discover -s acceptance`
  - qa: `python3 -m unittest discover -s qa` (the manifest's `verify.build` slot)
  - bench: `python3 -m unittest discover -s bench -p "test_*.py"` and `python3 -m unittest discover -s bench/acceptance`: not in `verify`, because `run_command` has no shell and the four slots are taken. They are part of WP-03's validation and of the final check before the pull request.

## 4. Repository structure
```
.claude/bin/quality.py                      WP-01  (new)
.claude/bin/test_quality.py                 WP-01  (new)
.claude/bin/agentic.py                      WP-02
.claude/bin/test_agentic.py                 WP-02
.claude/bin/test_acceptance_v27.py          AT     (new)
.claude/quality-baseline.json               nobody: created by the maintainer with `agentic.py quality --init` after WP-02 (never owned)
.github/workflows/agentic-flow-ci.yml       WP-03
.claude-plugin/plugin.json                  WP-03
.claude/bin/upgrade.py                      WP-03
README.md                                   WP-03
docs/how-to/README.md                       WP-03
docs/how-it-works.md                        WP-03
(done, already on the branch: test_acceptance_{v2,v21,v22,v23,v24,v241,v25,upgrade}.py, test_definitions.py,
 acceptance/test_docs.py, qa/test_qa_docs.py)
```

## 4b. Existing code context
| What an implementer needs to know | Where it is | Pattern or rule |
|---|---|---|
| Sibling modules are imported from the script's own folder, so a frozen copy imports frozen siblings | `agentic.py:1618-1629` (`sibling`, `brief_module`) | `quality_module()` = `sibling("quality")`, same as `brief_module` |
| A pure sibling module's style: module docstring, compiled regexes as constants, small functions, no I/O beyond what is passed | `brief.py:1-40` | Mirror it in `quality.py` |
| Code files the flow looks at: git's tracked and untracked-not-ignored files, without `SKIP_DIRS` (which contains `.claude`) | `agentic.py:986-995` (`source_files`), `:129` (`SKIP_DIRS`) | Quality scans `source_files()`; in the flow's own repo it also scans `.claude/bin/*.py` and `.claude/workflows/*.js` |
| Code extensions | `agentic.py:132-142` (`SYMBOL_RES`), `:1061-1062` (`symbol_re`) | A file is code when `symbol_re(rel)` is not None |
| The flow's own repo | `agentic.py:1711-1720` (`is_flow_repo`) | Decides whether `.claude/bin` is scanned and whether a baseline is foreign |
| Never-owned paths | `agentic.py:110-111` (`NEVER_OWNED`), `:1728-1738` (`never_owned_problem`) | Add `.claude/quality-baseline.json` |
| Bash rules for flow agents | `agentic.py:192-201` (`FORBIDDEN_BASH`, `(regex, reason)` pairs) | Add a rule for `agentic.py quality --init/--update` |
| Verify phases run in order and are compared with the baseline line by line | `agentic.py:1866-1876` (`run_phases`), `:1858-1863` (`normal_failure`, `failure_lines`), `:1899-1918` (`baseline`), `:1920-1964` (`verify`) | The quality phase is appended in `run_phases`, so baseline and verify treat it like any phase |
| Failure lines are found with `FAILURE_LINE_RE` and attributed by file path | `agentic.py:152` (`FAILURE_LINE_RE`), `:1879-1896` (`attribute`) | Each quality failure line starts with `FAIL` and contains the repo-relative path, with no line numbers (so a moved function reads the same) |
| `baseline` does nothing without `verify` commands | `agentic.py:1902-1905` | Change: it also runs when the quality baseline exists |
| `install` creates `.claude/agentic.json` only when missing | `agentic.py:1397-1406`, `:1417-1418` | Same pattern for the quality baseline, after the files are copied (it measures the target) |
| What install ships | `agentic.py:144` (`INSTALL_GLOBS`) | Add `.claude/bin/quality.py` |
| CLI dispatch, one `elif` per command; usage in the module docstring | `agentic.py:2498-2620` (`main`), `:20-56` (docstring) | Add `quality`; `test_cited_commands_exist` needs it in the docstring |
| Test helpers: a temporary git repo with `architecture.md`, the agents, workflows and settings copied in; commands run the **live** `agentic.py` with `CLAUDE_PROJECT_DIR` set to the temp repo | `test_agentic.py:43-74` (`Repo`) | Use it for CLI, verify and hook tests; `quality.py` is then imported from the live `.claude/bin` |
| Hook Bash tests | `test_agentic.py:1267-1290` (`HookBashTests.BLOCKED/ALLOWED`) | Add the quality commands |
| `pipeline_plan` exposes `"baseline": bool(verify)` | `agentic.py:1703` | Unchanged: the engines always call `baseline` and it decides; do not touch the plan |
| Docs size caps and README table checks | `qa/test_qa_docs.py` (`Sizes.test_line_caps`: README 150 lines, hub 260), `test_readme_table_rows` (every guardrail row has two non-empty cells) | The hub is at its cap: merge, do not add lines |

## 5. Data model
`.claude/quality-baseline.json`, committed, written only by `quality --init/--update` or by a person:
```json
{
  "version": 1,
  "flow_repo": true,
  "limits": {"function_lines": 60, "test_function_lines": 100, "nesting": 4,
             "file_lines": 800, "file_growth": 30, "line_chars": 120},
  "exclude": [],
  "files": {".claude/bin/agentic.py": {"lines": 2652, "long_lines": 50}},
  "functions": {".claude/bin/agentic.py::main": {"lines": 151, "nesting": 2}}
}
```
- `files`: only files with `lines > file_lines` or `long_lines > 0`.
- `functions`: only functions over a limit, by key `path::qualname`.
- `exclude`: path prefixes or `fnmatch` globs that are not measured.
- Limit keys missing from `limits` fall back to `DEFAULT_LIMITS`.
- An `exclude` entry with a glob character (`*?[`) is matched with `fnmatch`. Otherwise it is a path prefix that matches only whole segments: `vendor` excludes `vendor/x.py` and `vendor`, not `vendor2/x.py`.
- An entry always stores **both** of its metrics (a file: `lines` and `long_lines`; a function: `lines` and `nesting`), even when only one is over its limit.

**The ratchet, per metric** (`L` = the limit for that kind of file, `b` = the stored value, absent entry = no `b`):

| Metric | Allowed now |
|---|---|
| function `lines` | `max(L_function, b)` (test files: `L_test_function`) |
| function `nesting` (not for test files) | `max(L_nesting, b)` |
| file `lines` | `b + file_growth` if `b > L_file`, else `L_file` |
| file `long_lines` | `b`, or 0 without an entry |

A value above "allowed now" is a violation. Functions and files that no longer exist are ignored by `check` and dropped by `tighten`.

Python qualnames:
- `Class.method`;
- nested functions as `outer.inner`;
- a repeated qualname in one file gets ` #2`, ` #3`… in source order.

A **test file** is a file whose name matches `test_*.py`, `*_test.py`, `*.test.*` or `*.spec.*`, or whose path has a segment `tests`, `test` or `__tests__`. Test files:
- use `test_function_lines`;
- have no nesting check;
- use the same file and line limits.

## 6. Contracts between modules
```python
# .claude/bin/quality.py — stdlib only, no annotations
DEFAULT_LIMITS = {"function_lines": 60, "test_function_lines": 100, "nesting": 4,
                  "file_lines": 800, "file_growth": 30, "line_chars": 120}
def is_test_file(rel) -> bool
def measure_file(rel, text, limits=None) -> dict
    # limits defaults to DEFAULT_LIMITS (only line_chars is used here).
    # {"lines": int, "long_lines": int,
    #  "functions": {qualname: {"lines": int, "nesting": int}}}. Python via ast (a SyntaxError gives no functions,
    #  never raises); .js/.mjs/.cjs/.ts/.tsx/.jsx via the heuristic scanner; other extensions: no functions.
    # text comes from Path.read_text(encoding="utf-8", errors="replace"), which translates CRLF, so "\r" never
    # counts toward line_chars.
def measure(root, files, limits) -> dict
    # {"files": {rel: {"lines", "long_lines"}}, "functions": {"rel::qualname": {"lines", "nesting", "test": bool}}}
    # Every file, every function (the baseline keeps only offenders; the check needs all of them).
def check(baseline, current) -> dict
    # {"ok": bool, "violations": [str], "details": [str], "improvable": [str]}. Rules: the table in section 5.
    # A violation is one line "FAIL <kind> <path or path::qualname> exceeds its <metric> allowance": no values and no
    # line numbers, so the same problem reads the same in every run (the baseline/verify comparison is textual).
    # details holds the values, one line each, without the words fail/error: "  <key> <metric>: now 160, allowed 151".
    # improvable lists the keys whose stored value is above the current one.
def tighten(baseline, current) -> dict
    # The new baseline: every entry lowered to the current value (never raised), entries now within limits dropped,
    # no entry added. limits, exclude and flow_repo are kept.
def initial(current, limits, flow_repo) -> dict
    # A baseline that records every current offender (so `check(initial(c), c)` is ok).
```
- Nesting: `if/for/while/try/with/match` (and `async for/with`) add one level. Rules:
  - An `elif`, which is an `If` alone in the `orelse` of an `If`, is the same level, so a 30-branch `elif` chain has nesting 1.
  - Nested `def`/`lambda` bodies are measured as their own functions and do not add to the parent's nesting.
  - Their lines do count in the parent's `lines` (= `end_lineno - lineno + 1`).
- The JS/TS scanner:
  - Blanks comments, strings and template literals, so braces inside them never count.
  - Recognises named functions: `function name(`, `async function name(`, `name(…) {` as a class or object method, and `const|let|var name = (…) => {`, `name = async (…) => {`, `name: function (`.
  - `name(…) {` is never a function when `name` is a keyword: `if`, `for`, `while`, `switch`, `catch`, `with`, `function` or `return`.
  - Keys: a class method is `Class.method`; an object-literal method is `objname.method` when the object is `const|let|var objname = {`, and `method` otherwise.
  - `.pyi` files go through `ast`, like `.py`.
  - Anonymous callbacks are part of the enclosing named function.
  - Length runs from the function's line to its closing brace.
  - Nesting counts blocks opened by `if/for/while/switch/try`. `else`, `else if`, `catch` and `finally` stay at the same level.

```python
# .claude/bin/agentic.py
QUALITY_BASELINE = ".claude/quality-baseline.json"     # also appended to NEVER_OWNED
def quality_module()                                    # sibling("quality")
def quality_files() -> list                             # source_files() code files (symbol_re), minus the baseline's
                                                        # exclude; plus .claude/bin/*.py and .claude/workflows/*.js when
                                                        # is_flow_repo(ROOT). Repo-relative, "/" separators, sorted.
def quality_state() -> dict | None                      # the baseline; None when missing or foreign
                                                        # (flow_repo true while not is_flow_repo(ROOT));
                                                        # {"unreadable": True} when it is not a JSON object
def quality_phase() -> dict | None                      # None without a baseline; else {"name": "quality",
                                                        # "command": "agentic.py quality", "exit": 0|3, "passed": bool,
                                                        # "tail": last 8 lines, "_scan": the violation lines}
def quality(args) -> int                                # CLI; see AC-004
```
- `run_phases(manifest)` appends `quality_phase()` when it is not None, after the manifest's phases. It runs in-process, so a frozen guard measures with its frozen `quality.py`.
- `baseline(manifest)` skips only when there are no `verify` commands **and** `quality_state()` is None.
- CLI output of `quality`: each violation line followed by its detail line, then one JSON line `{"ok", "files", "functions", "violations", "improvable"}`. `files` and `functions` are the numbers of files and functions measured, `violations` is a number, and `improvable` is a list of strings. Exit codes:
  - 0: ok;
  - 3: violations;
  - with no baseline: prints `{"ok": true, "skipped": "no quality baseline: run agentic.py quality --init"}` and exits 0.
- `--init`:
  - writes `initial(...)` and exits 0;
  - when a non-foreign baseline already exists, it refuses with exit 1, without writing;
  - a foreign one is replaced.
- `--update`:
  - writes `tighten(...)`;
  - then runs the check and exits with its code;
  - without a baseline it exits 1.
- An unreadable baseline (invalid JSON or not an object):
  - `quality` prints `FAIL quality baseline unreadable: .claude/quality-baseline.json` and exits 3;
  - `--update` exits 1;
  - `--init` replaces it;
  - the verify phase fails with that line.
- Install prints exactly one of these lines:
  - `quality baseline: created`;
  - `quality baseline: kept`;
  - `quality baseline: replaced (copied from the template)`;
  - `quality baseline: would be created` (with `--dry-run`, which writes nothing);
  - `quality baseline: could not be created (<first line of stderr>)`, if the `--init` subprocess fails. This one does not fail the install, mirroring the rules-sync branch at `agentic.py:1420-1427`.

## 7. Conventions
- English. No type annotations in `agentic.py` or `quality.py`. This contradicts `.claude/rules/agentic/python.md`; the plan wins, for Python 3.9 and the frozen guard.
- Messages name the path and the metric, with values only on the detail line:
  - violation: `FAIL function .claude/bin/agentic.py::main exceeds its lines allowance`;
  - detail: `  .claude/bin/agentic.py::main lines: now 160, allowed 151`.
- No magic numbers: limits only in `DEFAULT_LIMITS` and the baseline file.
- The baseline is never edited by an agent. A person loosens it by editing the JSON, which shows in the diff.
- One commit per WP; no model names.

## 8. Work packages and acceptance criteria
### Acceptance criteria
- AC-001 · Python measurement
  - Scenario: the source below is measured with `quality.measure_file("m.py", src)`. Its parts:
    - `def f():` with 3 body lines;
    - `class C:` containing `def g(self):` with an `if` that holds a `for` that holds a `while`;
    - `def chain(x):` with `if … elif … elif … else`;
    - `def outer():` containing `def inner():` with one `if`;
    - one 130-character line.
  - Action: `measure_file`.
  - Expected:
    - `functions["f"]["lines"] == 4`;
    - `functions["C.g"]["nesting"] == 3`;
    - `functions["chain"]["nesting"] == 1`;
    - `functions["outer"]["nesting"] == 0`;
    - `functions["outer.inner"]["nesting"] == 1`;
    - `long_lines == 1`;
    - `lines` equals the source's line count.
  - Must not: an `elif` chain must not count as nesting; a nested def must not add to its parent's nesting; a file with a syntax error must not raise (it returns `functions == {}`).
  - Check: `test_acceptance_v27.MeasureTests`.
  - WP: WP-01
- AC-002 · JavaScript/TypeScript measurement
  - Scenario: the JS source below is measured with `measure_file("w.js", src)`. Its parts:
    - `function a() {` with an `if (x) { … } else if (y) { … } else { … }`;
    - `const b = async (p) => {` containing a `for` that holds a `try` that holds an `if`;
    - a class `C` with a method `m() {`;
    - a template literal and a comment, both containing `{` and `}`;
    - an anonymous callback `items.map(i => { … })` inside `b`.
  - Action: `measure_file`.
  - Expected:
    - `a`, `b` and `C.m` are present (a method is keyed `Class.method`, as in Python);
    - `functions["a"]["nesting"] == 1`;
    - `functions["b"]["nesting"] == 3`;
    - each function's `lines` runs from its line to its closing brace;
    - no function named after the callback.
  - Must not: braces inside strings, template literals or comments must not change any count; `else if` must not add a level.
  - Check: `test_acceptance_v27.MeasureTests`.
  - WP: WP-01
- AC-003 · Ratchet rules
  - Scenario: a baseline with the default limits, one baselined function `p.py::big` (90 lines, nesting 5) and one baselined file `p.py` (900 lines, 2 long lines).
  - Action: `quality.check(baseline, current)` with variations of `current`.
  - Expected:
    - **Fails** with one `FAIL …` line naming the path, when any of these happens:
      - `big` grows to 91 lines or nesting 6;
      - a new function has 61 lines, or nesting 5;
      - a new test function (in `test_x.py`) has 101 lines;
      - `p.py` reaches 931 lines (900 + 30 + 1);
      - `p.py` has 3 long lines;
      - a new file has 801 lines or 1 long line.
    - **Passes** when any of these happens:
      - `big` stays at 90, or shrinks to 50 lines and nesting 3 (then `improvable` names it);
      - `p.py` reaches 930 lines;
      - a new test function has 100 lines and nesting 9.
    - `tighten` lowers `big` to its current values and never raises any value; it drops an entry once it is within the limits and never adds a new one.
    - For files, `tighten` lowers the stored `lines` to `min(old, current)`. The +30 margin therefore stays anchored to the lowest size reached.
  - Must not:
    - a violation line must not contain a line number or any measured value;
    - shrinking a function that still violates must not change its violation line;
    - `tighten` must not raise any value or add an entry.
  - Check: `test_acceptance_v27.RatchetTests`.
  - WP: WP-01
- AC-004 · The `quality` command
  - Scenario: a temporary git repo (the `Repo` helper of `test_agentic.py`; it is not the flow's repo) with `src/a.py`, which holds `def big():` of 80 lines and `def small():` of 5.
  - Action: run `agentic.py quality`, then `quality --init`, then `quality` again, then grow `big` to 90 lines and run `quality`, then shrink it to 70 and run `quality --update`.
  - Expected:
    - The first `quality` exits 0 and its JSON has `"skipped"`.
    - `--init` exits 0 and writes `.claude/quality-baseline.json` with `"flow_repo": false` and `src/a.py::big` at 80 lines. A second `--init` exits 1 and leaves the file byte-identical.
    - After the growth, `quality` exits 3 and prints `FAIL` lines containing `src/a.py`. Its last line is JSON with `"ok": false`.
    - After the shrink, `--update` exits 0 and the baseline records `src/a.py::big` with `lines == 70`.
    - A baseline with `"flow_repo": true` in this non-flow repo is treated as absent: `quality` reports `"skipped"`.
  - Must not:
    - `quality` without flags must not write the baseline;
    - `--update` must not raise a value;
    - `.claude/` files of an installed project must not be measured outside the flow's repo.
  - Check: `test_acceptance_v27.CommandTests`.
  - WP: WP-02
- AC-005 · Quality as a verify phase
  - Scenario: a temporary repo with a manifest whose WP-01 owns `src/a.py`, verify `tests` = a passing command, and a committed quality baseline.
  - Action:
    1. Run `baseline`.
    2. Make a function in `src/a.py` exceed 60 lines.
    3. Run `verify`.
    4. Separately: a repo whose code already violated the baseline before `baseline` ran, then `verify` with nothing changed.
    5. Separately: a manifest with no `verify` key but a quality baseline, then `baseline`.
  - Expected:
    - After step 3, `verify` exits 3. Its JSON has a phase `quality` with status `regression` (or `fails`), `blocking` includes `"quality"`, and `suspects` has `WP-01` with `src/a.py`.
    - In the pre-existing case the quality phase has status `pre-existing failure` and does not block.
    - With no `verify` key, `baseline` runs the quality phase instead of printing `"skipped": true`.
  - Must not: a repo without a quality baseline must not get a quality phase (the phase list is unchanged from today).
  - Check: `test_acceptance_v27.VerifyTests`.
  - WP: WP-02
- AC-006 · Agents cannot loosen the ratchet
  - Scenario: the flow's guardrails.
  - Action:
    - `never_owned_problem(".claude/quality-baseline.json")`;
    - the hook with an agent (`AGENTIC_WP=WP-01`) running `python3 .claude/bin/agentic.py quality --update`, `… quality --init` and `… quality`;
    - the same three from the main session.
  - Expected:
    - `never_owned_problem` returns a message;
    - the agent's `--update` and `--init` exit 2;
    - the agent's plain `quality` exits 0;
    - the main session's three all exit 0.
  - Must not: a maintainer-mode manifest that owns `.claude/quality-baseline.json` must not validate.
  - Check: `test_acceptance_v27.GuardTests`.
  - WP: WP-02
- AC-007 · Install ships it and starts the ratchet
  - Scenario: `agentic.py install <target>` into a clean git repo with one code file `main.py`. Also run it into a repo that already has a non-foreign baseline, and into one whose baseline has `"flow_repo": true`.
  - Action: install.
  - Expected:
    - `.claude/bin/quality.py` exists in the target.
    - A missing baseline is created (`"flow_repo": false`, and `quality` on the target exits 0), and the output says `quality baseline: created`.
    - An existing non-foreign baseline is kept byte-identical.
    - A foreign one is replaced by a fresh one with `"flow_repo": false`.
  - Must not: install must not overwrite a project's own baseline; `--dry-run` must not write one.
  - Check: `test_acceptance_v27.InstallTests`.
  - WP: WP-02
- AC-008 · CI and release
  - Scenario: this repository after all WPs.
  - Action: read the files.
  - Expected:
    - `.github/workflows/agentic-flow-ci.yml` has a step whose `run` contains `python .claude/bin/agentic.py quality`. That is `python`, like the file's other steps: `python3` may be missing on the Windows runner.
    - `upgrade.NOTES["2.7.0"]` exists, has at least one note, and its text mentions `quality-baseline.json` and `verify`.
    - The README's Guardrails table has a row whose text contains `quality`.
    - The hub's script reference contains `quality --init` and stays ≤ 260 lines.
  - Must not:
    - the hub must not exceed 260 lines;
    - no test may assert the plugin's version (the single version check is `test_definitions.PluginTests.test_the_version_has_its_upgrade_note`).
  - Check: `test_acceptance_v27.ReleaseTests`.
  - WP: WP-03

### Work packages
#### WP-01 · `quality.py`: measurement and ratchet
- Wave: 1.
- Files: `.claude/bin/quality.py`, `.claude/bin/test_quality.py`.
- Contracts: implements `quality.py` of section 6; consumes nothing.
- ACs: AC-001, AC-002, AC-003.
- **Patterns to mirror:** `brief.py:1-40` (module docstring, constants, small pure functions); `agentic.py:1061-1062` (how extensions map to languages).
- **Gotchas:**
  - Use `getattr(ast, "Match", ())`, because `ast.Match` does not exist on 3.9.
  - `end_lineno` exists from 3.8.
  - Decode files with `errors="replace"`.
  - The JS scanner must handle `\` escapes and `${…}` inside templates, at least by skipping the whole template. A regex literal containing `{` is a known heuristic limit: document it in the module docstring rather than parsing regexes.
  - Keep every function in `quality.py` within its own limits (≤ 60 lines, nesting ≤ 4): the flow's baseline will measure this file.
  - The violation/detail split exists so that a pre-existing violation whose value changes is not read as a new failure by `verify`'s textual comparison. Keep values out of `FAIL` lines.
- **Exact imports:** `ast`, `fnmatch`, `json`, `re`, `pathlib.Path`.
- **WP validation:** `python3 -m unittest discover -s .claude/bin -p "test_quality.py"`; from `.claude/bin`: `python3 -m unittest test_acceptance_v27.MeasureTests test_acceptance_v27.RatchetTests`.

#### WP-02 · Wire it into `agentic.py`
- Wave: 2, after WP-01. Its acceptance and unit tests run the real `quality.py`, so it consumes WP-01 by implementation.
- Files: `.claude/bin/agentic.py`, `.claude/bin/test_agentic.py`.
- Contracts: implements `agentic.py` of section 6; consumes `quality.py` by signature.
- ACs: AC-004, AC-005, AC-006, AC-007.
- **Patterns to mirror:**
  - `agentic.py:1618-1629` (`sibling`);
  - `agentic.py:1866-1876` (`run_phases`);
  - `agentic.py:1899-1918` (`baseline`);
  - `agentic.py:1397-1418` (install's create-if-missing);
  - `agentic.py:192-201` (`FORBIDDEN_BASH`);
  - `agentic.py:110-111` (`NEVER_OWNED`);
  - `test_agentic.py:43-74` (`Repo`);
  - `test_agentic.py:1267-1290` (hook Bash tests).
- **Gotchas:**
  - `install` must measure the **target**: run `quality --init` through a subprocess of this version's `agentic.py` with `CLAUDE_PROJECT_DIR=<target>`, as `rules-sync` already does at `agentic.py:1420-1425`. Do not reuse this process's `ROOT`.
  - In `--dry-run` nothing is written.
  - The `FORBIDDEN_BASH` regex must match `quality` followed by `--init` or `--update` anywhere in the arguments, and must not match plain `quality`.
  - `quality_phase` must not raise: an unreadable baseline gives a failing phase with one `FAIL quality baseline unreadable` line.
  - Add `quality` to the module docstring and to `INSTALL_GLOBS`.
  - `main()` and `install()` are already over 60 lines and baselined. Keep the added dispatch to one `elif` that calls `quality(args)`, and put the install logic in a helper. Otherwise the flow's own ratchet fails when the baseline is created after this WP.
- **Exact imports:** none new beyond `quality_module()`.
- **WP validation:** `python3 -m unittest discover -s .claude/bin -p "test_agentic.py"`; from `.claude/bin`: `python3 -m unittest test_acceptance_v27.CommandTests test_acceptance_v27.VerifyTests test_acceptance_v27.GuardTests test_acceptance_v27.InstallTests`.

#### WP-03 · CI, release and docs
- Wave: 3 (it needs the command to exist: the docs cite `quality --init`, which `test_cited_commands_exist` checks).
- Files: `.github/workflows/agentic-flow-ci.yml`, `.claude-plugin/plugin.json`, `.claude/bin/upgrade.py`, `README.md`, `docs/how-to/README.md`, `docs/how-it-works.md`.
- Contracts: none.
- ACs: AC-008.
- **Patterns to mirror:** `upgrade.py:58-75` (a release's notes); the CI file's existing `- name:` / `run:` steps.
- **Gotchas:**
  - The hub is at its 260-line cap: merge the new script-reference line into an existing one.
  - `docs/how-it-works.md:312` lists the files of `.claude/bin`: add `quality.py` there.
  - `bench/acceptance/test_acceptance_bench.py:400-411` (`CiTests.test_ac_007_ci`) asserts on the CI file's content: run the bench suites after editing it.
  - `qa/test_qa_docs.py` requires every Guardrails row to have two non-empty cells.
  - The version is `2.7.0`, and `upgrade.NOTES["2.7.0"]` must exist: `test_the_version_has_its_upgrade_note`.
  - The CI step goes after the guardrails tests, on every matrix entry, and uses `python`, like the existing steps.
  - The baseline file is not this WP's: the maintainer creates it (section 9).
- **WP validation:** `python3 -m unittest discover -s .claude/bin -p "test_*.py"`, `python3 -m unittest discover -s acceptance`, `python3 -m unittest discover -s qa`, `python3 -m unittest discover -s bench -p "test_*.py"`, `python3 -m unittest discover -s bench/acceptance`.

```json wp-manifest
{
  "maintainer": true,
  "stack": ["python", "typescript"],
  "allow_bash": ["Bash(python3 -m unittest:*)", "Bash(node .claude/bin/test_workflow.mjs)"],
  "acceptance": {"files": [".claude/bin/test_acceptance_v27.py"], "command": "python3 -m unittest discover -s .claude/bin -p test_acceptance_v27.py"},
  "verify": {"build": "python3 -m unittest discover -s qa", "lint": "node .claude/bin/test_workflow.mjs", "types": "python3 -m unittest discover -s acceptance", "tests": "python3 -m unittest discover -s .claude/bin -p \"test_*.py\""},
  "docs": {"files": ["docs/assets/"], "codemap": null},
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": [".claude/bin/quality.py", ".claude/bin/test_quality.py"],
     "acs": ["AC-001", "AC-002", "AC-003"], "mirror": [".claude/bin/brief.py:1-40", ".claude/bin/agentic.py:1061-1062"]},
    {"id": "WP-02", "wave": 2, "depends_on": ["WP-01"], "files": [".claude/bin/agentic.py", ".claude/bin/test_agentic.py"],
     "acs": ["AC-004", "AC-005", "AC-006", "AC-007"], "mirror": [".claude/bin/agentic.py:1618-1629", ".claude/bin/agentic.py:1866-1876", ".claude/bin/agentic.py:1899-1918", ".claude/bin/agentic.py:1397-1418", ".claude/bin/agentic.py:192-201", ".claude/bin/test_agentic.py:43-74", ".claude/bin/test_agentic.py:1267-1290"]},
    {"id": "WP-03", "wave": 3, "depends_on": ["WP-02"], "files": [".github/workflows/agentic-flow-ci.yml", ".claude-plugin/plugin.json", ".claude/bin/upgrade.py", "README.md", "docs/how-to/README.md", "docs/how-it-works.md"],
     "acs": ["AC-008"], "mirror": [".claude/bin/upgrade.py:58-75"]}
  ]
}
```

## 9. Test strategy
- Unit: WP-01 in `test_quality.py` (pure functions, inline sources); WP-02 in `test_agentic.py` (the `Repo` helper, real subprocesses, no network).
- Acceptance: `.claude/bin/test_acceptance_v27.py`, written before the code, red today (the module and the command do not exist). Test names start with `test_ac_00N_`, so failures are attributed by criterion.
- The flow's own ratchet, a maintainer step outside the WPs: after WP-02 the maintainer runs `python3 .claude/bin/agentic.py quality --init`, reviews the baseline, and checks that it has an entry for `.claude/bin/agentic.py::main` and that `quality` exits 0. It is committed in the same pull request. Until it exists, CI's `quality` reports `skipped` and exits 0. This plan is executed by hand, so no pause between waves is needed.
- Existing suites must stay green: `.claude/bin`, `test_workflow.mjs`, `acceptance`, `qa`, `bench`, `bench/acceptance`.

## 10. Decisions
- **Ratchet with a committed baseline** (user's choice), not hard limits now (that would force refactoring five functions first) and not advisory only (it does not stop anything).
- **Scope:** this repo and projects (user's choice). In projects it is a `verify` phase, so attribution and fix cycles work as for any failing phase. The alternative was a manifest `verify.quality` command, but the four phase slots are fixed and a command could point at an unfrozen script.
- **Oversized files:** they may grow at most 30 lines over their **lowest** recorded size (user's choice). The alternatives were "no growth" and "no file check".
- **Tests count, with their own limits** (user's choice): function length 100, no nesting check, same file and line limits.
- **Limits 60 / 4 / 800 / 120** (user's choice); per-repo in the baseline file.
- **In-process phase**, not a subprocess command: a maintainer run's frozen guard then measures with its frozen `quality.py` (the 0012 design), and the phase cannot be redirected by editing a command string.
- **The baseline is never owned, and its writing commands are blocked for agents.** Loosening is a person editing JSON, visible in review. The stage fingerprint check would also catch an agent writing it.
- **Foreign baselines** (`flow_repo: true` outside the flow's repo) are ignored and replaced by install. Template copies inherit the flow's file, which describes the flow's code, not theirs.
- **The flow's own `.claude/` code** is measured only in the flow's repo. In projects it is installed code, not theirs to keep clean.
- **No line numbers in failure lines**, so moving a function does not read as a new failure in the baseline comparison.
- **Reuse:** `source_files`, `symbol_re`, `sibling`, `attribute`, the baseline/verify comparison and the install pattern. No new dependency (ruff/radon/eslint rejected: projects may not have them, and the flow is stdlib-only).
- **The JS/TS metric is a heuristic** (no stdlib JS parser). Accepted limits are documented in `quality.py`.

## 11. Risks and open questions
- The JS heuristic may misread unusual syntax: regex literals with braces, or JSX with braces in text. The effect is a wrong count on such a function; the ratchet then compares like with like, so a stable misreading does not cause false failures.
- `main()` grows by one `elif` per new CLI command. Once frozen in the baseline, the next command will fail the ratchet unless something shrinks first. This is intended (it pushes the dispatch to a table), but the next feature pays for it.
- First run in a project: `install` creates the baseline from the current code, so nothing fails until someone makes it worse.
- Rollback: delete `.claude/quality-baseline.json`. Without it there is no phase and the command reports `skipped`.
- This run is a maintainer run, so it is judged by the frozen pre-change guard: neither the quality phase nor the new Bash rule protects this run itself. They protect the next ones.
- The manifest's `stack` keeps `typescript` for the rules of `agentic-implement.js`, although no WP writes JS. The `docs` zone (`docs/assets/`) holds no file this plan changes; WP-03 owns the README and docs it edits.
- `quality.py` is not added to `FLOW_MODULES` in the frozen `test_acceptance_portable.py`. `test_quality.py` covers reading with `errors="replace"` instead, so no frozen acceptance file is edited.
- Not measured: run time on large repos. `ast` parsing is fast for this repo (not timed), but a monorepo with thousands of files is untested.
