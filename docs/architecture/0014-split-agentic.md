# Architecture: split `agentic.py` into modules by domain
Type: refactor · Size: large

## 1. Goal
`.claude/bin/agentic.py` is 2,790 lines with 144 functions, and 34 CLI commands dispatched by an `elif` chain inside a 153-line `main()`. The clean-code ratchet (design 0013) froze that file at 2,790 lines (+30) and `main` at 153, so the next command cannot be added without loosening the baseline by hand. This refactor moves the code into eight modules by domain, replaces the chain with a dispatch table, and splits the three other functions over the 60-line limit (`install` 116, `validate` 93, `guard` 70) into pieces that respect it. Behaviour does not change: every suite stays green, every CLI command keeps its arguments, output and exit codes, `agentic.py` keeps re-exporting the names tests and frozen acceptance files use, and the frozen guard of a maintainer run keeps working because it copies the whole folder.

## 2. Scope
### Included
- Eight new modules in `.claude/bin/`: `core`, `manifest_check`, `repo_scan`, `verification`, `stage`, `installer`, `launch`, `guardrail`.
- `agentic.py` reduced to the entry point: docstring, re-exports, one `cmd_*` handler per command, the `COMMANDS` table, `main()`.
- `install`, `validate` and `guard` split into functions of at most 60 lines and nesting 4.
- `INSTALL_GLOBS`, the four `mock.patch` targets in `test_agentic.py`, `agentic_subcommands()` in `test_definitions.py` and `FLOW_MODULES` in `test_acceptance_portable.py` updated.
- Version 2.8.0, its upgrade note, and the file list in `docs/how-it-works.md`.
- After the last WP, the maintainer runs `agentic.py quality --update` so the baseline drops the entries that vanished.

### Excluded (non-goals)
- Splitting `test_agentic.py` (1,849 lines): tests keep importing `agentic` and run through its re-exports. A follow-up.
- Any change of behaviour, message text, argument parsing or exit code.
- `pipeline.py`, `brief.py`, `upgrade.py`, `quality.py`, `compat.py`, `waiting.py`, `hook.py`: untouched.
- Shrinking `Pipeline.judge` (96 lines, in `pipeline.py`): it does not move, so the ratchet does not see it as new.

## 3. Stack
- Python ≥ 3.9, standard library only; no type annotations in any `.claude/bin/*.py` that ships (they are frozen into the maintainer guard and must import on 3.9).
- Node 22 for `test_workflow.mjs` only.
- Commands:
  - compile: `python3 -m compileall -q .claude/bin` (run by hand; the manifest's `build` slot runs `qa`, whose `test_qa_docs.py:16,190-198` reads text in `agentic.py`)
  - tests: `python3 -m unittest discover -s .claude/bin -p "test_*.py"`
  - workflow: `node .claude/bin/test_workflow.mjs`
  - docs: `python3 -m unittest discover -s acceptance`
  - qa: `python3 -m unittest discover -s qa`
  - bench: `python3 -m unittest discover -s bench -p "test_*.py"` and `python3 -m unittest discover -s bench/acceptance`
  - ratchet: `python3 .claude/bin/agentic.py quality`

## 4. Repository structure
```
.claude/bin/core.py                 WP-01 (new)  paths, constants shared by ≥2 domains, manifest access, ledger, locks, flow-repo tests
.claude/bin/manifest_check.py       WP-02 (new)  validate and its error families, require_valid
.claude/bin/repo_scan.py            WP-03 (new)  stack detection, rules-sync, codemap, callers, docs-check
.claude/bin/verification.py         WP-04 (new)  run_command, acceptance, baseline/verify phases, attribution, quality_*
.claude/bin/stage.py                WP-05 (new)  snapshots, stage checks, open/close-stage, fix diffs, the stop gate
.claude/bin/installer.py            WP-06 (new)  install (split), merge_settings, sync-permissions, flow-history
.claude/bin/launch.py               WP-07 (new)  claude -p launchers, run-* commands, seq, run-pipeline, pipeline-plan, the frozen guard
.claude/bin/guardrail.py            WP-08 (new)  the PreToolUse hook: guard (split), claims, content checks, hooks-check
.claude/bin/agentic.py              WP-09        entry point: docstring, re-exports, cmd_* handlers, COMMANDS, main
.claude/bin/test_agentic.py         WP-09        four patch targets
.claude/bin/test_definitions.py     WP-09        agentic_subcommands reads COMMANDS; a structure test
.claude/bin/test_acceptance_portable.py  WP-09   FLOW_MODULES gains the eight modules
.claude-plugin/plugin.json          WP-10        2.8.0
.claude/bin/upgrade.py              WP-10        NOTES["2.8.0"]
docs/how-it-works.md                WP-10        the .claude/bin file list
.claude/quality-baseline.json       nobody: the maintainer runs `quality --update` after WP-09 (never owned)
```

## 4b. Existing code context
Line numbers are those of `agentic.py` today (2,790 lines, commit `bf7c36d`). The inventory below is the authority on what moves where; a function not listed stays in `agentic.py`.

| What an implementer needs to know | Where it is | Pattern or rule |
|---|---|---|
| How a sibling module sets itself up: docstring, `sys.path.insert(0, <own folder>)`, `import compat` | `waiting.py:1-16` | Every new module starts the same way; `core` is imported with explicit names, never `*` |
| Paths are computed from the script's own folder, frozen copy included | `agentic.py:76-86` (`HERE`, `FROZEN`, `SOURCE_ROOT`, `ROOT`) | Move verbatim to `core.py`; the frozen copy's `core.py` sits in the same folder as its `agentic.py`, so the values are identical |
| Every `Path(__file__)` in `agentic.py` means "this folder" or "the entry script" | `:76, :79` (folder); `:1429, :1449, :1532, :1887` (`agentic.py` as a subprocess); `:1628` (`sibling`) | In a module, `__file__` would name the module. Use `core.HERE` and the new `core.ENTRY = HERE / "agentic.py"` |
| `sibling(name)` imports a module from the script's folder | `:1627-1629` | Moves to `core`; `pipeline_module`, `brief_module` (`:1632-1637`) to `launch`; `quality_module` (`:1773-1774`) to `verification` |
| The frozen guard copies every non-test `.claude/bin/*.py` and the spec | `:1750-1768` (`freeze_guard`, filter at `:1761`) | New modules are copied automatically; `test_acceptance_v25.FrozenCopyTests` runs `validate` from the frozen copy and must stay green |
| What `install` ships | `:148-149` (`INSTALL_GLOBS`) | Gains the eight modules; `test_definitions.test_what_is_installed_exists` checks each glob matches a file |
| The hook launcher runs `agentic.py` through `runpy` with `run_name="__main__"` | `hook.py:16-30` | `agentic.py` keeps `if __name__ == "__main__": main()` at the end; `hook.py` is not edited |
| Names other files use as `agentic.X` | `test_agentic.py`, `test_definitions.py`, frozen `test_acceptance_v21.py`, `test_acceptance_v241.py`, `acceptance/test_docs.py`; `test_acceptance_v25.py:249-256` calls `load_spec()` on the frozen copy loaded under another name | listed in section 6; `agentic.py` re-exports exactly those |
| Tests that patch `agentic` attributes | `test_agentic.py:151` (`USAGE`), `:1738, :1740` (`is_flow_repo`), `:1770` (`ROOT`) | A patch must target the module where the function under test looks the name up (section 7) |
| Two tests parse `agentic.py` as text for a constant | `test_definitions.py:287-291` (`STACK_SIGNALS`), `:424-429` (`INSTALL_GLOBS`) | WP-09 makes them read `repo_scan.STACK_SIGNALS` and `installer.INSTALL_GLOBS` |
| How tests derive the command list | `test_definitions.py:70-75` (`agentic_subcommands`: regex over `cmd == "..."`), used by `test_cited_commands_exist` `:450-458` | With a table there is no `cmd ==`; it reads `agentic.COMMANDS` instead |
| Modules the portability test checks for encoding | `test_acceptance_portable.py:22` (`FLOW_MODULES`) | Gains the eight modules (a frozen file, edited on purpose: section 10) |
| Sections of `agentic.py` | `:260` configuration · `:277` manifest · `:584` snapshots and stage checks · `:758` launchers · `:992` language rules · `:1067` living documentation · `:1108` callers · `:1274` installing · `:1507` native workflow commands · `:1564` the whole pipeline · `:1771` the clean-code ratchet · `:2130` hook PreToolUse · `:2156` the stop gate · `:2212` ledger · `:2632` CLI | The inventory in section 5 maps each function to its module |
| `main()` and the `elif` chain | `:2634-2786` | Each branch becomes `cmd_<name>(args)` in `agentic.py`, with its argument checks and prints unchanged |
| The usage text `die(__doc__)` prints | `:1-62` (module docstring) | Stays in `agentic.py`, unchanged |
| The ratchet's limits and the baseline entries for this file | `.claude/quality-baseline.json`: `agentic.py` 2,790 lines / 51 long lines; `main` 153, `install` 116, `validate` 93, `guard` 70 | A moved function is a new key: `lines ≤ 60`, `nesting ≤ 4`. A new file: `≤ 800` lines, `0` long lines (>120 chars). `python3 .claude/bin/agentic.py quality` must exit 0 before any baseline edit |
| Error handling: `die(msg)` prints to stderr and exits 1; `block(msg)` prints the guard's refusal and exits 2; `ManifestError` for a bad manifest | `:251-257`, `:2327-2329` | Unchanged; `block` moves to `guardrail`, `die`/`ManifestError` to `core` |
| Locked JSON state files (`claims`, `gate`, `hook-seen`, `usage`) | `:2132-2153` (`locked_json`, `with_claims`) | `core`: used by the hook, the stage check and the ledger |
| Content guardrails shared by the hook and the stage check | `:221-246` (`PROTECTED_CONFIG_RE`, `SKIP_MARKER_RE`, `TEST_PATH_RE`, `SECRET_RES`), `:674-698` (`content_problems`), `:2410-2433` (`content_checks`) | The regexes go to `core`; `content_problems` to `stage`; `content_checks` to `guardrail` |
| `validate` already delegates families of checks | `:482-570` (`stack_errors`, `docs_errors`, `agent_model_errors`, `mirror_errors`) | The split of `validate` follows that pattern (section 6) |
| `install` is one function with inner closures | `:1338-1453` | Split into plan / guard / write / report (section 6) |
| `guard` is one function with six phases | `:2446-2515` | Split into universal checks / owner resolution / report gate / bash rules / write rules (section 6) |
| The CI job that installs into a project and runs the shipped tests | `.github/workflows/agentic-flow-ci.yml` (`installed`) | Runs on every pull request; it catches a module missing from `INSTALL_GLOBS` |
| Bench installs the flow from a checkout with `agentic.py install` | `bench/bench.py:229` | Nothing to change: install ships the modules |

## 5. Data model
No data changes. The inventory of moves (function → module), by current line range. Constants move with the first module listed; a constant used by two domains goes to `core`.

**core.py** — `:79-119` all paths and constants (`HERE`, `GUARD_DIR`, `GUARD_CMD`, `LIVE_CMD`, `FROZEN`, `SOURCE_ROOT`, `ROOT`, `ARCH`, `STATE`, `USAGE`, `CLAIMS`, `LEDGER_JSON`, `LEDGER_MD`, `LEDGER_STATES`, `GATE`, `HOOK_SEEN`, `HOOK_SEEN_MAX_AGE_S`, `HOOK_SEEN_COMMAND_CHARS`, `GATE_MAX_DENIALS`, `GATE_MAX_LINES`, `GATE_TIMEOUT_S`, `GATE_STATUSES`, `WP_ID_RE`, `CONFIG`, `BASE_TOOLS`, `QA_DEFAULT_FILES`, `AT_DEFAULT_FILES`, `DOCS_DEFAULT_FILES`, `DEFAULT_CODEMAP`, `RESERVED_IDS`, `ARCHIVE_DIR`, `NEVER_OWNED`, `QUALITY_BASELINE`, `FLOW_NAME`, `TEMPLATE_MARKER`, `RULES_LIBRARY`, `RULES_DIR`) plus the new `ENTRY = HERE / "agentic.py"`; `:133-146` `SKIP_DIRS`, `SYMBOL_RES`; `:153` `VERIFY_PHASES`; `:159` `BASELINE`; `:166` `WORKER_MODEL`; `:173-181` `DEFAULT_CONFIG`, `API_AUTH_VARS`; `:186` `MANIFEST_RE`; `:221-246` `PROTECTED_CONFIG_RE`, `SKIP_MARKER_RE`, `TEST_PATH_RE`, `SECRET_RES`; `:1569` `READ_ONLY_AGENTS`. Functions: `ManifestError` `:251`, `die` `:255`, `load_config` `:262`, `load_manifest` `:279`, `wps` `:294`, `qa_entity` `:298`, `at_entity` `:303`, `review_entity` `:309`, `docs_entity` `:313`, `codemap_path` `:322`, `entities` `:327`, `owns` `:339`, `owner_conflict` `:344`, `ignored` `:348`, `child_env` `:760`, `source_files` `:994`, `symbol_re` `:1069`, `sibling` `:1627`, `is_flow_repo` `:1720`, `maintainer_mode` `:1731`, `never_owned_problem` `:1737`, `flow_path_refused` `:1745`, `locked_json` `:2132`, `with_claims` `:2152`, `now_hm` `:2214`, `ledger_read` `:2218`, `ledger_update` `:2222`, `ledger_stage` `:2230`, `status_to_state` `:2238`, `stage_of` `:2244`, `usage_records` `:2253`, `usage_summary` `:2263`, `usage_line` `:2269`, `ledger_render` `:2274`, `stop` `:2310`, `is_old_hook_command` `:2526`, `flow_hooks` `:2531`. Estimated 480 lines (not measured).

**manifest_check.py** — `:160` `MIRROR_RE`, `:162` `TYPE_RE` stays in launch (see there), `:169-172` `ARCHITECT_MODEL`, `AGENT_MODEL_OVERRIDES`, `:187` `AC_RE`, `:246` `OPEN_ENDED`, `:509` `FRONTMATTER_MODEL_RE`. Functions: `open_ended_rule` `:359`, `open_ended_command` `:366`, `validate` `:383` (split), `known_packs` `:478`, `stack_errors` `:482`, `docs_errors` `:493`, `frontmatter_model` `:512`, `agent_model_errors` `:520`, `mirror_errors` `:549`, `require_valid` `:573`. Estimated 230 lines.

**repo_scan.py** — `:121` `STACK_SIGNALS`, `:1110-1114` `CALLERS_PER_SYMBOL`, `CALLERS_MAX`, `CALLER_TEXT_MAX`, `CALLER_RE_TEMPLATE`, `EMPTY_CALLERS`, `:1235-1236` `LINK_RE`, `PATH_RE`. Functions: `detect_stack` `:1006`, `declared_stack` `:1022`, `rule_files` `:1030`, `rules_hint` `:1038`, `rules_sync` `:1043`, `codemap` `:1073`, `_git_paths` `:1117`, `changed_code_files` `:1126`, `file_symbols` `:1140`, `find_callers` `:1157`, `callers` `:1203`, `heading_anchors` `:1218`, `docs_files` `:1228`, `docs_check` `:1239`. Estimated 270 lines.

**verification.py** — `:156-158` `FAILURE_LINE_RE`, `DURATION_RE`, `MAX_TAIL_LINE`. Functions: `run_command` `:1456`, `acceptance_check` `:1478`, `acceptance` `:1500`, `quality_module` `:1773`, `quality_state` `:1777`, `quality_files` `:1794`, `quality_measure` `:1805`, `quality_check` `:1810`, `quality_phase` `:1823`, `write_quality_baseline` `:1834`, `quality_init` `:1838`, `quality` `:1849`, `install_quality_baseline` `:1872`, `normal_failure` `:1989`, `failure_lines` `:1994`, `run_phases` `:1999`, `attribute` `:2015`, `baseline` `:2035`, `verify` `:2056`. Estimated 300 lines.

**stage.py** — `:183` `DEFAULT_IGNORE`, `:601` `STAGE_LABELS`, `:1963` `MAX_DIFF_BYTES`. Functions: `tracked_files` `:586`, `digest` `:592`, `stage_owners` `:604`, `git_tree` `:610`, `snapshot` `:630`, `git_state` `:647`, `index_files` `:668`, `content_problems` `:674`, `check_stage` `:701`, `stage_label` `:1903`, `open_stage` `:1909`, `close_stage` `:1923`, `write_fix_diffs` `:1966`, `gate_denials` `:2158`, `gate_reset` `:2162`, `own_failure` `:2169`, `gate_check` `:2185`, `stage_guarded` `:2561`. Estimated 330 lines.

**installer.py** — `:148-152` `INSTALL_GLOBS`, `INSTALL_RECORD`, `RESULT_FILE`, `INSTALL_GITIGNORE`, `:161` `WORKFLOW_NAME`. Functions: `flow_version` `:1276`, `merge_settings` `:1284`, `install` `:1338` (split), `sync_permissions` `:2102`, and the new `flow_history()` (the body of the `flow-history` branch, `:2751-2762`, minus the print). Estimated 230 lines.

**launch.py** — `:162` `TYPE_RE`, `:163` `REVIEW_TOOLS`, `:857-860` `REPORT_FILE_RE`, `REPORT_KEYS`, `SOURCE_RANK`, `:1509-1511` `SEQ_OUTPUT_CAP`, `SEQ_COMMANDS`, `:1566-1568` `PIPELINE_STATE`, `PIPELINE_SPEC`, `:1590` `FENCED_JSON_RE`. Functions: `load_spec` `:768`, `usage_of` `:774`, `run_agent` `:787`, `write_briefs` `:829`, `run_stage` `:841`, `render_prompt` `:852`, `_report_items` `:863`, `_record_items` `:873`, `latest_reports` `:886`, `fix_defects` `:922`, `run_wave` `:935`, `run_acceptance` `:971`, `run_review` `:978`, `run_qa` `:982`, `run_docs` `:986`, `cap_output` `:1514`, `run_steps` `:1526`, `seq` `:1545`, `pipeline_tools` `:1572`, `text_report` `:1593`, `structured_report` `:1605`, `pipeline_module` `:1632`, `brief_module` `:1636`, `run_pipeline` `:1640`, `architecture_type` `:1695`, `pipeline_plan` `:1700`, `freeze_guard` `:1750`, `release_guard` `:1895`, `finish` `:2118`. Estimated 560 lines.

**guardrail.py** — `:189-219` `CLAIM_RE`, `GIT_WRITE_RE`, `FORBIDDEN_BASH`, `GIT_HOOK_BYPASS_RE`, `GIT_COMMIT_N_RE`, `MAX_CHECKED_COMMAND`, `QUOTED_RE`, `:2333` `CLAIM_KINDS`, `:2518` `HOOKS_DEAD_MSG`. Functions: `block` `:2327`, `claimable` `:2337`, `claim` `:2345`, `written_text` `:2374`, `result_text` `:2389`, `content_checks` `:2410`, `claim_required_types` `:2436`, `guard` `:2446` (split), `is_flow_agent` `:2538`, `record_hook_seen` `:2546`, `hooks_static_problem` `:2570`, `hooks_check` `:2590`, `hook` `:2615`. Estimated 380 lines.

**agentic.py** (after) — docstring `:1-62` unchanged; imports; the re-export block (section 6); `cmd_*` handlers from `:2634-2786`; `COMMANDS`; `main`; `if __name__ == "__main__"`. Estimated 420 lines.

Import graph (an arrow means "imports at module level"): `core` ← `manifest_check`, `repo_scan`, `verification`; `stage` → `core`, `verification`; `installer` → `core`, `verification`; `launch` → `core`, `stage`, `repo_scan`; `guardrail` → `core`, `stage`; `agentic` → all. No cycles. Siblings (`compat`, `upgrade`, `pipeline`, `brief`, `quality`, `waiting`) are leaves.

## 6. Contracts between modules
All moved functions keep their names, parameters, return values, messages and exit codes exactly. Below are only the new names and the splits.

```python
# core.py
ENTRY = HERE / "agentic.py"   # the entry script, live or frozen: what subprocesses and run_steps execute

# manifest_check.py — validate(manifest) -> list[str] keeps its signature and returns the same strings in the same
# order as today. It is now a sum of families, each ≤ 60 lines, each returning a list:
def maintainer_errors(manifest) -> list      # :386-392 (the flag's type and the flow-repo check)
def package_errors(manifest, table) -> list  # :393-430 (empty table, reserved IDs, acceptance command, the per-WP loop with mirror_errors and depends_on)
def ownership_errors(manifest, maintainer) -> list  # :431-454 (files as lists, path shape, never-owned/.claude, two owners)
def command_errors(manifest) -> list         # :455-466 (allow_bash rules, acceptance/verify commands)
def shape_errors(manifest) -> list           # :467-472 (ignore, verify object)
# validate = maintainer_errors + package_errors + ownership_errors + command_errors + shape_errors
#            + stack_errors + docs_errors + agent_model_errors   (the last three exist today, :473-474 call them)
# `maintainer = maintainer_mode(manifest)` (:392) is computed once in validate and passed to ownership_errors.

# installer.py — install(target, force=False, dry_run=False, allow_dirty=False) keeps its signature, output and exits.
def install_plan(target, upgrade, force) -> dict
    # :1342-1370. Returns {"record", "previous", "history", "sources", "plan", "removed", "intact"}; `intact` is the
    # closure of :1355-1357 returned as a callable. Dies (:1344-1347) as today.
def install_guard(target, plan, dry_run, allow_dirty) -> list
    # :1371-1382 (`guarded`, `guard_problems`, the git and blocking exits). Returns `problems`; prints and exits 3 as today.
def install_write(target, plan, dry_run) -> tuple
    # :1383-1416 (the copy loop with the `kept` rule, removals, merge_settings, .gitignore, agentic.json, the record).
    # Returns (report, settings_added, missing_ignore, config_missing).
def install_report(target, plan, written, dry_run, problems) -> None
    # :1417-1453. Every print, the rules-sync, quality-baseline and validate subprocesses (through ENTRY), notes, warnings.
def flow_history() -> dict
    # :2754-2760: build_history through sibling("upgrade"), write .claude/flow-history.json, return the summary
    # dict {"paths", "hashes", "generated_from"}; a ValueError from build_history dies with "flow-history: <e>".

# guardrail.py — guard(data) keeps its signature; it calls these in this order and returns where today returns:
def universal_checks(tool, tinput, agent_id, owner_id) -> None     # :2452-2457 (command length, git hook bypass)
def resolve_owner(data, tool, tinput, agent_id, owner_id) -> tuple
    # :2459-2466 only. Returns (claimed, owner_id): a claim command claims and returns (True, None), and guard
    # returns at once; otherwise (False, owner) with the owner from the environment or the claims file, or None.
def report_gate(owner_id, tinput) -> None                          # :2467-2478 (StructuredOutput: the stop gate; guard returns after it)
def require_claim(data, agent_id, owner_id) -> None                # :2479-2481 (the "First of all, run ... claim" block)
def bash_rules(owner_id, cmd) -> None                              # :2485-2490 (FORBIDDEN_BASH)
def write_rules(data, owner_id, tool, tinput) -> None              # :2492-2515 (path resolution, protected paths, ownership, content_checks)
# guard itself: ≤ 25 lines, in today's order: universal_checks; resolve_owner (return if claimed); if StructuredOutput:
# report_gate and return; require_claim; if no owner: return (:2482-2483); if Bash: bash_rules and return; write_rules.

# agentic.py
COMMANDS = {"hook": cmd_hook, "hooks-check": cmd_hooks_check, ...}   # the 34 names of the docstring, same spelling
def cmd_<name>(args) -> int | None   # one per command; the body of today's branch, with its argument checks
def main() -> None
    # compat.utf8_stdio(); no argument or unknown command -> die(__doc__); handler = COMMANDS[cmd];
    # code = handler(args); sys.exit(code) when code is an int. Handlers that exit themselves keep doing so.
# `snapshot`, `check-wave` and `run-wave` share the argument check of :2772-2773: a helper stage_arg(cmd, args) -> str.
```

The re-export block of `agentic.py`: the 23 names other files read as `agentic.X`, `load_spec` (which `test_acceptance_v25.py:249-256` calls on the frozen `agentic.py` loaded as module `m`), `require_valid` (the handlers use it), and `compat`. Documentation only: the annotations in this section are not written in the code.
```python
import compat
from core import (ROOT, GUARD_DIR, QUALITY_BASELINE, SKIP_DIRS, USAGE, is_flow_repo, maintainer_mode,
                  never_owned_problem, flow_path_refused, locked_json, usage_records, status_to_state)
from manifest_check import validate, frontmatter_model, require_valid
from repo_scan import PATH_RE
from verification import attribute, run_command, quality_files
from installer import merge_settings
from launch import structured_report, run_steps, render_prompt, release_guard, load_spec
```
`agentic.py` imports every module it dispatches to; nothing else in the repo imports a new module except `test_agentic.py` for its four patches.

## 7. Conventions
- The "consumes" lists of section 8 name what each module needs from `core`, but they are not exhaustive. A name missing from `from core import (...)` fails only at run time, in WP-09's suites, which cannot edit the module. So every module WP's validation runs `python3 .claude/bin/agentic.py quality` and the undefined-names check: a scratchpad script that parses the module with `ast`, collects every `Name` in `Load` context, and asserts each is a builtin, a module-level binding, a function parameter or local, or a loop/comprehension target. Known omissions found in review: WP-04 needs `die`; WP-06 needs `DEFAULT_CONFIG`; WP-08 needs `ledger_update`, `stage_of`, `now_hm`, `ARCHIVE_DIR`.
- English. No type annotations in the shipped scripts (3.9, frozen guard). This contradicts `.claude/rules/agentic/python.md`; the plan wins.
- A new module: shebang-less, module docstring in the style of `brief.py:1-6`, stdlib imports, then `sys.path.insert(0, str(Path(__file__).resolve().parent))` and `import compat` as `waiting.py:15-16`, then `from core import (...)` with explicit names. Never `import *`. Never `import agentic` from a module (it would be a cycle).
- **Moves are verbatim, with one permitted edit.** A function's body, docstring and comments are copied unchanged; only `Path(__file__)` becomes `HERE`/`ENTRY`, the imports change, and a line over 120 characters is re-wrapped (a new module has no long-line allowance; `agentic.py` has 45 such lines outside its docstring). A re-wrap must not change a string's text. `INSTALL_GLOBS` is written one entry per line. Section 6 names the only functions whose bodies are restructured.
- **Name binding and patches.** Modules bind names with `from core import ROOT`; a test that patches must target the module whose function reads the name: `mock.patch.object(core, "USAGE", ...)` for `usage_records`, `mock.patch.object(core, "is_flow_repo", ...)` for `maintainer_mode`, `mock.patch.object(launch, "ROOT", ...)` for `release_guard`.
- Every function ≤ 60 lines and nesting ≤ 4; every module ≤ 800 lines; no line over 120 characters in a new module (the ratchet counts them as new files with no allowance).
- Messages, exit codes and output are byte-identical to today; `test_agentic.py` asserts many of them.
- One commit per WP; no model names.

## 8. Work packages and acceptance criteria
### Acceptance criteria
In a refactor the acceptance is the existing suites. The criteria name the checks that make a wrong split visible.

- AC-001 · Every suite is green after the split
  - Scenario: the repository after WP-09.
  - Action: run the commands of section 3.
  - Expected: `.claude/bin` (444 tests today), `test_workflow.mjs` (39 scenarios), `acceptance`, `qa`, `bench`, `bench/acceptance` all pass; `compileall` exits 0.
  - Must not: no test is skipped, deleted or weakened to pass. The only test edits are WP-09's: the four patch targets, `agentic_subcommands`, `FLOW_MODULES`, the new `StructureTests`, and the two tests that today read `agentic.py` as text (`test_definitions.py:287-291` finds `STACK_SIGNALS = {`, `:424-429` finds `INSTALL_GLOBS = [`), which read `repo_scan.STACK_SIGNALS` and `installer.INSTALL_GLOBS` instead.
  - Check: the suites themselves, run by WP-09's validation and by CI.
  - WP: WP-09 (WP-01 also lists it: `core` is the first file every suite imports after the split)
- AC-002 · The ratchet is green without touching the baseline
  - Scenario: the repository after WP-09, `.claude/quality-baseline.json` as committed today.
  - Action: `python3 .claude/bin/agentic.py quality`.
  - Expected: exit 0, `"violations": 0`. Every new module ≤ 800 lines with 0 long lines; every function in a new module ≤ 60 lines and nesting ≤ 4; `agentic.py::main` ≤ 60.
  - Must not: the baseline is not edited by any WP; no `exclude` entry is added.
  - Check: `test_definitions.StructureTests.test_quality_is_green` (new, WP-09) runs the command and asserts exit 0; each module WP runs the command in its validation.
  - WP: WP-01 to WP-09 (each module WP for its own file; WP-09 for `agentic.py`)
- AC-003 · `agentic.py` keeps its public names and the frozen copy works
  - Scenario: `import agentic` from `.claude/bin`.
  - Action: read every name of the re-export block of section 6 as an attribute; run `test_acceptance_v25.FrozenCopyTests` (the frozen `validate` and `load_spec`).
  - Expected: every attribute exists and is the same object as the module's (`agentic.validate is manifest_check.validate`); the frozen tests pass.
  - Must not: `agentic.py` must not define a second copy of any moved function.
  - Check: `test_definitions.StructureTests.test_reexports_are_the_modules_objects` (new, WP-09); `test_acceptance_v25.FrozenCopyTests` (existing).
  - WP: WP-09
- AC-004 · The dispatch table covers the documented commands
  - Scenario: `agentic.COMMANDS` and the docstring of `agentic.py`.
  - Action: compare `set(COMMANDS)` with the commands the docstring lists (every line matching `^  ([a-z][\w-]+)` under `Subcommands:`).
  - Expected: equal sets, 34 names (the 31 `elif` branches plus `snapshot`, `check-wave` and `run-wave`); `test_cited_commands_exist` passes for every doc.
  - Must not: `agentic_subcommands()` must not parse source text; an unknown command still prints the usage and exits 1.
  - Check: `test_definitions.StructureTests.test_commands_match_the_docstring` (new, WP-09); `test_cited_commands_exist` (existing).
  - WP: WP-09
- AC-005 · Install ships the modules and a project runs them
  - Scenario: the CI job `installed`, and `test_definitions.test_what_is_installed_exists`.
  - Action: install into an empty project, run `quality` and the shipped suite there.
  - Expected: the eight modules are present in the project; the shipped suite passes; `INSTALL_GLOBS` has one entry per module.
  - Must not: a project that kept an edited `agentic.py` must not break: the old monolith stays self-contained and the new modules sit beside it unused (install's "kept" rule, `agentic.py:1387-1390` today).
  - Check: `test_what_is_installed_exists` (existing); the `installed` CI job.
  - WP: WP-06 (`INSTALL_GLOBS`), WP-09
- AC-006 · Release
  - Scenario: this repository after WP-10.
  - Action: read the files.
  - Expected: `plugin.json` is `2.8.0`; `upgrade.NOTES["2.8.0"]` exists and mentions the eight module names and that an edited `agentic.py` kept by install keeps working alone; `docs/how-it-works.md` lists each new module under `.claude/bin` with one line each.
  - Must not: no version pinned in any test.
  - Check: `test_the_version_has_its_upgrade_note` (existing); `test_definitions.StructureTests.test_docs_list_every_module` (new, WP-09, reads the how-it-works tree).
  - WP: WP-10

### Work packages
Expand-contract: waves 1-4 create modules beside the monolith (duplicate code, every suite still green through the untouched `agentic.py`); WP-09 rewires `agentic.py` and deletes the duplicates. Each module is created by copying the line ranges of section 5.

#### WP-01 · `core.py`
- Wave: 1.
- Files: `.claude/bin/core.py`.
- Contracts: implements `core.py` of sections 5-6; consumes nothing.
- ACs: AC-001 (its share), AC-002.
- **Patterns to mirror:** `waiting.py:1-16` (module header), `agentic.py:76-119` (paths; move verbatim), `brief.py:1-6` (docstring).
- **Gotchas:** `ROOT` depends on `CLAUDE_PROJECT_DIR` at import, as today (`:86`); `FROZEN` is computed before `SOURCE_ROOT` and `ROOT` (`:84-86`); `ledger_render` (`:2274`) calls `sibling("waiting")`, so `sibling` must be defined above it or be a plain function (it is); `stop` (`:2310`) uses `subprocess` and `time`. Keep the `# ---------- ... ----------` section comments.
- **WP validation:** `python3 -m compileall -q .claude/bin`; an import check (a scratchpad script: `import core; print(core.ROOT, core.ENTRY)` with `.claude/bin` on `sys.path`; `allow_bash` has no `python3 -c`, so validations use scripts, not inline code); `python3 .claude/bin/agentic.py quality` (exit 0: the new file is measured); the `.claude/bin` suite (unchanged, green).

#### WP-02 · `manifest_check.py`
- Wave: 2, after WP-01.
- Files: `.claude/bin/manifest_check.py`.
- Contracts: implements the `validate` split of section 6; consumes `core` by implementation.
- ACs: AC-002.
- **Patterns to mirror:** `agentic.py:482-506` (`stack_errors`, `docs_errors`: a family returns a list), `:549-570` (`mirror_errors`).
- **Gotchas:** the order of the returned errors must not change: `test_agentic.ValidateTests` and the frozen acceptance files assert on specific messages and sometimes on `errors[0]`. Concatenate the families in the order of section 6. `package_errors` is the only one near 40 lines; its `continue` statements stay.
- **WP validation:** `compileall`; an import check; `quality` exit 0; a throwaway comparison script that imports both `agentic` and `manifest_check` and asserts `agentic.validate(m) == manifest_check.validate(m)` for the manifests of `test_agentic.MANIFEST` and `test_acceptance_v25.manifest(True)`.

#### WP-03 · `repo_scan.py`
- Wave: 2, after WP-01.
- Files: `.claude/bin/repo_scan.py`.
- Contracts: verbatim moves; consumes `core` (`source_files`, `symbol_re`, `SKIP_DIRS`, `RULES_LIBRARY`, `RULES_DIR`, `ROOT`).
- ACs: AC-002.
- **Patterns to mirror:** `agentic.py:1108-1116` (section comment and constants).
- **Gotchas:** `codemap` (`:1073-1105`) is 33 lines; `find_callers` (`:1157-1200`) is 44: both fit. `PATH_RE` is re-exported by `agentic` (used by `acceptance/test_docs.py`).
- **WP validation:** `compileall`; import check; `quality` exit 0.

#### WP-04 · `verification.py`
- Wave: 2, after WP-01.
- Files: `.claude/bin/verification.py`.
- Contracts: verbatim moves; consumes `core` (`child_env`, `load_config`, `source_files`, `symbol_re`, `is_flow_repo`, `ledger_stage`, `at_entity`, `wps`, `STATE`, `ROOT`, `BASELINE`, `GUARD_DIR`, `QUALITY_BASELINE`, `VERIFY_PHASES`, `LEDGER_STATES`, `sibling`).
- ACs: AC-002.
- **Patterns to mirror:** `agentic.py:1771-1774` (`quality_module` through `sibling`).
- **Gotchas:** `install_quality_baseline` (`:1872-1892`) runs `quality --init` as a subprocess of `Path(__file__)`: use `ENTRY`. `verify` (`:2056-2099`) is 44 lines, nesting 4: it fits as is. `run_command` (`:1456`) uses `compat.resolve`, `compat.group_kwargs`, `compat.kill_tree`.
- **WP validation:** `compileall`; import check; `quality` exit 0.

#### WP-05 · `stage.py`
- Wave: 3, after WP-04.
- Files: `.claude/bin/stage.py`.
- Contracts: verbatim moves; consumes `core` and `verification` (`attribute`, `acceptance_check`, `normal_failure`, `run_command`) by implementation.
- ACs: AC-002.
- **Patterns to mirror:** `agentic.py:584-607` (section header, `STAGE_LABELS` built from the `*_entity` functions).
- **Gotchas:** `STAGE_LABELS` (`:601`) maps labels to `core` functions: import them explicitly. `snapshot` (`:630`) calls `sibling("waiting").clear(STATE)`. `check_stage` (`:701-755`) is 55 lines, nesting ≤ 4: fits. `gate_check` (`:2185`) runs the acceptance command through `run_command` with `GATE_TIMEOUT_S`.
- **WP validation:** `compileall`; import check; `quality` exit 0.

#### WP-06 · `installer.py`
- Wave: 3, after WP-04.
- Files: `.claude/bin/installer.py`.
- Contracts: implements the `install` split and `flow_history` of section 6; consumes `core` (`SOURCE_ROOT`, `ENTRY`, `die`, `sibling`, `flow_hooks`, `is_old_hook_command`, `at_entity`, `qa_entity`, `ROOT`), `verification` (`install_quality_baseline`). It does not use `stage` (`install` hashes with `compat.content_hash`).
- ACs: AC-002, AC-005.
- **Patterns to mirror:** `agentic.py:1338-1453` (`install`; the closures `shipped` and `intact` become parameters or module functions), `:2751-2762` (the `flow-history` branch).
- **Gotchas:** `INSTALL_GLOBS` gains the eight modules in this WP, in the same list style as `:148-149`; the `rules-sync` and `quality --init` subprocesses run `ENTRY`, not `__file__`. `install` prints in a fixed order that `test_agentic.InstallTests` and `test_acceptance_v27.InstallTests` assert (`quality baseline: ...`, `rules: ...`, `upgrade notes:`); keep the order of `:1417-1453`. The `kept` rule (`:1387-1390`) writes the new version under `.claude/state/upgrade/`.
- **WP validation:** `compileall`; import check; `quality` exit 0; a scratchpad script comparing `installer.install` and `agentic.install` with `dry_run=True` into the same temporary git repo, under `mock.patch.object(installer, "INSTALL_GLOBS", agentic.INSTALL_GLOBS)` (the new list names modules the monolith does not ship yet): identical stdout.

#### WP-07 · `launch.py`
- Wave: 4, after WP-03 and WP-05.
- Files: `.claude/bin/launch.py`.
- Contracts: verbatim moves; consumes `core`, `stage` (`snapshot`, `stage_owners`, `check_stage`, `STAGE_LABELS`), `repo_scan` (`rule_files`, `rules_hint`).
- ACs: AC-002.
- **Patterns to mirror:** `agentic.py:1507-1512` (section header), `:1627-1637` (`sibling` users).
- **Gotchas:** `run_steps` (`:1526-1542`) defaults its script to `Path(__file__)`: use `ENTRY`, and keep the `script` parameter (the pipeline's gate passes the frozen path). `run_pipeline` (`:1640-1692`) is 53 lines: fits. `freeze_guard` (`:1750-1768`) copies `ROOT/.claude/bin/*.py` except tests: unchanged, it now also copies the modules. `release_guard` is the function `test_agentic.py:1770` patches `ROOT` for: it reads `ROOT` bound in `launch`.
- **WP validation:** `compileall`; import check; `quality` exit 0.

#### WP-08 · `guardrail.py`
- Wave: 4, after WP-05.
- Files: `.claude/bin/guardrail.py`.
- Contracts: implements the `guard` split of section 6; consumes `core` (`locked_json`, `with_claims`, `load_manifest`, `entities`, `at_entity`, `codemap_path`, `owns`, `maintainer_mode`, `flow_path_refused`, `flow_hooks`, `is_old_hook_command`, the content regexes, `ROOT`, `STATE`, `HOOK_SEEN`, `CLAIMS`, `WP_ID_RE`, `GATE_MAX_DENIALS`, `READ_ONLY_AGENTS`, `WORKER_MODEL`), `stage` (`gate_check`, `gate_denials`).
- ACs: AC-002.
- **Patterns to mirror:** `agentic.py:2446-2515` (`guard`, the phases in order), `:2615-2629` (`hook`: fail closed).
- **Gotchas:** the order of checks in `guard` decides which message an agent sees; `test_agentic.HookWriteTests`, `HookBashTests`, `StopGateTests`, `V2EntityTests` and `test_acceptance_v27.GuardTests` assert them. `hook()` must keep its `try/except SystemExit/except Exception` shape (`:2615-2629`). `hooks_check` (`:2590-2612`) reads `.claude/settings.json` through `flow_hooks`.
- **WP validation:** `compileall`; import check; `quality` exit 0; the hook tests run against the live `agentic.py` and stay green only after WP-09; here, a scratchpad script that feeds `test_agentic.write_payload("src/a.py")` to `guardrail.guard` inside a `test_agentic.Repo` (with `CLAUDE_PROJECT_DIR` set before importing) and sees the same exit as `agentic.guard`.

#### WP-09 · `agentic.py` becomes the entry point; tests follow
- Wave: 5, after WP-06, WP-07, WP-08 and WP-10 (its docs test reads what WP-10 writes).
- Files: `.claude/bin/agentic.py`, `.claude/bin/test_agentic.py`, `.claude/bin/test_definitions.py`, `.claude/bin/test_acceptance_portable.py`.
- Contracts: implements `COMMANDS`, `cmd_*`, `main`, the re-export block; consumes every module by implementation.
- ACs: AC-001, AC-002, AC-003, AC-004, AC-005, AC-006 (the docs test).
- **Patterns to mirror:** `agentic.py:2634-2786` (each branch's checks and prints, verbatim into its handler), `test_definitions.py:380-392` (`PluginTests` style for the new `StructureTests`).
- **Gotchas:**
  - Delete every moved definition from `agentic.py`; AC-003 forbids duplicates. What remains: docstring, imports, re-exports, handlers, `COMMANDS`, `main`, the `__main__` guard.
  - `main()` ≤ 60 lines; `cmd_save_result` (`:2699-2714`, 16 lines) and `cmd_codemap` (`:2727-2737`) are the largest handlers.
  - `test_agentic.py`: the four patch targets of section 7; nothing else changes.
  - `test_definitions.agentic_subcommands()` returns `set(agentic.COMMANDS)`; add `StructureTests` with the four tests named in AC-002, AC-003, AC-004 and AC-006. `test_quality_is_green` and `test_docs_list_every_module` carry `@FLOW_REPO_ONLY` (`test_definitions.py:26`): the suite ships to projects (`upgrade.EXTRA_GLOBS`) and the CI `installed` job runs it there, where there is no how-it-works and the ratchet would measure the project. `test_docs_list_every_module` asserts that the `.claude/bin` tree of `docs/how-it-works.md` contains `── <module>.py` for each of the eight modules.
  - `test_acceptance_portable.FLOW_MODULES` gains the eight module file names, one per line: the file's long-line allowance is already used by `:259`.
  - The docstring is unchanged; `die(__doc__)` for no command and for an unknown one. `qa/test_qa_docs.py:190-198` requires every flag the docs cite to appear in `agentic.py`'s text: the docstring is what keeps them there.
  - `hook.py` is not touched: it runs `agentic.py` with `sys.argv = [target, "hook"]`.
- **WP validation:** every command of section 3, bench included, plus `python3 .claude/bin/agentic.py quality` (exit 0) and `python3 .claude/bin/agentic.py validate`.

#### WP-10 · Version, note and docs
- Wave: 1 (it depends on nothing; WP-09 reads its output).
- Files: `.claude-plugin/plugin.json`, `.claude/bin/upgrade.py`, `docs/how-it-works.md`.
- Contracts: none.
- ACs: AC-006.
- **Patterns to mirror:** `upgrade.py:99-112` (the 2.7.x notes), `docs/how-it-works.md:312-321` (the `.claude/bin` tree).
- **Gotchas:** `docs/how-it-works.md:312-313` describes `agentic.py` as the owner of every command: rewrite those two lines as the entry point and dispatch, and add one line per module. `test_the_version_has_its_upgrade_note` requires `NOTES["2.8.0"]`; `qa/test_qa_docs.py` caps README at 150 lines and the hub at 260 (neither is edited here). The how-it-works tree uses `│   ├──` box characters: copy a line.
- **WP validation:** `python3 -m unittest discover -s .claude/bin -p "test_definitions.py"`, `python3 -m unittest discover -s acceptance`, `python3 -m unittest discover -s qa`.

```json wp-manifest
{
  "maintainer": true,
  "stack": ["python", "typescript"],
  "allow_bash": ["Bash(python3 -m unittest:*)", "Bash(python3 -m compileall:*)", "Bash(node .claude/bin/test_workflow.mjs)", "Bash(python3 .claude/bin/agentic.py quality)", "Bash(python3 .claude/bin/agentic.py validate)"],
  "verify": {"build": "python3 -m unittest discover -s qa", "lint": "node .claude/bin/test_workflow.mjs", "types": "python3 -m unittest discover -s acceptance", "tests": "python3 -m unittest discover -s .claude/bin -p \"test_*.py\""},
  "docs": {"files": ["docs/assets/"], "codemap": null},
  "_docs_note": "the docs zone is a placeholder that overlaps nothing: WP-10 owns the documentation this change touches",
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": [".claude/bin/core.py"], "acs": ["AC-001", "AC-002"], "mirror": [".claude/bin/waiting.py:1-16", ".claude/bin/core.py", ".claude/bin/brief.py:1-6"]},
    {"id": "WP-02", "wave": 2, "depends_on": ["WP-01"], "files": [".claude/bin/manifest_check.py"], "acs": ["AC-002"], "mirror": [".claude/bin/manifest_check.py"]},
    {"id": "WP-03", "wave": 2, "depends_on": ["WP-01"], "files": [".claude/bin/repo_scan.py"], "acs": ["AC-002"], "mirror": [".claude/bin/repo_scan.py"]},
    {"id": "WP-04", "wave": 2, "depends_on": ["WP-01"], "files": [".claude/bin/verification.py"], "acs": ["AC-002"], "mirror": [".claude/bin/verification.py"]},
    {"id": "WP-05", "wave": 3, "depends_on": ["WP-04"], "files": [".claude/bin/stage.py"], "acs": ["AC-002"], "mirror": [".claude/bin/stage.py"]},
    {"id": "WP-06", "wave": 3, "depends_on": ["WP-04"], "files": [".claude/bin/installer.py"], "acs": ["AC-002", "AC-005"], "mirror": [".claude/bin/installer.py"]},
    {"id": "WP-07", "wave": 4, "depends_on": ["WP-03", "WP-05"], "files": [".claude/bin/launch.py"], "acs": ["AC-002"], "mirror": [".claude/bin/launch.py"]},
    {"id": "WP-08", "wave": 4, "depends_on": ["WP-05"], "files": [".claude/bin/guardrail.py"], "acs": ["AC-002"], "mirror": [".claude/bin/guardrail.py"]},
    {"id": "WP-09", "wave": 5, "depends_on": ["WP-06", "WP-07", "WP-08", "WP-10"], "files": [".claude/bin/agentic.py", ".claude/bin/test_agentic.py", ".claude/bin/test_definitions.py", ".claude/bin/test_acceptance_portable.py"], "acs": ["AC-001", "AC-002", "AC-003", "AC-004", "AC-005", "AC-006"], "mirror": [".claude/bin/agentic.py", ".claude/bin/test_definitions.py:380-392"]},
    {"id": "WP-10", "wave": 1, "depends_on": [], "files": [".claude-plugin/plugin.json", ".claude/bin/upgrade.py", "docs/how-it-works.md"], "acs": ["AC-006"], "mirror": [".claude/bin/upgrade.py:99-112"]}
  ]
}
```

## 9. Test strategy
- No acceptance tests are written: the acceptance is the existing suites (refactor). The manifest therefore has no `acceptance` block; `verify.tests` runs the `.claude/bin` suite.
- Unit: each module WP's validation imports the module and, where the body was restructured (`validate`, `install`, `guard`), compares the new function with the monolith's on the same inputs before WP-09 deletes the original.
- WP-09 adds `StructureTests` to `test_definitions.py`: ratchet green, re-exports are the modules' objects, `COMMANDS` equals the docstring's list, how-it-works lists every module.
- After WP-09: every suite of section 3, the `installed` CI job, and `agentic.py quality` exit 0 before any baseline edit. Then the maintainer runs `agentic.py quality --update`, which drops the `main`, `install`, `validate` and `guard` entries and lowers the `agentic.py` file entry; commits the baseline.
- The run is executed by hand, sequentially in wave order.

## 10. Decisions
- **Eight modules by domain** (user's choice) over five coarser ones (two would start near the 800-line limit) or a table-only change (leaves 2,790 lines frozen).
- **Split `install`, `validate` and `guard`** (user's choice) rather than move them and rewrite their baseline keys by hand. The split follows the families `validate` already uses.
- **Re-exports in `agentic.py`** for the 23 names other files read, so no frozen acceptance file changes and `test_agentic.py` keeps importing `agentic`. The alternative (tests import the modules) would edit three frozen files and hundreds of lines.
- **`from core import name`** in modules, not `import core` plus `core.name`: bodies stay verbatim and the diff is a move. The cost is that patches must target the reading module (section 7, four sites).
- **`source_files`, `symbol_re`, `child_env`, `flow_hooks`, `is_old_hook_command` go to `core`**, not to the domain of their section: each is used by two or more domains, and leaving them where they sit would add import edges (`verification → repo_scan`, `guardrail → installer`) and one more wave each.
- **The frozen-guard functions (`freeze_guard`, `release_guard`) go to `launch`**, where `pipeline_plan` calls them, instead of the `ratchet` module the interview mentioned; `verification` holds the ratchet and the verify phases.
- **`flow_history` becomes a function in `installer`** (it reads `INSTALL_GLOBS` and `upgrade`); the handler only prints.
- **Expand-contract in five waves.** Modules import real siblings at module level, so a module cannot be validated before its dependencies exist: waves follow the import DAG, with three WPs in parallel in waves 2 and 4. A single wave would require stubbing imports, and the user executes by hand anyway.
- **`test_acceptance_portable.FLOW_MODULES` is edited** although the file is frozen: its encoding check is the only one that reads every shipped module as bytes, and leaving the eight out would be a coverage gap on Windows.
- **Version 2.8.0** (user's choice): projects receive eight new files and a different `agentic.py`.
- **`test_agentic.py` is not split** (user's choice): a follow-up.
- **Reuse:** `sibling`, `compat`, the existing error families of `validate`, the `installed` CI job, the ratchet as the size check. No new dependency.

## 11. Risks and open questions
- **A broken module import fails open.** Today a syntax error anywhere in `agentic.py` stops the hook before `hook()`'s try block too, so this is not new, but the surface grows: eight files. `compileall` in CI and `test_acceptance_v25.FrozenCopyTests` cover it; a project's `hooks-check` does not. Not mitigated further.
- **Hook latency.** The hook now imports eight modules instead of parsing one file; bytecode caches make this comparable, but it is not measured. If a run shows the hook slower, `guardrail` could import `stage` lazily inside `report_gate`; not planned.
- **A project that kept an edited `agentic.py`** gets the new modules beside the old monolith. The monolith is self-contained and keeps working; the modules are unused there. `install` reports the file as kept, as today.
- **Name clashes on `sys.path`.** `core`, `stage`, `launch` are generic names; the flow's folder is inserted at position 0, so they win over anything else importable, and nothing in the stdlib has those names. A project with its own `core.py` in `.claude/bin` is not a supported layout.
- **Patch targets.** A future test that patches `agentic.X` for a moved function will silently patch a re-export and test nothing. Section 7 states the rule; `StructureTests.test_reexports_are_the_modules_objects` makes the aliasing visible.
- **The maintainer guard during this run** is the pre-refactor copy and executes the monolith; fine, since the run is by hand.
- **Line counts are estimates** from today's inventory, not measured; `quality` (AC-002) is the measurement. If a module lands over 800 lines, split it along its section comments before WP-09.
- **The manifest's `mirror` references named line ranges of the pre-refactor `agentic.py`** (section 4b keeps them for reading). Once WP-09 shrank the file, `validate` rejected them as out of range, so the manifest now names the module each pattern moved to; the WP texts keep the original ranges.
- **One more frozen-file edit, found at the end:** `test_acceptance_v25.HookTests.test_ac_004` loosens the live `guard` by editing `agentic.py`; after the split it edits `guardrail.py` (one line). AC-001's list did not foresee it.
- **Rollback:** revert the pull request; projects on 2.7.x are unaffected until they install 2.8.0.
