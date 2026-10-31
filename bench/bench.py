"""A measurement bench for the flow: runs the real pipeline on fixture repos and records what it cost and how good it was.

`run` copies each fixture into a temp project, installs the flow, runs `agentic.py run-pipeline`, reads its result file
and counts how many of the fixture's hidden oracle tests the produced code passes. `report` turns the results files into
bench/RESULTS.md. Callers: a person at the command line and the manual bench workflow; the bench's tests use the
simulated `claude` of .claude/bin/testutil.py.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / ".claude" / "bin"))
import compat  # noqa: E402

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
GIT_IDENTITY = ["-c", "user.name=bench", "-c", "user.email=bench@localhost", "-c", "commit.gpgsign=false"]
USAGE_KEYS = ("input", "cache_read", "output", "turns")
OWN_OUTPUT = (":(exclude)bench/results", ":(exclude)bench/RESULTS.md")  # written by every run: never "dirty"
RESULTS_TITLE = "# Bench results"
RESULTS_INTRO = ("Each row is one fixture in one bench run of one flow version; numbers are medians over the runs "
                 "(Oracle also shows min–max). A `?` means no run had that value.")
TABLE_HEADER = ["Version", "Commit", "Date", "Fixture", "Runs", "OK", "Oracle", "Fix cycles", "Cost $",
                "Output tokens", "Minutes"]
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
    env = {k: v for k, v in base.items() if k != "AGENTIC_WP"}
    env["CLAUDE_PROJECT_DIR"] = str(project)
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
    passed, total = oracle_counts(project, target)
    return {"passed": passed, "total": total}


def _run_once(fixture: Path, index: int, source: Path, auth: str, timeout_s: float, base_env: dict) -> dict:
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
        verdict = result.get("result") if result else None
        outcome = "timeout" if state == "timeout" else (verdict if verdict in ("OK", "REVIEW") else "error")
        return _record(fixture, index, outcome, result, seconds, _run_oracle(fixture, project))
    finally:
        remove_tree(project)


def _record(fixture: Path, index: int, outcome: str, result: dict | None, seconds: float, oracle: dict) -> dict:
    usage, agents = _usage(result)
    data = _as_dict(result)
    stage = data.get("failed_stage")
    return {"fixture": fixture.name, "index": index, "result": outcome,
            "failed_stage": stage if isinstance(stage, str) else None,
            "fix_cycles": _number_or(data.get("fix_cycles"), None),
            "test_audit_rounds": _number_or(_as_dict(data.get("test_audit")).get("rounds"), None),
            "agents": agents, "seconds": round(max(seconds, 0.001), 1), "oracle": oracle, "usage": usage}


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


def _summarize(runs: list[dict]) -> dict:
    rates = [_oracle_rate(r) for r in runs]
    rate_min = _rounded([min(rates)]) if rates else None
    rate_max = _rounded([max(rates)]) if rates else None
    minutes = [r["seconds"] / 60 for r in runs]
    return {"runs": len(runs), "ok": sum(1 for r in runs if r["result"] == "OK"),
            "oracle_rate_median": _rounded(rates), "oracle_rate_min": rate_min, "oracle_rate_max": rate_max,
            "fix_cycles_median": _rounded(_non_null(r["fix_cycles"] for r in runs)),
            "cost_usd_median": _rounded(_non_null(r["usage"]["cost_usd"] for r in runs)),
            "output_median": _rounded(_non_null(r["usage"]["output"] for r in runs)),
            "minutes_median": _rounded(minutes)}


def _summaries(runs: list[dict]) -> dict:
    names = sorted({r["fixture"] for r in runs})
    return {name: _summarize([r for r in runs if r["fixture"] == name]) for name in names}


def _validate(fixtures: list[Path], source: Path, repeat: int, auth: str, timeout_s: float) -> None:
    if repeat < 1:
        raise BenchError("repeat must be at least 1")
    if timeout_s <= 0:
        raise BenchError("timeout must be greater than 0")
    if auth not in AUTH_MODES:
        raise BenchError(f"auth must be one of {', '.join(AUTH_MODES)}")
    if not fixtures:
        raise BenchError("no fixtures to run")
    if not (source / ".claude" / "bin" / "agentic.py").is_file():
        raise BenchError(f"{source} has no .claude/bin/agentic.py")
    for fixture in fixtures:
        missing = [p for p in ("fixture.json", "repo", "oracle") if not (fixture / p).exists()]
        if missing:
            raise BenchError(f"fixture {fixture.name} lacks {', '.join(missing)}")


def run(fixtures: list[Path], source: Path, repeat: int, out_dir: Path, auth: str = "subscription",
        timeout_s: float = 3600, env: dict | None = None) -> Path:
    """Runs each fixture `repeat` times and writes one results file in out_dir (rewritten after each run);
    returns its path. A run that fails or times out is recorded, never raised."""
    fixtures = [Path(f) for f in fixtures]
    source, out_dir = Path(source), Path(out_dir)
    _validate(fixtures, source, repeat, auth, timeout_s)
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
            doc["runs"].append(_run_once(fixture, index, source, auth, timeout_s, base_env))
            doc["summary"] = _summaries(doc["runs"])
            path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


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
        rows.append([str(doc["flow_version"]), commit, str(doc["started"])[:10], name, _number(s.get("runs")),
                     f"{s.get('ok', 0)}/{s.get('runs', 0)}", oracle, _number(s.get("fix_cycles_median")),
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
        print(f"{r['fixture']} #{r['index']} {r['result']} oracle {o['passed']}/{o['total']} "
              f"{r['seconds'] / 60:.1f} min")
    print(path)


def main(argv: list[str]) -> int:
    """`run` and `report` subcommands; BenchError or a bad argument: one message on stderr, returns 1."""
    try:
        args = _build_parser().parse_args(argv)
        if args.command == "report":
            report(args.out, args.out.parent / "RESULTS.md")
            return 0
        if args.fixture:
            fixtures = [_resolve_fixture(n) for n in args.fixture]
        else:
            root = HERE / "fixtures"
            fixtures = sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
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
