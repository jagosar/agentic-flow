# Architecture: retire the per-release acceptance files (issue 99, agentic-flow 2.10.0)
Type: refactor · Size: standard

## 1. Goal
Twelve per-release acceptance files in `.claude/bin` (`test_acceptance.py`, `_portable`, `_upgrade`, `_waiting`, `_v2`, `_v21`, `_v22`, `_v23`, `_v24`, `_v241`, `_v27`, `_v29`) hold 3,111 lines and 129 tests that pin yesterday's behaviour and are edited on almost every release. Measured with line coverage (`coverage` 7.17.2, subprocesses followed, production Python of `.claude/bin` only), they execute 70 lines that the remaining suites do not; most of their other assertions duplicate unit tests or pin wording. This refactor moves every check that is still unique behaviour or a structural invariant into the unit suites, by module, deletes the twelve files, and adds the rule, enforced by a test, that `.claude/bin` holds at most one acceptance file: the current release's (`test_acceptance_v210.py` stays until 2.11).

## 2. Scope
### Included
- The checks marked MOVE in section 4b, moved into the destination files listed there, as behaviour tests.
- Deleting the twelve files; `test_acceptance_v210.py` stays.
- A test in a new `test_layout.py`: at most one `test_acceptance*.py` in `.claude/bin` (agentic-flow repository only), added in wave 2 with the deletions.
- `bench/acceptance/test_acceptance_bench.py:410`: stop running the deleted `test_acceptance_portable` module.
- `testutil.py`'s docstring, `NOTES["2.10.0"]` (one more note), the publish ceremony in `docs/how-to/plugin.md` (the rule), the quality baseline lowered with `quality --update`.

### Excluded (non-goals)
- `bench/acceptance/` (the bench's own acceptance set) and `test_acceptance_v210.py`.
- Any production code change, except the one `NOTES["2.10.0"]` note in `upgrade.py`. The refactor is green before and after.
- Checks marked DROP: wording, version numbers, counts, roadmap text and notes text are not kept anywhere.
- `docs/roadmap/` and the archived designs, which mention the old files as history.
- `.claude/bin/fixtures/lean-agents-plan.md`, a fixture whose text cites `test_acceptance.py`.

## 3. Stack
- Python 3.9+ standard library and `unittest`; Node 22 for `test_workflow.mjs`. No new dependency (coverage was only a measuring tool, outside the repo).
- Everything: `python3 -m unittest discover -s .claude/bin -p "test_*.py"`, `python3 -m unittest discover -s bench -p "test_*.py"`, `python3 -m unittest discover -s bench/acceptance`, `node .claude/bin/test_workflow.mjs`, `python3 .claude/bin/agentic.py quality`.

## 4. Repository structure
```
.claude/bin/test_quality.py            WP-01  measurement, ratchet, the quality command and verify phase, encodings scan
.claude/bin/test_install.py            WP-02  new: install end to end
.claude/bin/test_guardrail.py          WP-03  new: heartbeat, hooks-check, stage liveness, gate messages
.claude/bin/test_pipeline.py           WP-04  engine records, spec schemas
.claude/bin/test_launcher.py           WP-04  new: launchers, usage, fix sources (keeps test_pipeline.py small)
.claude/bin/test_brief.py              WP-05  brief contracts and the briefs command
.claude/bin/test_compat.py             WP-05  no fcntl outside compat, UTF-8 end to end
.claude/bin/test_waiting.py            WP-05  status section, url detail, isolation, stage reset
.claude/bin/test_release.py            WP-05  tag gap and shallow clone through the command
.claude/bin/test_ci.py                 WP-06  new: CI and release workflow structure
.claude/bin/test_definitions.py        WP-06  unknown command, template headings, live command, pre-flight
.claude/bin/test_upgrade.py            WP-06  release files stay out of EXTRA_GLOBS
.claude/bin/test_manifest_check.py     WP-06  new: open-ended commands, never-owned in a by-hand plan
.claude/bin/test_repo_scan.py          WP-06  new: callers order, keys and whole words
bench/test_bench.py                    WP-07  bootstrap and sign-test edge cases
bench/acceptance/test_acceptance_ab.py WP-07  new: bench.py ab end to end
bench/acceptance/test_acceptance_bench.py WP-08  line 410: drop test_acceptance_portable
.claude/bin/test_layout.py             WP-08  new: the one-file rule
.claude/bin/testutil.py                WP-07  docstring
.claude/bin/upgrade.py                 WP-07  one more NOTES["2.10.0"] note
docs/how-to/plugin.md                  WP-07  the one-file rule in the ceremony
.claude/bin/test_acceptance.py, _portable, _upgrade, _waiting, _v2, _v21, _v22, _v23, _v24, _v241, _v27, _v29   WP-08  deleted
.claude/quality-baseline.json          MAINT  rewritten with quality --update (never owned; expect a larger diff: some entries are stale)
.claude/flow-history.json              MAINT  regenerated as the branch's last commit: 2.10.0 is untagged, so CI's history check also covers HEAD
```

## 4b. Existing code context
**Measured:** 70 production lines executed only by the twelve files (none by `_portable`, `_upgrade`, `_v22`, `_v241`). Each is kept by a MOVE row below; the row says which.

**Shared helpers** (copy what a destination needs into it; do not import from a deleted file):
| Helper | Where | Use |
|---|---|---|
| `Repo(manifest)`, `.run(*args, stdin, env)`, `.hook`, `.write`, `.cleanup`; `MANIFEST`, `PY`, `SCRIPT`, `write_payload`, `bash_payload`, `report_payload` | `.claude/bin/test_agentic.py:20-100` | Temporary project with agents, workflows and settings; `Repo.run` returns the `CompletedProcess` (use it, not `Repo.hook`, when stderr matters) |
| `Copy` (a repo with a copy of `.claude/bin`), `publish(tag)` | `.claude/bin/test_release.py:20-60` | Tag and history scenarios |
| `world`, `run_scenario`, `CONFORMANCE`, `SPEC`, `E2E_MANIFEST`, `RunPipelineEndToEndTests.setUp`, `saved()` | `.claude/bin/test_pipeline.py:24-140`, `:240-280` | Engine and end-to-end runs with the fake claude |
| `testutil.install_fake_claude`, `fake_calls`; switches `FAKE_MODE` (`structured`, `text`, `nousage`), `FAKE_WRITE`, `FAKE_NOT_CHECKED`, `FAKE_NEEDS_VALIDATION`, `FAKE_CONCERNS`, `FAKE_SLEEP` | `.claude/bin/testutil.py:40-135` | Fake agents |
| `Repo`/`GIT`/`sha` for git histories | `.claude/bin/test_upgrade.py:15-36` | Install and history scenarios |
| `Sandbox`, `make_fixture` | `bench/acceptance/test_acceptance_bench.py:48-110` | `bench.py` runs |
| `Project`, `Portable`, `testutil()`, `manifest()` | `.claude/bin/test_acceptance_portable.py:25-118` | CRLF install (WP-02) and prompt-on-stdin (WP-04) |
| `Upgrade` base class, `sha`, `write`, `commit` | `.claude/bin/test_acceptance_upgrade.py:18-86` | Install scenarios (WP-02) |
| v27 `InstallTests.target`/`install` | `.claude/bin/test_acceptance_v27.py:330-380` | Baseline install (WP-02) |
| `FLOW_REPO_ONLY` | `.claude/bin/test_definitions.py:28` | Skip outside the agentic-flow repository |
| `is_flow_repo` patched where it is read: `mock.patch.multiple(core, is_flow_repo=...)` and the same on `manifest_check` | `.claude/bin/test_acceptance_v210.py:51-54` | Never-owned rule of a by-hand plan |

**The inventory.** Every test of the twelve files, with its verdict. MOVE: keep the listed behaviour (only it) in the destination. DUP: an existing test already checks it (named). PIN: wording, version, count or notes; dropped. Line references `vNN:L` are to the file being retired, read before deleting it.

`test_acceptance.py`
| Test | Verdict | Behaviour kept, destination |
|---|---|---|
| test_ac_001_wp_brief | MOVE | A WP brief: header `> Brief for WP-01:`, sections 1, 2, 3, 4b, 5, 6, 7, 9, 11, its AC and WP block, a JSON tail with only its manifest entry; no other AC/WP, no section 4 or 10, no `wp-manifest`. → test_brief.py |
| test_ac_002_at_brief | MOVE | The AT brief: sections 1, 2, 3, 4b, 5, 6, 7, 9, every AC, a `{"acceptance": ...}` tail; no WP blocks, no section 10 or 11, no manifest. → test_brief.py |
| test_ac_003_fallback | MOVE | Missing WP heading and unknown WP id fall back to the whole text with `sliced=False` (the only hit of `brief.section_eight`'s `return None`). → test_brief.py |
| test_ac_004_fences | MOVE | A backtick fence in section 6 holding `## 10.` and `#### WP-02` lines starts no section and no WP block. → test_brief.py |
| test_ac_005_briefs_command | MOVE | `briefs` writes `.claude/state/briefs/{WP-01,WP-02,AT}.md` equal to the slicer, prints `briefs[id].sliced/words` and `full_words`, writes nothing else, works inside `seq pipeline-plan + briefs`, and exits 1 without a manifest (the only hit of `require_valid`'s and `load_manifest`'s error lines). → test_brief.py |
| test_ac_007_single_report_format | MOVE (second half) | With `FAKE_MODE=text`, `run-wave` exits 3 and the ledger shows WP-01 `error` with `NO REPORT`. First half DUP of `test_pipeline::RunPipelineEndToEndTests::test_every_agent_runs_with_its_schema_identity_and_tools`. → test_launcher.py |
| test_ac_008_fix_defects | MOVE (second half) | `run-wave 1 WP-01 --fix` when the only defect is WP-02's exits 1 with `WP-01: no blocking defect from review or QA is attributed to it.` and starts no agent. First half DUP of `test_agentic::LauncherTests::test_fix_only_when_requested`. → test_launcher.py |
| test_ac_009_dead_commands | MOVE (one command) | An unknown subcommand exits 1 and prints the usage (`Subcommands`). Retired names are PIN. → test_definitions.py |
| test_ac_010_usage | MOVE | Each agent appends a `usage.jsonl` record `{id, agent, label, input, cache_read, output, cost_usd, turns}`; `status` shows `## Usage` and a total. → test_launcher.py |
| test_ac_010_usage_missing_fields | MOVE | No usage in the output: `input=0, cache_read=0, output=0, cost_usd=None`; `status` shows `$?`. → test_launcher.py |
| test_ac_010_run_pipeline_reports_usage | MOVE | `workflow-result.json` has `usage.by_agent` and `usage.total`; each implementer prompt cites `.claude/state/briefs/<id>.md`. Counts become relative (no `7`). → test_launcher.py |
| test_ac_006_prompts_use_briefs | DUP | `test_workflow.mjs` "agents read their brief, the judges the whole document" and the batched-gates test |
| test_ac_011_agents_json_only | DUP | `test_definitions::AgentDefinitionTests::test_report_is_json_by_schema`, `test_agents_that_get_a_brief_read_it` |
| test_ac_012_architect_template | MOVE | `architect.md` has `#### WP-NN · ` and the `acs` field; `plan-reviewer.md` has `#### WP-` and `- AC-NNN ·` (the slicer's headings). → test_definitions.py |
| test_ac_013_docs | PIN | |

`test_acceptance_portable.py`
| Test | Verdict | Behaviour kept, destination |
|---|---|---|
| test_ac_001_no_fcntl | MOVE | `agentic` imports and `locked_json` works with `fcntl` blocked; no flow module but `compat.py` imports `fcntl` or `msvcrt`. → test_compat.py |
| test_ac_003_utf8 | MOVE | With `PYTHONIOENCODING=ascii` and non-ASCII text, `validate`, `mark` and `status` raise no Unicode error. → test_compat.py |
| test_ac_004_encodings_declared | MOVE | AST scan: every text `open`, `read_text`, `write_text` and text `subprocess.run/Popen` in the flow modules declares `encoding`. → test_quality.py |
| test_ac_007_crlf_intact | MOVE | Install lists a CRLF target file whose LF hash is in the history as `updated`, not `modified by you`. → test_install.py |
| test_ac_008_prompt_on_stdin | MOVE | The launcher passes the prompt on stdin: no argv element contains a newline; `--json-schema` present. → test_launcher.py |
| test_ac_010_no_visible_change | MOVE (reduced) | `settings.json` allows `Bash(python3 .claude/bin/agentic.py:*)`; the workflow calls `python3 .claude/bin/agentic.py`; no `sh .claude/bin/agentic` in settings, workflow or `implementer.md`. → test_definitions.py |
| test_ac_011_ci_matrix | MOVE | CI: `runs-on: ${{ matrix.os }}`, ubuntu-latest and windows-latest, Python 3.9, 3.12, 3.14, `shell: bash`. → test_ci.py |
| test_ac_002_resolve, _005_native_paths, _006_claims, _009_unreadable_ledger, _012_compat_installed | DUP | `test_compat::ResolveTests::test_finds_a_program_on_path`; `test_agentic::HookWriteTests::test_fallback_mode_own_and_foreign`, `::test_workflow_mode_needs_claim`; `test_upgrade::GuardTests::test_an_unreadable_ledger_blocks`; `test_agentic::InstallTests::test_installed_flow_works` |

`test_acceptance_upgrade.py` (all MOVE → test_install.py, with the `Upgrade` helper at `test_acceptance_upgrade.py:18-86`)
| Test | Verdict | Behaviour kept |
|---|---|---|
| test_ac_001_intact_without_record | MOVE | With no install record, an intact old file found in `flow-history.json` is updated and listed `updated`; `agentic-install.json` records the version |
| test_ac_002_edited_file_kept | MOVE | An edited flow file is kept, the new version goes to `.claude/state/upgrade/<path>`, the kept-files message is printed; `--dry-run` writes no copy |
| test_ac_004_removed_only_if_intact | MOVE | A retired file is removed and listed `removed` if intact, kept if edited |
| test_ac_005_dirty_and_not_git | MOVE | Uncommitted flow files: exit 3, `uncommitted: <path>`, nothing written; `--allow-dirty` proceeds; `--dry-run` only warns; a non-git directory exits 1 with `not a git repository` |
| test_ac_006_run_in_progress | MOVE | A running WP: exit 3 with `a run is in progress (WP-01)` and the `stop` hint even with `--allow-dirty`; exit 0 once stopped |
| test_ac_007_versions_and_notes | MOVE | First line `agentic-flow <old|unknown> -> <new>`; `upgrade notes:` only when the version rises (also from unknown). The `wave-plan` check is PIN |
| test_ac_009_validate_after | MOVE | After install, a bad manifest prints `validate: FAILED:` before `RESULT: OK` and exit 0; a good one prints `validate: OK` |
| test_ac_003_template_leftovers, _008_flow_history | DUP | `test_upgrade::LeftoverTests::test_a_partial_test_suite_is_completed_ci_and_plugin_files_are_not`; `test_upgrade::HistoryTests::test_every_version_of_every_matching_path` and `test_release` |
| test_ac_010_docs | PIN | |

`test_acceptance_v2.py`
| Test | Verdict | Behaviour kept, destination |
|---|---|---|
| test_ac_001_fields_in_both_engines | MOVE (trim) | `pipeline-spec.json`: reviewer and qa require `needs_validation`; findings/defects require `fix` and `if_skipped`; each `needs_validation` item has exactly wp, file, kind, claim, fact, how_to_check with kind `["external","unchanged_code"]`; implementer, test-author and test-auditor require `not_checked`; test-auditor does not require `needs_validation`. → test_pipeline.py |
| test_ac_002_needs_validation_pending | MOVE | Reviewer and QA `needs_validation` items become pending entries (reviewer then qa), no severity, keys claim/fact/how_to_check/kind/wp/file, `line` kept when an int (the only hit of `pipeline.needs_item`'s line copy); run OK with 0 fix cycles. → test_pipeline.py |
| test_ac_003_not_checked_collected | MOVE (part) | `not_checked` entries carry `items`; a real `run-pipeline` with `FAKE_NOT_CHECKED` and `FAKE_NEEDS_VALIDATION` saves at least 5 `not_checked` entries and one `needs validation` pending item. → test_pipeline.py |
| test_ac_004_prompts | DUP | `test_definitions::AgentDefinitionTests` (severity anchors, four parts, reuse ladder, tautological tests, nothing invented, expand-contract, injection defence) |
| test_ac_005_version_and_notes | PIN | |

`test_acceptance_v21.py`
| Test | Verdict | Behaviour kept, destination |
|---|---|---|
| test_ac_001_red_acceptance_refuses_the_report | MOVE (part) | The denial's stderr names the package, says `denial 1 of 2` and shows the failing line; a criterion shared with another package is not the package's own failure: let through, nothing counted (the only hit of `stage.own_failure`'s shared branch). → test_guardrail.py |
| test_ac_002_cap_and_reset | MOVE | The second denial says `denial 2 of 2`; the third report goes through; `open-stage` resets the count. → test_guardrail.py |
| test_ac_003_close_stage_line | MOVE | `close-stage 1 WP-01=done WP-02=done` prints `GATE: WP-01=1 WP-02=0` before `RESULT: OK`; a qa stage prints no GATE line. → test_guardrail.py |
| test_ac_008_matcher_upgrade | MOVE | `merge_settings` on an old flow hook: matcher extended with `StructuredOutput`, timeout 900, command moved to `hook.py`, the project's own entry first, a second merge adds nothing (the only hit of those three lines). → test_install.py |
| test_ac_004_status_mapping | MOVE (part) | Python engine: the needs-context re-dispatch prompt holds `architecture.md, whole`; gates carry `close-stage 1 WP-01=done` for a concern, `WP-02=done` after a re-dispatch, `WP-02=blocker` after two, `WP-01=blocker --fix` in a fix wave; a concern pending item has no severity and `wp=WP-01`. → test_pipeline.py |
| test_ac_005_schema_in_both_engines_and_fake | MOVE (part) | The spec's implementer `status` enum is exactly DONE, DONE_WITH_CONCERNS, NEEDS_CONTEXT, BLOCKED and `required` holds `concerns` and `missing_context`; a real run with `FAKE_CONCERNS` saves one concern per WP and `gate_denials == {}`. → test_pipeline.py |
| test_ac_003_engines_sum, _006_prompts | DUP | `test_pipeline::EngineTests::test_new_scenarios_end_as_described`, `ConformanceTests`; `test_definitions::AgentDefinitionTests::test_implementer_has_four_statuses_and_knows_the_gate` |
| test_ac_007_version_and_notes | PIN | |

`test_acceptance_v22.py`
| Test | Verdict | Behaviour kept, destination |
|---|---|---|
| test_ac_001_callers_outside_the_diff | MOVE (part) | Callers are ordered by symbol, file, line and include `tests/`; each item has exactly symbol, defined_in, file, line, text; a `.md` file is not scanned; the defining file is not listed; `splitter` and `my_split` do not match `split`. → test_repo_scan.py |
| test_ac_002, _003, _004 | DUP | `test_agentic::CallersTests` (caps, no git, state excluded, new files), `test_pipeline::EngineTests`, `test_definitions::AgentDefinitionTests::test_reviewer_reads_the_callers_outside_the_diff` |
| test_ac_005_version_and_notes | PIN | |

`test_acceptance_v23.py`
| Test | Verdict | Behaviour kept, destination |
|---|---|---|
| test_ac_001_newest_source | MOVE (part) | From the run record `--fix` reads `confirmed`, never `refuted`; among `REVIEW-<n>.json` only a reviewer-shaped report counts, a newer verifier or test-auditor report is ignored (the only hit of `launch._report_items`' `return None`). Case (c) DUP of `test_agentic::LauncherTests::test_fix_reads_the_newest_source_and_ties_go_to_the_one_off_report`. → test_launcher.py |
| test_ac_002_all_and_messages | MOVE (part) | `--fix` with only non-blocking defects exits 1 naming `workflow-result.json`; `--fix --all` takes medium and low defects but not `kind=design`; the cap (exit 4) applies with `--all`; `--all` without `--fix` exits 1 with `--fix [--all]` (the only hit of that `die`). → test_launcher.py |
| test_ac_003_verification_failures | MOVE (part) | The first `verification_failures` record: `fix_cycle` 0, `blocking` `["tests"]`, the failing WP in `suspects`, `failing[0]["name"] == "tests"`. → test_pipeline.py |
| test_ac_004_statistics | MOVE (part) | `bootstrap_interval` is deterministic per seed and ignores the global `random` state; a constant ratio of 2 gives (2.0, 2.0); identical samples bracket 1.0; `sign_test(0,0) == 1.0` and `sign_test(1,0) == 1.0`. → bench/test_bench.py |
| test_ac_005_ab_run | MOVE | `bench.py ab` end to end with the fake claude: one `ab-*.json` (schema `ab-1`, arms a,b,b,a), specs and `verification_failures` recorded, `.md` report, two sessions per arm, no worktree left, `report` leaves `ab-` out of `RESULTS.md`; `--repeat 0` and a fixture failing selftest exit 1 with nothing written; all-timeout sessions are recorded as `timeout` with minutes None. → bench/acceptance/test_acceptance_ab.py |
| test_ac_006_version_notes_roadmap | PIN | |

`test_acceptance_v24.py`
| Test | Verdict | Behaviour kept, destination |
|---|---|---|
| test_ac_001_every_call_leaves_a_heartbeat | MOVE | `.claude/state/hook-seen.json` records tool, command, agent_type, ts and guarded_ts; only a flow agent moves guarded_ts. → test_guardrail.py |
| test_ac_001_fallback_agents_and_read_only_agents_count | MOVE | `AGENTIC_WP` calls and the read-only verifier count as guards; the gatekeeper does not. → test_guardrail.py |
| test_ac_002 (fresh, stale, none, corrupt) | MOVE | Live `hooks-check` (`CLAUDECODE=1`): fresh heartbeat exit 0 mode `live`; stale, missing or corrupt exit 3 with the dead-hook message and no traceback (the only hits of `hooks_check`'s live branch). One test with subtests. → test_guardrail.py |
| test_ac_003 (installed settings, no hook, disableAllHooks) | MOVE | Static `hooks-check`: installed settings pass without reading or writing the heartbeat; settings without the flow hook exit 3 naming `settings.json`; `disableAllHooks` exits 3 (the only hits of `hooks_static_problem`'s two returns). → test_guardrail.py |
| test_ac_004 (five stage-liveness tests) | MOVE | `close-stage` fails with `GUARDRAIL HOOK SAW NO FLOW AGENT` when files changed with no flow-agent hook call; a guarded stage closes; gatekeeper and main-thread calls do not guard; a guard older than the stage does not count; a stage that changed nothing closes. → test_guardrail.py |
| test_ac_006_implement_checks_the_hook_first | MOVE (ordering only) | `implement.md`'s pre-flight runs `agentic.py hooks-check` before `validate` (safety order). → test_definitions.py |
| test_ac_009_the_fallback_checks_statically_and_runs | MOVE | With `CLAUDECODE=1` and no heartbeat, `run-pipeline` still reaches OK (gates run `hooks-check` statically). → test_pipeline.py |
| test_ac_005_python_engine_stops_at_prepare | MOVE (part) | Scenario `the guardrail hook is not running`: REVIEW, failed_stage `prepare`, gates `["hooks-check"]`, no agents. → test_pipeline.py |
| test_ac_005_both_engines_agree | DUP | `test_pipeline::ConformanceTests::test_every_scenario_is_the_same_in_both_engines` |
| test_ac_007, test_ac_008 | PIN | |

`test_acceptance_v241.py`: every test DUP (`ConformanceTests` compares prompts; `test_definitions::AgentDefinitionTests::test_implementer_has_four_statuses_and_knows_the_gate`) or PIN. Nothing moves.

`test_acceptance_waiting.py`
| Test | Verdict | Behaviour kept, destination |
|---|---|---|
| test_ac_001_permission_shown | MOVE | A real `waiting.py` call then `status` shows `## Waiting for you` before `## Stages` with the line `- WP-01 (implementer) needs your permission for Bash: npm run e2e — waiting 0 min (since HH:MM)` (the only hit of `ledger_render`'s waiting branch); after the matching end event the section is gone. → test_waiting.py |
| test_ac_003_kinds | MOVE (part) | A `WebFetch` request is described with its `url`. → test_waiting.py |
| test_ac_004_never_blocks | MOVE (part) | `waiting.py` imports none of agentic, pipeline, brief, upgrade (AST). → test_waiting.py |
| test_ac_005_stage_resets | MOVE | `snapshot 1` clears the waiting list. → test_waiting.py |
| test_ac_006_install | MOVE (part) | Install adds exactly one waiting entry to each of PermissionRequest, PostToolUse, PostToolUseFailure and SubagentStop, keeps the project's own PostToolUse hook, prints `hook PermissionRequest` only the first time, copies `waiting.py`. → test_install.py |
| test_ac_007_glob_arguments | MOVE | `bash -c *`, `python3 -c *` and `npm *` are open-ended commands; a `*` in a later argument (`-p test_*.py`) is accepted (the only hit of `open_ended_command`'s loop return). → test_manifest_check.py |
| test_ac_002_cleared | DUP | `test_waiting::HandleTests::test_each_ending_removes_only_that_agent` |

`test_acceptance_v27.py`
| Test | Verdict | Behaviour kept, destination |
|---|---|---|
| test_ac_001_python | MOVE | An elif chain is one level; a nested def does not add to its parent (`outer.inner`, `C.g`); lines and long lines counted. → test_quality.py |
| test_ac_001_syntax_error_does_not_raise | MOVE | A syntax error gives `functions == {}` and still counts lines (the only hit of `_python`'s except). → test_quality.py |
| test_ac_002_javascript | MOVE | `else if` is not deeper; braces in strings, templates and comments ignored; an async arrow is a function; a class method is `C.m`; a callback `j => {}` is not. → test_quality.py |
| test_ac_003 (worse, same or better, partial, tighten) | MOVE | `check` fails each regression kind (offender growth, new function over 60 or nesting over 4, test function over 100, file growth over 30, long-line growth, new file over 800 or with a long line) with `FAIL ` lines that carry no digits; same or better passes and lands in `improvable`; `tighten` only lowers and drops entries within limits. → test_quality.py |
| test_ac_004 (init/check/update, flow files in a project, foreign baseline) | MOVE | The `quality` command: skipped without a baseline; `--init` writes it and a second `--init` exits 1 leaving it unchanged; a worse file exits 3 without writing; `--update` lowers; `.claude/` files stay out of a project's baseline; a `flow_repo: true` baseline in a project is skipped. → test_quality.py |
| test_ac_005 (four verify tests) | MOVE | The `quality` verify phase blocks a regression and names the owning WP; a pre-existing violation does not block; `baseline` runs it without verify commands; no baseline, no phase. → test_quality.py |
| test_ac_006_never_owned | MOVE (second half) | A by-hand plan owning the quality baseline is refused by `validate` (patch `is_flow_repo` in `core` and `manifest_check`). First half DUP of `test_agentic::QualityCommandTests::test_the_baseline_is_never_owned`. → test_manifest_check.py |
| test_ac_007 (four install tests) | MOVE | Install creates the baseline (`flow_repo` false, `quality baseline: created`), keeps an existing one byte for byte, replaces a template one, and `--dry-run` writes none. → test_install.py |
| test_ac_008_ci_release_and_docs | MOVE (one line) | The CI runs `python .claude/bin/agentic.py quality`. → test_ci.py |
| test_ac_006_agents_cannot_write_the_baseline | DUP | `test_agentic::HookBashTests::test_blocked` |

`test_acceptance_v29.py`
| Test | Verdict | Behaviour kept, destination |
|---|---|---|
| test_ac_002_unknown_tag_content_fails | MOVE | A tag whose content the history lacks: exit 3, `missing == [{"ref": "<tag>", "path": ".claude/agents/qa.md"}]`, history unchanged. → test_release.py |
| test_ac_005_shallow_clone_refused | MOVE | `flow-history --check` in a depth-1 clone exits 1 with `flow-history: needs the full git history` and no JSON. → test_release.py |
| test_ac_008_release_workflow | MOVE | Release workflow: triggers (push to main on plugin.json, dispatch; no pull_request, schedule, tags), top-level `contents: read`, job `contents: write`, SHA pins, `fetch-depth: 0`, `persist-credentials: false`, repository and ref guards, `GH_TOKEN`, no `softprops`, no `${{` inside `run:`, order already exists < check < notes < `gh release create`. → test_ci.py (helpers `block`, `run_scripts` at `test_acceptance_v29.py:208-230`) |
| test_ac_009_history_job | MOVE | The CI `history` job: repository guard, `fetch-depth: 0`, `persist-credentials: false`, `flow-history --check`; both `paths` lines hold the release workflow and `bench/**`; `test`, `installed`, `plugin` have no `fetch-depth`. → test_ci.py |
| test_ac_010_version_notes_and_history | MOVE (one line) | No `EXTRA_GLOBS` entry names the release workflow. → test_upgrade.py |
| test_ac_001, _003, _004, _006, _007 | DUP | `test_release::CheckCommandTests`, `NotesCommandTests`; `test_core` exemption test |
| test_ac_011_ceremony | PIN | |

**Other references to the deleted files:** `bench/acceptance/test_acceptance_bench.py:410` runs `test_acceptance_portable` in a subprocess (keep `test_definitions` only); `.claude/bin/testutil.py:3` names `test_acceptance*.py`; `upgrade.leftovers` (`upgrade.py:190-195`) keeps acceptance files out of projects that lack them: unchanged.

**Projects:** `install` removes a retired flow file when it is intact (`installer.py:173-180`), so projects lose the twelve files on update; edited copies are kept.

**Ratchet:** `test_agentic.py` (1852 lines, allowance 1879) does not grow: its destinations are new files. Test functions stay under 100 lines; lines under 120 characters.

What must NOT change: production code; the remaining suites' existing tests; `test_acceptance_v210.py`.

## 5. Data model
No data.

## 6. Contracts between modules
No production contract changes. The only cross-file test contract is the rule:
```python
# test_layout.py (WP-08)
def acceptance_files(folder) -> list:
    """The test_acceptance*.py files directly in folder, sorted by name."""

# unit-tested on a temporary folder (none, one, two); and, agentic-flow repository only (FLOW_REPO_ONLY):
def test_at_most_one_acceptance_file(self):
    """.claude/bin holds at most one test_acceptance*.py: the current release's. A release that adds its own
    acceptance file moves the previous one's unique checks into the unit suites and deletes it."""
```

## 7. Conventions
- A moved check is rewritten as a behaviour test in the destination's style (Arrange, act, assert; one behaviour per test; names that describe it). It is not copied with its `test_ac_NNN` name, its frozen-version comments or its pins.
- Copy helpers into the destination; never import a file that this design deletes.
- Every destination file ships to projects (`.claude/bin/test_*.py` is in `EXTRA_GLOBS`) and runs in CI's `installed` job, unlike the retired files (`upgrade.leftovers`, `upgrade.py:190-195`). A check that reads `.github/`, `docs/`, `bench/`, this repository's `plugin.json`, tags or history is `FLOW_REPO_ONLY` or builds its own temporary repository.
- No version numbers, note counts, roadmap text or doc wording in assertions.
- Each moved test's docstring names the 4b row it comes from (for example `from test_acceptance_v24 ac_004`), so a reviewer can trace it. Every moved test must fail if its behaviour breaks: when moving one, break the code locally (by hand) and see it fail, then restore.
- Standard library and `unittest` only; no type annotations in `.claude/bin` tests, as in the existing ones (an exception to the generic Python rule); bench files follow `bench/`'s own style.
- The teeth check edits production files temporarily, by hand, and restores them; such an edit is never committed.

## 8. Work packages and acceptance criteria
### Acceptance criteria
Refactor: acceptance is the whole existing suite, green before and after, plus the rule.

- AC-001 · Every suite stays green and no check that only the deleted files made is lost
  - Scenario: the branch after design 0016.
  - Action: run the commands of section 3 before and after.
  - Expected: all pass before and after; after, the twelve files do not exist; each MOVE row of section 4b has a test in its destination; the 70 measured lines are still executed by the remaining suites (re-measured by the maintainer with coverage).
  - Must not: weaken or delete an existing test of the remaining suites, or import a deleted file.
  - Check: `python3 -m unittest discover -s .claude/bin -p "test_*.py"` and the commands of section 3; the coverage re-measure in section 9.
  - WP: WP-01, WP-02, WP-03, WP-04, WP-05, WP-06, WP-07, WP-08
- AC-002 · At most one acceptance file in .claude/bin
  - Scenario: the agentic-flow repository after the change; then a temporary second `test_acceptance_x.py`.
  - Action: run `test_layout` (enforced through `verify.tests`; the manifest has no acceptance block, as a refactor).
  - Expected: passes with only `test_acceptance_v210.py`; fails naming both files with the second one present.
  - Must not: run outside the agentic-flow repository (projects may keep edited copies).
  - Check: `python3 -m unittest discover -s .claude/bin -p test_layout.py` (the two-file case on a temporary folder through `acceptance_files`)
  - WP: WP-08

### Work packages
WP-01 to WP-07 are wave 1: disjoint files, and each reads the files being retired. WP-08 is wave 2: it deletes those files and adds the rule, so it depends on all of them.

#### WP-01 · test_quality.py
- Files: `.claude/bin/test_quality.py`.
- Moves: the `test_acceptance_v27.py` rows for measurement, ratchet, the command and the verify phase; `test_acceptance_portable.py::test_ac_004_encodings_declared`.
- Patterns to mirror: `.claude/bin/test_quality.py:1-60` (style, inline sources); `.claude/bin/test_agentic.py:45-77` (`Repo`).
- Helpers to copy: `PY_SOURCE`, `JS_SOURCE`, `baseline()`, `current()`, `function_source`, `last_json`, `verify_manifest`, `prepared`/`phase` (`test_acceptance_v27.py:22-290`); `FLOW_MODULES` (`test_acceptance_portable.py:22-23`).
- Validation: `python3 -m unittest discover -s .claude/bin -p test_quality.py`; `python3 .claude/bin/agentic.py quality`.

#### WP-02 · test_install.py (new)
- Files: `.claude/bin/test_install.py`.
- Moves: `test_acceptance_upgrade.py` MOVE rows; `test_acceptance_portable.py::test_ac_007_crlf_intact`; `test_acceptance_v21.py::test_ac_008_matcher_upgrade`; `test_acceptance_waiting.py::test_ac_006_install` (part); the four `test_acceptance_v27.py::InstallTests`.
- Patterns to mirror: `.claude/bin/test_upgrade.py:15-36` (git repos); `.claude/bin/test_agentic.py:1089-1160` (`InstallTests`).
- Gotchas: the file ships to projects (`.claude/bin/test_*.py` is in `EXTRA_GLOBS`) and the CI `installed` job runs it in a fresh project: every test builds its own source and target; none reads this repository's tags, history or version.
- Validation: `python3 -m unittest discover -s .claude/bin -p test_install.py`.

#### WP-03 · test_guardrail.py (new)
- Files: `.claude/bin/test_guardrail.py`.
- Moves: `test_acceptance_v24.py` heartbeat, hooks-check and stage-liveness rows; `test_acceptance_v21.py` gate rows (001 part, 002, 003).
- Patterns to mirror: `.claude/bin/test_agentic.py:45-100` (`Repo`, payloads); `.claude/bin/test_core.py:1-54` (a module-scoped test file importing from `test_agentic`).
- Gotchas: `Repo` already pops `CLAUDECODE`, `AGENTIC_WP`, `AGENTIC_CLAUDE`; set `CLAUDECODE=1` explicitly for live checks. The "guard older than the stage" case relies on file mtimes: keep its short sleep.
- Validation: `python3 -m unittest discover -s .claude/bin -p test_guardrail.py`.

#### WP-04 · test_pipeline.py and test_launcher.py
- Files: `.claude/bin/test_pipeline.py`, `.claude/bin/test_launcher.py` (new).
- Moves: the rows with destination `test_pipeline.py` in `test_acceptance.py`, `_portable`, `_v2`, `_v21`, `_v23`, `_v24`. Engine and spec checks go to `test_pipeline.py`; launcher, usage and `--fix` source checks (`test_acceptance.py` 007, 008, 010 x2; `_portable` 008; `_v23` 001, 002) go to `test_launcher.py`.
- Patterns to mirror: `.claude/bin/test_pipeline.py:24-140` (`world`, `run_scenario`), `:240-280` (end to end).
- Gotchas: `test_pipeline.py` is 356 lines; it may grow to 800. A launcher test that needs a full project can use `test_agentic.Repo` plus `testutil.install_fake_claude`.
- Validation: `python3 -m unittest discover -s .claude/bin -p test_pipeline.py`; `node .claude/bin/test_workflow.mjs`.

#### WP-05 · test_brief.py, test_compat.py, test_waiting.py, test_release.py
- Files: `.claude/bin/test_brief.py`, `.claude/bin/test_compat.py`, `.claude/bin/test_waiting.py`, `.claude/bin/test_release.py`.
- Moves: the rows with those destinations.
- Patterns to mirror: `.claude/bin/test_brief.py:1-50`; `.claude/bin/test_compat.py:1-40`; `.claude/bin/test_waiting.py:1-40`; `.claude/bin/test_release.py:20-60`.
- Gotchas: `test_release.py` ships to projects: tag tests build their own `Copy`. The shallow clone must use a `file://` URL (`repo.dir.as_uri()`): `git clone --depth 1` ignores the depth for a plain local path.
- Validation: each file with `python3 -m unittest discover -s .claude/bin -p <file>`.

#### WP-06 · test_ci.py, test_definitions.py, test_upgrade.py, test_manifest_check.py, test_repo_scan.py
- Files: `.claude/bin/test_ci.py`, `.claude/bin/test_definitions.py`, `.claude/bin/test_upgrade.py`, `.claude/bin/test_manifest_check.py`, `.claude/bin/test_repo_scan.py`.
- Moves: the rows with those destinations.
- Patterns to mirror: `.claude/bin/test_definitions.py:341-372` (`CIHardeningTests`, reading workflows); `.claude/bin/test_agentic.py:880-900` (`CallersTests` helpers).
- Gotchas: `test_ci.py` checks the agentic-flow repository's own workflows: every test is `FLOW_REPO_ONLY` (projects receive and may edit the CI copy). `test_definitions.py` is at its long-line allowance.
- Validation: each file with `python3 -m unittest discover -s .claude/bin -p <file>`.

#### WP-07 · bench, notes and the ceremony
- Wave: 1.
- Files: `bench/test_bench.py`, `bench/acceptance/test_acceptance_ab.py`, `.claude/bin/testutil.py`, `.claude/bin/upgrade.py`, `docs/how-to/plugin.md`.
- Moves: `test_acceptance_v23.py` 004 (part) and 005.
- Patterns to mirror: `bench/test_bench.py:1-60` (`StatisticsTests`); `bench/acceptance/test_acceptance_bench.py:48-110` (`Sandbox`, `make_fixture`).
- Gotchas:
  - `NOTES["2.10.0"]` gains: "The per-release acceptance test files in .claude/bin are retired; their remaining checks live in the unit suites. install removes intact copies from projects; edited ones are kept."
  - `docs/how-to/plugin.md`, step 1 of "Publish a version": a release that adds its own `test_acceptance_*.py` moves the previous release's unique checks into the unit suites and deletes that file.
- Validation: `python3 -m unittest discover -s bench -p "test_*.py"`; `python3 -m unittest discover -s bench/acceptance`; `python3 .claude/bin/agentic.py docs-check`.

#### WP-08 · Delete the twelve files and add the rule
- Wave: 2, after WP-01 to WP-07.
- Files: the twelve files (deleted), `.claude/bin/test_layout.py` (new), `bench/acceptance/test_acceptance_bench.py` (line 410: run only `test_definitions`).
- Implements: `acceptance_files(folder)` and the rule of section 6 (AC-002).
- Patterns to mirror: `.claude/bin/test_definitions.py:15-30` (`ROOT`, `FLOW_REPO_ONLY`).
- Gotchas: `test_layout.py` ships to projects: the real-repository test is `FLOW_REPO_ONLY`; the helper's tests use a temporary folder.
- Validation: the commands of section 3.

```json wp-manifest
{
  "maintainer": true,
  "stack": ["python"],
  "allow_bash": ["Bash(python3 -m unittest:*)", "Bash(node .claude/bin/test_workflow.mjs)"],
  "verify": {"build": "python3 -m unittest discover -s bench -p \"test_*.py\"", "lint": "node .claude/bin/test_workflow.mjs", "types": "python3 -m unittest discover -s bench/acceptance", "tests": "python3 -m unittest discover -s .claude/bin -p \"test_*.py\""},
  "docs": {"files": ["docs/assets/"], "codemap": null},
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": [".claude/bin/test_quality.py"], "acs": ["AC-001"],
     "mirror": [".claude/bin/test_quality.py:1-60", ".claude/bin/test_agentic.py:45-77"]},
    {"id": "WP-02", "wave": 1, "depends_on": [], "files": [".claude/bin/test_install.py"], "acs": ["AC-001"],
     "mirror": [".claude/bin/test_upgrade.py:15-36", ".claude/bin/test_agentic.py:1089-1160"]},
    {"id": "WP-03", "wave": 1, "depends_on": [], "files": [".claude/bin/test_guardrail.py"], "acs": ["AC-001"],
     "mirror": [".claude/bin/test_agentic.py:45-100", ".claude/bin/test_core.py:1-54"]},
    {"id": "WP-04", "wave": 1, "depends_on": [], "files": [".claude/bin/test_pipeline.py", ".claude/bin/test_launcher.py"], "acs": ["AC-001"],
     "mirror": [".claude/bin/test_pipeline.py:24-140", ".claude/bin/test_pipeline.py:240-280"]},
    {"id": "WP-05", "wave": 1, "depends_on": [], "files": [".claude/bin/test_brief.py", ".claude/bin/test_compat.py", ".claude/bin/test_waiting.py", ".claude/bin/test_release.py"], "acs": ["AC-001"],
     "mirror": [".claude/bin/test_brief.py:1-50", ".claude/bin/test_compat.py:1-40", ".claude/bin/test_waiting.py:1-40", ".claude/bin/test_release.py:20-60"]},
    {"id": "WP-06", "wave": 1, "depends_on": [], "files": [".claude/bin/test_ci.py", ".claude/bin/test_definitions.py", ".claude/bin/test_upgrade.py", ".claude/bin/test_manifest_check.py", ".claude/bin/test_repo_scan.py"], "acs": ["AC-001"],
     "mirror": [".claude/bin/test_definitions.py:341-372", ".claude/bin/test_agentic.py:880-900"]},
    {"id": "WP-07", "wave": 1, "depends_on": [], "files": ["bench/test_bench.py", "bench/acceptance/test_acceptance_ab.py", ".claude/bin/testutil.py", ".claude/bin/upgrade.py", "docs/how-to/plugin.md"], "acs": ["AC-001"],
     "mirror": ["bench/test_bench.py:1-60", "bench/acceptance/test_acceptance_bench.py:48-110"]},
    {"id": "WP-08", "wave": 2, "depends_on": ["WP-01", "WP-02", "WP-03", "WP-04", "WP-05", "WP-06", "WP-07"], "files": ["bench/acceptance/test_acceptance_bench.py", ".claude/bin/test_layout.py", ".claude/bin/test_acceptance.py", ".claude/bin/test_acceptance_portable.py", ".claude/bin/test_acceptance_upgrade.py", ".claude/bin/test_acceptance_waiting.py", ".claude/bin/test_acceptance_v2.py", ".claude/bin/test_acceptance_v21.py", ".claude/bin/test_acceptance_v22.py", ".claude/bin/test_acceptance_v23.py", ".claude/bin/test_acceptance_v24.py", ".claude/bin/test_acceptance_v241.py", ".claude/bin/test_acceptance_v27.py", ".claude/bin/test_acceptance_v29.py"], "acs": ["AC-001", "AC-002"],
     "mirror": [".claude/bin/test_definitions.py:15-30"]}
  ]
}
```

## 9. Test strategy
- The existing suites are the acceptance: green before and after (section 3).
- Each moved test is checked for teeth by hand: break the behaviour, see it fail, restore (section 7).
- Coverage re-measure by the maintainer after the move: the same harness as the design measurement (coverage 7.17.2 in a scratch directory, `COVERAGE_PROCESS_START` with a `sitecustomize`, source `.claude/bin`, tests and `testutil` omitted) over the remaining suites; every one of the 70 lines must be executed. Lines inside temporary copies of `.claude/bin` are not counted, as in the original measurement.

## 10. Decisions
- **One acceptance file at most, the current release's** (user's choice): `test_acceptance_v210.py` stays until 2.11; the issue's proposal. Discarded: none on main (each PR would move and delete its own the same day).
- **A test enforces it** (user's choice), only in the agentic-flow repository.
- **Wording pins are dropped** (user's choice): docs, notes, versions, counts and prompts. Links and cited commands are already checked by `test_definitions::DocumentationDriftTests` and `docs-check`.
- **Destinations by module** (user's choice), with new files for install, guardrail, CI, manifest checks and callers: `test_agentic.py` is at its size allowance.
- **The inventory was made by reading every test** (four parallel readers with one rule set, cross-checked against the coverage measurement), not by coverage alone: coverage cannot see assertions on definitions, the JS workflow or CI files.
- **No production change**, so no version bump beyond 2.10.0 (set by design 0016).
- **Executed by hand**, like 0013 to 0016.
- **The flow history is regenerated by the maintainer as the branch's last commit** (the 2.9.0 ceremony): 2.10.0 has no tag yet, so CI's `history` check covers HEAD, and the new test files are shipped content.

## 11. Risks and open questions
- A MOVE (part) row may lose an assertion the readers judged duplicated; the coverage re-measure and the teeth check limit that, but assertion-level losses are not measured.
- `bench/acceptance/test_acceptance_ab.py` runs `bench.py ab` with the fake claude and git worktrees: slower than unit tests (not measured).
- Rollback: revert the commit; the twelve files return.
