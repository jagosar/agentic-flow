# Architecture: the flow on Windows (with Git for Windows) and macOS
Type: change · Size: large

## 1. Goal
The flow only runs on Linux and macOS today: `agentic.py` imports `fcntl` (absent on Windows), kills processes with `os.killpg`, calls Python as `python3` everywhere (on Windows it is `python` or `py`), runs `npm`/`claude` without resolving `.cmd` files, reads and writes text with the platform's default encoding, and nothing tests it outside Ubuntu. This change makes it run on native Windows with Git for Windows — what Claude Code recommends there, and what runs hooks and the Bash tool in Git Bash — with the same guardrails, and proves it with CI on Windows and macOS. Without Git Bash the flow refuses to start instead of running without guardrails.

## 2. Scope
### Included
- `compat.py`: the operating-system layer (file locks, process groups and killing, executable resolution, UTF-8 standard streams, line-ending-independent content hashes).
- `.claude/bin/agentic`: a POSIX `sh` launcher that finds Python 3.9+ (`python3`, `python`, `py -3`). Every caller (hook, permissions, workflow, agents, commands, plugin, docs) uses `sh .claude/bin/agentic <command>`.
- `agentic.py` and `upgrade.py` use `compat.py`; UTF-8 explicit in every text read and write; the hook also guards the `PowerShell` tool (blocked for the flow's agents); `install` migrates the old `python3 … agentic.py` hook and permission and keeps the launcher's line endings LF through `.gitattributes`.
- Portable tests (fake executables as `.cmd` on Windows) and a CI matrix with `windows-latest` and `macos-latest`.
- Version 1.2.0 with its upgrade note; docs.
### Excluded (non-goals)
- Windows without Git for Windows (PowerShell-only): detected and refused, not supported.
- WSL: it is Linux; nothing to do.
- A manual end-to-end run of Claude Code on Windows (user's choice: CI only). See §11.
- Rewriting manifest commands per OS: manifests keep POSIX-style commands with forward slashes.

## 3. Stack
Python 3.9+ standard library only (`msvcrt` on Windows, `fcntl` elsewhere, both stdlib). POSIX `sh` (Git Bash on Windows). Node ≥ 18 for the workflow tests. GitHub Actions.
- Build: `python3 -m compileall -q .claude/bin`
- Tests: `python3 -m unittest discover -s .claude/bin -p "test_*.py"`
- Acceptance: `python3 -m unittest discover -s .claude/bin -p test_acceptance_windows.py`

## 4. Repository structure
```
.claude/bin/compat.py                       WP-01 (new)
.claude/bin/test_compat.py                  WP-01 (new)
.claude/bin/agentic                         WP-02 (new, sh launcher, LF)
.gitattributes                              WP-02 (new)
.claude/bin/test_launcher.py                WP-02 (new)
.claude/bin/agentic.py                      WP-03
.claude/bin/upgrade.py                      WP-03
.claude/bin/test_agentic.py                 WP-03
.claude/bin/test_upgrade.py                 WP-03
.claude/settings.json                       WP-04
.claude/workflows/agentic-implement.js      WP-04
.claude/agents/*.md                         WP-04
.claude/commands/*.md                       WP-04
plugin/commands/init.md                     WP-04
.claude/bin/test_workflow.mjs               WP-04
.claude/bin/test_definitions.py             WP-04
.claude/bin/testutil.py                     WP-05 (new)
.claude/bin/test_pipeline.py                WP-05
.claude/bin/test_acceptance.py              WP-05
.claude/bin/test_acceptance_upgrade.py      WP-05
.github/workflows/agentic-flow-ci.yml       WP-05
README.md, docs/how-it-works.md, docs/how-to/*.md   WP-06
.claude-plugin/plugin.json, .claude/flow-history.json WP-06
.claude/bin/test_acceptance_windows.py      AT (new)
```
Waves: WP-01, WP-02, WP-04, WP-05 (1) → WP-03 (2) → WP-06 (3); see D8.

## 4b. Existing code context
| What an implementer needs to know | Where it is | Pattern or rule |
|---|---|---|
| POSIX-only imports | `agentic.py:56` (`import fcntl`), `64` (`import signal`) | `fcntl` makes the module fail to import on Windows: remove it from `agentic.py` |
| File lock of the ledger and claims | `agentic.py:1443-1458` (`locked_json`, `fcntl.flock` at 1447) | Becomes `with compat.locked(fh):` |
| Process group and kill | `agentic.py:612` (`start_new_session=True` in `run_agent`), `1547-1551` (`kill_group`, `os.killpg`), `1554` (`stop`) | Use `compat.group_kwargs()` and `compat.kill_tree(pid)` |
| Commands run without a shell | `agentic.py:1043` (`run_command`: `shlex.split(cmd)`), `1091` (`run_steps`, runs `sys.executable`), `599-612` (`run_agent`: `["claude", …]`) | Pass argv through `compat.resolve(argv)` so `npm` finds `npm.cmd` and `claude` finds `claude.exe`/`.cmd` |
| Text encodings | e.g. `agentic.py:538, 548, 589, 610, 630, 1155, 1196, 1203, 1313, 1378, 1446, 1505` (no `encoding=`), `1705` and `1781` (`json.load(sys.stdin)`) | Every text `open`/`read_text`/`write_text` passes `encoding="utf-8"`; stdin is read as bytes and decoded as UTF-8; `main()` calls `compat.utf8_stdio()` first |
| The claim pattern | `agentic.py:151` (`CLAIM_RE`) | Must match `sh .claude/bin/agentic claim WP-01` and the old `python3 .claude/bin/agentic.py claim WP-01` |
| Messages that name the interpreter | `agentic.py:605` (`--allowedTools … "Bash(python3 .claude/bin/agentic.py claim:*)"`), `1416` (`sync_permissions`), `1667` (claim message), codemap header (`agentic.py:826`) | Use `sh .claude/bin/agentic` |
| The hook | `agentic.py:1647-1700` (`guard`), `1701-1716` (`hook`); paths: `guard` resolves `file_path` and calls `.relative_to(ROOT.resolve()).as_posix()` | Already separator-safe; add the `PowerShell` tool rule (§6) |
| Settings merge on install | `agentic.py:906-926` (`merge_settings`) | Today it skips adding the hook if any hook command contains `agentic.py` and ends in `hook`: replace with the migration of §6 |
| Gitignore lines on install | `agentic.py:120` (`INSTALL_GITIGNORE`), used in `install` around line 989 | Same pattern for `.gitattributes` |
| Installed files | `agentic.py:117` (`INSTALL_GLOBS`) | Add `.claude/bin/compat.py` and `.claude/bin/agentic` |
| Content hashes | `agentic.py:894` (`sha256`), `upgrade.py:100-127` (`build_history`, `hashlib.sha256` at 120) | Use `compat.content_hash` (CRLF → LF before hashing) in `install` and `build_history`; `digest()` (ownership check) keeps raw bytes |
| Hook entry and permission | `.claude/settings.json:4` (`Bash(python3 .claude/bin/agentic.py:*)`), `:16` (matcher), `:20` (command) | New values in §6 |
| Workflow command prefix | `agentic-implement.js:25` (`const AGENTIC = 'python3 .claude/bin/agentic.py'`) | `'sh .claude/bin/agentic'`; the gatekeeper's rule (`agents/gatekeeper.md:16`) follows |
| Workflow tests parse the prefix | `test_workflow.mjs:43` (`prompt.split('agentic.py ')`), `:191` | Split on the new prefix |
| Docs drift test | `test_definitions.py:322` (regex for `python3 .claude/bin/agentic.py <cmd>`) | Must also recognise `sh .claude/bin/agentic <cmd>` |
| Fake `claude` executables in tests | `test_agentic.py:32-48`, `test_pipeline.py:188-237`, `test_acceptance.py:55-100` (shebang + `chmod`) | Replace with `testutil.fake_exe` (§6) |
| POSIX paths in tests | `test_agentic.py:160` (`"/tmp/outside.py"`) | Use `tempfile.gettempdir()` |
| CI | `.github/workflows/agentic-flow-ci.yml:20-44` (job `test`, Ubuntu, Python 3.9/3.12/3.14) | Add an OS axis (§6) |

## 5. Data model
- **Launcher** `.claude/bin/agentic` (no extension, LF line endings, run as `sh .claude/bin/agentic …`).
- **`.gitattributes` line** written by `install` and present in this repo: `.claude/bin/agentic text eol=lf` (a CRLF checkout of a `sh` script fails with `$'\r': command not found`).
- **Content hash:** `sha256(bytes.replace(b"\r\n", b"\n"))`, hex.
- **Settings entries owned by the flow** (current / legacy):
  - permission `Bash(sh .claude/bin/agentic:*)` / legacy `Bash(python3 .claude/bin/agentic.py:*)`;
  - PreToolUse hook `{"matcher": "Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell", "hooks": [{"type": "command", "command": "sh \"$CLAUDE_PROJECT_DIR/.claude/bin/agentic\" hook"}]}` / legacy: any hook whose command contains `.claude/bin/agentic.py` and ends in `hook`.

## 6. Contracts between modules
**`compat.py`** (WP-01) — `IS_WINDOWS = os.name == "nt"`; every function branches on it, so tests can patch it.
```python
@contextlib.contextmanager
def locked(fh):
    """Exclusive lock of an open file for the block. POSIX: fcntl.flock(LOCK_EX). Windows: msvcrt.locking on byte 0
    with LK_LOCK, retried until acquired (LK_LOCK gives up after ~10 s with OSError), released with LK_UNLCK."""

def group_kwargs() -> dict
    """Popen kwargs that start the child in its own process group: {"start_new_session": True} on POSIX,
    {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} on Windows."""

def kill_tree(pid: int) -> None
    """Ends the process and its children; never raises. POSIX: os.killpg(pid, SIGTERM). Windows:
    `taskkill /T /F /PID <pid>` (output discarded)."""

def resolve(argv: list[str]) -> list[str]
    """argv with argv[0] replaced by shutil.which(argv[0]) when found (so npm -> npm.cmd on Windows); unchanged
    otherwise, so the caller's FileNotFoundError handling still applies."""

def utf8_stdio() -> None
    """Reconfigures sys.stdout and sys.stderr to UTF-8 (errors="replace") when they support reconfigure()."""

def read_stdin_text() -> str
    """sys.stdin.buffer.read().decode("utf-8")."""

def content_hash(path) -> str
    """sha256 hex of the file's bytes with CRLF turned into LF."""
```
**Launcher** `.claude/bin/agentic` (WP-02): `sh .claude/bin/agentic ARGS…` runs `agentic.py ARGS…` (the file next to the launcher) with the first of `python3`, `python`, `py -3` for which `-c 'import sys; sys.exit(sys.version_info < (3, 9))'` exits 0, using `exec` so the exit code passes through; stdin is inherited (the hook reads it). If none qualifies: stderr `agentic: Python 3.9 or later not found (tried python3, python, py -3)` and exit 2 (so a hook blocks, fail-closed). The candidate test must run the interpreter (the Microsoft Store `python3` stub exists on PATH but exits non-zero).

**`agentic.py`** (WP-03)
- Imports `compat` via `sibling("compat")` at module level (it is next to it), and never `fcntl`.
- `locked_json` uses `compat.locked`; `run_agent` uses `compat.group_kwargs()` and `compat.resolve`; `kill_group` becomes `compat.kill_tree` (callers updated); `run_command` and `run_steps` resolve argv.
- `main()` first calls `compat.utf8_stdio()`; `hook` and `save-result` read stdin with `compat.read_stdin_text()`.
- `CLAIM_RE = re.compile(r"agentic(?:\.py)?\s+claim\s+(WP-\d+|QA|AT|REVIEW|DOCS)\b")`.
- `guard`: if `tool == "PowerShell"` and the caller is one of the flow's agents (an `agent_id`, or `AGENTIC_WP`), block with `the flow's agents use the Bash tool (Git for Windows); PowerShell is not allowed for them`; the main session is not restricted.
- Interpreter text: `sh .claude/bin/agentic` in the claim message, `run_agent`'s allowed tool (`Bash(sh .claude/bin/agentic claim:*)`), `sync_permissions` (`Bash(sh .claude/bin/agentic:*)`) and the codemap header.
- `merge_settings(dst, src)`: removes the legacy permission and every legacy hook entry (§5) before adding the flow's current ones; adds the current hook entry only if no hook command contains `.claude/bin/agentic"` (the launcher) and ends in `hook`; reports `migrated hook to sh .claude/bin/agentic` / `migrated permission` in `added` when it replaced something. Nothing else of the user's is touched.
- `install` adds `.claude/bin/agentic text eol=lf` to `.gitattributes` when missing (same reporting as `.gitignore`: `  .gitattributes: <lines>`), and uses `compat.content_hash` for every comparison and for the record. `INSTALL_GLOBS` gains `.claude/bin/compat.py` and `.claude/bin/agentic`. `.gitattributes` joins the paths the dirty guard checks.
- Every text `open`, `read_text` and `write_text` in `agentic.py`, `upgrade.py`, `pipeline.py`, `brief.py`, `compat.py` passes `encoding="utf-8"` (binary modes excepted).
- `upgrade.build_history` hashes with the CRLF-normalised digest (same as `compat.content_hash`, applied to the blob bytes). `upgrade.NOTES["1.2.0"]` = `["Commands run through 'sh .claude/bin/agentic <command>' (it finds python3, python or py -3); install migrates the hook and permission. On Windows the flow needs Git for Windows."]`.

**`testutil.py`** (WP-05)
```python
def fake_exe(directory, name, python_source) -> Path
    """An executable `name` on PATH that runs python_source with sys.executable: on POSIX a script with a shebang and
    mode 0o755; on Windows `name.py` plus `name.cmd` (`@"<sys.executable>" "%~dp0<name>.py" %*`). Returns its path."""
```
**References** (WP-04): `settings.json` per §5; `AGENTIC = 'sh .claude/bin/agentic'`; the gatekeeper accepts only commands starting with `sh .claude/bin/agentic`; agents' first action `sh .claude/bin/agentic claim <ID>`; commands and `plugin/commands/init.md` use `sh .claude/bin/agentic …` and `sh "${CLAUDE_PLUGIN_ROOT}/.claude/bin/agentic" install <root>`; `init.md` explains that on Windows a `sh: command not found` or `python not found` means installing Git for Windows or Python.
**CI** (WP-05): job `test` matrix `os: [ubuntu-latest]` × `python: ["3.9", "3.12", "3.14"]` plus `include` entries `{os: windows-latest, python: "3.12"}` and `{os: macos-latest, python: "3.12"}`; `runs-on: ${{ matrix.os }}`; `shell: bash` for every run step; Windows keeps the runner's default `core.autocrlf` (so CRLF is exercised).

## 7. Conventions
- Stdlib only. `compat.py` is the only module that branches on the OS; nobody else checks `os.name`.
- English; `agentic.py`'s style (no annotations; `except Exception` only where a function promises not to raise).
- Manifest and documentation commands keep POSIX syntax with forward slashes; on Windows they run in Git Bash or, for `verify`/`acceptance`, without a shell through `compat.resolve`.
- Every doc that shows a flow command writes `sh .claude/bin/agentic <command>`.

## 8. Work packages and acceptance criteria
### Acceptance criteria
Tests run on every OS of the CI matrix; the local run here is Linux only.
- AC-001 · The launcher finds a working Python 3.9+
  - Scenario: a temp dir with a copy of `.claude/bin/`; `PATH` holds a fake `python3` that exits 9009 (the Store stub) and a fake `python` that runs the real interpreter with its arguments, and the real `sh`.
  - Action: `sh <copy>/.claude/bin/agentic stack` with that PATH; then with a PATH whose fakes `python3`, `python`, `py` all exit 1.
  - Expected: the first prints the `stack` JSON and exits 0; the second exits 2 with `Python 3.9 or later not found` on stderr.
  - Must not: run the Store stub's output as the result, or exit 0 when no Python qualifies.
  - Check: `test_acceptance_windows.py::test_ac_001_launcher`.
  - WP: WP-02
- AC-002 · `agentic.py` imports and locks without `fcntl`
  - Scenario: a Python process where `sys.modules["fcntl"] = None` before importing.
  - Action: import `agentic` from `.claude/bin` and call `locked_json` on a temp file with a writer function, using `compat.IS_WINDOWS` patched to False on POSIX runners (real `fcntl`) — and natively on Windows.
  - Expected: the import succeeds; `locked_json` writes the dict; `grep -n "^import fcntl" .claude/bin/agentic.py` finds nothing.
  - Must not: import `fcntl` or `msvcrt` outside `compat.py`.
  - Check: `test_acceptance_windows.py::test_ac_002_no_fcntl`.
  - WP: WP-01, WP-03
- AC-003 · Commands are found through PATHEXT
  - Scenario: a project whose manifest has `verify: {"tests": "faketool --ok"}`, with `faketool` created by `testutil.fake_exe` (a `.cmd` on Windows) on PATH, exiting 0.
  - Action: `sh .claude/bin/agentic verify`.
  - Expected: the `tests` phase has `"passed": true`.
  - Must not: report `command not found`.
  - Check: `test_acceptance_windows.py::test_ac_003_resolve`.
  - WP: WP-03
- AC-004 · Non-ASCII text survives any console encoding
  - Scenario: a project whose `architecture.md` contains `· € ñ` and a ledger with a label `WP-01 · ñ`.
  - Action: `agentic.py validate` and `agentic.py status` with `PYTHONIOENCODING=ascii`.
  - Expected: both exit 0 and `status` prints `WP-01`.
  - Must not: raise `UnicodeEncodeError` or `UnicodeDecodeError`.
  - Check: `test_acceptance_windows.py::test_ac_004_utf8`.
  - WP: WP-03
- AC-005 · Every text read and write declares UTF-8
  - Scenario: the sources `agentic.py`, `upgrade.py`, `pipeline.py`, `brief.py`, `compat.py`.
  - Action: parse them with `ast` and inspect every call to `open`, `.open`, `read_text`, `write_text`.
  - Expected: each has an `encoding` keyword, or a mode containing `b`.
  - Must not: allow a call without either.
  - Check: `test_acceptance_windows.py::test_ac_005_encodings_declared`.
  - WP: WP-03
- AC-006 · Native paths in the hook
  - Scenario: a project with the manifest of `test_agentic.py` (WP-01 owns `src/a.py`).
  - Action: the hook with `{"tool_name": "Write", "tool_input": {"file_path": str(<project>/"src"/"a.py")}}` (native separators: backslashes on Windows) for WP-01, and for WP-02.
  - Expected: exit 0 for WP-01, exit 2 for WP-02.
  - Must not: block the owner because of the separator.
  - Check: `test_acceptance_windows.py::test_ac_006_native_paths`.
  - WP: WP-03
- AC-007 · PowerShell is closed to the flow's agents
  - Scenario: the AC-006 project.
  - Action: the hook with `tool_name: "PowerShell"` and `command: "Get-ChildItem"`, once with `agent_id` `a1` claimed as WP-01, once from the main session (no `agent_id`, no `AGENTIC_WP`).
  - Expected: exit 2 with `PowerShell is not allowed` for the agent; exit 0 for the main session.
  - Must not: let an agent through.
  - Check: `test_acceptance_windows.py::test_ac_007_powershell`.
  - WP: WP-03
- AC-008 · Claims through the launcher and the legacy form
  - Scenario: the AC-006 project.
  - Action: hook Bash payloads `sh .claude/bin/agentic claim WP-01` (agent `a1`) and `python3 .claude/bin/agentic.py claim WP-02` (agent `a2`).
  - Expected: `.claude/state/claims.json` maps `a1` → `WP-01` and `a2` → `WP-02`.
  - Must not: ignore either form.
  - Check: `test_acceptance_windows.py::test_ac_008_claims`.
  - WP: WP-03
- AC-009 · Install migrates the old hook and permission
  - Scenario: a git repo whose committed `.claude/settings.json` has the legacy hook (`python3 "$CLAUDE_PROJECT_DIR/.claude/bin/agentic.py" hook`), the legacy permission, a user permission `Bash(make test)` and a user hook `PostToolUse` entry.
  - Action: `install`.
  - Expected: exactly one PreToolUse entry whose command is `sh "$CLAUDE_PROJECT_DIR/.claude/bin/agentic" hook` with matcher `Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell`; `Bash(sh .claude/bin/agentic:*)` present and the legacy permission gone; `Bash(make test)` and the `PostToolUse` entry unchanged; `.gitattributes` contains `.claude/bin/agentic text eol=lf`; running `install` again reports `settings.json: unchanged` and adds no line to `.gitattributes`.
  - Must not: leave two flow hooks, or remove anything of the user's.
  - Check: `test_acceptance_windows.py::test_ac_009_migrate_settings`.
  - WP: WP-03
- AC-010 · CRLF copies of intact files are recognised
  - Scenario: an upgrade source whose history lists the LF content `OLD\n` for `.claude/agents/qa.md`; the target holds `OLD\r\n`.
  - Action: `install`.
  - Expected: the file is listed under `updated:`.
  - Must not: list it under `modified by you (left alone)`.
  - Check: `test_acceptance_windows.py::test_ac_010_crlf_intact`.
  - WP: WP-03
- AC-011 · Every reference uses the launcher
  - Scenario: the repo.
  - Action: read `.claude/settings.json`, `.claude/workflows/agentic-implement.js`, `.claude/agents/*.md`, `.claude/commands/*.md`, `plugin/commands/init.md`.
  - Expected: none contains `python3 .claude/bin/agentic.py` or `python3 "`; settings and workflow use `sh .claude/bin/agentic` / the §5 hook.
  - Must not: keep a `python3` reference to the flow.
  - Check: `test_acceptance_windows.py::test_ac_011_references`.
  - WP: WP-04
- AC-012 · CI covers Windows and macOS
  - Scenario: `.github/workflows/agentic-flow-ci.yml`.
  - Action: parse it as text.
  - Expected: the `test` job runs on `${{ matrix.os }}` and the matrix includes `windows-latest` and `macos-latest`; run steps use `shell: bash`.
  - Must not: drop the Ubuntu Python versions.
  - Check: `test_acceptance_windows.py::test_ac_012_ci_matrix`; and the real CI run on the pull request is green on all three systems.
  - WP: WP-05
- AC-013 · Docs say how to run on Windows
  - Scenario: `docs/how-to/README.md`, `docs/how-to/onboarding.md`, `README.md`.
  - Action: read them.
  - Expected: `docs/how-to/README.md` has a requirement naming `Git for Windows`; no doc cites `python3 .claude/bin/agentic.py`; `README.md` mentions Windows, macOS and Linux.
  - Must not: break `DocumentationDriftTests`.
  - Check: `test_acceptance_windows.py::test_ac_013_docs`.
  - WP: WP-06

### Work packages
#### WP-01 · `compat.py`, the OS layer
- Wave 1. Files: `.claude/bin/compat.py`, `.claude/bin/test_compat.py`.
- Implements §6 `compat.py`. Unit tests patch `compat.IS_WINDOWS` and `subprocess.run`/`os.killpg` to check both branches on any OS; `locked` is tested for real on the runner's OS (two threads append to a file under the lock).
- ACs: AC-002 (shared with WP-03).
- Patterns to mirror: `.claude/bin/upgrade.py:1-40` (module docstring, small pure functions), `.claude/bin/test_upgrade.py:1-40`.
- Gotchas: `msvcrt` and `fcntl` must be imported inside the functions (each exists on one OS only); `msvcrt.locking` locks from the current position, so `seek(0)` first and restore; `LK_LOCK` raises `OSError` after ~10 tries: loop; `taskkill` exists only on Windows — never call it elsewhere; `shutil.which` on Windows already applies `PATHEXT`.
- Validation: `python3 -m unittest discover -s .claude/bin -p test_compat.py`.

#### WP-02 · The launcher
- Wave 1. Files: `.claude/bin/agentic`, `.gitattributes`, `.claude/bin/test_launcher.py`.
- Implements the launcher (§6) in POSIX `sh` (no bashisms: it must run in Git Bash's `sh` and in `dash`), and `.gitattributes` with `.claude/bin/agentic text eol=lf`.
- ACs: AC-001.
- Patterns to mirror: `.claude/bin/test_upgrade.py:1-40` (test module).
- Gotchas: `py -3` is two words: iterate over candidates as a string split by the shell on purpose; `exec` keeps stdin for the hook; locate `agentic.py` from `$0`'s directory (`dirname "$0"`), not from the current directory; tests build fakes with `testutil.fake_exe` (WP-05, by signature) and set `PATH` to the fakes' dir plus the dir of `sh` only.
- Validation: `python3 -m unittest discover -s .claude/bin -p test_launcher.py`.

#### WP-03 · `agentic.py` and `upgrade.py` on every OS
- Wave 2, `depends_on: ["WP-01"]`. Files: `.claude/bin/agentic.py`, `.claude/bin/upgrade.py`, `.claude/bin/test_agentic.py`, `.claude/bin/test_upgrade.py`.
- Implements every `agentic.py` and `upgrade.py` item of §6. Consumes `compat.py` by implementation, the launcher and `testutil.fake_exe` by signature.
- ACs: AC-002 to AC-010.
- Patterns to mirror: `.claude/bin/agentic.py:906-926` (`merge_settings`), `.claude/bin/agentic.py:1443-1458` (`locked_json`), `.claude/bin/test_agentic.py:700-740` (install tests).
- Gotchas: `sibling("compat")` must run before any use (module level, after `sibling` is defined, or import it the same way `sibling` does at the top); keep `digest()` on raw bytes (ownership compares a file with itself on one machine); the record now holds normalised hashes — old records of LF files are unchanged, and history covers the rest; `test_agentic.py:160` uses `/tmp/outside.py`, which is not absolute on Windows.
- Validation: `python3 -m unittest discover -s .claude/bin -p test_agentic.py` and `-p test_upgrade.py`.

#### WP-04 · Every reference goes through the launcher
- Wave 1. Files: `.claude/settings.json`, `.claude/workflows/agentic-implement.js`, `.claude/agents/*.md`, `.claude/commands/*.md`, `plugin/commands/init.md`, `.claude/bin/test_workflow.mjs`, `.claude/bin/test_definitions.py`.
- Implements the references of §5 and §6. In `test_definitions.py`: the drift regex also matches `sh .claude/bin/agentic <cmd>`; the plugin contract test expects `sh "${CLAUDE_PLUGIN_ROOT}/.claude/bin/agentic" install`; the gatekeeper test expects `sh .claude/bin/agentic`.
- ACs: AC-011.
- Patterns to mirror: `.claude/agents/gatekeeper.md:1-20`, `.claude/bin/test_definitions.py:295-310`.
- Gotchas: `test_workflow.mjs:43` splits prompts on `agentic.py `; the JS spec copies are untouched (no interpreter in prompts); keep `architect.md`'s manifest example commands (`python3 -m pytest`) — those are the project's commands, not the flow's.
- Validation: `node .claude/bin/test_workflow.mjs` and `python3 -m unittest discover -s .claude/bin -p test_definitions.py`.

#### WP-05 · Portable tests and the CI matrix
- Wave 1. Files: `.claude/bin/testutil.py`, `.claude/bin/test_pipeline.py`, `.claude/bin/test_acceptance.py`, `.claude/bin/test_acceptance_upgrade.py`, `.github/workflows/agentic-flow-ci.yml`.
- Implements `testutil.fake_exe` and moves every fake `claude` in its files to it; the CI matrix of §6.
- ACs: AC-012.
- Patterns to mirror: `.claude/bin/test_pipeline.py:188-237` (fake `claude`), `.github/workflows/agentic-flow-ci.yml:20-44`.
- Gotchas: on Windows a script named `claude` without extension is not executable — that is what `.cmd` solves; keep the actions pinned by SHA; `shell: bash` is Git Bash on Windows runners.
- Validation: `python3 -m unittest discover -s .claude/bin -p "test_pipeline.py"`.

#### WP-06 · Docs, version 1.2.0 and the history
- Wave 3, `depends_on: ["WP-03", "WP-04"]` (the drift test reads the new commands).
- Files: `README.md`, `docs/how-it-works.md`, `docs/how-to/*.md`, `.claude-plugin/plugin.json`, `.claude/flow-history.json`.
- Every flow command in the docs becomes `sh .claude/bin/agentic …`; `docs/how-to/README.md` requirements add Git for Windows on Windows (and what fails without it); `README.md` names Windows, macOS and Linux; version 1.2.0; then `flow-history` per the release rule.
- ACs: AC-013.
- Patterns to mirror: `docs/how-to/README.md:50-60` (requirements list).
- Validation: `python3 -m unittest discover -s .claude/bin -p test_definitions.py`.

```json wp-manifest
{
  "stack": ["python", "typescript"],
  "allow_bash": ["Bash(python3 -m unittest:*)", "Bash(python3 -m compileall:*)", "Bash(node .claude/bin/test_workflow.mjs:*)"],
  "acceptance": {"files": [".claude/bin/test_acceptance_windows.py"], "command": "python3 -m unittest discover -s .claude/bin -p test_acceptance_windows.py"},
  "verify": {"build": "python3 -m compileall -q .claude/bin", "tests": "python3 -m unittest discover -s .claude/bin -p test_*.py"},
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": [".claude/bin/compat.py", ".claude/bin/test_compat.py"],
     "acs": ["AC-002"], "mirror": [".claude/bin/upgrade.py:1-40", ".claude/bin/test_upgrade.py:1-40"]},
    {"id": "WP-02", "wave": 1, "depends_on": [], "files": [".claude/bin/agentic", ".gitattributes", ".claude/bin/test_launcher.py"],
     "acs": ["AC-001"], "mirror": [".claude/bin/test_upgrade.py:1-40"]},
    {"id": "WP-03", "wave": 2, "depends_on": ["WP-01"], "files": [".claude/bin/agentic.py", ".claude/bin/upgrade.py", ".claude/bin/test_agentic.py", ".claude/bin/test_upgrade.py"],
     "acs": ["AC-002", "AC-003", "AC-004", "AC-005", "AC-006", "AC-007", "AC-008", "AC-009", "AC-010"],
     "mirror": [".claude/bin/agentic.py:906-926", ".claude/bin/agentic.py:1443-1458", ".claude/bin/test_agentic.py:700-740"]},
    {"id": "WP-04", "wave": 1, "depends_on": [], "files": [".claude/settings.json", ".claude/workflows/agentic-implement.js", ".claude/agents/", ".claude/commands/", "plugin/commands/init.md", ".claude/bin/test_workflow.mjs", ".claude/bin/test_definitions.py"],
     "acs": ["AC-011"], "mirror": [".claude/agents/gatekeeper.md:1-20", ".claude/bin/test_definitions.py:295-310"]},
    {"id": "WP-05", "wave": 1, "depends_on": [], "files": [".claude/bin/testutil.py", ".claude/bin/test_pipeline.py", ".claude/bin/test_acceptance.py", ".claude/bin/test_acceptance_upgrade.py", ".github/workflows/agentic-flow-ci.yml"],
     "acs": ["AC-012"], "mirror": [".claude/bin/test_pipeline.py:188-237", ".github/workflows/agentic-flow-ci.yml:20-44"]},
    {"id": "WP-06", "wave": 3, "depends_on": ["WP-03", "WP-04"], "files": ["README.md", "docs/how-it-works.md", "docs/how-to/", ".claude-plugin/plugin.json", ".claude/flow-history.json"],
     "acs": ["AC-013"], "mirror": ["docs/how-to/README.md:50-60"]}
  ]
}
```

## 9. Test strategy
- Unit: `test_compat.py` (both branches by patching `IS_WINDOWS`), `test_launcher.py`, and the existing suites, made portable with `testutil.fake_exe`.
- Acceptance: `.claude/bin/test_acceptance_windows.py` from AC-001…AC-013, red before the code. It runs on every OS of the CI matrix; locally only on Linux.
- CI: the pull request's run must be green on `ubuntu-latest` (3.9, 3.12, 3.14), `windows-latest` and `macos-latest` (3.12). Every commit uses `git -c user.name=t -c user.email=t@t`.
- Regression: the whole existing suite on Linux, and then on the new systems.

## 10. Decisions
- **D1 · Implemented outside `/implement`** (as designs 0001 and the safe upgrade): the files are the flow's own, under `.claude/`; `validate` rejects this manifest on purpose.
- **D2 · Git for Windows required (user's choice).** Claude Code recommends it; with it, hooks and Bash run in Git Bash and the guardrails work unchanged. Without it the Bash tool does not exist and a `Bash`-only hook never fires; the launcher (`sh`) is missing too, so `/implement`'s first command fails and nothing runs. Discarded: rewriting the guardrails for PowerShell.
- **D3 · A `sh` launcher (user's choice)** instead of one interpreter name: `python3` is missing on Windows, `python` is missing on many Linux systems. The launcher tries both and `py -3`, and runs the candidate to skip the Store stub. Discarded: per-machine settings (a shared `settings.json` cannot name one interpreter for a mixed team).
- **D4 · One OS module.** `compat.py` is the only place that knows the OS, so the rest reads the same on every system and both branches are unit-tested anywhere.
- **D5 · PowerShell closed to the flow's agents:** if a Windows machine has both tools, the guardrails only understand Bash commands; an agent using PowerShell would bypass them.
- **D6 · CRLF-normalised content hashes** for upgrades only; Windows checkouts with `core.autocrlf=true` then upgrade like any other. Ownership checks keep raw bytes.
- **D7 · CI only (user's choice)** as proof; no manual Windows run in this change.
- **D8 · Waves:** WP-03 runs `compat.py`'s real code; WP-06's docs cite the new commands that WP-03/WP-04 make real. WP-01, WP-02, WP-04 and WP-05 are independent.
- **D9 · Version 1.2.0** with an upgrade note, because the hook command and permission change in every repo.

## 11. Risks and open questions
- **No real Claude Code run on Windows** (D7): CI proves the code, not the hook as Claude Code invokes it in Git Bash. First real use should be watched; the PR says so.
- **`$CLAUDE_PROJECT_DIR` in a shell-form hook under Git Bash** is the documented form; if a user's setup runs hooks in PowerShell (no Git Bash), the hook fails as a non-blocking error — the flow is unsupported there (D2) and `/implement` cannot start.
- **Windows runners' Git Bash `sh`** is assumed on `PATH` for `shell: bash` steps; if not, the launcher tests call it by `shutil.which("sh")`.
- **Long paths and OneDrive-synced folders** on Windows are not covered.
- **Rollback:** one commit per WP; reverting WP-04 and the settings migration restores `python3` everywhere (the legacy claim form stays accepted). `install` of the previous version would re-add the legacy hook next to the new one; users then delete one by hand.
