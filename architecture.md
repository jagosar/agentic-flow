# Architecture: agent shortcuts, validate warnings, the workflow-subagent claim and clean UTF-8 (issues 57, 60, 68, 58; agentic-flow 2.11.0)
Type: feature · Size: standard

## 1. Goal
Four small guardrails in one release. Agents may no longer add the usual shortcuts (a broad `except` that only `pass`es, an empty `catch {}`, an assertion that is always true, a `[DEBUG-` log left behind, a Python test without an assertion): the hook blocks them on a write and `close-stage` fails when they arrive another way, counting only what a change adds (#57). `validate` warns, without failing, about a package with too many files or criteria, a wave too wide, and a plan that is a chain of one-package waves (#60). A subagent of type `workflow-subagent` without a claim may not write files, which closes a hole if the Workflow tool's subagents arrive with that type (#68, not verifiable from a cloud session). A test of this repository fails on tracked text that is not clean UTF-8: invalid bytes, double encoding or a byte-order mark (#58). Following the one-acceptance-file rule of design 0017, `test_acceptance_v210.py` is retired in the same release.

## 2. Scope
### Included
- `core.py`: `SHORTCUT_RES`, `assertless_tests(text)`, `shortcut_problems(path, old, new)`.
- `stage.py`: `content_problems` reports shortcuts.
- `guardrail.py`: `content_checks` blocks shortcuts; `require_claim` blocks file writes by an unclaimed `workflow-subagent`.
- `manifest_check.py`: `complexity_warnings(manifest)`; `agentic.py validate` prints them after `Manifest valid.`.
- `.claude/bin/test_encoding.py` (new): `text_problems(root, paths)` and a repository test.
- `upgrade.py` `NOTES["2.11.0"]`, `plugin.json` 2.11.0, `docs/how-it-works.md:233` (the content checks) and `docs/how-to/README.md:172` (the `validate` line).
- Retiring `test_acceptance_v210.py`: its unique checks move to `test_launcher.py` and `test_guardrail.py`.

### Excluded (non-goals)
- JavaScript tests without assertions (only Python, by AST).
- The UTF-8 check in `close-stage` or in projects: only this repository's tracked files.
- Verifying which `agent_type` the Workflow tool's subagents carry: it needs a local session (section 11).
- Bench-calibrated thresholds for the warnings: the values below are not measured against runs (section 10).
- The other roadmap issues.

## 3. Stack
- Python 3.9+ standard library (`re`, `ast`), `unittest`; Node 22 for `test_workflow.mjs`. No new dependency.
- Acceptance: `python3 -m unittest discover -s .claude/bin -p test_acceptance_v211.py`
- Everything: `python3 -m unittest discover -s .claude/bin -p "test_*.py"`, `python3 -m unittest discover -s bench -p "test_*.py"`, `python3 -m unittest discover -s bench/acceptance`, `node .claude/bin/test_workflow.mjs`, `python3 .claude/bin/agentic.py quality`.

## 4. Repository structure
```
.claude/bin/core.py                    WP-01  SHORTCUT_RES, assertless_tests, shortcut_problems
.claude/bin/stage.py                   WP-01  content_problems reports shortcuts
.claude/bin/test_shortcuts.py          WP-01  new: unit tests of the three core functions and close-stage
.claude/bin/guardrail.py               WP-02  content_checks blocks shortcuts; workflow-subagent write rule
.claude/bin/test_guardrail.py          WP-02  hook tests; hook.py-runs-live moved from test_acceptance_v210
.claude/bin/manifest_check.py          WP-03  complexity_warnings
.claude/bin/agentic.py                 WP-03  validate prints the warnings
.claude/bin/test_manifest_check.py     WP-03  warning tests
.claude/bin/test_encoding.py           WP-04  new: text_problems and the repository check
docs/how-it-works.md                   WP-04  the content-checks sentence (:233)
.claude/bin/test_launcher.py           WP-05  launchers refuse a by-hand plan (moved from test_acceptance_v210)
.claude/bin/test_acceptance_v210.py    WP-05  deleted
.claude/bin/upgrade.py                 WP-05  NOTES["2.11.0"]
.claude-plugin/plugin.json             WP-05  version 2.11.0
docs/how-to/README.md                  WP-04  the validate line mentions the warnings
.claude/bin/test_acceptance_v211.py    AT     acceptance tests of this design
```

## 4b. Existing code context
| What an implementer needs to know | Where it is (`file:lines`) | Pattern or rule |
|---|---|---|
| The content guardrails are module constants in `core.py`, shared by the hook and the stage check | `.claude/bin/core.py:88-115` (`PROTECTED_CONFIG_RE`, `SKIP_MARKER_RE`, `TEST_PATH_RE`, `SECRET_RES`) | Add `SHORTCUT_RES` and the two functions right after `SECRET_RES`, same comment style |
| The rule for "added": a pattern counts only when it appears more times in the new content than in the old | `.claude/bin/stage.py:131-135`, `.claude/bin/guardrail.py:170-187` | `shortcut_problems` applies the same rule per kind |
| `content_problems(manifest, label, changes)`: old content from the stage's tree, new from disk; returns `"<path>: <what>"` strings | `.claude/bin/stage.py:114-138` | Append `f"{path}: {what}"` for each item of `shortcut_problems(path, old, new)` |
| `content_checks(owner_id, ent, rel, abs_path, tool, tinput)`: computes `new`/`old` for Write, Edit, MultiEdit; `old` is only completed for test paths today | `.claude/bin/guardrail.py:165-187` | Compute `old` for every path before the checks (the block at `:179-184`, moved up and applied to all paths), then `block(...)` on the first `shortcut_problems` item |
| `block(msg)` prints `[agentic guard] msg` to stderr and exits 2 | `.claude/bin/guardrail.py:77-79` | Messages name the owner, the file and the way out (fix it, or the blocked status) |
| `require_claim(data, agent_id, owner_id)` blocks a claim-required type with no owner, for every tool | `.claude/bin/guardrail.py:230-235` | Add: `agent_type == "workflow-subagent"` with an `agent_id`, no owner and a tool in `FILE_WRITE_TOOLS` is blocked with the same claim message; Bash and reads are not |
| `guard` order: universal checks, owner resolution (a claim command ends the call), report gate, `require_claim`, then rules for an agent with a zone | `.claude/bin/guardrail.py:270-290` | Unchanged; a claimed `workflow-subagent` gets the owner's zone through the claims file |
| `claimable(manifest, agent_type)` returns `None` for a type the flow does not know (no restriction on the ID it claims) | `.claude/bin/guardrail.py:81-86` | `workflow-subagent` may claim any ID; unchanged |
| `validate(manifest)` returns the error list; `cmd_validate` prints `Manifest valid.` | `.claude/bin/manifest_check.py:62-70`, `.claude/bin/agentic.py:150-152` | Warnings are a separate function; `cmd_validate` prints each as `warning: <text>` after `Manifest valid.`, exit 0. `require_valid` (used by every other command) does not print them |
| Measured on the 17 archived manifests (`docs/architecture/0001`..`0017`): at most 14 files and 8 ACs in one package, at most 7 packages in one wave; one plan (0013) was a chain of three one-package waves | this design's reconnaissance | Thresholds just above what plans needed: more than 15 files, more than 8 ACs, more than 8 packages in a wave |
| Hook test helpers: `Repo`, `write_payload`, `bash_payload`, `Repo.hook(payload, wp)` returns the exit code; `Repo.run("hook", stdin=..., env=...)` returns the process | `.claude/bin/test_agentic.py:20-100`; style of content tests `:395-425` | Mirror for the hook tests |
| Stage check tests: a committed base, `snapshot 1`, a write, then `check-wave 1` (exit 3 on a problem) | `.claude/bin/test_agentic.py:1345-1362` (`SafetyNetTests`) | Mirror for the close-stage shortcut tests |
| `test_guardrail.py` (design 0017) holds hook tests in classes per concern | `.claude/bin/test_guardrail.py:1-60` | Add classes there |
| `FLOW_REPO_ONLY`, `tracked_files()` | `.claude/bin/test_definitions.py:28`, `:67-75` | The repository check in `test_encoding.py` uses both |
| Retiring `test_acceptance_v210.py`: its unique checks are the launchers' refusal of a by-hand plan before writing anything (its `RefusalTests`, lines 72-100, with `FlowRepo` at 34-42) and `hook.py` running the live guard with a leftover copy (`HookTests`, lines 121-139); the rest duplicates `test_agentic::MaintainerModeTests`, `test_definitions` and `ConformanceTests` or pins notes and docs | `.claude/bin/test_acceptance_v210.py` | Move the two into `test_launcher.py` (refusals) and `test_guardrail.py` (hook.py); then delete the file |
| `NOTES` entry shape; `plugin.json` version must equal the newest key | `.claude/bin/upgrade.py:130-150`, `.claude/bin/test_definitions.py:405-410` | Same package |
| The sentence listing the stage's content checks | `docs/how-it-works.md:233` | Add "or an agent shortcut (a swallowed exception, an empty catch, an always-true assertion, a `[DEBUG-` log, a test without an assertion)" |
| Ratchet: functions under 60 lines, nesting 4, lines under 120 characters; `agentic.py` and `upgrade.py` are at their long-line allowance | `.claude/quality-baseline.json` | No new long lines |

What must NOT change: what the hook and the stage already block; `validate`'s errors and exit codes; `require_valid`'s output; the claim rules for the flow's own agent types.

## 5. Data model
```python
# core.py
SHORTCUT_RES = [  # (regex, what, tests_only)
    (re.compile(r"\bexcept(\s+(Exception|BaseException)(\s+as\s+\w+)?)?\s*:[ \t]*(#[^\n]*)?\n?[ \t]*pass\b"),
     "an exception swallowed with pass", False),
    (re.compile(r"\bcatch\s*(\([^)]*\))?\s*\{\s*\}"), "an empty catch block", False),
    (re.compile(r"\bassert\s+True\b|\bassertTrue\(\s*True\s*\)|expect\(\s*true\s*\)\.(toBe|toEqual)\(\s*true\s*\)"),
     "an assertion that is always true", True),
    (re.compile(r"\[DEBUG-"), "a [DEBUG-] log left behind", False),
]
ASSERT_CALL_PREFIXES = ("assert", "check", "expect", "verify", "fail", "raises")
# The shortcuts are looked for in code only: documentation that names them (this design, the guide) is not blamed.
CODE_SUFFIXES = (".py", ".pyi", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".java", ".kt", ".go", ".rb", ".php",
                 ".cs", ".swift", ".rs")
```

## 6. Contracts between modules
```python
# core.py (WP-01)
def assertless_tests(text) -> int:
    """How many `def test_*` / `async def test_*` functions, at module level or directly in a class (not nested in
    another function), contain no `assert` statement and no call whose name (the attribute or the function) starts,
    case-sensitively, with one of ASSERT_CALL_PREFIXES. 0 for text that does not parse."""

def shortcut_problems(path, old, new) -> list:
    """[] unless path ends with one of CODE_SUFFIXES. Otherwise the `what` of every SHORTCUT_RES kind that appears
    more often in new than in old (tests_only kinds only when
    TEST_PATH_RE matches path), then "a test without an assertion" when path is a .py test path and
    assertless_tests(new) > assertless_tests(old). [] when nothing was added. old may be ""."""

# manifest_check.py (WP-03)
WP_FILES_WARN = 15
WP_ACS_WARN = 8
WAVE_WPS_WARN = 8

def complexity_warnings(manifest) -> list:
    """Advice, never errors, in this order and wording:
    "<WP>: owns <n> files (more than 15): consider splitting it"
    "<WP>: answers for <n> criteria (more than 8): consider splitting it"
    "wave <w>: <n> packages (more than 8): consider another wave"
    "every wave holds one package: the plan is a chain, nothing runs in parallel" (2 or more waves, all with one)
    [] otherwise. Checked per package and per rule: <n> is len(wp.get("files", [])) (a folder prefix such as "src/b/"
    counts as one) and len(wp.get("acs", [])) (a missing "acs" counts as []); a value of the wrong type skips only
    that rule for that package. Waves are grouped by wp["wave"]."""

# guardrail.py (WP-02)
FILE_WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

# test_encoding.py (WP-04)
def text_problems(root, paths) -> list:
    """"<path>: <problem>" for each file under root among paths that is text (no NUL in its first 8000 bytes) and
    is not valid UTF-8 ("not valid UTF-8"), starts with a BOM, U+FEFF ("starts with a byte-order mark"), or holds
    a double-encoding sequence ("double-encoded text"): U+00C3 followed by U+0080..U+00BF, U+00E2 U+20AC, or U+00C2
    followed by U+00A0..U+00BF. paths are repository-relative POSIX strings; the result uses them as given, sorted;
    a path that is not a regular file (deleted, a folder) is skipped. In code and fixtures these characters are
    always written as escapes ("\u00c3", "\ufeff"), never literally, so this repository's own files stay clean."""
```
Command line (WP-03): `agentic.py validate` prints `Manifest valid.` and then one line `warning: <text>` per warning; exit 0. An invalid manifest is unchanged (errors, exit 1, no warnings).

Hook (WP-02): a write by an agent with a zone whose result adds a shortcut exits 2 with `[agentic guard] <owner>: <what> in <file>. ...`. A `Write`/`Edit`/`MultiEdit`/`NotebookEdit` call with `agent_type: "workflow-subagent"`, an `agent_id`, no `AGENTIC_WP` and no claim exits 2 with the existing claim message; a `Bash` call from it is not blocked by this rule.

## 7. Conventions
- English everywhere; no type annotations, as in the existing modules (an exception to the generic Python rule, which asks for them: the code base targets Python 3.9 and has none).
- Messages say what was found and the way out: fix it, or return the blocked status the schema allows.
- Only what a change adds counts; never blame what was already there.
- Moved tests name their origin in the docstring (design 0017's convention).
- No new long lines; functions under 60 lines.
- Commits are the maintainer's; agents do not commit.

## 8. Work packages and acceptance criteria
### Acceptance criteria
Hook and stage tests use `test_agentic.Repo` with its default manifest (WP-01 owns `src/a.py` and `tests/test_a.py`).

- AC-001 · The hook blocks each shortcut a write adds
  - Scenario: WP-01 (fallback mode, `AGENTIC_WP`) writes its own files.
  - Action: `Write` of `src/a.py` with `try:\n    x()\nexcept Exception:\n    pass\n`; of `src/a.py` with `try { x() } catch (e) {}`; of `src/a.py` with `print("[DEBUG-1]")`; of `tests/test_a.py` with `def test_a():\n    assert True\n`; of `tests/test_a.py` with `def test_a():\n    x = 1\n`.
  - Expected: each exits 2 and stderr names the file and, in order, `an exception swallowed with pass`, `an empty catch block`, `a [DEBUG-] log left behind`, `an assertion that is always true`, `a test without an assertion`. `except ValueError:\n    pass`, `def test_a():\n    self.assertEqual(1, 1)` and `def test_a():\n    check_total()` exit 0; `assert True` in `src/a.py` exits 0 (tests only).
  - Must not: block an `Edit` whose file already held the same shortcut once and still holds it once.
  - Check: `test_acceptance_v211.HookTests.test_ac_001_shortcuts_blocked`
  - WP: WP-01, WP-02
- AC-002 · close-stage fails on a shortcut written another way, and not on one already there
  - Scenario: a committed `src/a.py` that already holds `except Exception:\n    pass` once; `snapshot 1`.
  - Action: one hook call from WP-01 (`repo.as_agent()`, as `test_agentic.py:1409` does, so the stage counts as guarded); write (on disk, no hook) `src/a.py` with that block twice and a `[DEBUG-x]` line; `check-wave 1`.
  - Expected: exit 3; stdout holds `src/a.py: an exception swallowed with pass` and `src/a.py: a [DEBUG-] log left behind`. Restoring the original content and checking again exits 0.
  - Must not: report the block that was already in the committed file.
  - Check: `test_acceptance_v211.StageTests.test_ac_002_close_stage`
  - WP: WP-01
- AC-003 · Counting tests without assertions
  - Scenario: `core.assertless_tests`.
  - Action: call it on: two tests with `assert`; one test with `self.assertIn`; one with `pytest.raises`; one with only `x = 1`; a method `test_b` in a class with `pass`; text `def (:`.
  - Expected: 0, 0, 0, 1, 1, 0.
  - Must not: count a function whose name does not start with `test_`.
  - Check: `test_acceptance_v211.CoreTests.test_ac_003_assertless_tests`
  - WP: WP-01
- AC-004 · An unclaimed workflow-subagent cannot write files
  - Scenario: no `AGENTIC_WP`; payloads with `agent_id: "w1"`, `agent_type: "workflow-subagent"`.
  - Action: hook a `Write` of `src/a.py`; a `Bash` `ls`; the claim `python3 .claude/bin/agentic.py claim WP-01`; then a `Write` of `src/a.py` and of `src/b/x.py`.
  - Expected: the first `Write` exits 2 with `claim` in stderr; `Bash` exits 0; the claim exits 0; after it `src/a.py` exits 0 and `src/b/x.py` exits 2.
  - Must not: block the main thread (no `agent_id`) or an agent of another unknown type writing without a claim.
  - Check: `test_acceptance_v211.HookTests.test_ac_004_workflow_subagent`
  - WP: WP-02
- AC-005 · validate warns and still passes
  - Scenario: the default manifest changed to: WP-01 owning 16 files; WP-02 with 9 ACs; 9 packages in wave 1 (in another manifest); a manifest of three waves with one package each.
  - Action: `agentic.py validate` in a temporary repository for each.
  - Expected: exit 0; `Manifest valid.` then the lines `warning: WP-01: owns 16 files (more than 15): consider splitting it`, `warning: WP-02: answers for 9 criteria (more than 8): consider splitting it`, `warning: wave 1: 9 packages (more than 8): consider another wave`, `warning: every wave holds one package: the plan is a chain, nothing runs in parallel`. The default manifest prints no `warning:`.
  - Must not: print warnings from `pipeline-plan` or any other command, or change the exit code.
  - Check: `test_acceptance_v211.ValidateTests.test_ac_005_warnings`
  - WP: WP-03
- AC-006 · Text that is not clean UTF-8 is found
  - Scenario: a temporary folder with `ok.md` (valid UTF-8 with `\u00f1`), `latin.txt` (bytes `caf\xe9`), `double.md` (`"caf\u00c3\u00a9"` encoded as UTF-8), `bom.md` (`"\ufeffx"` as UTF-8), `bin.dat` (bytes `\x00\xff`); every fixture written with escapes.
  - Action: `test_encoding.text_problems(folder, [all five])`.
  - Expected: exactly `["bom.md: starts with a byte-order mark", "double.md: double-encoded text", "latin.txt: not valid UTF-8"]` (sorted by path).
  - Must not: report the binary file or the valid one.
  - Check: `test_acceptance_v211.EncodingTests.test_ac_006_text_problems`
  - WP: WP-04
- AC-007 · This repository's text is clean, and 2.11.0 says what changed
  - Scenario: this checkout.
  - Action: `text_problems(ROOT, <git ls-files as repository-relative paths>)`; read `plugin.json` and `upgrade.NOTES`.
  - Expected: `[]`; version `2.11.0`; `NOTES["2.11.0"]` mentions `shortcut`, `validate` and `workflow-subagent`. Skipped outside the agentic-flow repository.
  - Must not: skip the check in this repository.
  - Check: `test_acceptance_v211.ReleaseTests.test_ac_007_repo_and_release`
  - WP: WP-04, WP-05
- AC-008 · The retired acceptance file's unique checks still run
  - Scenario: after WP-05.
  - Action: run `test_launcher.py` and `test_guardrail.py`; list `.claude/bin/test_acceptance*.py`.
  - Expected: both pass; `test_launcher.py` has `ByHandPlanTests.test_every_agent_command_refuses_before_writing`, where `pipeline-plan`, `run-wave 1`, `run-review`, `run-acceptance` and `run-pipeline` on a by-hand plan exit 1 with `executed by hand` and start no agent; `test_guardrail.py` has `HookLauncherTests.test_a_leftover_frozen_copy_is_never_run`, where `hook.py` with a leftover `.claude/state/guard/` blocks a foreign write (exit 2) without running the copy; the only acceptance file is `test_acceptance_v211.py`.
  - Must not: keep `test_acceptance_v210.py`.
  - Check: `test_acceptance_v211.RetireTests.test_ac_008_v210_retired`
  - WP: WP-02, WP-05

### Work packages
All files are disjoint. Wave 1 holds WP-01, WP-03 and WP-04. WP-02 is wave 2: `guardrail.py` imports `shortcut_problems` from `core.py`, and `agentic.py` imports `guardrail`, so until WP-01 lands every command, the hook included, would fail to import. WP-05 is wave 3: it deletes `test_acceptance_v210.py` after WP-02 has moved its hook check. The packages are executed by hand.

#### WP-01 · Shortcut detection in core and the stage check
- Wave: 1.
- Files: `.claude/bin/core.py`, `.claude/bin/stage.py`, `.claude/bin/test_shortcuts.py` (new).
- Implements: `SHORTCUT_RES`, `ASSERT_CALL_PREFIXES`, `assertless_tests`, `shortcut_problems`; `content_problems` uses them.
- ACs: AC-002, AC-003, and the core side of AC-001.
- Patterns to mirror: `.claude/bin/core.py:88-115` (constants); `.claude/bin/stage.py:114-138` (`content_problems`); `.claude/bin/test_agentic.py:1345-1362` (stage tests).
- Gotchas:
  - `assertless_tests` uses `ast`; a call's name is `node.func.attr` for `self.assertX(...)`/`pytest.raises(...)` and `node.func.id` for `check_total()`; a `with pytest.raises(...)` holds a call too.
  - Python 3.9: no `match`, no `|` in annotations.
  - `import ast` in `core.py` (standard library, alphabetical with the others).
- Validation: `python3 -m unittest discover -s .claude/bin -p test_shortcuts.py`; `python3 -m unittest discover -s .claude/bin -p test_agentic.py` (its `SafetyNetTests` run `content_problems`); `python3 .claude/bin/agentic.py quality`.

#### WP-02 · The hook: shortcuts and the workflow-subagent claim
- Wave: 2, after WP-01 (it imports `core.shortcut_problems`).
- Files: `.claude/bin/guardrail.py`, `.claude/bin/test_guardrail.py`.
- Implements: shortcut blocking in `content_checks`; `FILE_WRITE_TOOLS` and the `workflow-subagent` rule in `require_claim`. Moves `test_acceptance_v210.HookTests` (hook.py runs the live guard) into `test_guardrail.py`. Consumes `core.shortcut_problems` by implementation (WP-01).
- ACs: AC-001, AC-004, part of AC-008.
- Patterns to mirror: `.claude/bin/guardrail.py:165-187`, `:230-235`; `.claude/bin/test_guardrail.py:1-60`; `.claude/bin/test_agentic.py:395-425`.
- Gotchas: `old` must be computed for every path now, not only test paths; keep the Edit "already there" case (`old` from the file before the edit). The claim message stays the one at `guardrail.py:233-235`.
- Validation: `python3 -m unittest discover -s .claude/bin -p test_guardrail.py`; `python3 -m unittest discover -s .claude/bin -p test_agentic.py` (its hook content tests at `:395-425`).

#### WP-03 · validate warnings
- Wave: 1.
- Files: `.claude/bin/manifest_check.py`, `.claude/bin/agentic.py`, `.claude/bin/test_manifest_check.py`.
- Implements: `complexity_warnings`, the three constants, `cmd_validate`'s printing.
- ACs: AC-005.
- Patterns to mirror: `.claude/bin/manifest_check.py:62-70`; `.claude/bin/agentic.py:150-152`; `.claude/bin/test_manifest_check.py:1-30`.
- Gotchas: `cmd_validate` imports `complexity_warnings` from `manifest_check` (add it to the existing import line without making it long). The chain rule needs two or more waves.
- Validation: `python3 -m unittest discover -s .claude/bin -p test_manifest_check.py`; `python3 -m unittest discover -s .claude/bin -p test_definitions.py`.

#### WP-04 · Clean UTF-8, version and docs
- Wave: 1.
- Files: `.claude/bin/test_encoding.py` (new), `docs/how-it-works.md`, `docs/how-to/README.md`.
- Implements: `text_problems` and the repository test (`FLOW_REPO_ONLY`, over `git ls-files`); the content-checks sentence (`docs/how-it-works.md:233`) and the `validate` line of the command list (`docs/how-to/README.md:172`: add `; warns about oversized packages or a chain of waves`).
- ACs: AC-006, AC-007 (the repository part).
- Patterns to mirror: `.claude/bin/test_definitions.py:28`, `:67-75`.
- Gotchas: read files as bytes; a NUL in the first 8000 bytes means binary. `tracked_files()` returns absolute paths: build the repository-relative list with `git ls-files` instead. Every special character in this file is an escape.
- Validation: `python3 -m unittest discover -s .claude/bin -p test_encoding.py`; `python3 .claude/bin/agentic.py docs-check`.

#### WP-05 · Retire test_acceptance_v210.py
- Wave: 3, after WP-02.
- Files: `.claude/bin/test_launcher.py`, `.claude/bin/test_acceptance_v210.py` (deleted), `.claude/bin/upgrade.py`, `.claude-plugin/plugin.json`.
- Implements: version 2.11.0 and `NOTES["2.11.0"]`, three notes: (1) shortcuts blocked by the hook and close-stage, counted only when added; (2) `validate` prints complexity warnings (thresholds not measured), never errors; (3) a `workflow-subagent` without a claim cannot write files (#68 unverified). The bump is here, not in wave 1, because `test_acceptance_v210.ReleaseTests` pins 2.10.0 until this package deletes it. Also moves `test_acceptance_v210.RefusalTests` (by-hand plan refused by `pipeline-plan` and the `run-*` launchers before writing anything) into `test_launcher.py`, with its `FlowRepo` and marker helpers; deletes the file.
- ACs: part of AC-008, AC-007 (the release part).
- Patterns to mirror: `.claude/bin/test_launcher.py:30-70` (`LauncherCase`); `.claude/bin/upgrade.py:130-150`.
- Gotchas: `test_layout.py` passes only once v210 is gone and v211 exists: the maintainer runs it after this package.
- Validation: `python3 -m unittest discover -s .claude/bin -p test_launcher.py`; `python3 -m unittest discover -s .claude/bin -p test_layout.py`.

```json wp-manifest
{
  "maintainer": true,
  "stack": ["python"],
  "allow_bash": ["Bash(python3 -m unittest:*)", "Bash(node .claude/bin/test_workflow.mjs)"],
  "acceptance": {"files": [".claude/bin/test_acceptance_v211.py"], "command": "python3 -m unittest discover -s .claude/bin -p test_acceptance_v211.py"},
  "verify": {"build": "python3 -m unittest discover -s bench -p \"test_*.py\"", "lint": "node .claude/bin/test_workflow.mjs", "types": "python3 -m unittest discover -s bench/acceptance", "tests": "python3 -m unittest discover -s .claude/bin -p \"test_*.py\""},
  "docs": {"files": ["docs/assets/"], "codemap": null},
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": [".claude/bin/core.py", ".claude/bin/stage.py", ".claude/bin/test_shortcuts.py"],
     "acs": ["AC-001", "AC-002", "AC-003"], "mirror": [".claude/bin/core.py:88-115", ".claude/bin/stage.py:114-138", ".claude/bin/test_agentic.py:1345-1362"]},
    {"id": "WP-02", "wave": 2, "depends_on": ["WP-01"], "files": [".claude/bin/guardrail.py", ".claude/bin/test_guardrail.py"],
     "acs": ["AC-001", "AC-004", "AC-008"], "mirror": [".claude/bin/guardrail.py:165-187", ".claude/bin/guardrail.py:230-235", ".claude/bin/test_guardrail.py:1-60", ".claude/bin/test_agentic.py:395-425"]},
    {"id": "WP-03", "wave": 1, "depends_on": [], "files": [".claude/bin/manifest_check.py", ".claude/bin/agentic.py", ".claude/bin/test_manifest_check.py"],
     "acs": ["AC-005"], "mirror": [".claude/bin/manifest_check.py:62-70", ".claude/bin/agentic.py:150-152", ".claude/bin/test_manifest_check.py:1-30"]},
    {"id": "WP-04", "wave": 1, "depends_on": [], "files": [".claude/bin/test_encoding.py", "docs/how-it-works.md", "docs/how-to/README.md"],
     "acs": ["AC-006", "AC-007"], "mirror": [".claude/bin/test_definitions.py:28", ".claude/bin/test_definitions.py:67-75"]},
    {"id": "WP-05", "wave": 3, "depends_on": ["WP-02"], "files": [".claude/bin/test_launcher.py", ".claude/bin/test_acceptance_v210.py", ".claude/bin/upgrade.py", ".claude-plugin/plugin.json"],
     "acs": ["AC-007", "AC-008"], "mirror": [".claude/bin/test_launcher.py:30-70", ".claude/bin/upgrade.py:130-150"]}
  ]
}
```

## 9. Test strategy
- **Acceptance:** `.claude/bin/test_acceptance_v211.py`, written first, red before the code.
- **Unit:** each package in its files; the hook and stage tests through temporary repositories (`test_agentic.Repo`).
- **QA by hand:** run the hook against each shortcut kind with `Edit` and `MultiEdit` as well as `Write`; `validate` on the 17 archived manifests (expect the chain warning on 0013 only, measured in the reconnaissance).
- **Everything:** section 3, plus the teeth check (break each new check, see its test fail, restore).
- **Expected red during the run:** `test_layout.py` fails from the moment the acceptance file `test_acceptance_v211.py` exists until WP-05 deletes `test_acceptance_v210.py` (two acceptance files); it is not a defect of waves 1 and 2. The binary files under `docs/assets/` (GIF, PNG) are skipped by the NUL test: checked by QA.

## 10. Decisions
- **Shortcuts block** (user's choice), like secrets and skips: the hook on a write, `close-stage` for anything else; only additions count, so existing code is never blamed. Measured today: `guardrail.py:115-116` and `stage.py:83-84` already hold a commented `except Exception:` followed by `pass` (they match the first pattern); nothing else matches. Only additions count, so it is not blamed and stays as it is.
- **Tests without assertions: Python only, by AST** (user's choice); a call whose name starts with assert/check/expect/verify/fail/raises counts as asserting, so helper-based tests are not flagged.
- **`workflow-subagent`: file writes need a claim, Bash does not** (user's choice): it closes the write hole if the Workflow tool's subagents carry that type, without breaking a gatekeeper that might carry it too. Not verified (section 11).
- **UTF-8: a test of this repository only** (user's choice): projects may hold other encodings on purpose.
- **Warning thresholds 15 files, 8 ACs, 8 packages per wave:** just above the largest values in the 17 archived plans (14, 8, 7). Not calibrated against bench runs, as issue 60 asks: noted as not measured.
- **Retire `test_acceptance_v210.py` here**, as design 0017's rule asks when a release adds its own acceptance file.
- **Executed by hand**, like 0013 to 0017.

## 11. Risks and open questions
- **#68 is unverified.** If the Workflow tool's implementers arrive with another type, this rule changes nothing; if a gatekeeper arrives as `workflow-subagent` and ever writes a file (it should not), it would be blocked. To verify in a local session: run `/implement` and read `agent_type` in `.claude/state/hook-seen.json`.
- **This repository's own files contain the patterns** (`core.py`'s regexes, the tests of this design): a future agent stage that adds more of them would be flagged. Fixtures split the tokens (`"[DEB" "UG-"`, `"assert " + "True"`) so the files themselves add no match.
- **False positives:** a project test that legitimately asserts on the text `[DEBUG-`, a JS file with an intentional empty `catch {}`, or a Python test that asserts only through a helper whose name has none of the prefixes (`run_scenario(...)`, `self.w(...)`): the agent returns BLOCKED and a person decides.
- Rollback: revert the commits; nothing is migrated.
