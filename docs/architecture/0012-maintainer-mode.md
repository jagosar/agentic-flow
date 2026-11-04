# Architecture: a maintainer mode, so the flow can implement changes to its own repository (issue 71, agentic-flow 2.5.0)
Type: feature · Size: large

## 1. Goal
`validate` refuses a work package that owns a path under `.claude/`, and the hook and `close-stage` block writes there. That protects every project's flow from its own agents, and it is why every plan that changed the flow (designs 0002 to 0011) was executed by hand. This change adds a maintainer mode for the agentic-flow repository only: a plan with `"maintainer": true` may give its packages named paths under `.claude/`, except a fixed list that stays nobody's. Because most flow changes touch `agentic.py`, which holds the guard itself, the run is watched by a frozen copy of the guard taken when the run starts: the hook goes through a fixed launcher that uses that copy, and both engines run every deterministic step with it. What the agents write takes effect on the next run, never on the one watching them.

## 2. Scope
### Included
- `"maintainer": true` in the manifest, accepted only in the flow's own repo.
- Ownership of named `.claude/` paths in maintainer mode, in `validate`, the hook and `close-stage`; a never-ownable list.
- The frozen guard: `pipeline-plan` copies the guard to `.claude/state/guard/` and reports the command to use; `guard-release` ends it.
- `.claude/bin/hook.py`, a fixed launcher for the `PreToolUse` hook, in every project (projects never activate the guard, so for them it just runs `agentic.py hook`).
- Both engines use the frozen command after `prepare` and release the guard at the end, in maintainer mode only.
- `settings.json`: the hook command and the gatekeeper's permission for the frozen path; `install` migrates projects' old hook command.
- Version 2.5.0, notes, docs.
### Excluded (non-goals)
- Freezing agent definitions (`.claude/agents/*.md`): Claude Code reads them live; section 11.
- Using maintainer mode in any repo other than agentic-flow.
- Executing this plan with the mode it creates: it is executed by hand.

## 3. Stack
Python 3.9+ standard library (no type annotations in `agentic.py`, which must import on 3.9), Node 20 for the workflow.
- Tests: `python3 -m unittest discover -s .claude/bin -p "test_*.py"`, `node .claude/bin/test_workflow.mjs`, `python3 -m unittest discover -s acceptance`, `python3 -m unittest discover -s qa`.

## 4. Repository structure
```
.claude/bin/agentic.py             WP-01
.claude/bin/test_agentic.py        WP-01
.claude/bin/hook.py                WP-01 (new)
.claude/settings.json              WP-02
.claude/bin/test_definitions.py    WP-02 (the settings test)
.claude/agents/gatekeeper.md       WP-02 (accept the frozen path)
.claude/workflows/agentic-implement.js   WP-03
.claude/bin/pipeline.py            WP-03
.claude/bin/conformance.json       WP-03
.claude/bin/test_pipeline.py       WP-03
.claude/bin/test_workflow.mjs      WP-03
.claude-plugin/plugin.json         WP-04 (2.5.0)
.claude/bin/upgrade.py             WP-04
.claude/bin/test_acceptance_upgrade.py, test_acceptance_v2.py, test_acceptance_v21.py, test_acceptance_v22.py, test_acceptance_v23.py, test_acceptance_v24.py, test_acceptance_v241.py   WP-04 (version pins)
docs/how-it-works.md, docs/how-to/README.md, docs/roadmap/repo-review-2026-11.md   WP-04
.claude/bin/test_acceptance_v25.py AT (new)
```

## 4b. Existing code context
| What an implementer needs to know | Where it is | Pattern or rule |
|---|---|---|
| `validate` refuses `.claude/` paths | `agentic.py:408-416` (`cannot own`) | Maintainer mode relaxes this one test, for named paths outside `NEVER_OWNED` |
| `close-stage` treats `.claude/` as nobody's | `agentic.py:683-687` (`check_stage`) | Same relaxation |
| The hook refuses `.claude/` writes | `agentic.py:2262-2270` (`guard`) | Same relaxation |
| The code map refuses `.claude/` | `agentic.py:471`, `:2484` | Unchanged: the map is never under `.claude/` |
| How `agentic.py` finds the repo and its spec | `agentic.py:72-75` (`sys.path`, `ROOT` from `CLAUDE_PROJECT_DIR` or `parents[2]`), `:100` (`SOURCE_ROOT`), `:1526` (`PIPELINE_SPEC`), `:735-738` (`load_spec`), `:1585-1594` (`sibling` imports from the script's own folder) | A frozen copy lives four levels below the root: it needs its own `ROOT` and `PIPELINE_SPEC` |
| The plan the engines follow | `agentic.py:1657-1667` (`pipeline_plan` prints one JSON line) | Gains `"maintainer"` and `"agentic"` |
| Gate steps of the fallback engine | `agentic.py:1487-1501` (`run_steps` runs `Path(__file__)`), the pipeline's `gate` | In maintainer mode they run the frozen copy |
| The native workflow's command | `agentic-implement.js:25` (`const AGENTIC = 'python3 .claude/bin/agentic.py'`), `:142` (the gatekeeper prompt) | After `prepare`, the command comes from `plan.agentic` |
| The gatekeeper accepts one prefix | `.claude/agents/gatekeeper.md:16` ("Only commands starting with `python3 .claude/bin/agentic.py`") | Also `python3 .claude/state/guard/bin/agentic.py` |
| The hook entry and its settings | `agentic.py:2371-2384` (`hook`); `.claude/settings.json:13-25` (PreToolUse command `python3 "$CLAUDE_PROJECT_DIR/.claude/bin/agentic.py" hook`), permissions `Bash(python3 .claude/bin/agentic.py:*)` | The command becomes `python3 "$CLAUDE_PROJECT_DIR/.claude/bin/hook.py"`; a permission for the frozen path is added |
| Finding the flow's hook in settings | `agentic.py:2288-2291` (`flow_hooks`: `"agentic.py" in command and endswith("hook")`), used by `merge_settings` (`install`) and `hooks_static_problem` | Recognises both commands; `install` rewrites the old one to the new |
| What install ships | `agentic.py:131-132` (`INSTALL_GLOBS`) | Gains `.claude/bin/hook.py` |
| Settings test | `test_definitions.py:305-316` (`test_hook_registered`) | Accepts the launcher command |
| The flow's own repo | `.claude-plugin/plugin.json` (`"name": "agentic-flow"`), `README.md:1` (`<!-- agentic-flow-template -->`, removed by `reset-readme.yml` in template copies) | Both must hold for maintainer mode |
| Version pins | `test_acceptance_upgrade.py:258`, `_v2.py:177`, `_v21.py:283`, `_v22.py:171`, `_v23.py:256`, `_v24.py:270`, `_v241.py` (ReleaseTests) | Become `"2.5.0"`; `_v241.py` keeps checking `NOTES["2.4.1"]` |

## 5. Data model
`.claude/state/guard/` (git-ignored with the rest of `.claude/state/`):
```
.claude/state/guard/bin/*.py                    copies of the non-test .claude/bin/*.py
.claude/state/guard/workflows/pipeline-spec.json
.claude/state/guard/active.json                 {"root": "<abs path>", "frozen_at": "<iso>", "files": {"bin/agentic.py": "<sha256>", ...}}
```
Manifest key: `"maintainer": true` (optional, boolean).

## 6. Contracts between modules
```python
# .claude/bin/agentic.py
NEVER_OWNED = (".claude/settings.json", ".claude/settings.local.json", ".claude/state/", ".claude/bin/hook.py",
               ".claude/bin/waiting.py")  # the two live hook scripts: an agent must not reroute or replace a hook
GUARD_DIR = ".claude/state/guard"
GUARD_CMD = "python3 .claude/state/guard/bin/agentic.py"
LIVE_CMD = "python3 .claude/bin/agentic.py"
FROZEN  # True when this file runs from GUARD_DIR/bin (its folder is "bin", its parent "guard", then "state");
        # computed before ROOT. Then ROOT = SOURCE_ROOT = parents[4] unless CLAUDE_PROJECT_DIR is set, and
        # PIPELINE_SPEC = GUARD_DIR/workflows/pipeline-spec.json

def is_flow_repo(root) -> bool
    # .claude-plugin/plugin.json has "name": "agentic-flow" and README.md's first line is the template marker.
def maintainer_mode(manifest) -> bool
    # manifest.get("maintainer") is True AND is_flow_repo(ROOT): the hook and close-stage never run validate, so a
    # stray flag in a project must not relax anything.
def never_owned_problem(path) -> str | None
    # A message when `path` owns, or is owned by, an entry of NEVER_OWNED (prefix match either way); else None.
def freeze_guard() -> dict
    # Copies every ROOT/.claude/bin/*.py except test_*.py and testutil.py, and ROOT/.claude/workflows/pipeline-spec.json
    # (always the live tree, also when the running script is FROZEN), into GUARD_DIR, replacing any earlier copy, and
    # writes active.json. Returns its content.
def release_guard() -> None
    # Removes GUARD_DIR/active.json (the copies may stay). CLI `guard-release`; exit 0 even when nothing is active.
```
- `validate`: `"maintainer"` must be a boolean; `true` outside `is_flow_repo(ROOT)` is the error "maintainer mode is only for the agentic-flow repository". With it, a `.claude/` path is accepted unless `never_owned_problem` returns a message; `architecture.md` and `docs/architecture/` stay refused in both modes. Without it, nothing changes.
- `pipeline_plan` (CLI `pipeline-plan [--keep-guard]`): adds `"maintainer": bool` and `"agentic": GUARD_CMD if maintainer else LIVE_CMD`. In maintainer mode it calls `freeze_guard()` first, unless `--keep-guard` is given and `GUARD_DIR/active.json` exists (then the existing copy stays: a resumed run keeps watching with the guard of its first start, not with code the agents have since changed). Outside maintainer mode it calls `release_guard()`, so a guard left active by a crashed maintainer run never watches a normal run. Stdout stays one JSON line.
- `guard`, `check_stage`: in maintainer mode, a path under `.claude/` that an entity owns is that entity's unless `never_owned_problem(path)`; outside it, unchanged.
- `run_steps(groups, env=None, script=None)`: runs `script` (a path) when given, else `Path(__file__)` as today. `run_pipeline`'s `gate` closure becomes `gate(cmds, label, agentic=LIVE_CMD)`: it runs `ROOT / ".claude/state/guard/bin/agentic.py"` when `agentic == GUARD_CMD`, else the live script. `seq` keeps calling `run_steps` without `script`.
- `flow_hooks`: recognises `.claude/bin/hook.py` and the old `agentic.py ... hook`; `merge_settings` replaces an old command with the new one, keeping the project's matcher and timeout.
- `INSTALL_GLOBS` gains `.claude/bin/hook.py`. CLI gains `guard-release`; `SEQ_COMMANDS` gains it.

```python
# .claude/bin/hook.py — never ownable; tiny, standard library only, no type annotations (Python 3.9)
# <root> = CLAUDE_PROJECT_DIR or this file's parents[2]. If <root>/.claude/state/guard/active.json and
# <root>/.claude/state/guard/bin/agentic.py both exist, target = the frozen agentic.py; else <root>/.claude/bin/agentic.py.
# sys.argv = [str(target), "hook"]; runpy.run_path(str(target), run_name="__main__")  (run_name is required: the CLI
# runs under `if __name__ == "__main__"`). It never imports agentic.py at module level. If resolving the target
# raises, it prints the error on stderr and exits 2 (fails closed, as agentic.py's hook does inside an agent).
```
Engines: the first call stays `seq hooks-check + pipeline-plan + briefs` with the live command; a resumed run (`start_wave` set, `--resume`) sends `pipeline-plan --keep-guard` instead. After it, the engine keeps `plan.agentic` and passes it on every later gate call: in `pipeline.py`, `self._gate(cmds, label, self.agentic)` (the Pipeline's `gate` callable gains a third argument, default `"python3 .claude/bin/agentic.py"`); in the JS workflow, `AGENTIC` becomes a variable set from `plan.agentic`. When `plan.maintainer`, the last gate call of the run is `guard-release`, on every exit path once `pipeline-plan` has returned a plan: that includes `briefs` failing in the same first call, and every stop of a later stage. Conformance: both simulated worlds record the command prefix of every gate call after the first (the JS world reads it from the prompt, the Python world from the third argument) as the summary key `gate_prefixes` (the distinct prefixes, in order), compared between engines; existing scenarios have `["python3 .claude/bin/agentic.py"]` and do not otherwise change.

## 7. Conventions
- English; no type annotations in `agentic.py` or `hook.py` (they must import on Python 3.9), which contradicts `.claude/rules/agentic/python.md` (annotations on public signatures): the plan wins; messages name the key or the path.
- `qa/` is not in `verify` (four slots, all taken): WP-04's validation runs it.
- The frozen copy is never edited: it is replaced by the next `freeze_guard`.
- One commit per WP; no model names.

## 8. Work packages and acceptance criteria
### Acceptance criteria
- AC-001 · Maintainer mode exists only in the flow's repo
  - Scenario: two temp repos with the flow and a plan whose WP owns `.claude/bin/x.py` and has `"maintainer": true`: one with `.claude-plugin/plugin.json` named `agentic-flow` and the template marker on README line 1, one without the marker.
  - Action: `validate` in each; then the same plan without `"maintainer"`.
  - Expected: valid in the first; in the second, an error containing "only for the agentic-flow repository"; without the flag, `cannot own '.claude/bin/x.py'` in both.
  - Must not: accept `"maintainer": "yes"` (non-boolean).
  - Check: `test_acceptance_v25.py::ValidateTests`
  - WP: WP-01
- AC-002 · Never-owned paths stay nobody's
  - Scenario: the flow repo, maintainer plan.
  - Action: `validate` with a WP owning, in turn, `.claude/settings.json`, `.claude/settings.local.json`, `.claude/state/x`, `.claude/bin/hook.py`, `.claude/bin/waiting.py`, `.claude/` and `.claude/bin/`.
  - Expected: each is refused with a message naming the never-owned path; `architecture.md` and `docs/architecture/x.md` are refused too.
  - Must not: accept a prefix that contains a never-owned path.
  - Check: `test_acceptance_v25.py::NeverOwnedTests`
  - WP: WP-01
- AC-003 · `pipeline-plan` freezes the guard in maintainer mode
  - Scenario: the flow repo, maintainer plan; then a non-maintainer plan.
  - Action: `pipeline-plan`.
  - Expected: maintainer: `"maintainer": true`, `"agentic": "python3 .claude/state/guard/bin/agentic.py"`, the copies and `active.json` exist with the sha256 of each copied file, and no `test_*.py` or `testutil.py` was copied; non-maintainer, run after that: `"maintainer": false`, `"agentic": "python3 .claude/bin/agentic.py"`, and `active.json` is gone.
  - Must not: print anything but one JSON line on stdout; re-freeze on `pipeline-plan --keep-guard` when a guard is active (after changing the live `agentic.py`, the frozen copy's sha256 in `active.json` is unchanged).
  - Check: `test_acceptance_v25.py::FreezeTests`
  - WP: WP-01
- AC-004 · The hook is decided by the frozen guard while it is active
  - Scenario: the flow repo, maintainer plan, `pipeline-plan` run; then the live `.claude/bin/agentic.py` replaced by a version whose `hook` allows everything.
  - Action: `python3 .claude/bin/hook.py` with a write payload for a path WP-01 does not own, `AGENTIC_WP=WP-01`; then `guard-release` and the same call.
  - Expected: while active, exit 2 (blocked) by the frozen copy; after release, the live (permissive) script decides.
  - Must not: read the live script while the guard is active.
  - Check: `test_acceptance_v25.py::HookTests`
  - WP: WP-01
- AC-005 · Owned `.claude/` paths are writable in maintainer mode only
  - Scenario: the flow repo; WP-01 owns `.claude/bin/x.py`.
  - Action: the hook with a write to `.claude/bin/x.py` as WP-01 and to `.claude/settings.json` as WP-01, with and without the flag; `open-stage 1`, edit `.claude/bin/x.py`, one hook call as WP-01, `close-stage 1 WP-01=done`.
  - Expected: with the flag, the first write passes, the second is blocked naming the never-owned path, and the stage closes OK; without it, both are blocked as today.
  - Must not: let a write to a never-owned path through.
  - Check: `test_acceptance_v25.py::OwnershipTests`
  - WP: WP-01
- AC-006 · The frozen copy uses its own root and spec
  - Scenario: a frozen copy; the live `pipeline-spec.json` then changed (its `fix` prompt).
  - Action: run the frozen `agentic.py` as a subprocess with `CLAUDE_PROJECT_DIR` unset, from the repo root: `validate` (it never freezes); and import it with `importlib.util.spec_from_file_location` (in a subprocess with `CLAUDE_PROJECT_DIR` unset) and call `load_spec()["prompts"]["fix"]`.
  - Expected: `validate` finds the repo's `architecture.md` (exit 0); `load_spec` returns the frozen prompt, not the changed one.
  - Must not: resolve `ROOT` to `.claude/state`.
  - Check: `test_acceptance_v25.py::FrozenCopyTests`
  - WP: WP-01
- AC-007 · Both engines use the frozen command and release it
  - Scenario: the conformance scenarios "maintainer run uses the frozen guard" (plan with `"maintainer": true`, `"agentic"` the frozen command), "maintainer run whose briefs fail still releases the guard" (same plan, `gate_fail` on `briefs`), "a resumed maintainer run keeps the guard" (`start_wave` 1), and the happy path.
  - Action: run both through the Python and the Node runners.
  - Expected: in the maintainer scenario `gate_prefixes` is `["python3 .claude/state/guard/bin/agentic.py"]` and the last gate is `guard-release`; when briefs fail, the gates are the first `seq` and then `guard-release`; the resumed run's first gate contains `pipeline-plan --keep-guard`; in the happy path `gate_prefixes` is `["python3 .claude/bin/agentic.py"]` and the gates are unchanged; both engines' summaries agree on `gates` and `gate_prefixes`.
  - Must not: freeze or release in a non-maintainer run.
  - Check: `test_acceptance_v25.py::EnginesTests`
  - WP: WP-03
- AC-008 · Install ships the launcher and migrates the hook
  - Scenario: a project installed with 2.4.1 (old hook command).
  - Action: `install` from this tree.
  - Expected: `.claude/bin/hook.py` exists; `settings.json` has one flow PreToolUse entry whose command is `python3 "$CLAUDE_PROJECT_DIR/.claude/bin/hook.py"`, with the project's matcher and timeout kept; `hooks-check` (static) passes; the permission `Bash(python3 .claude/state/guard/bin/agentic.py:*)` is present; `gatekeeper.md` accepts both prefixes.
  - Must not: leave two flow hook entries.
  - Check: `test_acceptance_v25.py::InstallTests`
  - WP: WP-02
- AC-009 · Release 2.5.0
  - Scenario: the repository after the change.
  - Action: read `plugin.json`, `upgrade.NOTES`, the docs and the roadmap.
  - Expected: version `2.5.0`; `NOTES["2.5.0"]` has at least two notes, one naming `hook.py` and `settings.json`, one naming `maintainer`; `docs/how-it-works.md` §4 mentions the frozen guard; the hub's script reference lists `guard-release`; the roadmap line starting "- The flow cannot implement itself" contains "Shipped in 2.5.0"; earlier note counts unchanged.
  - Must not: hard-code a version in the hub or README.
  - Check: `test_acceptance_v25.py::ReleaseTests`
  - WP: WP-04

### Work packages
#### WP-01 · Maintainer mode and the frozen guard in `agentic.py`
- Wave: 1.
- Files: `.claude/bin/agentic.py`, `.claude/bin/test_agentic.py`, `.claude/bin/hook.py` (it ships in `INSTALL_GLOBS` in the same wave, so `test_definitions.py:397-402` stays green).
- ACs: AC-001, AC-002, AC-003, AC-004, AC-005, AC-006.
- **Patterns to mirror:** `agentic.py:408-416`, `:683-687`, `:2262-2270`, `:1657-1667`, `:1620-1626` (the pipeline's `gate` closure), `test_agentic.py:1087-1130` (install tests), the `Repo` helper (`test_agentic.py:42-70`), `.claude/bin/waiting.py` (a small hook script).
- **Gotchas:** `FROZEN` must be computed before `ROOT`; `sibling()` already imports from the script's folder, so a frozen copy imports frozen siblings. `pipeline_plan` must keep stdout one JSON line (freeze silently). `run_steps` is also used by `seq`, which never passes `script`. `guard-release` goes into the CLI dispatch, `SEQ_COMMANDS` and the module docstring (`agentic.py:20-51`), so `test_cited_commands_exist` accepts it in the docs. Never write into `GUARD_DIR` from a WP context (the hook already blocks `.claude/state/`).
- **WP validation:** `python3 -m unittest discover -s .claude/bin -p "test_agentic.py"`, `python3 -m unittest discover -s .claude/bin -p "test_definitions.py"`, and from `.claude/bin`: `python3 -m unittest test_acceptance_v25.ValidateTests test_acceptance_v25.NeverOwnedTests test_acceptance_v25.FreezeTests test_acceptance_v25.HookTests test_acceptance_v25.OwnershipTests test_acceptance_v25.FrozenCopyTests`.

#### WP-02 · Settings and the gatekeeper
- Wave: 2 (it needs WP-01's `hook.py`, `flow_hooks` and `merge_settings`).
- Files: `.claude/settings.json`, `.claude/bin/test_definitions.py`, `.claude/agents/gatekeeper.md`.
- ACs: AC-008.
- **Patterns to mirror:** `test_definitions.py:305-316`, `.claude/agents/gatekeeper.md:16`.
- **Gotchas:** keep the matcher and the 900 s timeout of the PreToolUse entry; only the command changes.
- **WP validation:** `python3 -m unittest discover -s .claude/bin -p "test_definitions.py"`, the AC-008 class.

#### WP-03 · Both engines
- Wave: 1 (it consumes `plan.agentic` and `plan.maintainer` by signature; the simulated worlds fake them).
- Files: `.claude/workflows/agentic-implement.js`, `.claude/bin/pipeline.py`, `.claude/bin/conformance.json`, `.claude/bin/test_pipeline.py`, `.claude/bin/test_workflow.mjs`.
- ACs: AC-007.
- **Patterns to mirror:** `agentic-implement.js:139-160` (`gate`, `seq`), `pipeline.py:232-245` (`prepare`), the conformance scenario format (`conformance.json`, any scenario with a `plan` override).
- **Gotchas:** `AGENTIC` becomes a variable set after `prepare`; the `guard-release` call must run on every exit path after `prepare` (wrap the rest of the run). The simulated worlds return exit 0 for unknown commands, so `guard-release` needs no stub. The Python world's `gate` (`test_pipeline.py:28-60`) gains the third argument and records it; the JS world (`test_workflow.mjs:40-60`) reads the prefix before `agentic.py ` in the prompt.
- **WP validation:** `node .claude/bin/test_workflow.mjs`, `python3 -m unittest discover -s .claude/bin -p "test_pipeline.py"`, the AC-007 class.

#### WP-04 · Version, notes and docs
- Wave: 2 (the docs cite `guard-release`, which must exist: `test_cited_commands_exist`).
- Files: `.claude-plugin/plugin.json`, `.claude/bin/upgrade.py`, the seven version-pin test files, `docs/how-it-works.md`, `docs/how-to/README.md`, `docs/roadmap/repo-review-2026-11.md`.
- ACs: AC-009.
- **Gotchas:** the hub is capped at 260 lines: add `guard-release` by merging with an existing line if it is at the cap.
- **WP validation:** `python3 -m unittest discover -s .claude/bin -p "test_acceptance_*.py"`, `python3 -m unittest discover -s acceptance`, `python3 -m unittest discover -s qa`.

```json wp-manifest
{
  "stack": ["python", "typescript"],
  "allow_bash": ["Bash(python3 -m unittest:*)", "Bash(node .claude/bin/test_workflow.mjs)"],
  "acceptance": {"files": [".claude/bin/test_acceptance_v25.py"], "command": "python3 -m unittest discover -s .claude/bin -p test_acceptance_v25.py"},
  "verify": {"build": "python3 -m compileall -q .claude/bin", "lint": "node .claude/bin/test_workflow.mjs", "types": "python3 -m unittest discover -s acceptance", "tests": "python3 -m unittest discover -s .claude/bin -p \"test_*.py\""},
  "docs": {"files": ["docs/assets/"], "codemap": null},
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": [".claude/bin/agentic.py", ".claude/bin/test_agentic.py", ".claude/bin/hook.py"],
     "acs": ["AC-001", "AC-002", "AC-003", "AC-004", "AC-005", "AC-006"], "mirror": [".claude/bin/agentic.py:408-416", ".claude/bin/agentic.py:683-687", ".claude/bin/agentic.py:2262-2270", ".claude/bin/agentic.py:1657-1667", ".claude/bin/agentic.py:1620-1626", ".claude/bin/waiting.py"]},
    {"id": "WP-02", "wave": 2, "depends_on": ["WP-01"], "files": [".claude/settings.json", ".claude/bin/test_definitions.py", ".claude/agents/gatekeeper.md"],
     "acs": ["AC-008"], "mirror": [".claude/bin/test_definitions.py:305-316", ".claude/agents/gatekeeper.md:16"]},
    {"id": "WP-03", "wave": 1, "depends_on": [], "files": [".claude/workflows/agentic-implement.js", ".claude/bin/pipeline.py", ".claude/bin/conformance.json", ".claude/bin/test_pipeline.py", ".claude/bin/test_workflow.mjs"],
     "acs": ["AC-007"], "mirror": [".claude/workflows/agentic-implement.js:139-160", ".claude/bin/pipeline.py:232-245"]},
    {"id": "WP-04", "wave": 2, "depends_on": ["WP-01"], "files": [".claude-plugin/plugin.json", ".claude/bin/upgrade.py", ".claude/bin/test_acceptance_upgrade.py", ".claude/bin/test_acceptance_v2.py", ".claude/bin/test_acceptance_v21.py", ".claude/bin/test_acceptance_v22.py", ".claude/bin/test_acceptance_v23.py", ".claude/bin/test_acceptance_v24.py", ".claude/bin/test_acceptance_v241.py", "docs/how-it-works.md", "docs/how-to/README.md", "docs/roadmap/repo-review-2026-11.md"],
     "acs": ["AC-009"], "mirror": [".claude/bin/upgrade.py:58-75"]}
  ]
}
```

## 9. Test strategy
- Acceptance: `.claude/bin/test_acceptance_v25.py`, AC-001…AC-009, written first and red. Temp repos built like `test_agentic.Repo`, with `plugin.json` and the README marker written by the test; the hook driven through `hook.py` with payloads; the engines through `test_pipeline.run_scenario` and the Node dump.
- Regression: every suite; the existing conformance scenarios must not change.
- After merging, by hand: `flow-history`, release 2.5.0, `install` in the projects (their `settings.json` changes: the hook command).
- First real use: the next plan that changes the flow, with `"maintainer": true`, through `/implement` (fallback in a cloud session).
- This plan itself owns `.claude/` paths without the mode: today's `validate`, `briefs`, `pipeline-plan` and `verify` refuse its manifest, so it runs entirely by hand.

## 10. Decisions
- **D1 · Frozen guard (user's choice):** the agents may change the guard; the run is watched by the copy taken at its start. Discarded: never-ownable `agentic.py` (most changes touch it).
- **D2 · Flag plus the flow's own repo (user's choice):** `plugin.json` named agentic-flow and the README template marker, which template copies lose on their first push.
- **D3 · Named paths except a fixed list (user's choice):** `settings.json`, `settings.local.json`, `.claude/state/` and the launcher stay nobody's even in maintainer mode, so an agent can neither reroute the hook nor touch the frozen copy.
- **D4 · A launcher in every project:** the hook command must point at a file the run never lets an agent edit. Shipping it everywhere keeps one settings layout; for projects it only runs `agentic.py hook`.
- **D5 · Release on every exit:** a leftover `active.json` would keep using a stale guard; `pipeline-plan` re-freezes at the next run anyway, and `guard-release` can be run by hand.
- **D7 · `docs.files` is `docs/assets/`:** a placeholder zone outside every WP (the default would overlap WP-04, which owns the docs this change needs); the doc-updater has nothing to do in a by-hand run.
- **D6 · 2.5.0:** projects' `settings.json` changes (the hook command) and a new file ships.

## 11. Risks and open questions
- **Agent definitions are read live:** a package that edits `reviewer.md` changes the reviewer of the same run. The frozen guard does not cover `.claude/agents/`. The commit gate (a person) is the control; a plan that changes agent files should say so in its section 11.
- **Regex Bash rules:** a determined agent could delete `active.json` through Bash; the hook's Bash rules stop mistakes, not intent (as documented today), and `close-stage` does not watch `.claude/state/`.
- **The native workflow's prompts are fixed at launch** (the Workflow tool loads the script then), and the fallback loads the spec into memory before the freeze (`agentic.py:1611`): both runs keep their starting prompts either way.
- **A resumed maintainer run** executes the live (possibly agent-edited) `pipeline-plan --keep-guard` once, in its first call, before the engines switch to the frozen command. An edited `pipeline_plan` could ignore the flag. Residual risk, accepted: the commit gate is the control, and a fresh run (not a resume) avoids it.
- **A crash between freeze and release** leaves the guard active: the next `pipeline-plan` replaces it; `hooks-check` should not be affected (it does not read the guard).
- **Settings migration:** projects that edited their hook entry keep their matcher and timeout; only the command changes.
