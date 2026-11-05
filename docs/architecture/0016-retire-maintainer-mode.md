# Architecture: retire maintainer mode; a flow plan runs by hand (issue 100, agentic-flow 2.10.0)
Type: change · Size: standard

## 1. Goal
Maintainer mode (design 0012, 2.5.0) was meant to let the flow's agents change the flow itself, judged by a frozen copy of the guard. It never worked: Claude Code refuses writes under `.claude/` from the agents the flow starts, so designs 0013, 0014 and 0015 were executed by hand. This change removes the frozen guard and everything around it (the copy in `.claude/state/guard/`, `pipeline-plan --keep-guard`, `guard-release`, the plan's `maintainer` and `agentic` fields, the engines' gate command through the copy, `hook.py`'s frozen branch, the permission and the gatekeeper rule for the copy). The `"maintainer": true` key stays with a smaller meaning: a plan for the agentic-flow repository itself, which `validate` accepts with `.claude/` files and which every agent launcher refuses to run, because it is executed by hand. `install` removes the copy's permission from projects' settings.

## 2. Scope
### Included
- `core.py`: remove `GUARD_DIR`, `GUARD_CMD`, `FROZEN`; `SOURCE_ROOT` is always `HERE.parents[1]`; `flow_path_refused(path)` loses its second parameter; new `refuse_by_hand_plan(manifest)` and `BY_HAND_PLAN`.
- `manifest_check.py`: unchanged rules for the flag (boolean; true only in the flow repository) and for never-owned paths; messages reworded.
- `stage.py`, `guardrail.py`: runtime always refuses `.claude/` writes.
- `hook.py`: always runs the live `agentic.py`.
- `launch.py`: no freeze or release; `run_steps` loses `script`; `guard-release` leaves `SEQ_COMMANDS`; the pipeline spec is always the live one.
- `agentic.py`: `pipeline-plan` takes no argument; `guard-release` is removed; `require_runnable()` refuses a by-hand plan in every command that starts agents; re-exports updated.
- `installer.py`: `merge_settings` removes the retired permission.
- Engines: `pipeline.py` and `agentic-implement.js` always use the live command, never `--keep-guard`, never call `guard-release`; the three maintainer scenarios leave `conformance.json`.
- `.claude/settings.json`, `.claude/agents/gatekeeper.md`: the copy's permission and rule removed.
- `upgrade.py` `NOTES["2.10.0"]` and `plugin.json` version `2.10.0`.
- Docs: `docs/how-it-works.md`, `docs/how-to/README.md`.
- Tests: the maintainer tests in `test_agentic.py`, `test_definitions.py`, `test_pipeline.py`, `test_workflow.mjs`, the resume assertion in `test_acceptance.py`, the count in `test_acceptance_v29.py`; `test_acceptance_v25.py` is deleted.

### Excluded (non-goals)
- Moving the flow's source out of `.claude/` (issue 100, option 1) and `bypassPermissions` (option 2).
- Retiring the other per-release acceptance files: design 0017 (issue 99), next on the same branch and in the same release.
- Regenerating `.claude/flow-history.json`: done by hand as the last commit of the branch, after design 0017.
- Deleting a leftover `.claude/state/guard/` folder in projects: it is untracked state, and nothing reads it any more.
- Renaming the `maintainer` key or `maintainer_mode()`: archived plans (0012 to 0015) carry the key, and tests import the function.

## 3. Stack
- Python 3.9+ standard library only; Node 22 for `test_workflow.mjs`. No new dependency.
- Acceptance: `python3 -m unittest discover -s .claude/bin -p test_acceptance_v210.py`
- Everything: `python3 -m unittest discover -s .claude/bin -p "test_*.py"`, `python3 -m unittest discover -s bench -p "test_*.py"`, `python3 -m unittest discover -s bench/acceptance`, `node .claude/bin/test_workflow.mjs`, `python3 .claude/bin/agentic.py quality`.

## 4. Repository structure
```
.claude/bin/core.py                      WP-01  guard constants out; flow_path_refused(path); refuse_by_hand_plan
.claude/bin/manifest_check.py            WP-01  messages; ownership_errors keeps the never-owned rule
.claude/bin/stage.py                     WP-01  flow_path_refused(path)
.claude/bin/guardrail.py                 WP-01  flow_path_refused(rel)
.claude/bin/hook.py                      MAINT  live agentic.py only (never owned: edited by the maintainer)
.claude/bin/verification.py              WP-01  one docstring
.claude/bin/launch.py                    WP-02  no freeze/release; refusals; run_steps without script
.claude/bin/agentic.py                   WP-02  pipeline-plan without arguments; guard-release removed
.claude/bin/installer.py                 WP-02  merge_settings removes the retired permission
.claude/bin/test_agentic.py              WP-02  MaintainerModeTests rewritten
.claude/bin/test_definitions.py          WP-02  settings, gatekeeper and re-export expectations
.claude/bin/test_acceptance_v29.py       WP-02  COMMANDS count no longer pinned
.claude/bin/pipeline.py                  WP-03  live command only; no --keep-guard, no guard-release
.claude/workflows/agentic-implement.js   WP-03  the same
.claude/bin/conformance.json             WP-03  three maintainer scenarios removed
.claude/bin/test_pipeline.py             WP-03  maintainer assertions removed
.claude/bin/test_workflow.mjs            WP-03  the same
.claude/bin/test_acceptance.py           WP-03  resumed run calls plain pipeline-plan
.claude/bin/test_acceptance_portable.py  WP-03  one comment (:259) about maintainer mode
.claude/settings.json                    MAINT  the copy's permission removed (never owned: edited by the maintainer)
.claude/agents/gatekeeper.md             WP-04  only the live command
.claude/bin/upgrade.py                   WP-04  NOTES["2.10.0"]
.claude-plugin/plugin.json               WP-04  version 2.10.0
.claude/bin/test_acceptance_v25.py       WP-04  deleted
docs/how-it-works.md                     WP-04  maintainer paragraph and module tree
docs/how-to/README.md                    WP-04  the pipeline-plan line
.claude/bin/test_acceptance_v210.py      AT     acceptance tests
```

## 4b. Existing code context
| What an implementer needs to know | Where it is (`file:lines`) | Pattern or rule |
|---|---|---|
| The guard constants and the frozen detection; `SOURCE_ROOT` depends on `FROZEN` | `.claude/bin/core.py:1-29` | Delete `GUARD_DIR`, `GUARD_CMD`, `FROZEN` and `LIVE_CMD` (its only user, `launch.py`, stops needing it); `SOURCE_ROOT = HERE.parents[1]`; fix the module docstring (lines 4-5) and the `ENTRY` comment (line 20) |
| `NEVER_OWNED`: settings, `.claude/state/`, `hook.py`, `waiting.py`, the quality baseline | `.claude/bin/core.py:54-57` | Keep the tuple; reword the comment: never owned by a by-hand plan either |
| `maintainer_mode`, `never_owned_problem`, `flow_path_refused` | `.claude/bin/core.py:235-261` | `maintainer_mode` unchanged. `never_owned_problem` message ends `is never owned, not even by a plan for the flow itself.` `flow_path_refused(path)` returns `path.startswith(".claude/")` |
| `die(msg, code=1)` | `.claude/bin/core.py:144-146` | `refuse_by_hand_plan` calls it |
| `validate`: `maintainer_errors` (flag boolean; true only in the flow repo) and `ownership_errors(manifest, maintainer)` (never-owned rule for `.claude/` paths of a maintainer plan, plain refusal otherwise) | `.claude/bin/manifest_check.py:62-81`, `:128-150` | Behaviour unchanged. Only the `maintainer_errors` docstring and message say "a plan for the agentic-flow repository itself, run by hand" |
| close-stage: `maintainer = maintainer_mode(manifest)` then `flow_path_refused(path, maintainer)` | `.claude/bin/stage.py:150-160` | Drop the variable; call `flow_path_refused(path)`; drop `maintainer_mode` from the import at `:19` if unused |
| The hook's guard: `flow_path_refused(rel, maintainer_mode(manifest))` | `.claude/bin/guardrail.py:252-263`, import `:17` | Call `flow_path_refused(rel)` |
| `hook.py`: `target()` picks the frozen copy when `.claude/state/guard/active.json` exists | `.claude/bin/hook.py:1-34` | `target()` returns `root / ".claude" / "bin" / "agentic.py"` only; keep the fail-closed `try` in `main()`, the `runpy` call, Python 3.9 compatibility and the rule of not importing `agentic.py` at module level |
| `SEQ_COMMANDS` includes `guard-release`; `PIPELINE_SPEC` reads the frozen copy's spec when `FROZEN` | `.claude/bin/launch.py:36-45` | Remove `guard-release`; `PIPELINE_SPEC = ROOT / ".claude" / "workflows" / "pipeline-spec.json"`; fix the comment |
| The agent launchers write state before `run_stage`: `run_wave` writes briefs and, with `--fix`, the ledger (`launch.py:244-246`); `run_acceptance` writes briefs (`:256`); `run_pipeline` creates `.claude/state/runs` and writes `workflow-result.json` | `.claude/bin/launch.py:217-268`, `:378-430` | So the refusal goes in the command handlers, before the launcher runs: `cmd_run_wave`, `cmd_run_acceptance`, `cmd_run_review`, `cmd_run_qa`, `cmd_run_docs`, `cmd_run_pipeline` and `cmd_pipeline_plan` (`agentic.py:149-156`, `:189-190`, `:223-224`, `:292-297`, `cmd_run_wave` after `stage_arg`) call `require_runnable()` instead of `require_valid()` |
| `run_steps(groups, env=None, script=None)` | `.claude/bin/launch.py:284-299` | Remove `script`; always `ENTRY` |
| `run_pipeline`'s `gate(cmds, label, agentic=LIVE_CMD)` passes the frozen script | `.claude/bin/launch.py:404-407` | `gate(cmds, label)` with `run_steps(..., env=gate_env)` |
| `pipeline_plan(manifest, keep_guard=False)`, `freeze_guard()`, `release_guard()` | `.claude/bin/launch.py:436-482` | `pipeline_plan(manifest)`: first `refuse_by_hand_plan(manifest)`, then the plan without `"maintainer"` and `"agentic"`. Delete the other two and the section comment. Remove `hashlib`, `shutil`, `time` imports if nothing else uses them (`grep` first) |
| CLI: `cmd_pipeline_plan` accepts `--keep-guard`; `cmd_guard_release`; `COMMANDS`; `__all__` lists `GUARD_DIR` and `release_guard`; the docstring lists `guard-release` | `.claude/bin/agentic.py:56`, `:74-100`, `:153-166`, `:329-342` | `cmd_pipeline_plan`: any argument dies with `Uso: pipeline-plan`. Delete `cmd_guard_release`, its `COMMANDS` entry and docstring line. Remove `GUARD_DIR` and `release_guard` from imports and `__all__` |
| `merge_settings(dst, src)` adds the flow's rules and never removes the project's | `.claude/bin/installer.py:62-92` | The add loop skips rules in `RETIRED_PERMISSIONS`; after it, remove each rule of a module constant `RETIRED_PERMISSIONS = ("Bash(python3 .claude/state/guard/bin/agentic.py:*)",)` from `permissions.allow` and append `f"removed allow {rule}"` to `added`. Update the docstring and the comment at `:84` |
| Python engine: `self.agentic`, the two-form gate call, the resumed `--keep-guard`, the `finally` that calls `guard-release` | `.claude/bin/pipeline.py:115-148`, `:228-260` | `seq` always calls `self._gate(cmds, label)`; delete `self.agentic` and the line that sets it from the plan; the first call is always `["hooks-check", "pipeline-plan", "briefs"]`; `execute` keeps `try/except Halted` without `finally` |
| JS engine: `let AGENTIC`, `if (plan.agentic) AGENTIC = plan.agentic`, the resumed `--keep-guard`, `try { return await runAfterPlan() } finally { if (plan.maintainer) ... }` | `.claude/workflows/agentic-implement.js:25-26`, `:395-407`, `:558-562` | `const AGENTIC`; always `'pipeline-plan'`; `return await runAfterPlan()` without `try/finally`; fix the comments |
| Conformance scenarios of maintainer mode, and the tests that read them | `.claude/bin/conformance.json:957-959`, `.claude/bin/test_pipeline.py:190-200`, `.claude/bin/test_workflow.mjs:552-560` | Delete the three scenarios and the assertions that name them; keep the JSON valid (no trailing comma) |
| The fake gates record `gate_prefixes` (the command of every gate call after the first), and `ConformanceTests` compares them between engines. They only existed to see the frozen command | `.claude/bin/test_pipeline.py:64-67`, `:156`; `.claude/bin/test_workflow.mjs:42-48` | Remove `gate_prefixes` everywhere: the Python fake gate becomes `gate(cmds, label)` without it, the JS fake world stops computing `gatePrefixes`, both summaries drop the key, and `:156` drops it from the compared keys. `grep -n "gate_prefixes\|gatePrefixes"` over `.claude/bin` must return nothing afterwards |
| The resumed run's first gates | `.claude/bin/test_acceptance.py:251-252` | `["hooks-check", "pipeline-plan", "briefs"]`; reword the comment |
| `MaintainerModeTests` | `.claude/bin/test_agentic.py:1710-1808` | Keep the `is_flow_repo`, flag, never-owned and hook-migration tests; replace `test_flow_paths_are_refused_outside_maintainer_mode_only` with a one-argument version; delete `test_releasing_with_nothing_active_is_fine` and `test_run_steps_runs_the_given_script`; add tests for `refuse_by_hand_plan` and the retired permission. The class docstring says what remains |
| `test_definitions.py`: the settings test requires the copy's permission; a gatekeeper test requires the frozen command; `REEXPORTS` lists `GUARD_DIR` and `release_guard`; the hook comment | `.claude/bin/test_definitions.py:310-340`, `:446-453` | Assert the permission is absent and the gatekeeper names only the live command (rename the test); remove the two names from `REEXPORTS` |
| `test_acceptance_v29.py` pins 35 commands | `.claude/bin/test_acceptance_v29.py:192` | Replace the count with: the `COMMANDS` names equal the docstring's (as `test_definitions` checks) and include `release-notes` |
| `test_definitions.test_commands_match_the_docstring` pins the count | `.claude/bin/test_definitions.py:474-477` | 34 after `guard-release` leaves |
| `settings.json` allow list | `.claude/settings.json:3-7` | Remove line 5 only |
| Gatekeeper rule 1 | `.claude/agents/gatekeeper.md:16` | Only `python3 .claude/bin/agentic.py` is accepted |
| `NOTES` entry shape; `test_the_version_has_its_upgrade_note` requires `plugin.json`'s version to be the newest `NOTES` key | `.claude/bin/upgrade.py:119-133`, `.claude/bin/test_definitions.py:405-410` | `NOTES["2.10.0"]` and version `2.10.0` in the same package |
| Docs: the maintainer paragraph; the `launch.py` line of the module tree; the `pipeline-plan` line of the command list | `docs/how-it-works.md:235`, `:320`, `docs/how-to/README.md:174` | Replace the paragraph with "Changing the flow itself" (section 8, WP-04); tree line ends at `pipeline-plan`; command line loses the `guard-release` clause |
| A by-hand plan is the current way the flow is changed; this very plan has `"maintainer": true` | this document's manifest | `validate` must keep accepting it after the change |
| Ratchet limits: 60 lines per function, 100 per test function, nesting 4, 800 lines per file (a larger file may grow 30), 120 characters per line | `.claude/quality-baseline.json` | Removing code only lowers numbers; `test_agentic.py` (1852 lines) may not grow past its allowance, so new tests there must replace deleted ones |

What must NOT change: `validate`'s results for any manifest (the flag rules, the never-owned rule, the plain refusal of `.claude/` without the flag); the hook's decisions for any write outside `.claude/`; `hook.py`'s path and the hook command in `settings.json`; the engines' gates for every non-maintainer scenario of `conformance.json`.

## 5. Data model
The plan `pipeline-plan` prints loses two keys:
```python
{"waves", "acceptance", "type", "verify", "max_fix_cycles", "agents", "baseline", "docs", "codemap", "rules",
 "wave_of", "work_packages"}          # no "maintainer", no "agentic"
```

## 6. Contracts between modules
```python
# core.py (WP-01)
BY_HAND_PLAN = ("This plan is for the agentic-flow repository itself (\"maintainer\": true): it is executed by hand, "
                "because Claude Code does not let the agents the flow starts write under .claude/. "
                "No agent was started.")

def refuse_by_hand_plan(manifest) -> None:
    """die(BY_HAND_PLAN) (exit 1) when maintainer_mode(manifest); returns None otherwise."""

def flow_path_refused(path) -> bool:
    """Whether path is under .claude/, which no agent of the flow writes."""

def never_owned_problem(path) -> str | None:   # signature unchanged; message reworded
def maintainer_mode(manifest) -> bool:          # unchanged: the flag is True and ROOT is the flow repo

# removed from core: GUARD_DIR, GUARD_CMD, FROZEN

# launch.py (WP-02)
def pipeline_plan(manifest) -> None             # prints the plan of section 5 (no keep_guard)
def run_steps(groups, env=None)                 # always runs ENTRY
# removed from launch: freeze_guard, release_guard

# agentic.py (WP-02)
def require_runnable() -> dict:
    """require_valid(), then refuse_by_hand_plan(manifest); returns the manifest. The handlers of every command that
    starts agents or plans a run use it: pipeline-plan, run-pipeline, run-wave, run-acceptance, run-review, run-qa,
    run-docs."""

# installer.py (WP-02)
RETIRED_PERMISSIONS = ("Bash(python3 .claude/state/guard/bin/agentic.py:*)",)
def merge_settings(dst, src) -> (dict, list)    # also removes RETIRED_PERMISSIONS from permissions.allow,
                                                # adding "removed allow <rule>" to the list
```
Command line (WP-02): `pipeline-plan` with any argument prints `Uso: pipeline-plan` on stderr, exit 1. `guard-release` is not a command: `agentic.py guard-release` prints the usage text and exits 1, as any unknown command. A by-hand plan: `pipeline-plan`, `run-pipeline` and every `run-*` one-off launcher print `BY_HAND_PLAN` on stderr and exit 1 before writing anything (no briefs, no snapshot, no ledger entry, no `runs/` file).

Engines (WP-03): the gatekeeper prompt always starts with `python3 .claude/bin/agentic.py`; the first call is `seq hooks-check + pipeline-plan + briefs`, resumed or not; no call is `guard-release`.

## 7. Conventions
- English everywhere; usage errors keep the `Uso:` prefix.
- Removed code goes entirely: no commented-out code, no unused imports or names (grep each removed name across `.claude/`, `docs/`, `bench/`).
- Comments and docstrings that mention the frozen guard are rewritten or removed, not left behind.
- The ratchet: no new long lines (`agentic.py`, `upgrade.py` and `test_definitions.py` are at their long-line allowance), functions under 60 lines.
- Commits are made by the maintainer; agents do not commit.
- No type annotations, as in the existing modules (Python 3.9 has no `str | None`); the signatures of section 6 are documentation.

## 8. Work packages and acceptance criteria
### Acceptance criteria
Acceptance tests run the live scripts. A "flow repository" is a temporary git repository with `.claude-plugin/plugin.json` named `agentic-flow`, a `README.md` whose first line is `<!-- agentic-flow-template -->`, an `architecture.md` with the manifest given, and `CLAUDE_PROJECT_DIR` pointing at it.

- AC-001 · validate keeps its rules for the flag
  - Scenario: three manifests: a maintainer plan owning `.claude/bin/x.py`; the same without the flag; the same plan in a repository that is not the flow's.
  - Action: `agentic.validate(manifest)` with `core.is_flow_repo` patched to return True or False, as `test_agentic.py:1740-1745` does.
  - Expected: `[]` for the first; an error `WP-01: cannot own '.claude/bin/x.py'.` for the second; an error starting `maintainer:` for the third. A maintainer plan owning `.claude/settings.json` gets an error containing `is never owned`.
  - Must not: accept `.claude/` ownership without the flag, or the flag outside the flow repository. (The third manifest is the first one with `is_flow_repo` returning False.)
  - Check: `test_acceptance_v210.ValidateTests.test_ac_001_flag_rules_unchanged`
  - WP: WP-01
- AC-002 · pipeline-plan refuses a by-hand plan
  - Scenario: a flow repository whose manifest has `"maintainer": true`.
  - Action: `agentic.py pipeline-plan`.
  - Expected: exit 1; stderr contains `executed by hand`; stdout has no JSON line.
  - Must not: create `.claude/state/guard/`.
  - Check: `test_acceptance_v210.RefusalTests.test_ac_002_pipeline_plan_refuses`
  - WP: WP-01, WP-02
- AC-003 · The one-off launchers refuse it before starting an agent
  - Scenario: as AC-002, with `AGENTIC_CLAUDE` set to a script that writes a marker file when run.
  - Action: `agentic.py run-wave 1`, `run-review`, `run-acceptance`, `run-pipeline`.
  - Expected: each exits 1 with `executed by hand` on stderr.
  - Must not: create the marker file (no `claude -p` was started), `.claude/state/briefs/`, `.claude/state/runs/` or any `.claude/state/snapshot-*.json`.
  - Check: `test_acceptance_v210.RefusalTests.test_ac_003_launchers_refuse`
  - WP: WP-01, WP-02
- AC-004 · The plan and the command line carry no guard
  - Scenario: a temporary repository with a normal manifest.
  - Action: `agentic.py pipeline-plan`; `pipeline-plan --keep-guard`; `guard-release`.
  - Expected: the plan's JSON has neither `maintainer` nor `agentic`; `--keep-guard` exits 1 with `Uso: pipeline-plan`; `guard-release` exits 1; `agentic.COMMANDS` has no `guard-release` and the docstring does not list it.
  - Must not: keep `freeze_guard`, `release_guard`, `GUARD_DIR`, `GUARD_CMD` or `FROZEN` on `agentic`, `launch` or `core`.
  - Check: `test_acceptance_v210.CommandTests.test_ac_004_no_guard_left`
  - WP: WP-01, WP-02
- AC-005 · hook.py runs the live guard even with a leftover copy
  - Scenario: a temporary repository with a copy of this checkout's `.claude/bin/*.py` (non-test files), a normal manifest, a claimed WP, and a leftover `.claude/state/guard/active.json` plus `.claude/state/guard/bin/agentic.py` that prints `FROZEN` and exits 0.
  - Action: run `python3 .claude/bin/hook.py` (a copy of the live one in that repository) with a write payload from the WP to a file it does not own.
  - Expected: exit 2 (blocked by the live guard); `FROZEN` appears in neither stdout nor stderr.
  - Must not: run the copy.
  - Check: `test_acceptance_v210.HookTests.test_ac_005_live_guard_only`
  - WP: maintainer (`hook.py` is never owned, so no package answers for it)
- AC-006 · No agent writes under .claude/, whatever the plan says
  - Scenario: `core.flow_path_refused`.
  - Action: call it with `.claude/bin/agentic.py`, `.claude/settings.json` and `src/a.py`.
  - Expected: `True`, `True`, `False`; `inspect.signature(core.flow_path_refused)` has one parameter.
  - Must not: depend on the manifest.
  - Check: `test_acceptance_v210.OwnershipTests.test_ac_006_flow_paths_always_refused`
  - WP: WP-01
- AC-007 · Both engines use the live command and never release a guard
  - Scenario: `conformance.json`, the Python engine through `test_pipeline.run_scenario`, and the JS engine source.
  - Action: run the resumed scenario in the Python engine; read the sources.
  - Expected: no scenario's plan has `maintainer` or `agentic`; the scenario `start_wave skips the baseline, wave 0 and earlier waves` run through `test_pipeline.run_scenario` has `pipeline-plan` as its second gate; `agentic-implement.js` assigns `AGENTIC` once, as `const AGENTIC = 'python3 .claude/bin/agentic.py'`; neither `pipeline.py` nor `agentic-implement.js` contains `guard-release`, `keep-guard`, `plan.agentic` or `self.agentic`; no file under `.claude/bin` contains `gate_prefixes` or `gatePrefixes`.
  - Must not: leave a scenario named with `maintainer`.
  - Check: `test_acceptance_v210.EngineTests.test_ac_007_live_only`
  - WP: WP-03
- AC-008 · install removes the retired permission and nothing else
  - Scenario: `src` is a dict built in the test (the flow's permissions plus the retired rule, so the result does not depend on the maintainer's edit); a project `settings.json` whose allow list has `Bash(python3 .claude/state/guard/bin/agentic.py:*)` and `Bash(make:*)`.
  - Action: `agentic.merge_settings(dst, src)` with the flow's `settings.json` as `src`.
  - Expected: the retired rule is gone, `Bash(make:*)` stays, and the returned list contains `removed allow Bash(python3 .claude/state/guard/bin/agentic.py:*)`. A second call, with the flow's `settings.json` after the maintainer's edit, removes nothing more and reports no removal.
  - Must not: remove any other rule of the project.
  - Check: `test_acceptance_v210.InstallTests.test_ac_008_retired_permission_removed`
  - WP: WP-02
- AC-009 · The flow's settings and gatekeeper only know the live command
  - Scenario: this checkout.
  - Action: read `.claude/settings.json` and `.claude/agents/gatekeeper.md`.
  - Expected: neither contains `state/guard`; the gatekeeper still accepts `python3 .claude/bin/agentic.py`.
  - Must not: remove `Bash(python3 .claude/bin/agentic.py:*)` from the allow list.
  - Check: `test_acceptance_v210.DefinitionTests.test_ac_009_live_command_only`
  - WP: WP-04
- AC-010 · Version 2.10.0 says what changed, and the docs no longer describe the copy
  - Scenario: this checkout.
  - Action: read `plugin.json`, `upgrade.NOTES`, `docs/how-it-works.md`, `docs/how-to/README.md`.
  - Expected: version `2.10.0`; `NOTES["2.10.0"]` mentions `guard-release` and `by hand`; `how-it-works.md` contains `Changing the flow itself` and neither `frozen` nor `guard-release`; `how-to/README.md` has no `guard-release`; `test_acceptance_v25.py` does not exist.
  - Must not: leave `.claude/state/guard` in either doc.
  - Check: `test_acceptance_v210.ReleaseTests.test_ac_010_version_notes_docs`
  - WP: WP-04

### Work packages
The four packages are coupled by imports and shared tests: removing `GUARD_DIR`, `GUARD_CMD` and `FROZEN` from `core.py` breaks `import launch` and `import agentic` until WP-02 lands, and WP-02's `test_definitions.py` reads files of WP-04 and the maintainer. They are applied together, with the maintainer's edits, and every package's validation runs once all four are in place. They share wave 1 because none can be validated alone, not because they are independent.

#### WP-01 · The rules: core, validate, runtime and the hook launcher
- Wave: 1.
- Files: `.claude/bin/core.py`, `.claude/bin/manifest_check.py`, `.claude/bin/stage.py`, `.claude/bin/guardrail.py`, `.claude/bin/verification.py`. The maintainer also edits `.claude/bin/hook.py` with this package (never owned, so outside the manifest).
- Implements: `BY_HAND_PLAN`, `refuse_by_hand_plan`, `flow_path_refused(path)`, the constants' removal, `hook.py`'s live-only target. Consumes nothing new.
- ACs: AC-001, AC-006, and the core side of AC-002, AC-003, AC-004. AC-005 is the maintainer's (`hook.py`).
- Patterns to mirror: `.claude/bin/core.py:235-261` (the functions to edit, their docstring style); `.claude/bin/hook.py:1-34` (keep its structure); `.claude/bin/core.py:124-136` (`root_drift`, a message that names the cause and the way out).
- Gotchas:
  - `SOURCE_ROOT` is used by `installer.py` and `root_drift`; it must stay `HERE.parents[1]`.
  - `verification.py:128`: only the docstring's parenthesis about the frozen guard changes.
  - `manifest_check.py` imports `never_owned_problem` and `maintainer_mode`; both stay.
  - `hook.py` must keep working when `agentic.py` is broken at import time: it never imports it.
  - `test_core.py` and every test file: grep `LIVE_CMD`, `GUARD_DIR`, `FROZEN` before deleting them.
  - Line references: `stage.py` imports `maintainer_mode` at `:19` (block from `:15`), `guardrail.py` at `:17` (block from `:13`).
- Validation: `python3 -m unittest discover -s .claude/bin -p "test_core.py"`; `python3 -m unittest discover -s .claude/bin -p "test_definitions.py"`; `python3 .claude/bin/agentic.py quality`.

#### WP-02 · The launchers, the command line and install
- Wave: 1.
- Files: `.claude/bin/launch.py`, `.claude/bin/agentic.py`, `.claude/bin/installer.py`, `.claude/bin/test_agentic.py`, `.claude/bin/test_definitions.py`, `.claude/bin/test_acceptance_v29.py`.
- Implements: `pipeline_plan(manifest)`, `require_runnable()` in the handlers, `run_steps(groups, env=None)`, the CLI of section 6, `RETIRED_PERMISSIONS` in `merge_settings`. Consumes WP-01's `refuse_by_hand_plan` and `flow_path_refused` by signature.
- ACs: AC-008, and the launcher side of AC-002, AC-003, AC-004.
- Patterns to mirror: `.claude/bin/launch.py:436-454` (`pipeline_plan`); `.claude/bin/installer.py:62-92` (`merge_settings`, the `added` list); `.claude/bin/test_agentic.py:1710-1808` (`MaintainerModeTests`, its `flow_dir` helper).
- Gotchas:
  - `launch.py` imports from `core`: remove `GUARD_CMD`, `GUARD_DIR`, `FROZEN`, `LIVE_CMD`, `maintainer_mode`, and `HERE` once `PIPELINE_SPEC` no longer uses it. `agentic.py` imports `refuse_by_hand_plan` from `core` for `require_runnable()`.
  - `test_agentic.py` sits at 1852 lines with an allowance of 1879: delete before adding.
  - `test_definitions.py` and `agentic.py` are at their long-line allowance.
  - `installer.py:84` has a comment about the frozen guard: rewrite it.
  - The `COMMANDS` count in `test_definitions.py` is at `:477` (35 today, 34 after).
- Validation: `python3 -m unittest discover -s .claude/bin -p "test_agentic.py"`; `python3 -m unittest discover -s .claude/bin -p "test_definitions.py"`; `python3 -m unittest discover -s .claude/bin -p "test_acceptance_v29.py"`; `python3 .claude/bin/agentic.py quality`.

#### WP-03 · The engines
- Wave: 1.
- Files: `.claude/bin/pipeline.py`, `.claude/workflows/agentic-implement.js`, `.claude/bin/conformance.json`, `.claude/bin/test_pipeline.py`, `.claude/bin/test_workflow.mjs`, `.claude/bin/test_acceptance.py`, `.claude/bin/test_acceptance_portable.py` (the comment at `:259`).
- Implements: the engine behaviour of section 6. Consumes the plan of section 5 by signature.
- ACs: AC-007.
- Patterns to mirror: `.claude/bin/pipeline.py:228-260` (the prepare step to simplify); `.claude/workflows/agentic-implement.js:392-412` (the same in JS).
- Gotchas:
  - Both engines must keep producing the same gates for every remaining scenario: `test_pipeline.py` and `test_workflow.mjs` compare them through `conformance.json`.
  - `runAfterPlan` stays a function; only the `try/finally` around its call goes.
  - `pipeline.py:57` `LIVE_CMD` is only used for `self.agentic`: remove both.
  - `gate_prefixes`: see section 4b; `test_pipeline.py` and `test_workflow.mjs` lose it together, or conformance breaks.
- Validation: `node .claude/bin/test_workflow.mjs`; `python3 -m unittest discover -s .claude/bin -p "test_pipeline.py"`; `python3 -m unittest discover -s .claude/bin -p "test_acceptance.py"`.

#### WP-04 · Configuration, release notes and docs
- Wave: 1.
- Files: `.claude/agents/gatekeeper.md`, `.claude/bin/upgrade.py`, `.claude-plugin/plugin.json`, `.claude/bin/test_acceptance_v25.py` (deleted), `docs/how-it-works.md`, `docs/how-to/README.md`.
- Implements: nothing in code. The maintainer also removes the permission from `.claude/settings.json` with this package (never owned, so outside the manifest).
- ACs: AC-009, AC-010.
- Patterns to mirror: `.claude/bin/upgrade.py:119-133` (a `NOTES` entry); `docs/how-it-works.md:233-237` (the paragraph to replace, same voice).
- Gotchas:
  - `NOTES["2.10.0"]`, two notes: (1) "Maintainer mode is retired: the frozen guard, `pipeline-plan --keep-guard` and `guard-release` are gone, and the hook always runs the live agentic.py. A plan with \"maintainer\": true is now only a plan for the agentic-flow repository itself, executed by hand: every agent launcher refuses it. An edited agentic-implement.js that still calls guard-release must be merged with the new one (.claude/state/upgrade/)." (2) "install removes the permission for the frozen guard's command from settings.json; a leftover .claude/state/guard/ folder can be deleted."
  - The new docs paragraph, **Changing the flow itself**: the flow's own repository is changed by hand, because Claude Code does not let the agents the flow starts write under `.claude/`; a plan with `"maintainer": true` may give packages `.claude/` files except the never-owned ones (settings, `.claude/state/`, `hook.py`, `waiting.py`, the quality baseline), `validate` accepts it only in the agentic-flow repository, and `pipeline-plan` and the `run-*` launchers refuse it.
  - Design 0017 adds to `NOTES["2.10.0"]` later; this package creates the entry.
  - The 2.5.0 note (`upgrade.py:82-86`) mentions the frozen guard: it is history, leave it.
- Validation: `python3 .claude/bin/agentic.py docs-check`; `python3 -m unittest discover -s .claude/bin -p "test_definitions.py"`.

```json wp-manifest
{
  "maintainer": true,
  "stack": ["python", "typescript"],
  "allow_bash": ["Bash(python3 -m unittest:*)", "Bash(node .claude/bin/test_workflow.mjs)"],
  "acceptance": {"files": [".claude/bin/test_acceptance_v210.py"], "command": "python3 -m unittest discover -s .claude/bin -p test_acceptance_v210.py"},
  "verify": {"build": "python3 -m unittest discover -s bench -p \"test_*.py\"", "lint": "node .claude/bin/test_workflow.mjs", "types": "python3 -m unittest discover -s bench/acceptance", "tests": "python3 -m unittest discover -s .claude/bin -p \"test_*.py\""},
  "docs": {"files": ["docs/assets/"], "codemap": null},
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": [".claude/bin/core.py", ".claude/bin/manifest_check.py", ".claude/bin/stage.py", ".claude/bin/guardrail.py", ".claude/bin/verification.py"],
     "acs": ["AC-001", "AC-002", "AC-003", "AC-004", "AC-006"], "mirror": [".claude/bin/core.py:235-261", ".claude/bin/hook.py:1-34", ".claude/bin/core.py:124-136"]},
    {"id": "WP-02", "wave": 1, "depends_on": [], "files": [".claude/bin/launch.py", ".claude/bin/agentic.py", ".claude/bin/installer.py", ".claude/bin/test_agentic.py", ".claude/bin/test_definitions.py", ".claude/bin/test_acceptance_v29.py"],
     "acs": ["AC-002", "AC-003", "AC-004", "AC-008"], "mirror": [".claude/bin/launch.py:436-454", ".claude/bin/installer.py:62-92", ".claude/bin/test_agentic.py:1710-1808"]},
    {"id": "WP-03", "wave": 1, "depends_on": [], "files": [".claude/bin/pipeline.py", ".claude/workflows/agentic-implement.js", ".claude/bin/conformance.json", ".claude/bin/test_pipeline.py", ".claude/bin/test_workflow.mjs", ".claude/bin/test_acceptance.py", ".claude/bin/test_acceptance_portable.py"],
     "acs": ["AC-007"], "mirror": [".claude/bin/pipeline.py:228-260", ".claude/workflows/agentic-implement.js:392-412"]},
    {"id": "WP-04", "wave": 1, "depends_on": [], "files": [".claude/agents/gatekeeper.md", ".claude/bin/upgrade.py", ".claude-plugin/plugin.json", ".claude/bin/test_acceptance_v25.py", "docs/how-it-works.md", "docs/how-to/README.md"],
     "acs": ["AC-009", "AC-010"], "mirror": [".claude/bin/upgrade.py:119-133", "docs/how-it-works.md:233-237"]}
  ]
}
```

## 9. Test strategy
- **Unit:** each package updates the tests it owns (section 4); `MaintainerModeTests` keeps the flag, flow-repo and hook-migration tests and gains the refusal and retired-permission tests.
- **Acceptance:** `.claude/bin/test_acceptance_v210.py`, written first, red before the code. `unittest`, temporary repositories, `AGENTIC_CLAUDE` pointing at a marker script for AC-003, no network, nothing spent.
- **QA:** by hand: `validate` on this plan stays green; `pipeline-plan` on it refuses; a normal temporary project's `pipeline-plan` output has no `agentic` key; the hook with a leftover copy runs live.
- **Everything:** the commands of section 3 and the ratchet.

## 10. Decisions
- **Retire, not move or bypass** (user's choice on issue 100): the feature cannot work while Claude Code protects `.claude/`, and keeping it half-way costs code and tests on every release.
- **The `maintainer` key stays as "a plan run by hand"** (user's choice): the flow's own designs still validate their `.claude/` zones and the never-owned rule; every agent launcher refuses such a plan before starting an agent, instead of spending money and failing at wave 0 as 0013's fallback run did. Discarded: dropping the key (the flow's designs could not declare their files).
- **Refusal in the command handlers** (`require_runnable()`): the launchers write briefs, ledger entries and run files before their first agent, so a refusal inside them would leave state behind. The native workflow reaches it through `pipeline-plan`.
- **No compatibility shims** (user's choice): `--keep-guard` and `guard-release` are removed; the upgrade note tells a project with an edited workflow to merge.
- **The plan loses `agentic` and `maintainer`; both engines use the live command** (user's choice): no indirection left.
- **install removes the retired permission** (user's choice): an auto-allowed command on a path nobody uses is a needless opening. It removes exactly that rule, nothing else.
- **`hook.py` stays**: projects' `settings.json` runs it; it now always runs the live `agentic.py`.
- **`test_acceptance_v25.py` is deleted here**, since its feature is gone; its still-valid checks are covered by `MaintainerModeTests` and AC-001. The other acceptance files are design 0017's.
- **One release with design 0017**: version 2.10.0 is set here; 0017 adds to the same notes; the history is regenerated at the end of the branch.
- **Executed by hand**, like 0013 to 0015, for the reason this design writes down. `hook.py` and `settings.json` are never owned, so they are outside the manifest and the maintainer edits them, marked `MAINT` in section 4.

## 11. Risks and open questions
- A project whose `agentic-implement.js` was edited and kept by install keeps calling `guard-release` and `pipeline-plan --keep-guard`: its runs stop at prepare with a usage error until the file is merged. None of the known projects has an edited workflow (their installs reported no kept files for it).
- `close-stage` and `check-wave` now report every `.claude/` change as unowned, even for a by-hand plan. That is intended: a by-hand plan runs no stages, since no agent can be launched for it.
- `docs/roadmap/repo-review-2026-11.md:112` still describes the frozen copy: it is a dated review, left as history.
- A session that started a maintainer run on 2.9 and resumes on 2.10 finds no frozen guard: the resume is refused as a by-hand plan, which is the intended outcome.
- Rollback: revert the commit; the removed code returns as it was.
