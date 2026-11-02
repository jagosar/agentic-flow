"""A measurement bench for the flow: runs the real pipeline on fixture repos and records what it cost and how good it was.

`run` copies each fixture into a temp project, installs the flow, runs `agentic.py run-pipeline`, reads its result file
and counts how many of the fixture's hidden oracle tests the produced code passes. `selftest` proves each fixture's
instruments before any spend (the oracle is red on the bare repo, green on reference/good, red on reference/bad); `run`
does it too. `report` turns the results files into bench/RESULTS.md. `ab` runs two flow versions (directories or git refs)
interleaved, fixture by fixture, and compares them: per-fixture ratios, a geometric mean, a seeded bootstrap interval
and an exact sign test. Every agent session runs without the user's
settings, CLAUDE.md files or auto memory, so two people measure the same flow. Callers: a person at the command line and the manual bench workflow; the bench's tests use the
simulated `claude` of .claude/bin/testutil.py.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
import statistics
from statistics import median

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / ".claude" / "bin"))
import compat  # noqa: E402

sys.path.insert(0, str(HERE))
import mutate  # noqa: E402

SCHEMA = 1
AUTH_MODES = ("subscription", "inherit")
DEFAULT_REPEAT = 3
DEFAULT_TIMEOUT_MIN = 60
INSTALL_TIMEOUT_S = 300
GIT_TIMEOUT_S = 120
ORACLE_TIMEOUT_S = 600
TAIL_LINES = 20
KILL_GRACE_S = 5
POLL_S = 0.1
WAIT_AFTER_KILL_S = 10
REMOVE_ATTEMPTS = 3  # a process that just ended can hold a handle for a moment on Windows
REMOVE_PAUSE_S = 1
ROUND_DIGITS = 3
UNKNOWN = "?"
# The bench measures the flow, not one person's setup: no user settings, no CLAUDE.md (the user's or a parent
# directory's), no auto memory. The flags go through AGENTIC_CLAUDE, which every flow version reads.
ISOLATION_FLAGS = ["--setting-sources", "project,local"]
ISOLATION_ENV = {"CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1", "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}
REFERENCE_DIRS = ("good", "bad")  # reference/good passes the whole oracle, reference/bad fails part of it
FIXTURE_PARTS = ("fixture.json", "repo", "oracle", "reference/good", "reference/bad")
GIT_IDENTITY = ["-c", "user.name=bench", "-c", "user.email=bench@localhost", "-c", "commit.gpgsign=false"]
USAGE_KEYS = ("input", "cache_read", "output", "turns")
OWN_OUTPUT = (":(exclude)bench/results", ":(exclude)bench/RESULTS.md")  # written by every run: never "dirty"
RESULTS_TITLE = "# Bench results"
RESULTS_INTRO = ("Each row is one fixture in one bench run of one flow version; numbers are medians over the runs "
                 "(Oracle also shows min–max). A `?` means no run had that value.")
TABLE_HEADER = ["Version", "Commit", "Date", "Fixture", "Runs", "OK", "Oracle", "Mutation", "Fix cycles", "Cost $",
                "Output tokens", "Minutes"]
RE_MANIFEST = re.compile(r"```json\s+wp-manifest\s*\n(.*?)\n```", re.S)
DEFAULT_QA_FILES = ["qa/"]
RE_RAN = re.compile(r"^Ran (\d+) tests?\b", re.MULTILINE)
RE_FAILED = re.compile(r"^FAILED \(([^)]*)\)", re.MULTILINE)
RE_OK = re.compile(r"^OK \(([^)]*)\)", re.MULTILINE)
RE_OK_LINE = re.compile(r"^OK\b", re.MULTILINE)
RE_COUNT = re.compile(r"(failures|errors|skipped)=(\d+)")


class BenchError(Exception):
    """Bad input or an unusable fixture/source: raised before any run starts."""


# ---------------------------------------------------------------- processes

def _process_table() -> dict[int, int]:
    """pid -> ppid of every process (POSIX `ps`); empty if ps is not available."""
    try:
        out = subprocess.run(["ps", "-A", "-o", "pid=,ppid="], capture_output=True, text=True, encoding="utf-8",
                             timeout=GIT_TIMEOUT_S).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    table = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2 and all(p.isdigit() for p in parts):
            table[int(parts[0])] = int(parts[1])
    return table


def _descendants(roots: set[int]) -> dict[int, int]:
    """pid -> process group of every descendant of roots (the roots excluded)."""
    table = _process_table()
    found: dict[int, int] = {}
    frontier = set(roots)
    while frontier:
        children = {pid for pid, ppid in table.items() if ppid in frontier and pid not in found and pid not in roots}
        for pid in children:
            try:
                found[pid] = os.getpgid(pid)
            except (ProcessLookupError, PermissionError):
                found[pid] = pid
        frontier = children
    return found


def _signal_groups(snapshot: dict[int, int], sig: int) -> None:
    own = os.getpgrp()
    for pid, pgid in snapshot.items():
        try:
            if pgid != own:
                os.killpg(pgid, sig)
            else:
                os.kill(pid, sig)
        except (ProcessLookupError, PermissionError):
            pass


def _is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def end_run(project: Path, proc: subprocess.Popen) -> None:
    """Ends run-pipeline and every agent it started, which live in their own process groups.
    Never raises."""
    try:
        if compat.IS_WINDOWS:
            compat.kill_tree(proc.pid)
        else:
            _end_posix(proc)
        proc.wait(WAIT_AFTER_KILL_S)
    except (OSError, subprocess.SubprocessError):
        pass


def _end_posix(proc: subprocess.Popen) -> None:
    first = _descendants({proc.pid})
    compat.kill_tree(proc.pid)
    _signal_groups(first, signal.SIGTERM)
    second = _descendants({proc.pid, *first})
    _signal_groups(second, signal.SIGTERM)
    everyone = {**first, **second}
    deadline = time.monotonic() + KILL_GRACE_S
    while time.monotonic() < deadline:
        proc.poll()
        if not any(_is_alive(pid) for pid in everyone):
            return
        time.sleep(POLL_S)
    _signal_groups({pid: pgid for pid, pgid in everyone.items() if _is_alive(pid)}, signal.SIGKILL)


def _make_writable(func, path, _exc) -> None:
    """rmtree error handler: git leaves its objects read-only, which Windows refuses to delete. Make the entry and
    its folder writable, then retry once; a second failure propagates to remove_tree."""
    for target in (os.path.dirname(path), path):
        try:
            os.chmod(target, stat.S_IRWXU)
        except OSError:
            pass
    func(path)


def remove_tree(path: Path) -> None:
    """Deletes a temp project, read-only git objects included. Never raises: a leftover is reported, not fatal."""
    handler = {"onexc": _make_writable} if sys.version_info >= (3, 12) else {"onerror": _make_writable}
    for attempt in range(REMOVE_ATTEMPTS):
        try:
            shutil.rmtree(path, **handler)
            return
        except FileNotFoundError:
            return
        except OSError as e:
            if attempt == REMOVE_ATTEMPTS - 1:
                print(f"bench: could not delete {path}: {e}", file=sys.stderr)
                return
            time.sleep(REMOVE_PAUSE_S)


# ---------------------------------------------------------------- one run

def _child_env(base: dict, project: Path) -> dict:
    """The environment of every child: the project as CLAUDE_PROJECT_DIR, no AGENTIC_WP, and the agents isolated
    from the user's context."""
    # CLAUDECODE: a bench started from a Claude session is not driven by that session's tool calls; inherited, it would
    # put the flow's hooks-check in live mode against a heartbeat that ages with every fixture.
    env = {k: v for k, v in base.items() if k not in ("AGENTIC_WP", "CLAUDECODE")}
    env["CLAUDE_PROJECT_DIR"] = str(project)
    env.update(ISOLATION_ENV)
    env["AGENTIC_CLAUDE"] = shlex.join(shlex.split(base.get("AGENTIC_CLAUDE") or "claude") + ISOLATION_FLAGS)
    return env


def _git(args: list[str], cwd: Path, env: dict) -> None:
    subprocess.run(["git", *GIT_IDENTITY, *args], cwd=cwd, env=env, check=True, capture_output=True,
                   timeout=GIT_TIMEOUT_S)


def _commit_all(project: Path, env: dict, message: str) -> None:
    _git(["add", "-A"], project, env)
    _git(["commit", "-q", "--allow-empty", "-m", message], project, env)


def _prepare(fixture: Path, project: Path, source: Path, auth: str, env: dict) -> None:
    """Copies the fixture's repo into project, commits, installs the flow, sets auth, commits again.
    Raises BenchError if any step fails."""
    try:
        shutil.copytree(fixture / "repo", project, dirs_exist_ok=True)
        _git(["init", "-q"], project, env)
        _commit_all(project, env, "fixture")
        subprocess.run([sys.executable, str(source / ".claude" / "bin" / "agentic.py"), "install", str(project)],
                       cwd=project, env=env, check=True, capture_output=True, timeout=INSTALL_TIMEOUT_S)
        config = project / ".claude" / "agentic.json"
        data = json.loads(config.read_text(encoding="utf-8")) if config.exists() else {}
        data["auth"] = auth
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(json.dumps(data, indent=2), encoding="utf-8")
        _commit_all(project, env, "bench setup")
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        detail = (getattr(e, "stderr", b"") or b"").decode("utf-8", errors="replace")
        raise BenchError(f"setup failed: {e} {detail[-500:]}") from e


def _pipeline(project: Path, env: dict, timeout_s: float) -> str:
    """Runs run-pipeline; returns "done" or "timeout". Prints the output's tail to stderr unless it ended OK."""
    with tempfile.TemporaryFile() as out:
        proc = subprocess.Popen([sys.executable, ".claude/bin/agentic.py", "run-pipeline"], cwd=project, env=env,
                                stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, **compat.group_kwargs())
        try:
            proc.wait(timeout=timeout_s)
            state = "done"
        except subprocess.TimeoutExpired:
            end_run(project, proc)
            state = "timeout"
        if state == "timeout" or proc.returncode != 0:
            out.seek(0)
            tail = out.read().decode("utf-8", errors="replace").splitlines()[-TAIL_LINES:]
            print("\n".join(tail), file=sys.stderr)
    return state


def _read_result(project: Path) -> dict | None:
    path = project / ".claude" / "state" / "runs" / "workflow-result.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _number_or(value, default):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else default


def _usage(result: dict | None) -> tuple[dict, int]:
    """Usage totals and agent count; a malformed result file gives zeros, never an exception."""
    usage = _as_dict(_as_dict(result).get("usage"))
    total = _as_dict(usage.get("total"))
    out = {k: _number_or(total.get(k), 0) for k in USAGE_KEYS}
    out["cost_usd"] = _number_or(total.get("cost_usd"), None)
    by_agent = usage.get("by_agent")
    return out, len(by_agent) if isinstance(by_agent, list) else 0


def _last(pattern: re.Pattern, text: str):
    matches = list(pattern.finditer(text))
    return matches[-1] if matches else None


def oracle_counts(project: Path, oracle: Path) -> tuple[int, int]:
    """(passed, total) of the oracle's unittest run over project; (0, 0) if unittest's summary is missing."""
    env = {**os.environ, "PYTHONPATH": str(project)}
    try:
        proc = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(oracle), "-t", str(oracle)],
                              cwd=project, env=env, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=ORACLE_TIMEOUT_S, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return 0, 0
    # unittest prints its summary last; a test (or the code under test) may print a fake one before it
    ran = _last(RE_RAN, proc.stderr)
    if not ran:
        return 0, 0
    total = int(ran.group(1))
    tail = proc.stderr[ran.end():]
    if not (RE_FAILED.search(tail) or RE_OK_LINE.search(tail)):
        return 0, total  # no verdict after the last count: trust nothing
    summary = RE_FAILED.search(tail) or RE_OK.search(tail)
    bad = sum(int(n) for _, n in RE_COUNT.findall(summary.group(1))) if summary else 0
    return max(total - bad, 0), total


def _run_oracle(fixture: Path, project: Path) -> dict:
    target = project / ".bench_oracle"
    try:
        shutil.copytree(fixture / "oracle", target)
    except OSError:
        return {"passed": 0, "total": 0}
    try:
        passed, total = oracle_counts(project, target)
    finally:
        remove_tree(target)  # the agents' suites must never see it
    return {"passed": passed, "total": total}


# ---------------------------------------------------------------- mutation

def manifest_of(project: Path) -> dict:
    """The json wp-manifest block of project/architecture.md; {} if absent or invalid."""
    try:
        match = RE_MANIFEST.search((project / "architecture.md").read_text(encoding="utf-8"))
        manifest = json.loads(match.group(1)) if match else {}
    except (OSError, ValueError):
        return {}
    return manifest if isinstance(manifest, dict) else {}


def _paths(value) -> list[str]:
    items = value if isinstance(value, list) else []
    return [i.replace("\\", "/").strip("/") for i in items if isinstance(i, str) and i.strip("/")]


def _is_under(rel: str, prefixes: list[str]) -> bool:
    return any(rel == p or rel.startswith(p + "/") for p in prefixes)


def production_files(project: Path, manifest: dict) -> list[str]:
    """Existing .py files under the work packages' paths, minus tests, acceptance and qa files; sorted, relative."""
    acceptance = manifest.get("acceptance") if isinstance(manifest.get("acceptance"), dict) else {}
    qa = manifest.get("qa") if isinstance(manifest.get("qa"), dict) else {}
    skipped = _paths(acceptance.get("files")) + _paths(qa.get("files", DEFAULT_QA_FILES))
    packages = manifest.get("work_packages") if isinstance(manifest.get("work_packages"), list) else []
    found = set()
    root = project.resolve()
    for package in packages:
        for entry in _paths(package.get("files") if isinstance(package, dict) else None):
            path = project / entry
            if not _inside(path, root):  # a manifest entry never reaches outside the project (symlinks included)
                continue
            for file in ([path] if path.is_file() else sorted(path.rglob("*.py")) if path.is_dir() else []):
                if not _inside(file, root):
                    continue
                rel = file.resolve().relative_to(root).as_posix()
                if (file.suffix == ".py" and rel.split("/")[0] != "tests" and not file.name.startswith("test_")
                        and not _is_under(rel, skipped)):
                    found.add(rel)
    return sorted(found)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root)
    except (ValueError, OSError):
        return False
    return True


def project_commands(manifest: dict) -> list[list[str]]:
    """verify.tests and acceptance.command, shlex-split, in that order. Raises mutate.MutationError on a command that
    cannot be split (the manifest is a file the agents can edit): the caller skips the mutation, not the run."""
    commands = []
    for key, field in (("verify", "tests"), ("acceptance", "command")):
        section = manifest.get(key)
        text = section.get(field) if isinstance(section, dict) else None
        if isinstance(text, str) and text.strip():
            try:
                commands.append(shlex.split(text))
            except ValueError as e:
                raise mutate.MutationError(f"{key}.{field} cannot be split: {e}") from e
    return commands


def _mutation(fixture: Path, project: Path, env: dict) -> dict | None:
    """Mutation block of the produced code (agents' suites and the oracle's ceiling); None if there is nothing to
    mutate or the instrument failed: a run is never lost to it."""
    manifest = manifest_of(project)
    oracle = fixture / "oracle"
    try:
        suites = {"agents": project_commands(manifest),
                  "oracle": [[sys.executable, "-m", "unittest", "discover", "-s", str(oracle), "-t", str(oracle)]]}
        return mutate.score(project, production_files(project, manifest), suites,
                            env={**env, "PYTHONPATH": str(project)})
    except mutate.MutationError as e:
        print(f"mutation skipped: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------- instruments

def _oracle_on(fixture: Path, overlay: str | None) -> tuple[int, int]:
    """The oracle's (passed, total) over the fixture's repo, with reference/<overlay> copied on top when given."""
    project = Path(tempfile.mkdtemp(prefix="bench-selftest-"))
    try:
        shutil.copytree(fixture / "repo", project, dirs_exist_ok=True)
        if overlay:
            shutil.copytree(fixture / "reference" / overlay, project, dirs_exist_ok=True)
        counts = _run_oracle(fixture, project)
    finally:
        remove_tree(project)
    return counts["passed"], counts["total"]


def selftest(fixture: Path) -> list[str]:
    """Problems with the fixture's instruments, [] when they are sound: the oracle has tests, passes none on the bare
    repo, all of them on reference/good and not all of them on reference/bad."""
    fixture = Path(fixture)
    problems = []
    for name, overlay, sound in (("bare", None, lambda p, n: p == 0), ("good", "good", lambda p, n: p == n),
                                 ("bad", "bad", lambda p, n: p < n)):
        passed, total = _oracle_on(fixture, overlay)
        if total == 0:
            return [f"{fixture.name}: the oracle ran no tests"]
        if not sound(passed, total):
            problems.append(f"{fixture.name}: {name} repo passes {passed}/{total} oracle tests")
    return problems


def _keep_session(project: Path, keep: Path, fixture: Path, index: int) -> None:
    """Copies the session's workflow-result.json (what the agents really reported) next to the results file."""
    source = project / ".claude" / "state" / "runs" / "workflow-result.json"
    if source.is_file():
        keep.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, keep / f"{fixture.name}-{index}.json")


def _run_once(fixture: Path, index: int, source: Path, auth: str, timeout_s: float, base_env: dict, keep: Path) -> dict:
    project = Path(tempfile.mkdtemp(prefix="bench-run-"))
    started = time.monotonic()
    try:
        env = _child_env(base_env, project)
        try:
            _prepare(fixture, project, source, auth, env)
        except BenchError as e:
            print(str(e), file=sys.stderr)
            return _record(fixture, index, "error", None, time.monotonic() - started, {"passed": 0, "total": 0})
        state = _pipeline(project, env, timeout_s)
        seconds = time.monotonic() - started
        result = _read_result(project)
        _keep_session(project, keep, fixture, index)
        verdict = result.get("result") if result else None
        outcome = "timeout" if state == "timeout" else (verdict if verdict in ("OK", "REVIEW") else "error")
        oracle = _run_oracle(fixture, project)
        mutation = _mutation(fixture, project, env) if outcome in ("OK", "REVIEW") and state != "timeout" else None
        return _record(fixture, index, outcome, result, seconds, oracle, mutation)
    finally:
        remove_tree(project)


def _record(fixture: Path, index: int, outcome: str, result: dict | None, seconds: float, oracle: dict,
            mutation: dict | None = None) -> dict:
    usage, agents = _usage(result)
    data = _as_dict(result)
    stage = data.get("failed_stage")
    return {"fixture": fixture.name, "index": index, "result": outcome,
            "failed_stage": stage if isinstance(stage, str) else None,
            "fix_cycles": _number_or(data.get("fix_cycles"), None),
            "test_audit_rounds": _number_or(_as_dict(data.get("test_audit")).get("rounds"), None),
            "agents": agents, "seconds": round(max(seconds, 0.001), 1), "oracle": oracle, "usage": usage,
            "mutation": mutation, "verification_failures": _count(data.get("verification_failures")),
            **_review_fields(result)}


def _review_fields(result: dict | None) -> dict:
    """Callers the reviewer received and findings it confirmed and refuted; None for anything missing or malformed."""
    review = _as_dict(_as_dict(result).get("review"))
    callers = review.get("callers")
    confirmed, refuted = review.get("confirmed"), review.get("refuted")
    return {"review_callers": callers if isinstance(callers, int) and not isinstance(callers, bool) else None,
            "review_confirmed": len(confirmed) if isinstance(confirmed, list) else None,
            "review_refuted": len(refuted) if isinstance(refuted, list) else None}


def _count(value) -> int:
    return len(value) if isinstance(value, list) else 0


# ---------------------------------------------------------------- results file

def _git_output(args: list[str], source: Path) -> str | None:
    try:
        done = subprocess.run(["git", *args], cwd=source, capture_output=True, text=True, encoding="utf-8",
                              timeout=GIT_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def _is_dirty(source: Path) -> bool:
    """Uncommitted changes in source, apart from the bench's own output (results files and RESULTS.md)."""
    status = _git_output(["status", "--porcelain", "--untracked-files=all", "--", ".", *OWN_OUTPUT], source)
    return bool(status)


def _flow_version(source: Path) -> str:
    try:
        return str(json.loads((source / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"])
    except (OSError, ValueError, KeyError, TypeError):
        return "dev"


def _rounded(values: list) -> float | None:
    return round(median(values), ROUND_DIGITS) if values else None


def _oracle_rate(run: dict) -> float:
    total = run["oracle"]["total"]
    return run["oracle"]["passed"] / total if total else 0.0


def _non_null(values) -> list:
    return [v for v in values if v is not None]


def _mutation_rates(runs: list[dict], key: str) -> list[float]:
    blocks = [r.get("mutation") for r in runs]
    return [b[key] / b["total"] for b in blocks if b and b.get(key) is not None and b.get("total")]


def _summarize(runs: list[dict]) -> dict:
    rates = [_oracle_rate(r) for r in runs]
    rate_min = _rounded([min(rates)]) if rates else None
    rate_max = _rounded([max(rates)]) if rates else None
    minutes = [r["seconds"] / 60 for r in runs]
    return {"runs": len(runs), "ok": sum(1 for r in runs if r["result"] == "OK"),
            "oracle_rate_median": _rounded(rates), "oracle_rate_min": rate_min, "oracle_rate_max": rate_max,
            "mutation_median": _rounded(_mutation_rates(runs, "killed")),
            "mutation_oracle_median": _rounded(_mutation_rates(runs, "oracle_killed")),
            "fix_cycles_median": _rounded(_non_null(r["fix_cycles"] for r in runs)),
            "cost_usd_median": _rounded(_non_null(r["usage"]["cost_usd"] for r in runs)),
            "output_median": _rounded(_non_null(r["usage"]["output"] for r in runs)),
            "minutes_median": _rounded(minutes)}


def _summaries(runs: list[dict]) -> dict:
    names = sorted({r["fixture"] for r in runs})
    return {name: _summarize([r for r in runs if r["fixture"] == name]) for name in names}


def _validate(fixtures: list[Path], source: Path, repeat: int, auth: str, timeout_s: float) -> None:
    _validate_args(fixtures, repeat, auth, timeout_s)
    if not (source / ".claude" / "bin" / "agentic.py").is_file():
        raise BenchError(f"{source} has no .claude/bin/agentic.py")


def _validate_args(fixtures: list[Path], repeat: int, auth: str, timeout_s: float) -> None:
    if repeat < 1:
        raise BenchError("repeat must be at least 1")
    if timeout_s <= 0:
        raise BenchError("timeout must be greater than 0")
    if auth not in AUTH_MODES:
        raise BenchError(f"auth must be one of {', '.join(AUTH_MODES)}")
    if not fixtures:
        raise BenchError("no fixtures to run")
    for fixture in fixtures:
        missing = [p for p in FIXTURE_PARTS if not (fixture / p).exists()]
        if missing:
            raise BenchError(f"fixture {fixture.name} lacks {', '.join(missing)}")


def run(fixtures: list[Path], source: Path, repeat: int, out_dir: Path, auth: str = "subscription",
        timeout_s: float = 3600, env: dict | None = None) -> Path:
    """Runs each fixture `repeat` times and writes one results file in out_dir (rewritten after each run), plus
    every session's workflow-result.json in <out_dir>/<results stem>/<fixture>-<index>.json; returns the results path. A run that fails or times out is recorded, never raised. Raises BenchError, before any
    spend, for bad input or a fixture whose instruments fail selftest."""
    fixtures = [Path(f) for f in fixtures]
    source, out_dir = Path(source), Path(out_dir)
    _validate(fixtures, source, repeat, auth, timeout_s)
    problems = [problem for fixture in fixtures for problem in selftest(fixture)]
    if problems:
        raise BenchError("instruments broken, nothing run: " + "; ".join(problems))
    base_env = dict(env if env is not None else os.environ)
    started = datetime.now().replace(microsecond=0)
    commit = _git_output(["rev-parse", "--short", "HEAD"], source)
    dirty = _is_dirty(source) if commit else False
    version = _flow_version(source)
    commit = commit or "unknown"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{version}-{started.strftime('%Y%m%d-%H%M%S')}-{commit}.json"
    doc = {"schema": SCHEMA, "flow_version": version, "flow_commit": commit, "dirty": dirty,
           "started": started.isoformat(), "repeat": repeat, "auth": auth, "runs": [], "summary": {}}
    for fixture in fixtures:
        for index in range(1, repeat + 1):
            doc["runs"].append(_run_once(fixture, index, source, auth, timeout_s, base_env, path.with_suffix("")))
            doc["summary"] = _summaries(doc["runs"])
            path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------- A/B

AB_SCHEMA = "ab-1"
BOOTSTRAP_ITERATIONS = 2000
CONFIDENCE = 0.95
DEFAULT_SEED = 0
RATIO_METRICS = ("cost_usd", "minutes", "output")
DIFF_METRICS = ("mutation", "oracle", "fix_cycles", "review_callers", "review_confirmed")
COUNTED = ("OK", "REVIEW")  # an error or a timeout is not a measurement: its minutes are a cap or a setup failure
ARMS = ("a", "b")


def geometric_mean(values: list[float]) -> float | None:
    """The geometric mean, or None for [] or any value that is not positive."""
    if not values or any(v is None or v <= 0 for v in values):
        return None
    return statistics.geometric_mean(values)


def sign_test(wins: int, losses: int) -> float:
    """Two-sided exact binomial p (p = 0.5) of wins against losses; ties are left out before calling."""
    n = wins + losses
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(wins, losses) + 1))
    return min(1.0, 2 * tail / 2 ** n)


def _percentile(ordered: list[float], q: float) -> float:
    index = min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))
    return ordered[index]


def bootstrap_interval(per_fixture: dict[str, tuple[list[float], list[float]]], seed: int,
                       iterations: int = BOOTSTRAP_ITERATIONS, confidence: float = CONFIDENCE) -> tuple[float, float] | None:
    """Percentile bootstrap of the geometric mean of the per-fixture ratios median(B) / median(A): each iteration
    resamples each arm of each fixture with replacement. A fixture whose resampled medians are not both positive is
    left out of that iteration; an iteration with no fixture left is skipped. Seeded: the global random is untouched."""
    usable = {f: (a, b) for f, (a, b) in per_fixture.items() if a and b}
    if not usable:
        return None
    rng = random.Random(seed)
    results = []
    for _ in range(iterations):
        ratios = []
        for name in sorted(usable):
            a, b = usable[name]
            ma, mb = median(rng.choices(a, k=len(a))), median(rng.choices(b, k=len(b)))
            if ma > 0 and mb > 0:
                ratios.append(mb / ma)
        mean = geometric_mean(ratios)
        if mean is not None:
            results.append(mean)
    if not results:
        return None
    results.sort()
    tail = (1 - confidence) / 2
    return (_percentile(results, tail), _percentile(results, 1 - tail))


def _metric(run: dict, name: str) -> float | None:
    """One run's value of a metric, or None when it has none or the run is not a measurement (error, timeout)."""
    if run.get("result") not in COUNTED:
        return None
    usage = _as_dict(run.get("usage"))
    if name in ("cost_usd", "output"):
        return _number_or(usage.get(name), None)
    if name == "minutes":
        seconds = _number_or(run.get("seconds"), None)
        return None if seconds is None else seconds / 60
    if name == "mutation":
        block = _as_dict(run.get("mutation"))
        killed, total = _number_or(block.get("killed"), None), _number_or(block.get("total"), None)
        return killed / total if killed is not None and total else None
    if name == "oracle":
        oracle = _as_dict(run.get("oracle"))
        total = _number_or(oracle.get("total"), 0)
        return _number_or(oracle.get("passed"), 0) / total if total else 0.0
    if name in ("review_callers", "review_confirmed"):
        return _number_or(run.get(name), None)
    return _number_or(run.get("fix_cycles"), None)


def _arm_values(runs: list[dict], fixture: str, metric: str) -> tuple[list[float], list[float]]:
    return tuple([v for r in runs if r.get("fixture") == fixture and r.get("arm") == arm
                  for v in [_metric(r, metric)] if v is not None] for arm in ARMS)


def compare(runs: list[dict], seed: int) -> dict:
    """Per fixture: B/A ratios of the medians for cost, minutes and output, B - A differences for mutation, oracle and
    fix cycles (None when an arm has no value, or A's median is 0 for a ratio). Overall, for the ratio metrics: the
    geometric mean of the per-fixture ratios, a bootstrap interval, wins (ratio below 1), losses, ties and a sign test."""
    names = sorted({r.get("fixture") for r in runs if r.get("fixture")})
    fixtures = {}
    for name in names:
        row = {}
        for metric in RATIO_METRICS + DIFF_METRICS:
            a, b = _arm_values(runs, name, metric)
            if not a or not b:
                row[metric] = None
            elif metric in RATIO_METRICS:
                row[metric] = round(median(b) / median(a), ROUND_DIGITS) if median(a) > 0 else None
            else:
                row[metric] = round(median(b) - median(a), ROUND_DIGITS)
        fixtures[name] = row
    overall = {}
    for metric in RATIO_METRICS:
        ratios = [fixtures[n][metric] for n in names if fixtures[n][metric] is not None]
        wins, losses = sum(1 for x in ratios if x < 1), sum(1 for x in ratios if x > 1)
        mean = geometric_mean(ratios)
        interval = bootstrap_interval({n: _arm_values(runs, n, metric) for n in names}, seed)
        overall[metric] = {"geomean": None if mean is None else round(mean, ROUND_DIGITS),
                           "interval": None if interval is None else [round(x, ROUND_DIGITS) for x in interval],
                           "wins": wins, "losses": losses, "ties": len(ratios) - wins - losses,
                           "p": round(sign_test(wins, losses), 4)}
    return {"fixtures": fixtures, "overall": overall}


def resolve_source(spec: str, repo: Path, worktree: Path) -> tuple[Path, bool]:
    """A directory holding .claude/bin/agentic.py is used as is: (path, False). Anything else is a git ref of repo,
    checked out at worktree (a path the caller chose) with `git worktree add --detach`: (worktree, True)."""
    path = Path(spec)
    if (path / ".claude" / "bin" / "agentic.py").is_file():
        return path.resolve(), False
    if _git_output(["rev-parse", "--git-dir"], repo) is None:
        raise BenchError(f"{spec} is not a flow directory, and {repo} is not a git repo to check it out from")
    try:
        done = subprocess.run(["git", "worktree", "add", "--detach", str(worktree), spec], cwd=repo, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=GIT_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError) as e:
        raise BenchError(f"cannot check out {spec}: {e}") from e
    if done.returncode != 0:
        raise BenchError(f"{spec} is neither a flow directory nor a git ref of {repo}: {done.stderr.strip()[-300:]}")
    if not (worktree / ".claude" / "bin" / "agentic.py").is_file():
        _remove_worktree(repo, worktree)
        raise BenchError(f"{spec} has no .claude/bin/agentic.py")
    return worktree, True


def _remove_worktree(repo: Path, worktree: Path) -> None:
    for args in (["worktree", "remove", "--force", str(worktree)], ["worktree", "prune"]):
        subprocess.run(["git", *args], cwd=repo, capture_output=True, timeout=GIT_TIMEOUT_S)


def _describe(spec: str, source: Path) -> dict:
    commit = _git_output(["rev-parse", "--short", "HEAD"], source)
    return {"spec": spec, "version": _flow_version(source), "commit": commit or "unknown",
            "dirty": _is_dirty(source) if commit else False}


def ab_markdown(doc: dict) -> str:
    """The comparison as Markdown: one table per fixture row, one for the overall ratios."""
    a, b = doc["a"], doc["b"]
    lines = [f"# A/B: {a['version']} ({a['spec']}) vs {b['version']} ({b['spec']})", "",
             f"{doc['repeat']} session(s) per arm and fixture, seed {doc['seed']}. Ratios are median(B) / median(A): "
             "below 1, B is cheaper, faster or shorter. Differences are B - A. Only OK and REVIEW sessions count.", "",
             "| Fixture | Cost | Minutes | Output | Mutation | Oracle | Fix cycles | Callers | Confirmed |",
             "|---|---|---|---|---|---|---|---|---|"]
    for name, row in doc["comparison"]["fixtures"].items():
        cells = [_number(row.get(m), 2) for m in RATIO_METRICS + DIFF_METRICS]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines += ["", "| Metric | Geometric mean | Interval | B better / worse / tie | Sign test p |", "|---|---|---|---|---|"]
    for metric, s in doc["comparison"]["overall"].items():
        interval = UNKNOWN if s["interval"] is None else f"{_number(s['interval'][0], 2)}–{_number(s['interval'][1], 2)}"
        lines.append(f"| {metric} | {_number(s['geomean'], 2)} | {interval} | {s['wins']} / {s['losses']} / {s['ties']} "
                     f"| {_number(s['p'], 3)} |")
    return "\n".join(lines) + "\n"


def ab(fixtures: list[Path], spec_a: str, spec_b: str, repeat: int, out_dir: Path, auth: str = "subscription",
       timeout_s: float = 3600, env: dict | None = None, seed: int = DEFAULT_SEED, repo: Path = HERE.parent) -> Path:
    """Two flow versions, interleaved fixture by fixture: A first on odd indexes, B first on even ones. Checks the
    arguments and every fixture's instruments before any worktree or spend. Each arm keeps its sessions in
    <out>/<stem>/<arm>/. Writes the results file after every session and its .md at the end; RESULTS.md is untouched.
    Removes the worktrees it created, also on error. Returns the results path."""
    fixtures, out_dir, repo = [Path(f) for f in fixtures], Path(out_dir), Path(repo)
    _validate_args(fixtures, repeat, auth, timeout_s)
    problems = [problem for fixture in fixtures for problem in selftest(fixture)]
    if problems:
        raise BenchError("instruments broken, nothing run: " + "; ".join(problems))
    base_env = dict(env if env is not None else os.environ)
    workdir = Path(tempfile.mkdtemp(prefix="bench-ab-"))
    created = []
    try:
        sources = {}
        for arm, spec in zip(ARMS, (spec_a, spec_b)):
            path, made = resolve_source(spec, repo, workdir / arm)
            if made:
                created.append(path)
            sources[arm] = path
        started = datetime.now().replace(microsecond=0)
        doc = {"schema": AB_SCHEMA, "a": _describe(spec_a, sources["a"]), "b": _describe(spec_b, sources["b"]),
               "started": started.isoformat(), "repeat": repeat, "auth": auth, "seed": seed, "runs": [], "comparison": {}}
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"ab-{doc['a']['version']}-vs-{doc['b']['version']}-{started.strftime('%Y%m%d-%H%M%S')}.json"
        for fixture in fixtures:
            for index in range(1, repeat + 1):
                for arm in (ARMS if index % 2 else tuple(reversed(ARMS))):
                    run = _run_once(fixture, index, sources[arm], auth, timeout_s, base_env, path.with_suffix("") / arm)
                    doc["runs"].append({"arm": arm, **run})
                    doc["comparison"] = compare(doc["runs"], seed)
                    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
        path.with_suffix(".md").write_text(ab_markdown(doc), encoding="utf-8")
        return path
    finally:
        for worktree in created:
            _remove_worktree(repo, worktree)
        remove_tree(workdir)


# ---------------------------------------------------------------- report

def _number(value, decimals: int | None = None) -> str:
    if value is None:
        return UNKNOWN
    if decimals is not None:
        return f"{value:.{decimals}f}"
    return str(int(value)) if float(value).is_integer() else str(value)


def _rows(doc: dict) -> list[list[str]]:
    commit = f"{doc['flow_commit']}-dirty" if doc.get("dirty") else str(doc["flow_commit"])
    rows = []
    for name in sorted(doc.get("summary", {})):
        s = doc["summary"][name]
        oracle = UNKNOWN if s.get("oracle_rate_median") is None else (
            f"{_number(s['oracle_rate_median'], 2)} ({_number(s.get('oracle_rate_min'), 2)}"
            f"–{_number(s.get('oracle_rate_max'), 2)})")
        minutes = s.get("minutes_median")
        halves = (s.get("mutation_median"), s.get("mutation_oracle_median"))
        mutation = UNKNOWN if halves == (None, None) else " / ".join(
            _number(h, 2) if h is not None else UNKNOWN for h in halves)
        rows.append([str(doc["flow_version"]), commit, str(doc["started"])[:10], name, _number(s.get("runs")),
                     f"{s.get('ok', 0)}/{s.get('runs', 0)}", oracle, mutation,
                     _number(s.get("fix_cycles_median")),
                     _number(s.get("cost_usd_median"), 2), _number(s.get("output_median")),
                     _number(minutes, 1)])
    return rows


def _load_results(results_dir: Path) -> list[dict]:
    docs = []
    for file in sorted(results_dir.glob("*.json")) if results_dir.is_dir() else []:
        try:
            doc = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(doc, dict) and doc.get("schema") == SCHEMA:
            docs.append(doc)
    return sorted(docs, key=lambda d: str(d.get("started")), reverse=True)


def report(results_dir: Path, out: Path) -> None:
    """Writes out (Markdown): a title, one line on how to read it and a row per (results file, fixture)."""
    rows = []
    for doc in _load_results(Path(results_dir)):
        try:
            rows.extend(_rows(doc))
        except (AttributeError, KeyError, TypeError, ValueError):
            continue
    lines = [RESULTS_TITLE, ""]
    if not rows:
        lines.append("No results yet.")
    else:
        lines += [RESULTS_INTRO, "", "| " + " | ".join(TABLE_HEADER) + " |", "|" + "---|" * len(TABLE_HEADER)]
        lines += ["| " + " | ".join(row) + " |" for row in rows]
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- command line

class _Parser(argparse.ArgumentParser):
    def error(self, message: str):
        raise BenchError(message)


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="bench.py", description="Measurement bench for the flow.")
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run", help="run fixtures through the real pipeline")
    run_p.add_argument("--fixture", action="append", default=[])
    run_p.add_argument("--repeat", type=int, default=DEFAULT_REPEAT)
    run_p.add_argument("--auth", default="subscription")
    run_p.add_argument("--timeout-min", type=float, default=DEFAULT_TIMEOUT_MIN)
    run_p.add_argument("--out", type=Path, default=HERE / "results")
    run_p.add_argument("--source", type=Path, default=HERE.parent)
    report_p = sub.add_parser("report", help="regenerate RESULTS.md")
    report_p.add_argument("--out", type=Path, default=HERE / "results")
    ab_p = sub.add_parser("ab", help="run two flow versions interleaved and compare them")
    ab_p.add_argument("--a", required=True, help="a flow directory or a git ref of --repo")
    ab_p.add_argument("--b", required=True, help="a flow directory or a git ref of --repo")
    ab_p.add_argument("--repo", type=Path, default=HERE.parent)
    ab_p.add_argument("--fixture", action="append", default=[])
    ab_p.add_argument("--repeat", type=int, default=DEFAULT_REPEAT)
    ab_p.add_argument("--auth", default="subscription")
    ab_p.add_argument("--timeout-min", type=float, default=DEFAULT_TIMEOUT_MIN)
    ab_p.add_argument("--out", type=Path, default=HERE / "results")
    ab_p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    self_p = sub.add_parser("selftest", help="check every fixture's oracle and references, no claude involved")
    self_p.add_argument("--fixture", action="append", default=[])
    self_p.add_argument("--source", type=Path, default=HERE.parent)
    return parser


def _resolve_fixture(name: str) -> Path:
    for candidate in (HERE / "fixtures" / name, Path(name)):
        if candidate.is_dir():
            return candidate
    raise BenchError(f"fixture not found: {name}")


def _print_runs(path: Path) -> None:
    doc = json.loads(path.read_text(encoding="utf-8"))
    for r in doc["runs"]:
        o = r["oracle"]
        m = r.get("mutation")
        extra = f" mutation {_number(m['killed'])}/{m['total']}" if m else ""
        arm = f"{r['arm']} " if r.get("arm") else ""
        print(f"{arm}{r['fixture']} #{r['index']} {r['result']} oracle {o['passed']}/{o['total']} "
              f"{r['seconds'] / 60:.1f} min{extra}")
    print(path)


def _fixtures(names: list[str]) -> list[Path]:
    if names:
        return [_resolve_fixture(n) for n in names]
    root = HERE / "fixtures"
    return sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []


def _selftest_all(fixtures: list[Path]) -> int:
    """One line per fixture; 1 if any instrument is broken."""
    if not fixtures:
        raise BenchError("no fixtures to check")
    broken = 0
    for fixture in fixtures:
        missing = [p for p in FIXTURE_PARTS if not (fixture / p).exists()]
        problems = [f"{fixture.name} lacks {', '.join(missing)}"] if missing else selftest(fixture)
        print(f"{fixture.name}: {'ok' if not problems else 'BROKEN: ' + '; '.join(problems)}")
        broken += bool(problems)
    return 1 if broken else 0


def main(argv: list[str]) -> int:
    """`run`, `ab`, `report` and `selftest` subcommands; BenchError or a bad argument: one message on stderr, returns 1.
    `selftest` returns 1 when an instrument is broken."""
    try:
        args = _build_parser().parse_args(argv)
        if args.command == "report":
            report(args.out, args.out.parent / "RESULTS.md")
            return 0
        fixtures = _fixtures(args.fixture)
        if args.command == "selftest":
            return _selftest_all(fixtures)
        if args.command == "ab":
            path = ab(fixtures, args.a, args.b, args.repeat, args.out, args.auth, args.timeout_min * 60,
                      seed=args.seed, repo=args.repo)
            _print_runs(path)
            print(path.with_suffix(".md").read_text(encoding="utf-8"))
            return 0
        path = run(fixtures, args.source, args.repeat, args.out, args.auth, args.timeout_min * 60)
        _print_runs(path)
        report(args.out, args.out.parent / "RESULTS.md")
    except BenchError as e:
        print(f"bench: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    compat.utf8_stdio()
    sys.exit(main(sys.argv[1:]))
