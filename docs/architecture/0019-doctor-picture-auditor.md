# Architecture: doctor, a picture of the plan, and the test-auditor's wrong expected values (issues 64, 59, 70; agentic-flow 2.12.0)
Type: feature · Size: standard

## 1. Goal
Three small additions in one release. `agentic.py doctor` lists what the flow left stale in a project, each finding as data with a severity that says what happens: `auto` (`--fix` repairs it), `route` (it names the command that repairs it) or `mention` (#64). `agentic.py plan-picture` writes a deterministic HTML page with an inline SVG of the manifest (packages by wave, `depends_on` arrows, files and criteria), and `/architect` generates it at the approval gate (#59). The test-auditor learns to flag an acceptance test whose expected value contradicts the criterion's Expected, the failure seen in the 2.1.0 bench (#70), shown red then green with the real auditor in a saved scenario. Following design 0017's rule, `test_acceptance_v211.py` is retired in the same release.

## 2. Scope
### Included
- `.claude/bin/doctor.py` (new) and `agentic.py doctor [--fix]`.
- `.claude/bin/plan_picture.py` (new) and `agentic.py plan-picture`; `/architect`'s wrap-up generates it.
- `repo_scan.wanted_rules()`, extracted from `rules_sync` so `doctor` can compare without writing.
- `test-auditor.md`: a wrong expected value is a critical finding.
- `bench/scenario.py` (new) and `bench/scenarios/auditor-wrong-expected/` (new): the #70 case, runnable against the real auditor.
- Shipping the two modules (`INSTALL_GLOBS`), version 2.12.0 and its notes, the docs lines, retiring `test_acceptance_v211.py`.

### Excluded (non-goals)
- `doctor` deciding whether a run is alive: a `running` ledger entry is a `route` to `agentic.py stop` (section 10).
- Repairs other than the two `auto` findings.
- An interactive or JavaScript picture, or publishing it anywhere: a file in `.claude/state/`.
- Engine changes for #70 (routing a BLOCKED implementer back to the test-author).

## 3. Stack
- Python 3.9+ standard library (`html`, `json`, `shutil`), `unittest`; Node 22 for `test_workflow.mjs`. No new dependency.
- Acceptance: `python3 -m unittest discover -s .claude/bin -p test_acceptance_v212.py`
- Everything: `python3 -m unittest discover -s .claude/bin -p "test_*.py"`, `python3 -m unittest discover -s bench -p "test_*.py"`, `python3 -m unittest discover -s bench/acceptance`, `node .claude/bin/test_workflow.mjs`, `python3 .claude/bin/agentic.py quality`.

## 4. Repository structure
```
.claude/bin/doctor.py                         WP-01  new: diagnose(), repair()
.claude/bin/repo_scan.py                      WP-01  wanted_rules(), used by rules_sync
.claude/bin/test_doctor.py                    WP-01  new
.claude/bin/plan_picture.py                   WP-02  new: render()
.claude/bin/test_plan_picture.py              WP-02  new
.claude/commands/architect.md                 WP-02  the wrap-up runs plan-picture and gives the path
.claude/bin/agentic.py                        WP-03  doctor and plan-picture commands
.claude/bin/installer.py                      WP-03  the two modules in INSTALL_GLOBS
.claude/bin/test_definitions.py               WP-03  COMMANDS count 36
docs/how-it-works.md                          WP-03  the module tree gains two lines
docs/how-to/README.md                         WP-03  the command list gains two lines
.claude/agents/test-auditor.md                WP-04  wrong expected values are critical
bench/scenario.py                             WP-04  new: runs a saved agent scenario
bench/test_scenario.py                        WP-04  new
bench/scenarios/auditor-wrong-expected/       WP-04  new: brief.md, acceptance/test_schedule.py, scenario.json
.claude/bin/upgrade.py                        WP-05  NOTES["2.12.0"]
.claude-plugin/plugin.json                    WP-05  version 2.12.0
.claude/bin/test_acceptance_v211.py           WP-05  deleted
.claude/bin/test_acceptance_v212.py           AT     acceptance tests of this design
```

## 4b. Existing code context
| What an implementer needs to know | Where it is (`file:lines`) | Pattern or rule |
|---|---|---|
| A sibling module of the flow: module docstring, explicit imports from `core`, pure functions, no type annotations | `.claude/bin/brief.py:1-40` | `doctor.py` and `plan_picture.py` follow it |
| `rules_sync` computes the wanted rule names inline (common + declared or detected languages with a file in the library) and writes | `.claude/bin/repo_scan.py:69-90` | Extract the first part as `wanted_rules()`; `rules_sync` calls it; behaviour unchanged |
| `RULES_LIBRARY`, `RULES_DIR`, `STATE`, `LEDGER_JSON` (Paths), `QUALITY_BASELINE` (a relative string: use `ROOT / QUALITY_BASELINE`), `ROOT`, `is_flow_repo(root)` | `.claude/bin/core.py:25`, `:52-56`, `:376`, `:281-290` | `doctor` reads them |
| `hooks_static_problem()` returns why settings would not run the hook, or None | `.claude/bin/guardrail.py:327-345` | `doctor`'s `hook-missing` finding uses its text |
| `INSTALL_RECORD` (a relative string: `ROOT / INSTALL_RECORD`), `flow_version()`, `RETIRED_PERMISSIONS` | `.claude/bin/installer.py:44`, `:55-60`, `:63` | `doctor`'s install and permission findings |
| `INSTALL_GLOBS` lists every shipped flow script, one per line | `.claude/bin/installer.py:19-43` | Add `.claude/bin/doctor.py` and `.claude/bin/plan_picture.py` |
| `stop(ids)` marks running ledger entries stopped (and kills fallback pids) | `.claude/bin/core.py:461-475` | `doctor` never stops anything; it routes to `agentic.py stop` |
| A command handler that prints JSON and returns 0/3; usage errors `die("Uso: ...")`; the `COMMANDS` table and the docstring list | `.claude/bin/agentic.py:275-284`, `:332-345`, docstring `:3-60` | Mirror for `doctor` and `plan-picture` |
| `require_valid()` returns the valid manifest or exits 1 with the errors | `.claude/bin/manifest_check.py:304-312` | `plan-picture` uses it |
| `test_definitions` pins the command count | `.claude/bin/test_definitions.py:474-477` | 34 → 36 |
| The docs module tree and the command list | `docs/how-it-works.md:311-323`, `docs/how-to/README.md:160-185` | One line per new module and command |
| The test-auditor's checklist and severities | `.claude/agents/test-auditor.md:18-33` | Add a checklist item and name it under critical/high |
| The #70 evidence: in the 2.1.0 bench (`bench/results/2.1.0-20261101-171319-bee023e/roster-2.json`) the test-author's `test_minutes_worked` asserted `minutes('Ann') == 960 + 480` where AC-009 says 960; the audit reported no critical finding; WP-03's implementer returned BLOCKED with the diagnosis | `bench/fixtures/roster/repo/architecture.md:157-163` | The saved scenario reproduces exactly this |
| How a `claude -p` agent run is built: `--agent`, `--model`, `--output-format json`, `--json-schema`, prompt on stdin, `AGENTIC_CLAUDE` overrides the binary | `.claude/bin/launch.py:65-80` | `bench/scenario.py` mirrors it, read-only tools |
| The test-auditor's schema and prompt (`{brief}`, `{coverage}`, `{rules}`) | `.claude/workflows/pipeline-spec.json` (`schemas["test-auditor"]`, `prompts["test_auditor"]`) | The scenario renders the same prompt |
| The fake `claude` for tests: `testutil.install_fake_claude(dir)`, `FAKE_MODE` | `.claude/bin/testutil.py:40-135` | `bench/test_scenario.py` runs the runner with it; no real call in tests |
| `/architect`'s wrap-up | `.claude/commands/architect.md:246-261` | Add one bullet before "Ask for explicit approval" |
| `test_acceptance_v211.py`: every check is covered by the unit suites of design 0018 (`test_shortcuts`, `test_guardrail.ShortcutHookTests` and `WorkflowSubagentTests`, `test_manifest_check.ComplexityWarningTests`, `test_encoding`) or pins 2.11.0's version and notes | `.claude/bin/test_acceptance_v211.py` | Delete it; nothing moves |
| `NOTES` entry; `plugin.json` version must equal the newest key | `.claude/bin/upgrade.py:147-160`, `.claude/bin/test_definitions.py:405-410` | Same package |
| Ratchet: functions under 60 lines, nesting 4, lines under 120 characters; `agentic.py` and `upgrade.py` are at their long-line allowance | `.claude/quality-baseline.json` | No new long lines |

What must NOT change: `rules_sync`'s output and effects; every existing command's output; the auditor's existing checks.

## 5. Data model
```python
# A doctor finding
{"code": str, "severity": "auto" | "route" | "mention", "message": str,
 "fix": str,     # only for "auto": what --fix does, in words
 "route": str}   # only for "route": the command or slash command that repairs it

# doctor's output (one JSON line)
{"ok": bool,                # no "auto" and no "route" finding left
 "fixed": [str],            # codes repaired by this --fix run, in order
 "findings": [finding]}     # after any repair, in the order of the table below
```
| code | severity | when | message | fix / route |
|---|---|---|---|---|
| `guard-leftover` | auto | `.claude/state/guard/` exists | `.claude/state/guard/ is left over from the frozen guard retired in 2.10.0` | fix: `delete .claude/state/guard/` |
| `retired-permission` | auto (one finding however many retired rules) | `.claude/settings.json` `permissions.allow` holds a rule of `RETIRED_PERMISSIONS` | `settings.json still allows <rule>` | fix: `remove it from permissions.allow` |
| `hook-missing` | route | `hooks_static_problem()` is not None | its text | route: `/agentic-flow:init` |
| `install-record` | route | not the flow repo, and `INSTALL_RECORD` is missing, unreadable, or its `version` differs from `flow_version()` | `no .claude/agentic-install.json`, `.claude/agentic-install.json is not valid JSON`, or `the install record says <a>, the installed flow is <b>` | route: `/agentic-flow:init` |
| `quality-baseline` | route | `QUALITY_BASELINE` does not exist | `no .claude/quality-baseline.json` | route: `python3 .claude/bin/agentic.py quality --init` |
| `rules` | route | `RULES_LIBRARY/common.md` exists and the `.md` files of `RULES_DIR` differ from `wanted_rules()` by name or content | `.claude/rules/agentic/ does not match the stack (missing: …; extra: …; changed: …)` with only the non-empty parts | route: `python3 .claude/bin/agentic.py rules-sync` |
| `agents-running` | route | the ledger has entries with `state == "running"` | `the ledger says <ids> running; if no run is in progress, stop them` (`<ids>` sorted, joined with `, `) | route: `python3 .claude/bin/agentic.py stop` |
| `upgrade-pending` | mention | `.claude/state/upgrade/` holds files (counted recursively: install nests them by path) | `<n> new version(s) kept beside your edits in .claude/state/upgrade/` | — |

## 6. Contracts between modules
```python
# repo_scan.py (WP-01)
def wanted_rules() -> list:
    """The rule names rules_sync installs: "common" plus each declared or detected language whose name matches
    r"[a-z][a-z0-9+-]*" and whose file exists in the library, sorted. It never exits: the missing-library check stays
    in rules_sync. rules_sync uses it; nothing else changes."""

# doctor.py (WP-01)
def diagnose() -> list:
    """The findings of section 5 for ROOT, in the table's order. Reads only; never writes."""

def repair(findings) -> list:
    """Applies the fix of each "auto" finding (delete the folder; remove the rules from settings.json, keeping the
    file's other keys and its 2-space JSON with a trailing newline). Returns their codes, in order."""

# plan_picture.py (WP-02)
def render(manifest, title="Plan") -> str:
    """A whole HTML document, UTF-8, with one inline <svg> and one <table>, no script and no external resource.
    Packages are columns by wave (ascending) and rows by id; each package is a <g id="wp-<ID>"> holding its id and
    "<n> files · <m> ACs"; each depends_on pair (both ids in the manifest) is one <line class="dep"
    data-from="<A>" data-to="<B>">. The table has one row per package: id, wave, depends_on (comma-separated), files (every path, comma-separated), ACs (comma-separated). All text
    goes through html.escape. The same manifest and title give the same string."""

# bench/scenario.py (WP-04)
def run(scenario_dir, claude=None, agent_file=None) -> dict:
    """Copies the scenario's files and this checkout's .claude/agents and .claude/workflows into a temporary folder
    (agent_file, when given, replaces the scenario agent's definition there, e.g. an older test-auditor.md),
    renders the agent's prompt from pipeline-spec.json with the scenario's values, runs
    `claude -p --agent <agent> --model sonnet --output-format json --json-schema <schema>` (claude: argv list, default
    from AGENTIC_CLAUDE or "claude") with the prompt on stdin, and returns {"report": <structured report or None>,
    "expect": <scenario.json's "expect">, "met": bool}. Never raises on a bad report: report None, met False.
    The run uses bench.py's ISOLATION_FLAGS and ISOLATION_ENV, so the person's own CLAUDE.md and settings do not
    leak into the experiment."""

# bench/scenario.py command line (WP-04)
#   python3 bench/scenario.py DIR [--agent-file PATH]
#   prints run()'s dict as one JSON line; exit 0 if met, 3 if not, 1 on a usage error or a missing scenario.json
```
Command line (WP-03):
| Command | Output | Exit |
|---|---|---|
| `agentic.py doctor` | one JSON line (section 5), nothing repaired | 0 if `ok`, 3 otherwise |
| `agentic.py doctor --fix` | the same, after repairing the `auto` findings; `fixed` lists them | 0 if `ok`, 3 otherwise |
| `agentic.py doctor <other>` | `Uso: doctor [--fix]` on stderr | 1 |
| `agentic.py plan-picture` | writes `.claude/state/plan.html` (creating `.claude/state/`), prints `{"path": ".claude/state/plan.html", "packages": n, "waves": w}` | 0; an invalid manifest exits 1 as `validate` does and writes nothing |
| `agentic.py plan-picture <other>` | `Uso: plan-picture` on stderr | 1 |

`bench/scenarios/auditor-wrong-expected/scenario.json`: `{"agent": "test-auditor", "prompt": "test_auditor", "values": {"brief": "brief.md", "coverage": "{\"AC-009\": [\"acceptance/test_schedule.py::test_ac_009_minutes_worked\"]}", "rules": ""}, "expect": {"status": "FAIL", "finding_mentions": ["AC-009", "960"]}}`. `met` is true when the report's `status` equals `expect.status` and some critical or high finding's `problem + " " + evidence` contains every string of `finding_mentions`.

## 7. Conventions
- English everywhere; no type annotations, as in the existing modules (an exception to the generic Python rule: the code base targets Python 3.9 and has none).
- `doctor` reads by default; only `--fix` writes, and only the two `auto` repairs.
- The picture is plain HTML and SVG: no `<script>`, no `http`.
- Every `open`, `read_text` and `write_text` in a `.claude/bin` module names `encoding="utf-8"` (`test_quality.EncodingTests` checks it).
- No new long lines; functions under 60 lines.
- Commits are the maintainer's; agents do not commit.

## 8. Work packages and acceptance criteria
### Acceptance criteria
`doctor` tests use `test_agentic.Repo` (it copies the flow's `settings.json`), then add or remove what each scenario needs. `Repo` does not copy `.claude/rules-library/`: AC-003 and AC-004 copy it from this checkout (`shutil.copytree`) so `rules` is checked and `rules-sync` works. "Not the agentic-flow repository" is tested by copying this checkout's `.claude-plugin/plugin.json` and `README.md` into a temporary repo (`is_flow_repo` reads only those two), never by running `doctor` on the real checkout.

- AC-001 · doctor reports each stale thing with its severity
  - Scenario: a temporary project with `.claude/state/guard/x`, a `settings.json` that also allows `Bash(python3 .claude/state/guard/bin/agentic.py:*)`, no install record, no quality baseline, a `running` ledger entry for WP-01, and one file in `.claude/state/upgrade/`.
  - Action: `agentic.py doctor`.
  - Expected: exit 3; `ok` false; the codes in order `guard-leftover`, `retired-permission`, `install-record`, `quality-baseline`, `agents-running`, `upgrade-pending`, with severities auto, auto, route, route, route, mention; each `route` carries the command of section 5 (`agents-running`: `python3 .claude/bin/agentic.py stop`).
  - Must not: change any file (the folder, settings and ledger stay byte-identical).
  - Check: `test_acceptance_v212.DoctorTests.test_ac_001_findings`
  - WP: WP-01, WP-03
- AC-002 · doctor --fix repairs only the auto findings
  - Scenario: as AC-001.
  - Action: `agentic.py doctor --fix`, then `agentic.py doctor`.
  - Expected: the first prints `fixed: ["guard-leftover", "retired-permission"]`, `.claude/state/guard/` is gone and `settings.json` no longer holds the rule but keeps its other permissions and hooks; both runs exit 3 (routes remain) and list no auto finding.
  - Must not: touch the ledger, the upgrade folder or the install record.
  - Check: `test_acceptance_v212.DoctorTests.test_ac_002_fix`
  - WP: WP-01, WP-03
- AC-003 · A clean project, or one with only mentions, passes
  - Scenario: a project with a matching install record, a quality baseline, rules matching `wanted_rules()` (from `rules-sync`), no ledger; then the same with a file in `.claude/state/upgrade/`.
  - Action: `agentic.py doctor`.
  - Expected: exit 0 with `findings: []`; then exit 0, `ok` true, one `upgrade-pending` finding.
  - Must not: report `install-record` in the agentic-flow repository itself; create anything under `.claude/state/` (no ledger, no folder).
  - Check: `test_acceptance_v212.DoctorTests.test_ac_003_clean`
  - WP: WP-01, WP-03
- AC-004 · rules out of sync are named
  - Scenario: a clean project; then `.claude/rules/agentic/common.md` edited and `.claude/rules/agentic/ruby.md` added.
  - Action: `agentic.py doctor`.
  - Expected: one `rules` finding whose message names `extra: ruby` and `changed: common`, route `python3 .claude/bin/agentic.py rules-sync`; after `rules-sync`, no finding.
  - Must not: write under `.claude/rules/`.
  - Check: `test_acceptance_v212.DoctorTests.test_ac_004_rules`
  - WP: WP-01, WP-03
- AC-005 · plan-picture draws the manifest, the same way every time
  - Scenario: a project whose manifest has WP-01 (wave 1), WP-02 (wave 1) and WP-03 (wave 2, `depends_on: ["WP-01"]`), WP-02 owning a file named `src/<b>.py`.
  - Action: `agentic.py plan-picture` twice; read `.claude/state/plan.html`.
  - Expected: exit 0; the JSON says 3 packages and 2 waves; the file holds one `<svg`, `<g id="wp-WP-01"`, `<g id="wp-WP-02"`, `<g id="wp-WP-03"`, exactly one `<line class="dep" data-from="WP-01" data-to="WP-03"`, a table row per package, and `src/&lt;b&gt;.py`; both runs give identical bytes.
  - Must not: contain `<script` or `http`; write anything for an invalid manifest (exit 1).
  - Check: `test_acceptance_v212.PictureTests.test_ac_005_picture`
  - WP: WP-02, WP-03
- AC-006 · The test-auditor treats a wrong expected value as critical
  - Scenario: `.claude/agents/test-auditor.md`; `bench/scenarios/auditor-wrong-expected/`.
  - Action: read the definition; run `bench/scenario.py`'s `run` on the scenario with `claude=[sys.executable, <a script that prints {"structured_output": {"status": "FAIL", "findings": [{"severity": "critical", "wp": "AT", "file": "acceptance/test_schedule.py", "problem": "AC-009 expects 960", "evidence": "the test asserts 1440"}], "not_checked": []}}>]`, then with one that prints status PASS and no findings. Import `bench/scenario.py` with `importlib.util.spec_from_file_location`, as `bench/test_bench.py:15-18` does.
  - Expected: `test-auditor.md` contains `**Wrong:**` and `contradicts the criterion's Expected` in its checklist, and `wrong expected value` in its critical/high severity line; the scenario holds `brief.md` with AC-009 expecting 960, `acceptance/test_schedule.py` asserting `960 + 480`, and `scenario.json` as in section 6; `run` returns a dict with `report`, `expect` and `met`; `met` is True for the first fake and False for the second.
  - Must not: call a real `claude` in the test.
  - Check: `test_acceptance_v212.AuditorTests.test_ac_006_auditor_and_scenario`
  - WP: WP-04
- AC-007 · Shipped, documented and versioned
  - Scenario: this checkout.
  - Action: read `installer.INSTALL_GLOBS`, `agentic.COMMANDS`, `docs/how-it-works.md`, `plugin.json`, `upgrade.NOTES`; list `.claude/bin/test_acceptance*.py`.
  - Expected: both modules in `INSTALL_GLOBS`; `doctor` and `plan-picture` in `COMMANDS` and the docstring; the module tree names `doctor.py` and `plan_picture.py`; version `2.12.0`; `NOTES["2.12.0"]` mentions `doctor`, `plan-picture` and `test-auditor`; the only acceptance file is `test_acceptance_v212.py`.
  - Must not: keep `test_acceptance_v211.py`.
  - Check: `test_acceptance_v212.ReleaseTests.test_ac_007_release`
  - WP: WP-03, WP-05

### Work packages
WP-01, WP-02, WP-04 and WP-05 are wave 1: disjoint files, none needs another's code. WP-03 is wave 2: `agentic.py` imports `doctor` and `plan_picture`, so it needs both modules. Executed by hand.

#### WP-01 · doctor.py and wanted_rules
- Wave: 1.
- Files: `.claude/bin/doctor.py` (new), `.claude/bin/repo_scan.py`, `.claude/bin/test_doctor.py` (new).
- Implements: `diagnose`, `repair`, `wanted_rules` (section 6), the table of section 5.
- ACs: the logic of AC-001 to AC-004.
- Patterns to mirror: `.claude/bin/brief.py:1-40`; `.claude/bin/repo_scan.py:69-90`; `.claude/bin/test_release.py:20-60` (a repo built per test).
- Gotchas: `diagnose` must create nothing: `core.ledger_read()` goes through `locked_json`, which creates `.claude/state/` and `ledger.json` (`core.py:348-365`), so read `core.LEDGER_JSON` directly with `json.loads` only if it exists, and treat an unreadable one as no running entries. Import `hooks_static_problem` from `guardrail`, `INSTALL_RECORD`, `flow_version`, `RETIRED_PERMISSIONS` from `installer`, `wanted_rules` from `repo_scan`, the rest from `core`. `repair` rewrites `settings.json` with `json.dumps(data, indent=2, ensure_ascii=False) + "\n"`, as the installer does (`installer.py:136`), so only the removed rule changes. Skip `install-record` when `is_flow_repo(ROOT)`; skip `rules` when the library has no `common.md`.
- Validation: `python3 -m unittest discover -s .claude/bin -p test_doctor.py`; `python3 -m unittest discover -s .claude/bin -p test_agentic.py` (rules-sync tests).

#### WP-02 · plan_picture.py and the approval gate
- Wave: 1.
- Files: `.claude/bin/plan_picture.py` (new), `.claude/bin/test_plan_picture.py` (new), `.claude/commands/architect.md`.
- Implements: `render` (section 6); in `architect.md`'s wrap-up, before "Ask for explicit approval", the bullet: run `python3 .claude/bin/agentic.py plan-picture` and give the user the path `.claude/state/plan.html`.
- ACs: the rendering of AC-005.
- Patterns to mirror: `.claude/bin/brief.py:1-40`; `.claude/commands/architect.md:246-261`.
- Gotchas: no `xmlns` on the `<svg>` (HTML5 does not need it, and its URL would break AC-005's no-`http` rule); fixed sizes (box width and height, column and row gaps) as module constants; coordinates are integers so the output does not depend on float formatting; a `depends_on` id that is not in the manifest draws no line.
- Validation: `python3 -m unittest discover -s .claude/bin -p test_plan_picture.py`.

#### WP-03 · The commands, shipping and docs
- Wave: 2, after WP-01 and WP-02.
- Files: `.claude/bin/agentic.py`, `.claude/bin/installer.py`, `.claude/bin/test_definitions.py`, `docs/how-it-works.md`, `docs/how-to/README.md`. (`README.md` lists no commands, so it does not change.)
- Implements: `cmd_doctor`, `cmd_plan_picture` and their table entries and docstring lines (section 6); the two globs; the count 36; one tree line per module (`doctor.py  what the flow left stale in a project, and --fix`; `plan_picture.py  the HTML+SVG picture of the manifest`) and one command line each in the how-to list.
- ACs: the command side of AC-001 to AC-005; AC-007 (shipping and docs).
- Patterns to mirror: `.claude/bin/agentic.py:275-284`, `:332-345`; `.claude/bin/installer.py:19-43`.
- Gotchas: `agentic.py` is at its long-line allowance: the import lines must stay under 120 characters. `plan-picture` writes with `encoding="utf-8"`.
- Validation: `python3 -m unittest discover -s .claude/bin -p test_definitions.py`; `python3 .claude/bin/agentic.py docs-check`; `python3 .claude/bin/agentic.py quality`.

#### WP-04 · The test-auditor and its scenario
- Wave: 1.
- Files: `.claude/agents/test-auditor.md`, `bench/scenario.py` (new), `bench/test_scenario.py` (new), `bench/scenarios/auditor-wrong-expected/` (new).
- Implements: a checklist item starting `**Wrong:**` that says an expected value that contradicts the criterion's Expected (or the plan's own arithmetic) makes a correct implementation fail, so every literal is checked against the criterion; the critical/high line names `a wrong expected value`; the Report's `evidence` also covers it (the literal in the test against the criterion's value); `run` (section 6); the scenario files.
- ACs: AC-006.
- Patterns to mirror: `.claude/agents/test-auditor.md:18-33`; `.claude/bin/launch.py:65-80`; `bench/test_bench.py:1-40`.
- Gotchas: the scenario's `brief.md` is the roster plan's sections 1, 6 and AC-009 only (`bench/fixtures/roster/repo/architecture.md:157-163`); its test function is `test_ac_009_minutes_worked` and asserts `960 + 480`. No `__init__.py` under `bench/scenarios/`, so `discover -s bench` never collects that deliberately wrong test. `run` gives the agent read-only tools (`Read,Glob,Grep,StructuredOutput`), never `acceptEdits`, and imports `ISOLATION_FLAGS`/`ISOLATION_ENV` from `bench/bench.py:57-58`. `bench/test_scenario.py` does not use `testutil`'s fake (it always answers `findings: []`): it writes its own tiny fake `claude` script per test that prints `{"structured_output": <report>}` and passes it as `claude=[sys.executable, <script>]`, one report that meets the expectation and one that does not. Update the agent's `description` and `# Role` too: it no longer only looks for tests that are too weak.
- Validation: `python3 -m unittest discover -s bench -p "test_*.py"`; `python3 -m unittest discover -s .claude/bin -p test_definitions.py`.

#### WP-05 · Version, notes and the retired acceptance file
- Wave: 1.
- Files: `.claude/bin/upgrade.py`, `.claude-plugin/plugin.json`, `.claude/bin/test_acceptance_v211.py` (deleted).
- Implements: version 2.12.0 and `NOTES["2.12.0"]`, three notes: (1) `agentic.py doctor [--fix]` lists what the flow left stale, with auto, route and mention findings; (2) `agentic.py plan-picture` writes `.claude/state/plan.html`, and `/architect` shows it at approval; (3) the test-auditor flags expected values that contradict the plan (test-auditor.md: merge it if you edited yours).
- ACs: the release part of AC-007.
- Patterns to mirror: `.claude/bin/upgrade.py:147-160`.
- Validation: `python3 -m unittest discover -s .claude/bin -p test_layout.py` (after the acceptance file of this design exists).

```json wp-manifest
{
  "maintainer": true,
  "stack": ["python"],
  "allow_bash": ["Bash(python3 -m unittest:*)", "Bash(node .claude/bin/test_workflow.mjs)"],
  "acceptance": {"files": [".claude/bin/test_acceptance_v212.py"], "command": "python3 -m unittest discover -s .claude/bin -p test_acceptance_v212.py"},
  "verify": {"build": "python3 -m unittest discover -s bench -p \"test_*.py\"", "lint": "node .claude/bin/test_workflow.mjs", "types": "python3 -m unittest discover -s bench/acceptance", "tests": "python3 -m unittest discover -s .claude/bin -p \"test_*.py\""},
  "docs": {"files": ["docs/assets/"], "codemap": null},
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": [".claude/bin/doctor.py", ".claude/bin/repo_scan.py", ".claude/bin/test_doctor.py"],
     "acs": ["AC-001", "AC-002", "AC-003", "AC-004"], "mirror": [".claude/bin/brief.py:1-40", ".claude/bin/repo_scan.py:69-90", ".claude/bin/test_release.py:20-60"]},
    {"id": "WP-02", "wave": 1, "depends_on": [], "files": [".claude/bin/plan_picture.py", ".claude/bin/test_plan_picture.py", ".claude/commands/architect.md"],
     "acs": ["AC-005"], "mirror": [".claude/bin/brief.py:1-40", ".claude/commands/architect.md:246-261"]},
    {"id": "WP-03", "wave": 2, "depends_on": ["WP-01", "WP-02"], "files": [".claude/bin/agentic.py", ".claude/bin/installer.py", ".claude/bin/test_definitions.py", "docs/how-it-works.md", "docs/how-to/README.md"],
     "acs": ["AC-001", "AC-002", "AC-003", "AC-004", "AC-005", "AC-007"], "mirror": [".claude/bin/agentic.py:275-284", ".claude/bin/agentic.py:332-345", ".claude/bin/installer.py:19-43"]},
    {"id": "WP-04", "wave": 1, "depends_on": [], "files": [".claude/agents/test-auditor.md", "bench/scenario.py", "bench/test_scenario.py", "bench/scenarios/auditor-wrong-expected/"],
     "acs": ["AC-006"], "mirror": [".claude/agents/test-auditor.md:18-33", ".claude/bin/launch.py:65-80", "bench/test_bench.py:1-40"]},
    {"id": "WP-05", "wave": 1, "depends_on": [], "files": [".claude/bin/upgrade.py", ".claude-plugin/plugin.json", ".claude/bin/test_acceptance_v211.py"],
     "acs": ["AC-007"], "mirror": [".claude/bin/upgrade.py:147-160"]}
  ]
}
```

## 9. Test strategy
- **Acceptance:** `.claude/bin/test_acceptance_v212.py`, written first, red before the code.
- **Unit:** each package in its files; no real `claude` call anywhere in the suites.
- **The #70 red and green, by hand (QA):** with the real `claude`, `git show agentic-flow--v2.11.0:.claude/agents/test-auditor.md > <scratch>/old-auditor.md`, then `python3 bench/scenario.py bench/scenarios/auditor-wrong-expected --agent-file <scratch>/old-auditor.md` (the old auditor) and `python3 bench/scenario.py bench/scenarios/auditor-wrong-expected` (the new one). Expected: the first does not meet the expectation (no critical finding about AC-009), the second meets it. Two runs per version; the result goes in the pull request. Cost: not measured, a few Sonnet calls.
- **QA by hand:** `doctor` on finanzas-familiares and webos-launcher clones; `plan-picture` on this design, opened in a browser.
- **Expected red during the run:** `test_definitions.DocumentationDriftTests.test_cited_commands_exist` fails after WP-02 (`architect.md` cites `plan-picture`) until WP-03 adds the command. `test_layout.py` fails while both `test_acceptance_v211.py` and `test_acceptance_v212.py` exist, until WP-05 deletes the first.
- **Everything:** section 3, plus the teeth check.

## 10. Decisions
- **`running` ledger entries are `route`, not `auto`** (changed from the user's first choice, and told to them): the flow cannot know whether a native workflow run is alive (its agents have no pid), so repairing would be a guess. `agentic.py stop` stays the person's call.
- **`doctor` exits 3 while something is left to do** (user's choice), like `quality` and `hooks-check`.
- **The picture is a command plus a step of `/architect`** (user's choice), written to `.claude/state/plan.html`: static, deterministic, no script.
- **#70 is a prompt change, proven with the real auditor** (user's choice). Cause, from the evidence: the auditor's checklist only looks for tests that are too weak; a wrong expected value makes a correct implementation fail, which the checklist never asks about.
- **`wanted_rules()` is extracted, not duplicated**, so `doctor` and `rules-sync` cannot disagree.
- **`test_acceptance_v211.py` is retired without moving anything**: every check is covered by 0018's unit suites or pins 2.11.0.
- **Executed by hand**, like 0013 to 0018.

## 11. Risks and open questions
- **The real auditor may still miss the case**, or flag it only sometimes: two runs per version are a small sample. If the new prompt does not meet the expectation, the PR says so and #70 stays open.
- **`install-record` in a template copy without a record** is reported as `route`; that is correct (install writes one), but a project that never used `install` will see it until it does.
- Rollback: revert the commits; nothing is migrated.
