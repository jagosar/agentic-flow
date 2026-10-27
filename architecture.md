# Architecture: the flow on Windows and macOS — delivery A (portable internals, no visible change)
Type: refactor · Size: standard

## 1. Goal
The flow only runs on Linux and macOS today: `agentic.py` imports `fcntl` (absent on Windows), kills processes with `os.killpg`, runs `npm`/`claude` without resolving `.cmd` files, reads and writes text with the platform's default encoding, and nothing tests it outside Ubuntu. Native Windows support is delivered in **two steps**, each one undoable on its own. This document is **delivery A**: the internals become portable and CI proves them on Linux, macOS and Windows, **without changing anything a user sees** — same `python3` commands, same hook, same `settings.json`. Delivery B (the `sh` launcher and the migration of the hook, end of §11) is planned only after A has been green for a while.

## 2. Scope
### Included (delivery A)
- `compat.py`: the operating-system layer (file locks, process groups and killing, executable resolution, UTF-8 standard streams and stdin, line-ending-independent content hashes), and `testutil.py` for portable fake executables in tests.
- `agentic.py` and `upgrade.py` use it: no `fcntl` import, UTF-8 explicit in every text read, write and subprocess, prompts to agents on stdin, claims reset under the lock, an unreadable ledger blocks an upgrade, CRLF-tolerant upgrade comparisons.
- Portable tests and a CI matrix with `windows-latest` and `macos-latest`.
- Version 1.1.1 (no upgrade notes: nothing changes for users).
### Excluded (delivery B, see the end of §11)
- The `sh .claude/bin/agentic` launcher and replacing `python3` in the hook, permissions, workflow, agents, commands, plugin and docs.
- Migrating users' `settings.json` (hook command, permission, `PowerShell` in the matcher) and `.gitattributes`.
- Closing the `PowerShell` tool to the flow's agents (it needs the matcher change).
### Excluded (both deliveries)
- Windows without Git for Windows; WSL (it is Linux already); a manual Claude Code run on Windows (CI only, user's choice).

## 3. Stack
Python 3.9+ standard library only (`msvcrt` on Windows, `fcntl` elsewhere). Node ≥ 18 for the workflow tests. GitHub Actions.
- Build: `python3 -m compileall -q .claude/bin`
- Tests: `python3 -m unittest discover -s .claude/bin -p "test_*.py"` (includes the workflow scenarios through `WorkflowLogicTests`)
- Acceptance: `python3 -m unittest discover -s .claude/bin -p test_acceptance_portable.py`

## 4. Repository structure
```
.claude/bin/compat.py                       WP-01 (new)
.claude/bin/testutil.py                     WP-01 (new)
.claude/bin/test_compat.py                  WP-01 (new)
.claude/bin/agentic.py                      WP-02
.claude/bin/upgrade.py                      WP-02
.claude/bin/test_agentic.py                 WP-02
.claude/bin/test_upgrade.py                 WP-02
.claude/bin/test_pipeline.py                WP-03
.claude/bin/test_acceptance.py              WP-03
.claude/bin/test_acceptance_upgrade.py      WP-03
.claude/bin/test_definitions.py             WP-03 (touch only if it fails on Windows or macOS)
.claude/bin/test_brief.py                   WP-03 (same)
.claude/bin/test_workflow.mjs               WP-03 (same)
.github/workflows/agentic-flow-ci.yml       WP-03
README.md                                   WP-03
docs/how-to/README.md                       WP-03
docs/how-to/desktop.md                      WP-03
.claude-plugin/plugin.json                  WP-03
.claude/bin/test_acceptance_portable.py     AT (new)
```
Waves: WP-01 (1) → WP-02 (2) → WP-03 (3), then the release step (§9). See D5.
Untouched on purpose: `.claude/settings.json`, `.claude/workflows/`, `.claude/agents/`, `.claude/commands/`, `plugin/`, and every `python3 .claude/bin/agentic.py` a user or agent runs.

## 4b. Existing code context
| What an implementer needs to know | Where it is | Pattern or rule |
|---|---|---|
| POSIX-only import | `agentic.py:56` (`import fcntl`) | Makes the module fail to import on Windows: remove it |
| What `install` copies | `agentic.py:117-118` (`INSTALL_GLOBS`), `upgrade.py:14-16` (`EXTRA_GLOBS`) | A new module the flow imports must be listed, or installed projects break (`test_agentic.py:809` `test_installed_flow_works`) |
| File lock of the ledger and claims | `agentic.py:1443-1458` (`locked_json`, `fcntl.flock` at 1447) | Becomes `with compat.locked(fh):` |
| Claims reset | `agentic.py:539` (`CLAIMS.unlink(missing_ok=True)` in `snapshot`) | On Windows a file another process holds open cannot be deleted: empty it under the lock |
| Process group and kill | `agentic.py:612` (`start_new_session=True` in `run_agent`), `1547-1551` (`kill_group`, `os.killpg`), `1554` (`stop`) | `compat.group_kwargs()` and `compat.kill_tree(pid)` |
| Commands run without a shell | `agentic.py:1043` (`run_command`, `shlex.split`), `1091` (`run_steps`), `599-612` (`run_agent`: `["claude", "-p", prompt, …]`) | Resolve argv with `compat.resolve`; the prompt moves to stdin |
| Text encodings | e.g. `agentic.py:538, 548, 589, 610, 630, 1155, 1196, 1203, 1313, 1378, 1446, 1505` (no `encoding=`), `1705` and `1781` (`json.load(sys.stdin)`); text subprocesses in `run_command`, `run_steps`, `install` (`rules-sync`, `validate`), `git_tree`, `tracked_files`, `write_fix_diffs`, `upgrade.git` (`upgrade.py:40-44`) | `encoding="utf-8"` everywhere (`errors="replace"` for subprocess output); stdin decoded as UTF-8; `main()` calls `compat.utf8_stdio()` first |
| The claim pattern | `agentic.py:151` (`CLAIM_RE`) | Also accept `agentic\s+claim` (prepares B; harmless now) |
| Content hashes | `agentic.py:894` (`sha256`), used by `install`; `upgrade.py:100-125` (`build_history`, hash at 120) | `compat.content_hash` (CRLF → LF) for upgrade comparisons and the record; `digest()` keeps raw bytes |
| Run-in-progress guard | `upgrade.py:80-97` (`guard_problems`; `except (OSError, ValueError)` at 90 turns an unreadable ledger into "no run") | `OSError` must become a blocking problem; `ValueError` (corrupt JSON) keeps today's behaviour |
| Fake `claude` in tests | `test_agentic.py:32-48, 909-917`, `test_pipeline.py:188-237`, `test_acceptance.py:55-100` (shebang + `chmod`, prompt read from argv) | `AGENTIC_CLAUDE` + a fake that reads the prompt from stdin |
| Test commands that call `python3` | manifests in `test_agentic.py` (`python3 acc.py`, `python3 ok.py`), `test_acceptance*.py` | `shlex.join([Path(sys.executable).as_posix(), …])`: on Windows `python3` may be missing or the Store stub |
| POSIX paths in tests | `test_agentic.py:160` (`"/tmp/outside.py"`) | `tempfile.gettempdir()` |
| Requirements in the docs | `docs/how-to/README.md:64-65` ("macOS, Linux or WSL 2… uses `fcntl`"), `README.md:51` ("macOS, Linux or WSL 2"), `docs/how-to/desktop.md:13` ("use WSL: `agentic.py` needs POSIX") | Rewrite all three (WP-03) |
| Version pinned by a test | `test_acceptance_upgrade.py:258` (asserts `"1.1.0"`) | Bump it with `plugin.json` (WP-03) |
| Rules on annotations | `.claude/rules-library/python.md:13` (annotations on public signatures) vs `agentic.py` (none) | New modules (`compat.py`, `testutil.py`) annotate public signatures as §6; edits inside `agentic.py`/`upgrade.py` keep their style |
| CI | `.github/workflows/agentic-flow-ci.yml:20-44` (job `test`, Ubuntu, Python 3.9/3.12/3.14) | Add an OS axis |
| Module style | `.claude/bin/upgrade.py:1-40`, `.claude/bin/test_upgrade.py:1-40` | Docstring with purpose and callers; small functions; stdlib only |

## 5. Data model
- **Content hash:** `sha256(bytes.replace(b"\r\n", b"\n"))`, hex. Used for upgrade comparisons and the install record only.
- **`AGENTIC_CLAUDE`** (environment, optional): the command that runs Claude Code, split with `shlex.split` in POSIX mode (paths with forward slashes or quoted); default `claude`.
- No change to `settings.json`, the manifest, the ledger or any file a user commits.

## 6. Contracts between modules
**`compat.py`** (WP-01) — `IS_WINDOWS = os.name == "nt"`; every function branches on it at call time, so tests can patch it. `fcntl` and `msvcrt` are imported inside the functions.
```python
@contextlib.contextmanager
def locked(fh):
    """Exclusive lock of an open file for the block. POSIX: fcntl.flock(LOCK_EX). Windows: seek(0), then
    msvcrt.locking(fileno, LK_LOCK, 1) retried until acquired (LK_LOCK gives up after ~10 s with OSError).
    On exit: fh.flush() BEFORE unlocking; on Windows seek(0) then LK_UNLCK."""

def group_kwargs() -> dict
    """{"start_new_session": True} on POSIX; {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} on Windows."""

def kill_tree(pid: int) -> None
    """Ends the process and its children; never raises. POSIX: os.killpg(pid, SIGTERM).
    Windows: `taskkill /T /F /PID <pid>`, output discarded."""

def resolve(argv: list[str]) -> list[str]
    """A copy of argv with argv[0] replaced by shutil.which(argv[0]) when found (npm -> npm.cmd; PATHEXT order);
    unchanged otherwise, so the caller's FileNotFoundError handling still applies. Empty argv returned as is."""

def utf8_stdio() -> None
    """sys.stdout and sys.stderr reconfigured to UTF-8 (errors="replace") when they support reconfigure()."""

def read_stdin_text() -> str
    """sys.stdin.buffer.read().decode("utf-8")."""

def content_hash(path) -> str
    """sha256 hex of the file's bytes with CRLF turned into LF."""
```
**`testutil.py`** (WP-01)
```python
def fake_exe(directory, name, python_source) -> Path
    """An executable `name` findable on PATH that runs python_source with sys.executable. POSIX: a script whose
    shebang names sys.executable by absolute path, mode 0o755. Windows (compat.IS_WINDOWS): name.py plus
    name.cmd = '@"<sys.executable>" "%~dp0<name>.py" %*'. For project commands in tests, not for `claude`."""

def claude_command(fake_py) -> str
    """The AGENTIC_CLAUDE value that runs fake_py with this interpreter:
    shlex.join([Path(sys.executable).as_posix(), Path(fake_py).as_posix()])."""
```
**`agentic.py`** (WP-02)
- `compat` is imported at module level with the same mechanism as `sibling()` (its directory on `sys.path`); `agentic.py` never imports `fcntl`.
- `import signal` goes (its only use, `agentic.py:1549`, moves to `compat`). `locked_json` uses `compat.locked`; `snapshot` empties the claims with `locked_json(CLAIMS, lambda c: {})`; `kill_group` is replaced by `compat.kill_tree` (callers updated); `run_agent` uses `compat.group_kwargs()`.
- `run_command`, `run_steps` and `run_agent` pass argv through `compat.resolve`.
- `run_agent`: the command is `shlex.split(os.environ.get("AGENTIC_CLAUDE", "claude")) + ["-p", "--agent", …]` (no prompt argument), started with `stdin=subprocess.PIPE` and fed with `proc.communicate(input=prompt.encode("utf-8"), timeout=cfg["timeout_s"])` (stdout and stderr still go to the run's files); the schema argument is `json.dumps(schema, separators=(",", ":"))`. On timeout: `compat.kill_tree`, then `proc.wait()`, as today.
- `main()` first calls `compat.utf8_stdio()`; `hook` and `save-result` read stdin with `compat.read_stdin_text()`.
- Every text `open`/`read_text`/`write_text` in `agentic.py`, `upgrade.py`, `pipeline.py`, `brief.py`, `compat.py` passes `encoding="utf-8"` (binary modes excepted); every `subprocess.run`/`Popen` with `text=True` passes `encoding="utf-8", errors="replace"`.
- `CLAIM_RE = re.compile(r"agentic(?:\.py)?\s+claim\s+(WP-\d+|QA|AT|REVIEW|DOCS)\b")`.
- `install` uses `compat.content_hash` for every comparison and for the record.
- `INSTALL_GLOBS` gains `.claude/bin/compat.py` (without it every installed `agentic.py` fails to import).

**`upgrade.py`** (WP-02): `EXTRA_GLOBS` gains `.claude/bin/testutil.py` (the refreshed flow tests import it); `git()` adds `encoding="utf-8", errors="replace"` **only when text mode is on** (`build_history` calls it with `text=False` and bytes input: encoding there would turn text mode back on and break it); `build_history` hashes blob bytes with CRLF turned into LF (same rule as `content_hash`); `guard_problems` adds `the run state cannot be read: stop any run and try again` when `ledger.json` exists but reading it raises `OSError` (a blocking problem; `install` then exits 3 and writes nothing, as for any other guard problem).

**CI** (WP-03): job `test` keeps `os: ubuntu-latest` × `python: ["3.9", "3.12", "3.14"]` and adds `include: [{os: windows-latest, python: "3.12"}, {os: macos-latest, python: "3.12"}]`; `runs-on: ${{ matrix.os }}`; `defaults.run.shell: bash`; `timeout-minutes` stays 15 except Windows, 30 (`timeout-minutes: ${{ matrix.os == 'windows-latest' && 30 || 15 }}`); Windows keeps the runner's default `core.autocrlf`.

## 7. Conventions
- Stdlib only. `compat.py` is the only module that branches on the OS (`testutil` uses `compat.IS_WINDOWS`).
- English; inside `agentic.py` and `upgrade.py`, their style (no annotations; `except Exception` only where a function promises not to raise).
- **No user-visible change:** the paths §4 lists as untouched must not change, and every command and message that names `python3 .claude/bin/agentic.py` stays as it is.
- Test commits use `git -c user.name=t -c user.email=t@t`; test files declare UTF-8 in their own reads and writes, and every `text=True` subprocess in tests passes `encoding="utf-8"` (otherwise Windows decodes the child's UTF-8 output as cp1252). That includes `Repo.run` (`test_agentic.py:62-64`, WP-02), which `test_acceptance.py` reuses.
- Tests compare paths only after `resolve()` (Windows runners use 8.3 short names such as `RUNNER~1`; macOS has `/var` → `/private/var`).

## 8. Work packages and acceptance criteria
### Acceptance criteria
They run on every OS of the CI matrix; locally, on Linux.
- AC-001 · `agentic.py` imports and locks without `fcntl`
  - Scenario: a temp JSON file and a fresh Python subprocess, with `CLAUDE_PROJECT_DIR` set to a temp dir in the subprocess's environment only, that sets `sys.modules["fcntl"] = None`, imports `agentic` from `.claude/bin` and calls `agentic.locked_json(<temp file>, lambda d: {"a": 1})`.
  - Action: run the subprocess (nothing is imported in the test process).
  - Expected: the subprocess exits 0; the file holds `{"a": 1}`; no line of `.claude/bin/agentic.py` matches `^\s*import fcntl`.
  - Must not: import `fcntl` or `msvcrt` outside `compat.py`.
  - Check: `test_acceptance_portable.py::test_ac_001_no_fcntl`.
  - WP: WP-01, WP-02
- AC-002 · Commands are found through PATHEXT
  - Scenario: a git project whose manifest has `verify: {"tests": "faketool --ok"}`, with `faketool` made by `testutil.fake_exe` (a `.cmd` on Windows) in a directory prepended to PATH, exiting 0.
  - Action: `agentic.py verify`, run with `sys.executable`.
  - Expected: the `tests` phase has `"passed": true`.
  - Must not: report `command not found`.
  - Check: `test_acceptance_portable.py::test_ac_002_resolve`.
  - WP: WP-02
- AC-003 · Non-ASCII text survives any console encoding
  - Scenario: a project whose `architecture.md` contains `· € ñ` and a ledger with the note `nota · ñ`.
  - Action: `agentic.py validate` and `agentic.py status` with `PYTHONIOENCODING=ascii`.
  - Expected: both exit 0 and `status` prints `nota`.
  - Must not: raise `UnicodeEncodeError` or `UnicodeDecodeError`.
  - Check: `test_acceptance_portable.py::test_ac_003_utf8`.
  - WP: WP-02
- AC-004 · Every text read, write and subprocess declares UTF-8
  - Scenario: `agentic.py`, `upgrade.py`, `pipeline.py`, `brief.py`, `compat.py`.
  - Action: parse them with `ast`; inspect every call to `open`, `.open`, `read_text`, `write_text`, and every `subprocess.run`/`subprocess.Popen` call with `text=True`.
  - Expected: each has an `encoding` keyword, or a literal mode containing `b`.
  - Must not: allow a call without either.
  - Check: `test_acceptance_portable.py::test_ac_004_encodings_declared`.
  - WP: WP-02
- AC-005 · Native paths in the hook
  - Scenario: a project where WP-01 owns `src/a.py` and WP-02 owns `src/b.py`.
  - Action: the hook with `{"tool_name": "Write", "tool_input": {"file_path": str(<project> / "src" / "a.py")}}` (backslashes on Windows), with `AGENTIC_WP=WP-01`, then with `AGENTIC_WP=WP-02`.
  - Expected: exit 0 for WP-01, exit 2 for WP-02.
  - Must not: block the owner because of the separator.
  - Check: `test_acceptance_portable.py::test_ac_005_native_paths`.
  - WP: WP-02
- AC-006 · Both claim forms are recorded
  - Scenario: the AC-005 project with a run snapshot taken.
  - Action: hook Bash payloads `python3 .claude/bin/agentic.py claim WP-01` (agent `a1`) and `sh .claude/bin/agentic claim WP-02` (agent `a2`).
  - Expected: `.claude/state/claims.json` maps `a1` → `WP-01` and `a2` → `WP-02`.
  - Must not: ignore either form.
  - Check: `test_acceptance_portable.py::test_ac_006_claims`.
  - WP: WP-02
- AC-007 · CRLF copies of intact files are recognised
  - Scenario: an upgrade source whose `flow-history.json` lists the hash of `OLD\n` for `.claude/agents/qa.md`; the target holds `OLD\r\n` there (written with `write_bytes`: `write_text` would add another `\r` on Windows), committed.
  - Action: `install <target>`.
  - Expected: the file is listed under `updated:`.
  - Must not: list it under `modified by you (left alone)`.
  - Check: `test_acceptance_portable.py::test_ac_007_crlf_intact`.
  - WP: WP-02
- AC-008 · Prompts reach agents on stdin
  - Scenario: a project with `AGENTIC_CLAUDE` = `testutil.claude_command(<fake>)`, where the fake logs its argv and its stdin and prints a valid structured report.
  - Action: `agentic.py run-wave 1`.
  - Expected: each logged stdin starts with `Implement WP-0`; no argv element contains a newline; argv contains `--json-schema`.
  - Must not: pass the prompt as an argument.
  - Check: `test_acceptance_portable.py::test_ac_008_prompt_on_stdin`.
  - WP: WP-02
- AC-009 · An unreadable ledger blocks an upgrade
  - Scenario: an install target with a committed flow and a directory named `.claude/state/ledger.json` (reading it raises `OSError` on every OS).
  - Action: `install <target>`.
  - Expected: exit 3; the output contains `the run state cannot be read`.
  - Must not: write any file in the target.
  - Check: `test_acceptance_portable.py::test_ac_009_unreadable_ledger`.
  - WP: WP-02
- AC-010 · Nothing changes for users
  - Scenario: the repo after delivery A.
  - Action: read `.claude/settings.json`, `.claude/workflows/agentic-implement.js`, `.claude/agents/implementer.md`.
  - Expected: the hook command is `python3 "$CLAUDE_PROJECT_DIR/.claude/bin/agentic.py" hook` with matcher `Write|Edit|MultiEdit|NotebookEdit|Bash`; the permission `Bash(python3 .claude/bin/agentic.py:*)` is present; the workflow contains `python3 .claude/bin/agentic.py`; the implementer contains `python3 .claude/bin/agentic.py claim <WP-ID>`.
  - Must not: contain `sh .claude/bin/agentic` in any of them.
  - Check: `test_acceptance_portable.py::test_ac_010_no_visible_change`.
  - WP: WP-02
- AC-011 · CI covers Windows and macOS
  - Scenario: `.github/workflows/agentic-flow-ci.yml`.
  - Action: read it.
  - Expected: the `test` job runs on `${{ matrix.os }}`, the matrix includes `windows-latest` and `macos-latest` and keeps the three Ubuntu Python versions; run steps use `bash`.
  - Must not: drop a system or a Python version.
  - Check: `test_acceptance_portable.py::test_ac_011_ci_matrix` (reads the YAML as text with regexes: stdlib only); and the pull request's real CI run is green on the three systems.
  - WP: WP-03
- AC-012 · An installed flow can import its OS layer
  - Scenario: an empty git repo with one commit.
  - Action: `install <target>`, then `<target>/.claude/bin/agentic.py validate` run with `sys.executable` from the target.
  - Expected: `<target>/.claude/bin/compat.py` exists; `validate` does not print `ModuleNotFoundError`.
  - Must not: install an `agentic.py` that imports a module `install` does not copy.
  - Check: `test_acceptance_portable.py::test_ac_012_compat_installed`.
  - WP: WP-02

### Work packages
#### WP-01 · `compat.py` and `testutil.py`
- Wave 1. Files: `.claude/bin/compat.py`, `.claude/bin/testutil.py`, `.claude/bin/test_compat.py`.
- Implements §6 `compat.py` and `testutil.py`. Unit tests patch `compat.IS_WINDOWS`, `subprocess.run` and `os.killpg` to check both branches on any OS; `locked` is tested for real on the runner's OS (two threads append to a JSON file under the lock, and no write is lost).
- ACs: AC-001 (shared with WP-02).
- Patterns to mirror: `.claude/bin/upgrade.py:1-40`, `.claude/bin/test_upgrade.py:1-40`.
- Gotchas: `msvcrt.locking` locks from the current position (seek first); `LK_LOCK` raises after ~10 tries (loop); flush before unlocking; never call `taskkill` outside Windows; `shutil.which` on Windows already applies `PATHEXT`; `subprocess.CREATE_NEW_PROCESS_GROUP` exists only on Windows (read it inside the branch). In tests, patch `os.killpg` and `subprocess.CREATE_NEW_PROCESS_GROUP` with `create=True` (each is missing on one OS); to run the Windows branch of `locked` on POSIX, `patch.dict(sys.modules, {"msvcrt": Mock()})`; the real two-thread lock test opens one file handle per thread (`flock` does not block threads sharing a handle).
- Validation: `python3 -m unittest discover -s .claude/bin -p test_compat.py`.

#### WP-02 · `agentic.py` and `upgrade.py` on every OS
- Wave 2, `depends_on: ["WP-01"]` (consumes `compat` by implementation). Files: `.claude/bin/agentic.py`, `.claude/bin/upgrade.py`, `.claude/bin/test_agentic.py`, `.claude/bin/test_upgrade.py`.
- Implements every `agentic.py` and `upgrade.py` item of §6, moves the fakes of its own test files to `AGENTIC_CLAUDE` (prompt on stdin) and its test manifests to `sys.executable`.
- ACs: AC-001 to AC-010, AC-012.
- Patterns to mirror: `.claude/bin/agentic.py:1443-1458` (`locked_json`), `.claude/bin/agentic.py:599-640` (`run_agent`), `.claude/bin/test_agentic.py:700-740` (install tests).
- Gotchas: keep `digest()` on raw bytes; the record now holds normalised hashes (records of LF files do not change, and the history covers older ones); `test_agentic.py:160` uses `/tmp/outside.py`; after this WP the fakes in `test_pipeline.py` and `test_acceptance.py` (prompt read from argv) fail until WP-03 lands, so only this WP's own files are its validation; do not touch the paths §4 lists as untouched.
- Validation: `python3 -m unittest discover -s .claude/bin -p test_agentic.py` and `-p test_upgrade.py`.

#### WP-03 · Portable tests, CI and the patch version
- Wave 3, `depends_on: ["WP-02"]` (its tests need `AGENTIC_CLAUDE`). Files: `.claude/bin/test_pipeline.py`, `.claude/bin/test_acceptance.py`, `.claude/bin/test_acceptance_upgrade.py`, `.claude/bin/test_definitions.py`, `.claude/bin/test_brief.py`, `.claude/bin/test_workflow.mjs` (these three only if they fail on Windows or macOS), `.github/workflows/agentic-flow-ci.yml`, `README.md`, `docs/how-to/README.md`, `docs/how-to/desktop.md`, `.claude-plugin/plugin.json`.
- Moves the fakes in its files to `AGENTIC_CLAUDE`, test manifests to `sys.executable`, UTF-8 in its reads and writes; the CI matrix of §6; rewrites `docs/how-to/README.md:64-65`: tested on Linux, macOS and Windows (Git for Windows); on Windows, until the next release, the `python3` command must run Python 3.9+; the same in `README.md:51` and `docs/how-to/desktop.md:13`; version `1.1.1` in `plugin.json` and in the assertion at `test_acceptance_upgrade.py:258`.
- ACs: AC-011.
- Patterns to mirror: `.claude/bin/test_pipeline.py:188-237`, `.github/workflows/agentic-flow-ci.yml:20-44`.
- Gotchas: keep the actions pinned by SHA; `shell: bash` is Git Bash on Windows runners; do not add upgrade notes.
- Validation: the whole suite, `python3 -m unittest discover -s .claude/bin -p "test_*.py"` (it includes every `test_acceptance*.py`).

```json wp-manifest
{
  "stack": ["python"],
  "allow_bash": ["Bash(python3 -m unittest:*)", "Bash(python3 -m compileall:*)"],
  "acceptance": {"files": [".claude/bin/test_acceptance_portable.py"], "command": "python3 -m unittest discover -s .claude/bin -p test_acceptance_portable.py"},
  "verify": {"build": "python3 -m compileall -q .claude/bin", "tests": "python3 -m unittest discover -s .claude/bin -p test_*.py"},
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": [".claude/bin/compat.py", ".claude/bin/testutil.py", ".claude/bin/test_compat.py"],
     "acs": ["AC-001"], "mirror": [".claude/bin/upgrade.py:1-40", ".claude/bin/test_upgrade.py:1-40"]},
    {"id": "WP-02", "wave": 2, "depends_on": ["WP-01"], "files": [".claude/bin/agentic.py", ".claude/bin/upgrade.py", ".claude/bin/test_agentic.py", ".claude/bin/test_upgrade.py"],
     "acs": ["AC-001", "AC-002", "AC-003", "AC-004", "AC-005", "AC-006", "AC-007", "AC-008", "AC-009", "AC-010", "AC-012"],
     "mirror": [".claude/bin/agentic.py:1443-1458", ".claude/bin/agentic.py:599-640", ".claude/bin/test_agentic.py:700-740"]},
    {"id": "WP-03", "wave": 3, "depends_on": ["WP-02"], "files": [".claude/bin/test_pipeline.py", ".claude/bin/test_acceptance.py", ".claude/bin/test_acceptance_upgrade.py", ".claude/bin/test_definitions.py", ".claude/bin/test_brief.py", ".claude/bin/test_workflow.mjs", ".github/workflows/agentic-flow-ci.yml", "README.md", "docs/how-to/README.md", "docs/how-to/desktop.md", ".claude-plugin/plugin.json"],
     "acs": ["AC-011"], "mirror": [".claude/bin/test_pipeline.py:188-237", ".github/workflows/agentic-flow-ci.yml:20-44"]}
  ]
}
```

## 9. Test strategy
- Unit: `test_compat.py` (both branches by patching `IS_WINDOWS`) and the existing suites, made portable.
- Acceptance: `.claude/bin/test_acceptance_portable.py`, from AC-001…AC-012, written first and red before the code.
- CI: the pull request's run must be green on `ubuntu-latest` (3.9, 3.12, 3.14), `windows-latest` and `macos-latest` (3.12).
- Branch protection (a GitHub setting the owner enables by hand): require the checks of the three systems before merging, so no later feature lands unless it works on all of them.
- Release step after the WPs: commit, `python3 .claude/bin/agentic.py flow-history`, commit `.claude/flow-history.json`.

## 10. Decisions
- **D1 · One codebase, not a fork (user's question).** The flow lives inside each project, and one project can be used from Linux, macOS and Windows at once, so it needs one flow that runs on all three. A fork would duplicate every feature and drift apart; CI on the three systems plus branch protection keeps them equal automatically.
- **D2 · Two deliveries (user's choice).** A changes internals only and is undone with a revert; B, the only part that touches users' `settings.json`, is planned once A has been green for a while.
- **D3 · Implemented outside `/implement`**, as in earlier designs: the files are the flow's own, under `.claude/`, so `validate` rejects this manifest on purpose.
- **D4 · One OS module.** `compat.py` is the only place that knows the OS; both branches are unit-tested on any OS.
- **D5 · Waves 1 → 2 → 3:** WP-02 runs `compat.py`'s real code; WP-03's tests need `AGENTIC_CLAUDE`, which WP-02 adds.
- **D6 · Prompts on stdin** (`claude -p` reads it): on Windows a `claude.cmd` passes arguments through `cmd.exe`, which cuts newlines and limits the line to 8191 characters.
- **D7 · CRLF-normalised hashes** for upgrades only; ownership checks keep raw bytes.
- **D8 · CI only (user's choice)** as proof of portability.
- **D9 · Version 1.1.1**, a patch: nothing a user sees changes, so no upgrade notes.

## 11. Risks and open questions
- **Rollback of delivery A:** `git revert` of its merge commit here. In a project that upgraded to 1.1.1, `git revert` of that project's upgrade commit (or install 1.1.0 again): A does not touch `settings.json` or any command a user runs, so both versions read the same files.
- **What A does not give yet:** on Windows the flow still calls `python3`, so it works only where that command runs Python 3.9+ (the python.org installer does not create it). Delivery B removes that requirement.
- **No real Claude Code run on Windows** (D8): CI proves the code, not Claude Code's own hook invocation.
- **`claude.cmd` (npm installs on Windows):** the JSON schema still crosses `cmd.exe` as one quoted argument; it has no newline or `%`, but it does contain `^` (the implementer's `"pattern": "^WP-[0-9]+$"`), cmd's escape character, inside `list2cmdline`'s `\"` quoting, which is untested; `claude.exe` from the native installer avoids it.
- **Long paths and OneDrive-synced folders** on Windows are not covered.

### Delivery B (next, to plan with `/architect` once A is green)
Already decided with the user: Windows requires Git for Windows (without Git Bash the flow refuses to start); a POSIX `sh` launcher `.claude/bin/agentic` that tries `python3`, `python`, `py -3` by running them (which skips the Microsoft Store stub) and exits 2 if none works; every reference becomes `sh .claude/bin/agentic <command>`; `install` migrates the hook and permission in place and adds `.claude/bin/agentic text eol=lf` to `.gitattributes`; the matcher adds `PowerShell` and the hook blocks that tool for the flow's agents; version 1.2.0 with an upgrade note. To keep B's rollback safe, its hook command will still contain `agentic.py` and end in `hook`, so an older installer run by mistake does not add a second hook.
