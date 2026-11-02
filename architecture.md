# Architecture: the flow knows when its guardrail hook is not running (agentic-flow 2.4)
Type: fix · Size: standard

## 1. Goal
Every guardrail of the flow except the stage file comparison lives in one `PreToolUse` hook (`agentic.py hook`). On 2026-11-02, in a cloud session with two repositories attached, that hook never ran: a payload dump saw zero invocations for the main thread and for an `implementer` subagent, the subagent wrote outside its zone without a block, and three `/implement` runs on this repo had finished "OK" with empty `claims.json` and `gate.json`. The official documentation says a cloud session reads a repository's hooks only when it has one repository and is not a thread inside a Claude project. The flow had no way to notice: it ran without guardrails and did not say so. This change makes the flow detect a hook that does not run, before the first agent is paid for and at the end of every stage, and stop with the cause. The bench and the fallback mode are not affected: `claude -p` runs project hooks (documented, and the bench sessions show hook blocks), but they get the stage check too. Issue #68's question (which `agent_type` the Workflow tool's subagents carry) stays open: it cannot be answered where the hook does not run.

## 2. Scope
### Included
- A heartbeat written by the hook on every invocation (`.claude/state/hook-seen.json`).
- A new command `hooks-check`, in the CLI and in `seq`, that passes only if the hook ran for that very call (or, outside a Claude tool call, only checks the configuration).
- The native workflow and the fallback pipeline run `hooks-check` first; a failure stops the run at `prepare` with the cause and the way out.
- `close-stage` refuses a stage in which files changed but the hook saw no tool call from any agent of the flow.
- `/implement` pre-flight runs `hooks-check` and, if it fails, explains and offers the fallback mode.
- Documentation, upgrade notes, version 2.4.0, acceptance tests.
### Excluded (non-goals)
- Verifying the Workflow tool's subagent `agent_type` (needs a session where the hook runs; the roadmap entry says how).
- Making the hook run where Claude Code does not load it. The flow cannot; it refuses to pretend.
- Any change to prompts, schemas or the agents' behaviour.
- A maintainer mode (#71). This plan is executed by hand like 0005 and 0007.

## 3. Stack
Python 3.9+ (`unittest`, standard library only), the workflow in JavaScript for Node 20 (`.claude/workflows/agentic-implement.js`, tested with `node .claude/bin/test_workflow.mjs`). Markdown docs.
- Build: `python3 -m compileall -q .claude/bin`
- Lint: `node .claude/bin/test_workflow.mjs`
- Tests: `python3 -m unittest discover -s .claude/bin -p "test_*.py"`; docs: `python3 -m unittest discover -s acceptance` and `python3 -m unittest discover -s qa -p "test_qa_docs.py"`.

## 4. Repository structure
```
.claude/bin/agentic.py                 WP-01 (heartbeat, hooks-check, stage liveness, SEQ_COMMANDS, CLI)
.claude/bin/test_agentic.py            WP-01 (unit tests; Repo drops CLAUDECODE and copies settings.json)
.claude/bin/testutil.py                WP-01 (the fake claude calls the hook before it writes)
.claude/commands/implement.md          WP-01 (pre-flight step)
.claude/workflows/agentic-implement.js WP-02 (hooks-check in the prepare call)
.claude/bin/pipeline.py                WP-02 (same)
.claude/bin/conformance.json           WP-02 (scenario "the guardrail hook is not running")
.claude/bin/test_pipeline.py           WP-02
.claude/bin/test_workflow.mjs          WP-02 (pinned first prompt)
.claude/bin/test_acceptance.py         WP-02 (pinned gate order, lines 249 and 251)
bench/bench.py, bench/test_bench.py    WP-02 (CLAUDECODE removed from the runs' environment)
.claude-plugin/plugin.json             WP-03 (2.4.0)
.claude/bin/upgrade.py                 WP-03 (NOTES 2.4.0)
.claude/bin/test_acceptance_upgrade.py, test_acceptance_v2.py, _v21.py, _v22.py, _v23.py  WP-03 (version pins)
docs/roadmap/repo-review-2026-11.md    WP-03 (found-while-using entries)
README.md, docs/how-it-works.md, docs/how-to/README.md, docs/how-to/web-ios.md  WP-04
.claude/bin/test_acceptance_v24.py     AT (new)
```

## 4b. Existing code context
| What an implementer needs to know | Where it is | Pattern or rule |
|---|---|---|
| The hook entry: reads stdin JSON, fails closed inside an agent | `.claude/bin/agentic.py:2263-2276` (`hook`) | The heartbeat is written right after `json.loads`, before `guard(data)`; a heartbeat error inside an agent blocks like any other (existing `except`) |
| State files and the locked JSON helper | `agentic.py:76-82` (`STATE`, `CLAIMS`, `GATE`), `agentic.py:1878-1897` (`locked_json`) | `HOOK_SEEN = STATE / "hook-seen.json"`, written with `locked_json` (creates `STATE`, survives a corrupt file) |
| What a payload carries | `test_agentic.py:70-93` (`write_payload`, `report_payload`, `bash_payload`) | `tool_name`, `tool_input`, `agent_id`, `agent_type`; the hook is driven in tests with `Repo.run("hook", stdin=json.dumps(payload), env=...)` (`test_agentic.py:54-60`) |
| Which agent types must claim | `agentic.py:2182-2189` (`claim_required_types`), `agentic.py:1516` (`READ_ONLY_AGENTS`) | A heartbeat counts as "guarded" when `agent_type` is one of those, or in `READ_ONLY_AGENTS`, or `AGENTIC_WP` is set (fallback). The `gatekeeper` and the main thread never count |
| Stage opening resets per-stage state | `agentic.py:594-602` (`snapshot`: `gitstate-<label>.json`, claims emptied) | `guarded_ts` is reset there too, with `locked_json(HOOK_SEEN, ...)` |
| Stage closing: changed files, owners, git state | `agentic.py:664-712` (`check_stage`: `changed` at 672, `owned`, `violations`, the `git state changed` block at 696-702) | The liveness check goes after the git-state block and before `content_problems`; it fails only when `changed` is non-empty |
| `seq` and its allowed commands | `agentic.py:1461-1462` (`SEQ_COMMANDS`), `agentic.py:1493-1509` (`seq`) | `hooks-check` joins `SEQ_COMMANDS`; `seq` stops at the first failing step, so a dead hook stops before `pipeline-plan` |
| CLI dispatch and exit codes | `agentic.py:2281-2340` (`main`), `agentic.py:230` (`die`) | `0` ok, `1` usage, `3` needs review (used by `open-stage`); `hooks-check` exits `3` when the hook is not running |
| The workflow's first gatekeeper call | `agentic-implement.js:395-398` (`first = seq(['pipeline-plan','briefs'],'prepare')`, `stop('prepare', ...)`) | Becomes `seq(['hooks-check','pipeline-plan','briefs'],'prepare')`; step indices shift by one |
| The pipeline's first call | `pipeline.py:232-240` (`_execute`: `first = self.seq(["pipeline-plan","briefs"],"prepare")`) | Same change; both engines must issue identical gate commands (`test_pipeline.py:115-130`, key `gates`) |
| The simulated worlds | `test_pipeline.py:28-60` (`respond`: unknown commands return exit 0), `test_workflow.mjs:40-60` | `hooks-check` passes by default in both; a scenario fails it with `gate_fail: [{"prefix":"hooks-check","exit_code":3,"output":...}]` |
| Pinned first prompt | `test_workflow.mjs:206` (`endsWith('agentic.py seq pipeline-plan + briefs')`) | Must become `seq hooks-check + pipeline-plan + briefs` |
| Claude marks its tool processes | the environment variable `CLAUDECODE=1` is set in every Bash tool process (observed in this session: `env` shows `CLAUDECODE=1`, `CLAUDE_CODE_ENTRYPOINT`) | `hooks-check` reads `CLAUDECODE` to know whether a hook should have fired for its own invocation |
| Hook configuration in the project | `.claude/settings.json:13-25` (`PreToolUse`, matcher `Write|Edit|MultiEdit|NotebookEdit|Bash|StructuredOutput`); `agentic.py:1250-1256` (`merge_settings`, used by `install`) finds the flow's hook with the rule `"agentic.py" in command and command.rstrip().endswith("hook")` | The static branch of `hooks-check` uses that same rule, extracted into a helper both call |
| Tests that drive the engines end to end with a fake `claude` | `.claude/bin/testutil.py:68-76` (the fake implementer writes `src/a.py` etc. directly, never through a hook), `test_pipeline.py:315-348`, `test_acceptance.py`, `test_acceptance_portable.py`, `_v2.py`, `_v21.py`, `_v23.py` (run-pipeline and run-wave expecting OK) | Without a hook call in the fake, the new stage check would turn every one of those runs into REVIEW: the fake calls the hook first (WP-01) |
| The test repo's environment and files | `test_agentic.py:46-52` (`Repo.__init__`: copies agents and workflows, env from `os.environ` minus `AGENTIC_WP`, `AGENTIC_CLAUDE`) | `Repo` also drops `CLAUDECODE` (tests run inside Claude Code inherit it) and copies `.claude/settings.json`, so `hooks-check` in tests takes the static branch and finds the hook |
| Pinned gate order | `test_acceptance.py:249` (`gates[:3] == ["pipeline-plan","briefs","baseline"]`), `:251` (`[:2]` on resume) | Both gain `hooks-check` first (WP-02) |
| Sequence diagram | `docs/how-it-works.md:112` (`W->>G: pipeline-plan + briefs`) | Becomes `hooks-check + pipeline-plan + briefs` (WP-04) |
| `/implement` pre-flight | `.claude/commands/implement.md:15-21` | New step 1 before `validate`; the fallback section at `implement.md:72-86` says `-p` sessions run project hooks |
| Upgrade notes and version pins | `upgrade.py:20-58` (`NOTES`, 2.3.0 has 2), `plugin.json:4`, pins at `test_acceptance_upgrade.py:258`, `_v2.py:177`, `_v21.py:283`, `_v22.py:171`, `_v23.py:256`; `_v23.py:250-262` is the release test to mirror | Every pin becomes `"2.4.0"`; `_v23.py:262` keeps `[2, 4, 7]` for 2.2/2.1/2.0 |
| Docs that describe the hook | `README.md:109` (guardrails row "A failure in the guardrail itself"), `docs/how-it-works.md:191-193` (§4 first paragraph), `docs/how-to/README.md:82` ("hooks and `deny` rules apply anyway"), `:169-206` (script reference), `:207-230` (troubleshooting table), `docs/how-to/web-ios.md:4,12,54` | The hub is capped at 260 lines and is at 260 (`acceptance/test_docs.py:158`, `qa/test_qa_docs.py:55`); the docs suites forbid hard-coded versions and counts |
| Roadmap entries to update | `docs/roadmap/repo-review-2026-11.md:106` ("Project hooks did not fire...") and `:110` ("Possible hole in the hook...") | Keep both; append what was observed and what shipped |

## 5. Data model
`.claude/state/hook-seen.json` (runtime, git-ignored with the rest of `.claude/state/`):
```json
{"ts": 1793620000.12, "tool": "Bash", "command": "python3 .claude/bin/agentic.py hooks-check",
 "agent_type": null, "guarded_ts": 1793619990.5}
```
- `ts`, `tool`, `command` (the Bash command, cut at 300 characters, `""` for other tools) and `agent_type`: the last hook invocation, any origin.
- `guarded_ts`: the last invocation that came from an agent of the flow (section 4b, "guarded"); `null` after `snapshot` opens a stage.

`hooks-check` output, one JSON line on stdout:
```json
{"ok": true, "mode": "live", "seen": 1793620000.12}
{"ok": false, "mode": "live", "seen": null, "reason": "the guardrail hook did not run for this call"}
{"ok": true, "mode": "static", "hook": "python3 \"$CLAUDE_PROJECT_DIR/.claude/bin/agentic.py\" hook"}
{"ok": false, "mode": "static", "reason": "no agentic.py hook in .claude/settings.json PreToolUse"}
{"ok": false, "mode": "static", "reason": "disableAllHooks is true in .claude/settings.local.json"}
```
`hooks-check` reads `hook-seen.json` through `locked_json`, so a corrupt file is set aside and counts as "no heartbeat" (exit 3), never a traceback.

## 6. Contracts between modules
```python
HOOK_SEEN = STATE / "hook-seen.json"
HOOK_SEEN_MAX_AGE_S = 120          # a heartbeat older than this does not prove the hook runs now
WRITE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")

def record_hook_seen(data: dict) -> None
    # Called by hook() after json.loads and before guard(). Updates ts/tool/command/agent_type;
    # updates guarded_ts when data["agent_type"] in claim_required_types() | READ_ONLY_AGENTS or os.environ.get("AGENTIC_WP").

def hooks_check() -> int
    # CLI `hooks-check` and seq step. Prints one JSON line (section 5). Returns the exit code:
    #   live mode (CLAUDECODE set): 0 if HOOK_SEEN exists and now - ts <= HOOK_SEEN_MAX_AGE_S (a dead hook leaves no fresh
    #     heartbeat: the launcher's own Bash call fired it seconds ago, whatever its command was); else 3.
    #   static mode (CLAUDECODE unset): 0 if .claude/settings.json has a PreToolUse hook that passes the rule of merge_settings
    #     (agentic.py:1250-1256) and neither settings.json nor settings.local.json sets "disableAllHooks": true; else 3.
    # On 3, stderr gets the message HOOKS_DEAD_MSG (section 7).

def run_steps(groups: list[list[str]], env: dict | None = None) -> tuple[bool, list[dict]]
    # Existing (agentic.py:1477-1483); gains `env`: the environment of the step subprocesses (default: today's
    # dict(os.environ, CLAUDE_PROJECT_DIR=...)). run_pipeline's gate (agentic.py:1607-1609) passes an env without
    # CLAUDECODE, so the fallback engine's own checks take the static branch: its agents are `claude -p` processes,
    # which load the project's hooks, and the stage check judges them. The native workflow's gatekeeper keeps live mode.

def stage_guarded(label: str) -> bool
    # True if HOOK_SEEN.guarded_ts is not None and >= mtime of STATE/f"gitstate-{label}.json". Used by check_stage.
```
`check_stage(manifest, label)` (existing, `agentic.py:672`) gains: when `changed` is non-empty and `not stage_guarded(label)`, it prints `GUARDRAIL HOOK SAW NO FLOW AGENT: <n> file(s) changed in stage <label> and no hook call came from an agent of the flow (agent_type or AGENTIC_WP). The ownership check above is the only guard that applied; if this repeats in every stage, run /implement fallback and report the agent_type the hook recorded in .claude/state/hook-seen.json.` and returns `False`. The stage then ends in `REVIEW` exactly as an ownership violation does; `close-stage` output already reaches the run result's `check` field in both engines, so no schema changes.

Both engines' first gatekeeper call is `seq hooks-check + pipeline-plan + briefs`. On a failing first step, they stop with `failed_stage: "prepare"` and `detail: "the guardrail hook is not running in this session: see .claude/state/runs or run `agentic.py hooks-check`"`, with `gate` set to that step (the same shape as `pipeline-plan failed`).

## 7. Conventions
- English, present tense, no marketing words; messages name the command that repairs or explains.
- `HOOKS_DEAD_MSG` (stderr, one paragraph): "The guardrail hook (`agentic.py hook`) did not run for this call, so no guardrail of the flow is active in this session. Known causes: a cloud session with several repositories attached, or a thread inside a Claude project (Claude Code does not read the repository's hooks there); `disableAllHooks` in a settings file; Windows without Git for Windows. The fallback mode runs each agent as `claude -p`, which does load the repository's hooks: `/implement fallback`. Or open a session with this repository alone."
- In static mode the stderr message is `HOOKS_UNCONFIGURED_MSG`: "The guardrail hook is not configured: <reason>. Run `python3 .claude/bin/agentic.py install .` from a copy of the flow to restore `.claude/settings.json`, or remove `disableAllHooks`." `HOOKS_DEAD_MSG` is only for live mode.
- No new dependencies. No clock mocking across processes: tests write `hook-seen.json` themselves with a fresh or a stale `ts`.
- `locked_json` for every write to `HOOK_SEEN`; never `Path.write_text` (two agents may fire at once).
- The hub (`docs/how-to/README.md`) stays at 260 lines or fewer: the script reference gains one line (`hooks-check`) and the troubleshooting table one row, so two existing lines are merged: `run-wave 1` / `run-wave 1 WP-02` into `run-wave 1 [WP-02]`, and `acceptance --expect red` / `--expect green` into `acceptance --expect red|green`, keeping the `#` column.
- Commits: one per WP, imperative subject, no model names.

## 8. Work packages and acceptance criteria
### Acceptance criteria
- AC-001 · The hook leaves a heartbeat on every call
  - Scenario: a repo with the flow installed and an empty `.claude/state/`.
  - Action: run `agentic.py hook` with a `bash_payload("ls", agent_id="a1", agent_type="implementer")` and then with `write_payload(...)` from the main thread (no `agent_id`, no `agent_type`).
  - Expected: after the first call `hook-seen.json` has `tool == "Bash"`, `command == "ls"`, `agent_type == "implementer"` and `guarded_ts` not null; after the second, `tool == "Write"`, `agent_type` null and `guarded_ts` unchanged.
  - Must not: block either call for the heartbeat alone (the first is blocked for the missing claim, as today; the test asserts the heartbeat was written anyway).
  - Check: `test_acceptance_v24.py::HeartbeatTests`
  - WP: WP-01
- AC-002 · `hooks-check` passes only when the hook ran for that call
  - Scenario: the test passes `CLAUDECODE=1` explicitly in the subprocess environment (`Repo.env` no longer carries it).
  - Action: (a) write `hook-seen.json` with `ts = now` (any `command`); (b) same with `ts = now - 1000`; (c) no file; (d) `CLAUDECODE` set but the file is corrupt.
  - Expected: (a) exit 0 and `{"ok": true, "mode": "live"}`; (b), (c), (d) exit 3, `ok: false`, and stderr contains "did not run for this call" and "/implement fallback".
  - Must not: pass on a stale heartbeat from an earlier session.
  - Check: `test_acceptance_v24.py::HooksCheckLiveTests`
  - WP: WP-01
- AC-003 · Outside a Claude tool call, `hooks-check` checks the configuration
  - Scenario: `CLAUDECODE` unset; the test repo has the copy of `.claude/settings.json` that `Repo` makes.
  - Action: run `hooks-check`; then with a `settings.json` whose `PreToolUse` list is empty; then with the original file plus a `settings.local.json` containing `{"disableAllHooks": true}`.
  - Expected: exit 0 with `mode: "static"`; then exit 3 with `reason` naming `settings.json`; then exit 3 with `reason` naming `disableAllHooks`.
  - Must not: read or require `hook-seen.json`.
  - Check: `test_acceptance_v24.py::HooksCheckStaticTests`
  - WP: WP-01
- AC-004 · A stage whose files changed without a guarded hook call ends in REVIEW
  - Scenario: `open-stage 1` (WP-01 owns `src/a.py`), then `src/a.py` is edited directly on disk.
  - Action: (a) `close-stage 1 WP-01=done` with no hook call in between; (b) the same after one `hook` call with `AGENTIC_WP=WP-01` (a `bash_payload("ls")`); (c) the same after only a `hook` call with `agent_type="gatekeeper"`; (d) `open-stage` then `close-stage` with no file changed and no hook call.
  - Expected: (a) exit non-zero and output containing `GUARDRAIL HOOK SAW NO FLOW AGENT`; (b) exit 0 and `all changes are within their owners`; (c) like (a); (d) exit 0.
  - Must not: count the gatekeeper's or the main thread's calls as guards; fail a stage that changed nothing.
  - Check: `test_acceptance_v24.py::StageLivenessTests`
  - WP: WP-01
- AC-005 · Both engines check the hook first and stop with the cause
  - Scenario: the conformance scenario `the guardrail hook is not running` (`gate_fail` on prefix `hooks-check`, exit 3).
  - Action: run it through `test_pipeline.world` and through the workflow runner.
  - Expected: both summaries have `result: REVIEW`, `failed_stage: prepare`, `detail` containing `guardrail hook is not running`, `gates == ["hooks-check"]`, `agents == []`; the happy path's first gate command is `hooks-check` followed by `pipeline-plan` and `briefs`.
  - Must not: call any agent after the failed check; differ between engines.
  - Check: `test_acceptance_v24.py::EnginesTests`
  - WP: WP-02
- AC-006 · `/implement` checks the hook before anything else
  - Scenario: the repository after the change.
  - Action: read `.claude/commands/implement.md`.
  - Expected: in section 1, a step that runs `python3 .claude/bin/agentic.py hooks-check` comes before the `validate` step, and the text names `/implement fallback` as the way out.
  - Must not: leave the old step numbering inconsistent (steps stay consecutive).
  - Check: `test_acceptance_v24.py::PreflightTests`
  - WP: WP-01
- AC-009 · The fallback engine is not stopped by a dead hook in the launcher's session
  - Scenario: a `Repo` with the fake `claude`, `CLAUDECODE=1` passed explicitly, no `hook-seen.json`.
  - Action: `agentic.py run-pipeline`.
  - Expected: the run does not stop at `prepare`; its first gate step is `hooks-check` with `mode: "static"` and exit 0; the run ends OK (the fake implementer's hook call marks the stages as guarded).
  - Must not: pass `CLAUDECODE` to the gate steps; remove it from the agents' environment (`child_env` is untouched).
  - Check: `test_acceptance_v24.py::FallbackGateTests`
  - WP: WP-01
- AC-007 · Release 2.4.0: version, notes and roadmap
  - Scenario: the repository after the change.
  - Action: read `plugin.json`, `upgrade.NOTES` and the roadmap.
  - Expected: version `2.4.0`; `NOTES["2.4.0"]` has at least 2 notes, mentioning `hooks-check` and `close-stage`; the note counts of 2.3/2.2/2.1/2.0 stay `[2, 2, 4, 7]`; the roadmap's found-while-using entry on cloud hooks contains "Fixed in 2.4.0".
  - Must not: change the version anywhere else than `plugin.json` and the pins.
  - Check: `test_acceptance_v24.py::ReleaseTests`
  - WP: WP-03
- AC-008 · The documentation describes the three layers
  - Scenario: the repository after the change.
  - Action: read `README.md`, `docs/how-it-works.md`, `docs/how-to/README.md`, `docs/how-to/web-ios.md`.
  - Expected: `README.md`'s guardrails row for the hook mentions `hooks-check`; `docs/how-it-works.md` §4 mentions the heartbeat and the stage check, and its sequence diagram shows `hooks-check + pipeline-plan + briefs`; the hub's script reference lists `hooks-check`, its troubleshooting table has a row for it, and the file has at most 260 lines; `web-ios.md` says the hook was observed not to run in a session with two repositories and that the flow now refuses to start there.
  - Must not: hard-code a test count or a flow version in those files (`acceptance/test_docs.py:95-97`).
  - Check: `test_acceptance_v24.py::DocsTests`
  - WP: WP-04

### Work packages
#### WP-01 · Heartbeat, `hooks-check` and stage liveness in `agentic.py`
- Wave: 1.
- Files: `.claude/bin/agentic.py`, `.claude/bin/test_agentic.py`, `.claude/bin/testutil.py`, `.claude/bin/test_acceptance_portable.py`, `.claude/commands/implement.md`.
- Contracts: implements section 6.
- ACs: AC-001, AC-002, AC-003, AC-004, AC-006, AC-009.
- **Patterns to mirror:** `agentic.py:1878-1897` (`locked_json`), `agentic.py:2182-2189` (`claim_required_types`), `agentic.py:1658-1669` (`open_stage` prints JSON and exits 3 on "nothing to do"), `agentic.py:1254` (settings parsing), `test_agentic.py:810-870` (`StopGateTests`: hook driven with payloads and env).
- **Gotchas:** the fake `claude` (`testutil.py:68-76`) writes files without any hook: before its first write the fake implementer must run the real hook: `[sys.executable, <absolute path of agentic.py>, "hook"]` with a `bash_payload`-shaped JSON on stdin (the temp repos have no `.claude/bin`, so `install_fake_claude` (`testutil.py:111`) embeds the absolute path of the real `agentic.py`, as it already embeds `sys.executable` at `testutil.py:22-32`; `AGENTIC_WP` and `CLAUDE_PROJECT_DIR` are set by `run_agent`, `agentic.py:753`), or every end-to-end test in `test_pipeline.py:315-348`, `test_acceptance.py`, `test_acceptance_portable.py`, `_v2.py`, `_v21.py` and `_v23.py` ends in REVIEW. `Repo.__init__` (`test_agentic.py:46-52`) and `Project.__init__` (`test_acceptance_portable.py:43-51`) must drop `CLAUDECODE` and copy `.claude/settings.json`, or the static branch finds no hook. `run_pipeline`'s `gate` (`agentic.py:1607-1609`) passes `run_steps` an env without `CLAUDECODE` (section 6). `/implement`'s result presentation gains one line: a `GUARDRAIL HOOK SAW NO FLOW AGENT` in a stage's `check` means the hook did not guard that stage; see the `agent_type` in `.claude/state/hook-seen.json`. `hook()` must call `record_hook_seen` before `guard` and inside the `try`, so a corrupt state file blocks inside an agent and only warns in the main thread. `snapshot` runs with stdout silenced; reset `guarded_ts` there, not in `open_stage`. `check_stage` is also used by `check-wave` and the one-off `run-*` commands: the liveness message must not break `test_agentic.py` tests that close stages after writing files directly, so those tests set `AGENTIC_WP` on a hook call or are updated (grep `close-stage` in `test_agentic.py` first). The `gatekeeper` type never counts as a guard. `hooks-check` is also valid in `seq`, so it goes into `SEQ_COMMANDS` and the docstring at `agentic.py:1-50`. Windows: `locked_json` opens with `a+`; keep it.
- **Exact imports and APIs:** `time.time()`, `os.environ.get("CLAUDECODE")`, `Path.stat().st_mtime`.
- **WP validation:** `python3 -m unittest discover -s .claude/bin -p "test_agentic.py"`, `python3 -m unittest discover -s .claude/bin -p "test_definitions.py"` (the new command is documented), `python3 -m unittest discover -s .claude/bin -p "test_pipeline.py"` (the end-to-end runs stay OK), and its own classes: `python3 -m unittest test_acceptance_v24.HeartbeatTests test_acceptance_v24.HooksCheckLiveTests test_acceptance_v24.HooksCheckStaticTests test_acceptance_v24.StageLivenessTests test_acceptance_v24.PreflightTests` from `.claude/bin`.

#### WP-02 · Both engines run `hooks-check` first
- Wave: 2 (its end-to-end tests run the real `seq`, which must already know `hooks-check`).
- Files: `.claude/workflows/agentic-implement.js`, `.claude/bin/pipeline.py`, `.claude/bin/conformance.json`, `.claude/bin/test_pipeline.py`, `.claude/bin/test_workflow.mjs`, `.claude/bin/test_acceptance.py`, `bench/bench.py`, `bench/test_bench.py`.
- Contracts: consumes `hooks-check` by implementation (WP-01, wave 1); implements the `prepare` stop of section 6; `bench.py:_child_env` drops `CLAUDECODE` (a unit test in `test_bench.py` asserts it).
- ACs: AC-005.
- **Patterns to mirror:** `agentic-implement.js:395-398` and `pipeline.py:232-240` (the `prepare` call and its stops), `conformance.json` scenario `briefs cannot be written` (a `gate_fail` on the prepare call), `test_workflow.mjs:206` (the pinned prompt), `test_pipeline.py:149-160` (the per-scenario comparison).
- **Gotchas:** `test_acceptance.py:249` and `:251` and `test_workflow.mjs:306-311` (the full gate list of the happy path) pin the gate order and gain `hooks-check` first. Step indices in `first` shift by one in both engines (`step(first, 1)` is now `pipeline-plan`, `step(first, 2)` is `briefs`). The conformance `gates` list is compared verbatim, so the new scenario and the happy path must produce identical command lists in both runners. `test_workflow.mjs --dump` output goes through `process.stdout.write` (not `process.exit`).
- **Exact imports and APIs:** none new.
- **WP validation:** `node .claude/bin/test_workflow.mjs`, `python3 -m unittest discover -s .claude/bin -p "test_pipeline.py"`, `python3 -m unittest discover -s .claude/bin -p "test_acceptance.py"`, `python3 -m unittest discover -s bench -p "test_bench.py"`.

#### WP-03 · Version 2.4.0, upgrade notes, roadmap
- Wave: 1.
- Files: `.claude-plugin/plugin.json`, `.claude/bin/upgrade.py`, `.claude/bin/test_acceptance_upgrade.py`, `.claude/bin/test_acceptance_v2.py`, `.claude/bin/test_acceptance_v21.py`, `.claude/bin/test_acceptance_v22.py`, `.claude/bin/test_acceptance_v23.py`, `docs/roadmap/repo-review-2026-11.md`.
- Contracts: none.
- ACs: AC-007.
- **Patterns to mirror:** `upgrade.py:50-58` (the 2.3.0 notes), `test_acceptance_v23.py:250-262` (the release test), roadmap lines 103-112 (the found-while-using list; the 2.3.0 fix at line 105 shows how a shipped fix is appended).
- **Gotchas:** every pin changes to `"2.4.0"`; `_v23.py:262` compares the note counts of 2.2/2.1/2.0 and stays `[2, 4, 7]`. The roadmap entry at line 106 keeps its observation and gains: the cause the documentation gives (several repositories, or a project thread), the payload dump of 2026-11-02, and "Fixed in 2.4.0: `hooks-check` before the first agent and the stage check in `close-stage`". Line 110 (the `agent_type` question) stays open and says it needs a session where the hook runs.
- **WP validation:** `python3 -m unittest discover -s .claude/bin -p "test_acceptance_*.py"`, `python3 -m unittest discover -s .claude/bin -p "test_upgrade.py"`.

#### WP-04 · Documentation
- Wave: 1.
- Files: `README.md`, `docs/how-it-works.md`, `docs/how-to/README.md`, `docs/how-to/web-ios.md`.
- Contracts: none.
- ACs: AC-008.
- **Patterns to mirror:** `README.md:93-111` (guardrails table), `docs/how-it-works.md:112` (sequence diagram) and `:191-193`, `docs/how-to/README.md:169-206` and `:207-230`, `docs/how-to/web-ios.md:1-16`.
- **Gotchas:** the hub is at its 260-line cap: apply the two merges of section 7 before adding the two lines. No `2.4.0`, no test counts (`acceptance/test_docs.py:95-97`). `web-ios.md`'s status line keeps "not tested" (no end-to-end run with guardrails there) but states the observation. `docs/how-to/README.md:82` becomes: "Without it, Claude Code ignores the project's `permissions.allow`; hooks and `deny` rules apply anyway, except in a cloud session with several repositories or a thread inside a Claude project, where no project hook runs: `hooks-check` tells you."
- **WP validation:** `python3 -m unittest discover -s acceptance`, `python3 -m unittest discover -s qa -p "test_qa_docs.py"`, `python3 -m unittest discover -s .claude/bin -p "test_definitions.py"`.

```json wp-manifest
{
  "stack": ["python", "typescript"],
  "allow_bash": ["Bash(python3 -m unittest:*)", "Bash(python3 -m compileall:*)", "Bash(node .claude/bin/test_workflow.mjs)"],
  "acceptance": {"files": [".claude/bin/test_acceptance_v24.py"], "command": "python3 -m unittest discover -s .claude/bin -p test_acceptance_v24.py"},
  "verify": {"build": "python3 -m compileall -q .claude/bin bench", "types": "python3 -m unittest discover -s qa -p test_qa_docs.py", "lint": "node .claude/bin/test_workflow.mjs", "tests": "python3 -m unittest discover -s .claude/bin -p test_*.py"},
  "docs": {"files": ["docs/assets/"], "codemap": null},
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": [".claude/bin/agentic.py", ".claude/bin/test_agentic.py", ".claude/bin/testutil.py", ".claude/bin/test_acceptance_portable.py", ".claude/commands/implement.md"],
     "acs": ["AC-001", "AC-002", "AC-003", "AC-004", "AC-006", "AC-009"], "mirror": [".claude/bin/agentic.py:1878-1897", ".claude/bin/agentic.py:2182-2189", ".claude/bin/agentic.py:1658-1669", ".claude/bin/test_agentic.py:810-870"]},
    {"id": "WP-02", "wave": 2, "depends_on": ["WP-01"], "files": [".claude/workflows/agentic-implement.js", ".claude/bin/pipeline.py", ".claude/bin/conformance.json", ".claude/bin/test_pipeline.py", ".claude/bin/test_workflow.mjs", ".claude/bin/test_acceptance.py", "bench/bench.py", "bench/test_bench.py"],
     "acs": ["AC-005"], "mirror": [".claude/workflows/agentic-implement.js:395-398", ".claude/bin/pipeline.py:232-240", ".claude/bin/test_pipeline.py:149-160", "bench/bench.py:196-202"]},
    {"id": "WP-03", "wave": 1, "depends_on": [], "files": [".claude-plugin/plugin.json", ".claude/bin/upgrade.py", ".claude/bin/test_acceptance_upgrade.py", ".claude/bin/test_acceptance_v2.py", ".claude/bin/test_acceptance_v21.py", ".claude/bin/test_acceptance_v22.py", ".claude/bin/test_acceptance_v23.py", "docs/roadmap/repo-review-2026-11.md"],
     "acs": ["AC-007"], "mirror": [".claude/bin/upgrade.py:50-58", ".claude/bin/test_acceptance_v23.py:250-262"]},
    {"id": "WP-04", "wave": 1, "depends_on": [], "files": ["README.md", "docs/how-it-works.md", "docs/how-to/README.md", "docs/how-to/web-ios.md"],
     "acs": ["AC-008"], "mirror": ["README.md:93-111", "docs/how-it-works.md:191-193", "docs/how-to/README.md:169-206", "docs/how-to/web-ios.md:1-16"]}
  ]
}
```

## 9. Test strategy
- Unit: WP-01 in `test_agentic.py` (heartbeat fields per payload kind; `guarded_ts` rules for each agent type, `AGENTIC_WP`, gatekeeper and main thread; `hooks-check` live and static branches; `stage_guarded` against the gitstate mtime; a corrupt `hook-seen.json` is set aside like other state files). WP-02 through the conformance scenario in both runners and the updated pinned prompt.
- Acceptance: `.claude/bin/test_acceptance_v24.py`, AC-001…AC-009, written first and red (today: no heartbeat file, `hooks-check` is an unknown command, `close-stage` passes a stage with direct edits, the first gate command is `pipeline-plan`, the version is 2.3.0). It uses `Repo` from `test_agentic.py` and `world`/`run_scenario` from `test_pipeline.py`, like `test_acceptance_v23.py:1-30`. For AC-005 the Node side runs `node .claude/bin/test_workflow.mjs --dump` and reads the scenario's summary, as `_v23.py` does for conformance.
- QA: the whole `.claude/bin` suite, `test_workflow.mjs`, the docs suites; plus a manual check after merging: in this cloud session (two repositories), `/implement` must stop at pre-flight with `HOOKS_DEAD_MSG`, and the native workflow launched by hand must stop at `prepare`.
- After merging, by hand: `agentic.py flow-history`, release 2.4.0 (the user publishes it), `install` in finanzas-familiares.

## 10. Decisions
- **D1 · Detect, do not work around.** The flow cannot make Claude Code load hooks it will not load; pretending to run with guardrails is the defect. Discarded: moving the guardrails to the gatekeeper (it would not see the agents' tool calls).
- **D2 · Three layers, each cheap.** `hooks-check` before any agent is paid for (pre-flight and the first gatekeeper call); the stage check for a hook that dies mid-run or that runs for the main thread but not for the subagents (#68's case); the existing file comparison stays the last line. Discarded: only the pre-flight check (it would not catch #68's case, because the gatekeeper's own call would pass).
- **D3 · Freshness, not identity.** A hook that does not run leaves no fresh heartbeat at all, so `hooks-check` only asks for one younger than 120 seconds; the launcher's own Bash call (`hooks-check`, `run-pipeline`) fired it seconds before. Matching the recorded command was discarded: in the fallback mode the heartbeat's command is `run-pipeline`, and in a bench launched from a Claude session it is the bench's own command. `command` is still recorded, for diagnosis.
- **D4 · `CLAUDECODE` decides live versus static.** Claude Code sets it in every Bash tool process; the fallback pipeline launched from a user's shell is not driven by a tool call, so a live check there would always fail. Observed in this session, not found in the documentation: section 11.
- **D5 · Both engines issue the same gate commands.** The conformance tests compare the `gates` list verbatim, so `pipeline.py` runs `hooks-check` too. Its gate steps run as subprocesses of `agentic.py` (`run_steps`, `agentic.py:1482-1483`, `env=dict(os.environ, ...)`), so they would inherit `CLAUDECODE`; the pipeline's gate removes it (section 6, `run_steps(env=...)`), because in the very session this plan is for (`/implement fallback` from a Bash tool whose hook is dead) a live check would stop the way out at `prepare`. The fallback's agents are `claude -p` processes that load the project's hooks (documented), and the stage check judges them through their `AGENTIC_WP` heartbeats. The bench removes `CLAUDECODE` from the environment it gives its runs (`bench.py:196-202`, `_child_env`), because a bench started from a Claude session is not driven by that session's tool calls and its later fixtures would see a stale heartbeat. Discarded: a per-engine conformance flag.
- **D6 · "Guarded" means an agent of the flow.** Only hook calls carrying a flow `agent_type` (or `AGENTIC_WP`) count for a stage; the gatekeeper and the main thread never do, because they always run whether or not the subagents' hooks do.
- **D7 · Version 2.4.0, not 2.3.1.** Projects get a new command, a new refusal in `close-stage` and a changed `/implement`; the upgrade notes must say so.
- **D8 · Executed by hand:** WP-01, WP-02 and WP-03 own paths under `.claude/` (`validate` refuses them, `agentic.py:403`); the manifest stays truthful; acceptance tests first and red, one commit per WP, as in 0005 and 0007.
- **D9 · `docs.files` is `docs/assets/`:** the default zone would overlap WP-04 and `validate` refuses `docs/architecture/`; nothing is expected to be written there by the doc-updater in a by-hand run.

## 11. Risks and open questions
- **`CLAUDECODE` is observed, not documented.** If a Claude Code version stops setting it, `hooks-check` falls to the static branch and the live check is lost silently; the stage check still applies. The test for the live branch sets the variable itself. Verify in the pre-flight of this plan's first real run that `CLAUDECODE=1` is present (`env | grep CLAUDECODE`).
- **Two sessions on one clone:** a second Claude session on the same checkout could leave a heartbeat younger than 120 seconds while this one's hook is dead; `hooks-check` would pass and the stage check would still catch the run. Accepted.
- **False REVIEW in a stage edited by a person:** if someone edits a file by hand during a stage, `close-stage` now says the hook saw no agent call; the message names the cause and the file comparison already treated such edits as suspicious.
- **If the Workflow tool's subagents carry no flow `agent_type` (#68's unknown):** in the native engine every stage that changes files would end in REVIEW with `GUARDRAIL HOOK SAW NO FLOW AGENT`, in local sessions too. That is the truthful outcome (the hook did not guard those writes); the message points to the fallback and to the recorded `agent_type`, and `/implement` says the same in its result presentation (WP-01); the first run in a session where `hooks-check` passes answers the question.
- **`hook-seen.json` keeps only the last call:** two agents firing at once overwrite each other's `ts`; the checks only compare against time and the stage opening, so an overwrite never produces a false failure.
- **`test_acceptance_portable.py`:** after WP-01 its `Project` drops `CLAUDECODE` and copies `settings.json`; it needs nothing else.
- **The `acceptance/` docs suite is not in `verify`** (four slots, all taken): WP-04's validation runs it.
- **#68 remains open:** the subagent `agent_type` of the Workflow tool is unknown; the roadmap says it needs a session where `hooks-check` passes.
