# Architecture: notice of agents waiting for a permission or an answer
Type: feature · Size: standard

## 1. Goal
During `/implement` a run can look stuck while one of its agents is only waiting for the user to approve a command or answer a question: Claude Code shows the prompt, but nothing in the flow says which agent of the run it is or for how long it has been waiting. This feature records, from Claude Code's own hook events, every subagent that is waiting for a permission or an answer, and shows it at the top of `agentic.py status` and `.claude/state/ledger.md` (who, what it asks, since when). The idea comes from foreman-vision; no code is taken from it.

## 2. Scope
### Included
- `waiting.py`: a small hook module, run on `PermissionRequest`, `PostToolUse`, `PostToolUseFailure` and `SubagentStop`, that records and clears waits in `.claude/state/waiting.json`. It never blocks and never prints to stdout.
- `agentic.py`: a "Waiting for you" section in the ledger and `status`; stale waits cleared when a stage opens; `waiting.py` installed; `install` adds the new hooks to a project's `settings.json` once.
- The flow's own `settings.json` with the new hooks; an upgrade note; docs.
- A fix found while validating this plan: `validate` rejects acceptance and verify commands that only carry a glob argument (`python3 -m unittest discover -s .claude/bin -p test_*.py`), a false positive introduced in 1.1.4.
### Excluded (non-goals)
- Any notification outside `status` and the ledger (sound, desktop, the workflow's result): the user chose status and ledger only. Claude Code already notifies the prompt itself.
- Answering or approving from the flow: the notice only reports.
- The main session's own waits (no `agent_id`): the user is looking at that prompt already.
- The fallback mode (`claude -p`): it is non-interactive and never shows a permission prompt.

## 3. Stack
Python 3.9+ standard library only. Node ≥ 18 only for the existing workflow tests.
- Build: `python3 -m compileall -q .claude/bin`
- Tests: `python3 -m unittest discover -s .claude/bin -p "test_*.py"`
- Acceptance: `python3 -m unittest discover -s .claude/bin -p test_acceptance_waiting.py`

## 4. Repository structure
```
.claude/bin/waiting.py                      WP-01 (new)
.claude/bin/test_waiting.py                 WP-01 (new)
.claude/bin/agentic.py                      WP-02
.claude/bin/upgrade.py                      WP-02
.claude/bin/test_agentic.py                 WP-02
.claude/settings.json                       WP-02
docs/how-it-works.md                        WP-02
docs/how-to/README.md                       WP-02
.claude/bin/test_acceptance_waiting.py      AT (new)
```
Waves: WP-01 (1) → WP-02 (2). WP-02 consumes `waiting.py` by implementation: `agentic.py` runs as a subprocess in most tests, so a double could not stand in for it (D4).

## 4b. Existing code context
| What an implementer needs to know | Where it is | Pattern or rule |
|---|---|---|
| The existing hook fails closed: any error inside an agent exits 2 | `agentic.py:1930-1945` (`hook`) | **Do not route the new events through `agentic.py hook`**: exit 2 on `PermissionRequest` denies the permission. `waiting.py` always exits 0 (D2) |
| How the state dir and root are found | `agentic.py:72-74` (`ROOT` from `CLAUDE_PROJECT_DIR` or the file's location; `STATE = ROOT/.claude/state`) | `waiting.py` computes them the same way, without importing `agentic` |
| Locked JSON read-modify-write | `agentic.py:1626-1644` (`locked_json`: open `a+`, `compat.locked`, corrupt → set aside) | Mirror it in `waiting.py` with `compat.locked`; on Windows a lock is mandatory, so reads take it too (`agentic.py` `usage_records`) |
| Claims: agent id → WP or QA/AT/REVIEW/DOCS | `.claude/state/claims.json` (`agentic.py:76`, written by the hook's `claim`) | `{"<agent_id>": "WP-01"}`; read it under the lock to name who is waiting |
| Stage start resets per-stage state | `agentic.py:569-579` (`snapshot`; claims emptied at 576) | Add the waits' reset next to the claims' |
| The ledger text | `agentic.py:1712-1737` (`ledger_render`; first lines at 1717) | Insert the "Waiting for you" section after `Updated:` and before `## Stages` |
| `status` renders, then prints the ledger | `agentic.py:1961-1963` | No change: it shows the new section through `ledger_render` |
| Importing a sibling module | `agentic.py:1328-1330` (`sibling(name)`) | `sibling("waiting")` |
| What `install` copies | `agentic.py:119-120` (`INSTALL_GLOBS`) | Add `.claude/bin/waiting.py` |
| Merging the flow's settings into a project's | `agentic.py:1030-1057` (`merge_settings`; only `PreToolUse`, detected by `agentic.py … hook`) | Add the other events' entries once, never removing the project's own hooks |
| The flow's settings | `.claude/settings.json` (hooks at 13-25) | Add four event entries (§5) |
| Upgrade notes | `upgrade.py:19-40` (`NOTES`, by version) | Add `"1.1.5"` |
| The over-broad command check | `agentic.py:400-405` (acceptance and verify commands), `agentic.py:326-330` (`open_ended_rule`, which treats any `*` as a wildcard) | `sync_permissions` (`agentic.py:1597-1604`) and `pipeline_tools` (`agentic.py:1289-1304`) copy each command into `Bash(<cmd>)` and `Bash(<cmd>:*)`, where Claude Code reads `*` as a wildcard. A `*` in a later argument is acceptable only because the program prefix stays fixed (§6). `open_ended_rule` itself stays as it is for `allow_bash` |
| Real hook payloads | foreman-vision's captured fixture (Windows, Claude Code 2.1.x) | `PermissionRequest` has `hook_event_name`, `session_id`, `agent_id`, `agent_type`, `tool_name`, `tool_input` (no `tool_use_id`); it comes after the agent's `PreToolUse` and before its `PostToolUse`; the main session's has no `agent_id` |
| Test repo and hook helpers | `test_agentic.py:42-75` (`Repo`: temp git repo, `run`, `hook`, `write`), `test_agentic.py:933-1000` (`InstallTests`) | Mirror them |
| Module style | `upgrade.py:1-40`, `compat.py:1-20` | Docstring with purpose and callers; small functions; stdlib only |

## 5. Data model
`.claude/state/waiting.json` (ignored by git, like all of `.claude/state/`):
```json
{"<agent_id>": {"who": "WP-02", "agent_type": "implementer", "tool": "Bash", "detail": "npm run e2e", "since": 1793462580.5}}
```
- `who`: the agent's claim from `claims.json`; without one, `null`.
- `detail`: the first string among `tool_input.command`, `file_path`, `url`, `description`, `prompt`; newlines turned into spaces; cut to 120 characters with `…`. `""` if none.
- `since`: `time.time()` when the request arrived.

New entries in the flow's `.claude/settings.json` `hooks`. The command for all four is `python3 "$CLAUDE_PROJECT_DIR/.claude/bin/waiting.py" || true`: Claude Code runs hook commands through a shell (Git Bash on Windows), and `|| true` keeps the exit code 0 even if the file is missing, because an exit 2 on `PermissionRequest` would deny the permission (D10):
```json
"PermissionRequest":  [{"matcher": "*", "hooks": [{"type": "command", "command": "<command>"}]}],
"PostToolUse":        [{"matcher": "*", "hooks": [{"type": "command", "command": "<command>"}]}],
"PostToolUseFailure": [{"matcher": "*", "hooks": [{"type": "command", "command": "<command>"}]}],
"SubagentStop":       [{"hooks": [{"type": "command", "command": "<command>"}]}]
```

## 6. Contracts between modules
**`waiting.py`** (WP-01). Imports only the standard library and `compat` (its folder on `sys.path`); never `agentic`, `pipeline`, `brief` or `upgrade`.
```python
WAITING_FILE = "waiting.json"

def handle(payload: dict, state_dir: Path, now: float) -> None
    """PermissionRequest with an agent_id: records the wait (§5); a tool_input that is not an object gives detail "". PostToolUse, PostToolUseFailure or SubagentStop
    with an agent_id: removes that agent's wait. Anything else: nothing. When the file does not exist, a removal
    returns at once and creates nothing (no folder, no file)."""

def current(state_dir: Path) -> list[dict]
    """The waits sorted by (since, agent_id), each the §5 entry plus "agent_id". [] if the file is missing, empty or
    corrupt."""

def describe(entry: dict, now: float) -> str
    """One line. tool "AskUserQuestion": "<name> has a question for you"; otherwise
    "<name> needs your permission for <tool>: <detail>" (": <detail>" omitted when detail is ""); then
    " — waiting <N> min (since <HH:MM>)", N = int((now - since) // 60), HH:MM = local time of since.
    <name> is "WP-02 (implementer)" with a claim, "implementer agent" without one, "subagent" with neither."""

def clear(state_dir: Path) -> None
    """Empties the file if it exists (no folder or file is created)."""

def main() -> None
    """Hook entry: reads stdin as UTF-8 (compat.read_stdin_text), calls handle(payload, <ROOT>/.claude/state,
    time.time()). Any exception is swallowed after one line on stderr; always exits 0; never writes to stdout."""
```
**`agentic.py`** (WP-02)
- `INSTALL_GLOBS` gains `.claude/bin/waiting.py`.
- `snapshot(label)`: after the claims reset, `sibling("waiting").clear(STATE)`; any exception there (a missing or broken module) is ignored, like in `ledger_render`.
- `ledger_render()`: reads the waits with `sibling("waiting").current(STATE)`; if the import or the call raises any exception, the section is left out and the ledger renders as before. When the list is not empty, inserts after `Updated: …` and its blank line: `## Waiting for you`, a blank line, one `- <describe(entry, time.time())>` per wait, a blank line. Nothing is added when there is no wait.
- `validate`: an acceptance or verify command (split with `shlex.split`) is "too broad" when (a) it is a single program from `OPEN_ENDED`, or (b) its first token contains `*`, or (c) a token containing `*` comes right after a program from `OPEN_ENDED`, or right after that program's `-c` or `-e`. Otherwise a `*` in an argument is allowed (`python3 -m unittest discover -s .claude/bin -p test_*.py`). `allow_bash` rules keep `open_ended_rule` unchanged.
- `merge_settings(dst, src)`: `PreToolUse` as today; for every other event in `src["hooks"]`, each `src` entry is appended unless the destination event already has a hook whose `command` equals one of that entry's commands; each event that gets an entry adds `hook <event>` to the returned list. The project's own entries are never removed or changed.

**`upgrade.py`** (WP-02): `NOTES["1.1.5"] = ["settings.json gets hooks on PermissionRequest, PostToolUse, PostToolUseFailure and SubagentStop: agentic.py status shows which agent of a run is waiting for your permission or answer."]`.

## 7. Conventions
- English; stdlib only; `agentic.py`'s style inside it (no annotations), annotated public signatures in the new module (`.claude/rules-library/python.md`).
- `waiting.py` is a hook that observes: exit 0 always, nothing on stdout (a hook's stdout can reach the agent's context), one line on stderr only on an unexpected error.
- UTF-8 declared on every text read and write in `waiting.py` too (a coding rule here; `test_acceptance_portable.py` is not changed).
- Test commits use `git -c user.name=t -c user.email=t@t`.

## 8. Work packages and acceptance criteria
### Acceptance criteria
Every check runs a real `python3 .claude/bin/waiting.py` (stdin JSON, `CLAUDE_PROJECT_DIR` set to a temp git repo with an `architecture.md` manifest and the repo's `.claude/workflows` and `.claude/agents`) and `agentic.py`, with `sys.executable`.
- AC-001 · A claimed agent's permission request is shown
  - Scenario: `claims.json` = `{"ag1": "WP-01"}`.
  - Action: `waiting.py` with `{"hook_event_name": "PermissionRequest", "agent_id": "ag1", "agent_type": "implementer", "tool_name": "Bash", "tool_input": {"command": "npm run e2e"}}`; then `agentic.py status`.
  - Expected: `waiting.py` exits 0 with empty stdout; `status` prints `## Waiting for you` above `## Stages` and a line matching `^- WP-01 \(implementer\) needs your permission for Bash: npm run e2e — waiting 0 min \(since \d\d:\d\d\)$` (a regex: the minute may roll over).
  - Must not: write anything to `waiting.py`'s stdout, or block (exit 2).
  - Check: `test_acceptance_waiting.py::test_ac_001_permission_shown`.
  - WP: WP-01, WP-02
- AC-002 · The wait ends when the tool runs, fails, or the agent stops
  - Scenario: the AC-001 wait recorded, three times (one per event).
  - Action: `waiting.py` with `PostToolUse`, then (new wait) `PostToolUseFailure`, then (new wait) `SubagentStop`, each with `"agent_id": "ag1"`; `status` after each.
  - Expected: no `Waiting for you` section after each one.
  - Must not: clear another agent's wait (a second wait of `ag2` stays listed after `ag1`'s `PostToolUse`).
  - Check: `test_acceptance_waiting.py::test_ac_002_cleared`.
  - WP: WP-01, WP-02
- AC-003 · Questions, unclaimed agents and the main session
  - Scenario: no claims.
  - Action: `PermissionRequest` with `"agent_id": "q1", "agent_type": "qa", "tool_name": "AskUserQuestion"`; one with `"agent_id": "x1", "agent_type": "implementer", "tool_name": "WebFetch", "tool_input": {"url": "https://example.com"}`; one with no `agent_id`.
  - Expected: `status` lists `qa agent has a question for you` and `implementer agent needs your permission for WebFetch: https://example.com`, and exactly two lines under the section.
  - Must not: record the main session's request.
  - Check: `test_acceptance_waiting.py::test_ac_003_kinds`.
  - WP: WP-01, WP-02
- AC-004 · The hook never blocks and costs little when nobody waits
  - Scenario: a repo with no `.claude/state/`.
  - Action: `waiting.py` with `PostToolUse` (`"agent_id": "a"`); with stdin `not json`; with `PermissionRequest` whose `tool_input` is a string.
  - Expected: exit 0 and empty stdout every time; after the first, `.claude/state/` does not exist; `waiting.py` imports none of `agentic`, `pipeline`, `brief`, `upgrade` (checked with `ast`).
  - Must not: exit with any other code or create files for a removal.
  - Check: `test_acceptance_waiting.py::test_ac_004_never_blocks`.
  - WP: WP-01
- AC-005 · A new stage starts with no waits
  - Scenario: the AC-001 wait recorded.
  - Action: `agentic.py snapshot 1`, then `status`.
  - Expected: no `Waiting for you` section.
  - Must not: keep a wait from an agent of an earlier stage.
  - Check: `test_acceptance_waiting.py::test_ac_005_stage_resets`.
  - WP: WP-02
- AC-006 · install adds the hooks once and keeps the project's
  - Scenario: a git repo whose `.claude/settings.json` has its own `PostToolUse` hook `{"matcher": "Write", "hooks": [{"type": "command", "command": "echo mine"}]}`, committed.
  - Action: `agentic.py install <repo>` (from this repo), commit, install again.
  - Expected: after the first, `settings.json` has one `waiting.py` entry under each of the four events, `echo mine` is kept, the output lists `hook PermissionRequest`, and `.claude/bin/waiting.py` exists; after the second, still one entry per event and the output lists no `hook PermissionRequest`.
  - Must not: duplicate an entry or remove the project's hook.
  - Check: `test_acceptance_waiting.py::test_ac_006_install`.
  - WP: WP-02

- AC-007 · A verify command with a glob argument is valid
  - Scenario: a manifest whose `verify.tests` is `python3 -m unittest discover -s .claude/bin -p test_*.py` and whose `acceptance.command` is `python3 -m pytest tests/*_acceptance.py`.
  - Action: `agentic.py validate`.
  - Expected: `Manifest valid.`, exit 0.
  - Must not: accept as `verify.tests` any of `python3`, `bash`, `*`, `bash -c *`, `python3 -c *`, `npm *` (each still `command too broad`), or relax `allow_bash` (`Bash(npm:*)` still rejected).
  - Check: `test_acceptance_waiting.py::test_ac_007_glob_arguments`.
  - WP: WP-02

### Work packages
#### WP-01 · `waiting.py`: record and clear waits
- Wave 1. Files: `.claude/bin/waiting.py`, `.claude/bin/test_waiting.py`.
- Implements §6 `waiting.py`. Unit tests call `handle`, `current`, `describe` and `clear` in-process on a temp dir (fixed `now`), and `main` through a subprocess for exit code and stdout.
- ACs: AC-001 (with WP-02), AC-002, AC-003, AC-004.
- Patterns to mirror: `.claude/bin/agentic.py:1626-1644` (locked read-modify-write), `.claude/bin/upgrade.py:1-40` (module style), `.claude/bin/test_upgrade.py:1-40` (tests).
- Gotchas: the root comes from `CLAUDE_PROJECT_DIR` or `Path(__file__).resolve().parents[2]`; `sys.path.insert(0, <its folder>)` before `import compat`; read `claims.json` under `compat.locked` too, and only if it exists (a missing file gives `who` null and creates nothing); a removal must check the file exists before opening it (`a+` would create it); never `print` to stdout.
- Validation: `python3 -m unittest discover -s .claude/bin -p test_waiting.py`.

#### WP-02 · Show the waits, reset them per stage, install the hooks
- Wave 2, `depends_on: ["WP-01"]` (consumes `waiting.py` by implementation). Files: `.claude/bin/agentic.py`, `.claude/bin/upgrade.py`, `.claude/bin/test_agentic.py`, `.claude/settings.json`, `docs/how-it-works.md`, `docs/how-to/README.md`.
- Implements §6 `agentic.py` and `upgrade.py`, the §5 settings entries, and docs: in `docs/how-it-works.md` §7 the `waiting.py` and `state/waiting.json` lines; in `docs/how-to/README.md` "Follow and stop the work" one bullet: `status` shows which agent is waiting for your permission or answer.
- ACs: AC-001, AC-002 and AC-003 (with WP-01, through `ledger_render`), AC-005, AC-006, AC-007.
- Patterns to mirror: `.claude/bin/agentic.py:1030-1057` (`merge_settings`), `.claude/bin/agentic.py:1712-1737` (`ledger_render`), `.claude/bin/test_agentic.py:988-1000` (settings install test).
- Gotchas: `waiting.py` exists from wave 1, and most tests run `agentic.py` as a subprocess, so use the real module; keep `merge_settings`'s legacy `PreToolUse` rule; the `InstallTests` fixture already has `"hooks": {"PostToolUse": []}` (`test_agentic.py:941`): an empty event list gets the entry and reports `hook PostToolUse`, and `test_reinstalling_is_idempotent` must still print `settings.json: unchanged` on the second install; `test_definitions.py` and `test_acceptance_portable.py::test_ac_010_no_visible_change` read `.claude/settings.json` (keep the `PreToolUse` entry unchanged).
- Validation: `python3 -m unittest discover -s .claude/bin -p test_agentic.py`.

```json wp-manifest
{
  "stack": ["python"],
  "allow_bash": ["Bash(python3 -m unittest:*)", "Bash(python3 -m compileall:*)"],
  "acceptance": {"files": [".claude/bin/test_acceptance_waiting.py"], "command": "python3 -m unittest discover -s .claude/bin -p test_acceptance_waiting.py"},
  "verify": {"build": "python3 -m compileall -q .claude/bin", "tests": "python3 -m unittest discover -s .claude/bin -p test_*.py"},
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": [".claude/bin/waiting.py", ".claude/bin/test_waiting.py"],
     "acs": ["AC-001", "AC-002", "AC-003", "AC-004"],
     "mirror": [".claude/bin/agentic.py:1626-1644", ".claude/bin/upgrade.py:1-40", ".claude/bin/test_upgrade.py:1-40"]},
    {"id": "WP-02", "wave": 2, "depends_on": ["WP-01"], "files": [".claude/bin/agentic.py", ".claude/bin/upgrade.py", ".claude/bin/test_agentic.py", ".claude/settings.json", "docs/how-it-works.md", "docs/how-to/README.md"],
     "acs": ["AC-001", "AC-002", "AC-003", "AC-005", "AC-006", "AC-007"],
     "mirror": [".claude/bin/agentic.py:1030-1057", ".claude/bin/agentic.py:1712-1737", ".claude/bin/test_agentic.py:988-1000"]}
  ]
}
```

## 9. Test strategy
- Unit: `test_waiting.py` (WP-01) and new cases in `test_agentic.py` (WP-02).
- Acceptance: `test_acceptance_waiting.py`, from AC-001…AC-007, written first and red before the code.
- CI: the existing matrix (Linux 3.9/3.12/3.14, macOS, Windows).
- Release step after the WPs: `python3 .claude/bin/agentic.py flow-history`, commit; the version bump to 1.1.5 is a separate PR, as before.

## 10. Decisions
- **D1 · Implemented outside `/implement`**, as every change to the flow: its files are under `.claude/`, so `validate` rejects this manifest on purpose.
- **D2 · A separate hook module, not `agentic.py hook`.** That hook fails closed, and exit 2 on `PermissionRequest` denies the permission; it also loads the whole `agentic.py`. `waiting.py` only observes, always exits 0 and loads the standard library and `compat`.
- **D3 · The wait ends on `PostToolUse` (user's choice)**, plus `PostToolUseFailure` and `SubagentStop`. Exact, at the cost of one short Python process per tool call; a removal with no file returns before reading anything. Discarded: clearing on the agent's next tool call (no cost, but "waiting" would show while an approved long command runs).
- **D4 · Two waves, not contracts first:** `ledger_render` and `snapshot` run in `agentic.py` subprocesses throughout the suite, and `test_definitions.py` checks that every `INSTALL_GLOBS` file exists; WP-02 needs the real `waiting.py`.
- **D5 · Shown in `status` and the ledger only (user's choice).** Claude Code already notifies the prompt; the flow adds which agent of the run it is and since when.
- **D6 · Who is named by the claim**, the flow's own identity (`WP-02`, `QA`); without a claim, by the agent type.
- **D7 · Main-session waits are not recorded:** they have no `agent_id`, and the user is already looking at that prompt.
- **D8 · Waits reset when a stage opens**, like claims: a run stopped mid-stage leaves no stale wait in the next one.
- **D9 · The glob false positive is fixed here** because WP-02 already owns `agentic.py` and the flow's own verify command trips it; it is a one-line rule change with its own criterion (AC-007).
- **D10 · `|| true` on the hook command:** without it, a checkout or a half-applied upgrade that has the settings but not `waiting.py` would deny every subagent's permission (Python exits 2 for a missing file). `ledger_render` also leaves the section out if the module is missing or fails.

## 11. Risks and open questions
- **Hook payload fields** come from one captured run (Claude Code 2.1.x on Windows) and Claude Code's documentation; a later version could rename them. `waiting.py` then records nothing, and nothing breaks.
- **Cost:** one more `python3` per tool call for every agent and the main session; on Windows, where starting Python is slower, a few hundred milliseconds per call is possible. Not measured.
- **A denied permission** may end without `PostToolUseFailure` in some versions; `SubagentStop` and the next stage's reset clear it then.
- **Workflow agents stopped from `/workflows`** may not fire `SubagentStop`: the wait stays until the next stage opens.
- **Follow-up, out of scope:** delivery B of Windows (the planned `sh` launcher, not yet designed) will have to change this hook's command too.
- **Without a shell to run hooks** (Windows without Git Bash, which the flow does not support) `|| true` would not apply.
- **Rollback:** revert the merge commit; in a project, revert its upgrade commit. The four hook entries are the only change to `settings.json`.
