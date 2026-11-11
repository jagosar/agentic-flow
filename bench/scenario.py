"""Saved scenarios for one agent: its inputs, real `claude -p` runs of that agent on them, and whether each report met
what the scenario expects. A prompt or agent change is tested like code: the old definition against the new one.

A scenario folder holds one or more scenario files (scenario.json, or any other top-level .json) and the files the agent
reads. A scenario file names the agent, the prompt (a key of pipeline-spec.json's prompts, or a literal prompt_text),
the values that fill it, the schema when it is not the agent's (schema_name) and the expectation. run() copies the
folder (without its scenario files) and this checkout's .claude/agents and .claude/workflows into a temporary project,
optionally with another definition of the agent (--agent-file), and runs the agent read-only with the bench's isolation,
so a person's settings do not leak in. Each run spends a real agent session; the tests of this module use a fake
`claude`.

    python3 bench/scenario.py TARGET [--agent-file PATH] [--repeat N] [--against PATH] [--save]

TARGET is a scenario folder (its scenario.json) or one scenario file. One run prints {"report", "expect", "met",
"text"}; --repeat N prints how many of N runs met; --against PATH runs the old definition at PATH and the current one
(or --agent-file) alternately, N times each (3 by default), with a one-sided Fisher exact probability. --save also
writes the printed JSON under bench/results/scenarios/. Exit 0 when every run of the new (or only) arm met, 3
otherwise, 1 on a usage error.
"""
from __future__ import annotations

import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKOUT = HERE.parent
sys.path.insert(0, str(CHECKOUT / ".claude" / "bin"))
import compat  # noqa: E402
from findings import blocks  # noqa: E402
from repo_scan import render_rules  # noqa: E402

sys.path.insert(0, str(HERE))
from bench import ISOLATION_ENV, ISOLATION_FLAGS  # noqa: E402

SPEC = CHECKOUT / ".claude" / "workflows" / "pipeline-spec.json"
RULES_LIBRARY = ".claude/rules-library"
RESULTS = HERE / "results" / "scenarios"
READ_ONLY_TOOLS = ["Read", "Glob", "Grep", "StructuredOutput"]
MODEL = "sonnet"
TIMEOUT_S = 900
DEFAULT_RUNS = 3
P_DIGITS = 3
SCENARIO_FILE = "scenario.json"
STAMP = "%Y%m%d-%H%M%S"
NAME_RE = re.compile(r"^name:.*$", re.M)
USAGE = "Uso: scenario.py TARGET [--agent-file PATH] [--repeat N] [--against PATH] [--save]"


def render(template, values):
    """The prompt with each {key} replaced; other braces (JSON in the template) stay as they are."""
    for key, value in values.items():
        template = template.replace("{" + key + "}", value)
    return template


def locate(target):
    """(scenario folder, scenario file) for a folder or one of its .json files."""
    target = Path(target)
    return (target.parent, target) if target.suffix == ".json" else (target, target / SCENARIO_FILE)


def blocking_findings(report, blocking):
    findings = report.get("findings") if isinstance(report, dict) else None
    return [f for f in findings or [] if isinstance(f, dict) and blocks(f, blocking)]


def mentions_found(report, expect, blocking):
    """The first blocking finding whose problem, evidence and rule hold every mention (casefolded), or None."""
    mentions = [m.casefold() for m in expect.get("finding_mentions") or []]
    for f in blocking_findings(report, blocking):
        text = " ".join(str(f.get(k, "")) for k in ("problem", "evidence", "rule")).casefold()
        if all(m in text for m in mentions):
            return f
    return None


def verdicts_all(report, verdict):
    """The report has at least one verdict and every one of them is `verdict` (a re-review)."""
    verdicts = report.get("verdicts")
    return isinstance(verdicts, list) and bool(verdicts) and all(
        isinstance(v, dict) and v.get("verdict") == verdict for v in verdicts)


def report_holds(report, expect, blocking):
    if "status" in expect and report.get("status") != expect["status"]:
        return False
    if "all_verdicts" in expect and not verdicts_all(report, expect["all_verdicts"]):
        return False
    if expect.get("no_blocking") and blocking_findings(report, blocking):
        return False
    if any(report.get(k) != v for k, v in (expect.get("equals") or {}).items()):
        return False
    if any(not isinstance(report.get(k), (int, float)) or report[k] < v for k, v in (expect.get("min") or {}).items()):
        return False
    if "finding_mentions" in expect or "tier" in expect:
        found = mentions_found(report, expect, blocking)
        return found is not None and ("tier" not in expect or found.get("tier") == expect["tier"])
    return True


def met(report, expect, text=None, blocking=("critical", "high")):
    """Every part of the expectation holds: of the structured report, or of the text answer for text_mentions."""
    mentions = [m.casefold() for m in expect.get("text_mentions") or []]
    if mentions and not (isinstance(text, str) and all(m in text.casefold() for m in mentions)):
        return False
    rest = {k: v for k, v in expect.items() if k != "text_mentions"}
    if not rest:
        return bool(mentions)
    return isinstance(report, dict) and report_holds(report, rest, blocking)


def parse_answer(stdout, schema):
    """(structured report or None, text answer or None) of a `--output-format json` run."""
    try:
        data = json.loads(stdout)
    except ValueError:
        return None, None
    if not isinstance(data, dict):
        return None, None
    text = data.get("result") if isinstance(data.get("result"), str) else None
    report = data.get("structured_output")
    if isinstance(report, str):
        try:
            report = json.loads(report)
        except ValueError:
            report = None
    if schema is None or not isinstance(report, dict) or any(k not in report for k in schema.get("required", [])):
        report = None
    return report, text


def prepare(scenario_dir, work, agent, agent_file):
    """The agent's world: the scenario's files (no scenario file) and the flow's agents and workflows."""
    shutil.copytree(scenario_dir, work, ignore=lambda d, names: [
        n for n in names if n == "__pycache__" or (Path(d) == Path(scenario_dir) and n.endswith(".json"))])
    for part in ("agents", "workflows"):
        shutil.copytree(CHECKOUT / ".claude" / part, work / ".claude" / part)
    if agent_file:
        text = Path(agent_file).read_text(encoding="utf-8")
        (work / ".claude" / "agents" / f"{agent}.md").write_text(NAME_RE.sub(f"name: {agent}", text, count=1),
                                                                 encoding="utf-8")


def prompt_of(meta, spec):
    values = dict(meta.get("values") or {})
    if "rules" in meta:
        names = [f"{RULES_LIBRARY}/{n}.md" for n in meta["rules"]]
        values["rules"] = render_rules(names, CHECKOUT)
    template = meta["prompt_text"] if "prompt_text" in meta else spec["prompts"][meta["prompt"]]
    return render(template, values) + meta.get("suffix", "")


def schema_of(meta, spec):
    """The schema the report must follow: schema_name's (a re-review), else the agent's; None in text mode."""
    return spec["schemas"][meta.get("schema_name", meta["agent"])] if meta.get("schema", True) else None


def command(meta, spec, claude):
    base = claude or compat.resolve(shlex.split(os.environ.get("AGENTIC_CLAUDE", "claude")))
    cmd = [*base, *ISOLATION_FLAGS, "-p", "--agent", meta["agent"], "--model", meta.get("model", MODEL),
           "--output-format", "json"]
    schema = schema_of(meta, spec)
    if schema is not None:
        cmd += ["--json-schema", json.dumps(schema, separators=(",", ":"))]
    return cmd + ["--strict-mcp-config", "--allowedTools", *READ_ONLY_TOOLS]


def run(target, claude=None, agent_file=None):
    """One run of the scenario's agent; never raises on a bad answer (report None, met False)."""
    scenario_dir, scenario_file = locate(target)
    meta = json.loads(scenario_file.read_text(encoding="utf-8"))
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    schema = schema_of(meta, spec)
    tmp = Path(tempfile.mkdtemp(prefix="scenario-"))
    try:
        work = tmp / "project"
        prepare(scenario_dir, work, meta["agent"], agent_file)
        env = dict(os.environ, **ISOLATION_ENV, CLAUDE_PROJECT_DIR=str(work))
        try:
            proc = subprocess.run(command(meta, spec, claude), cwd=work, input=prompt_of(meta, spec),
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
                                  timeout=TIMEOUT_S)
            report, text = parse_answer(proc.stdout, schema)
        except (OSError, subprocess.TimeoutExpired):
            report, text = None, None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    expect = meta["expect"]
    return {"report": report, "expect": expect, "met": met(report, expect, text, spec["constants"]["blocking"]),
            "text": text}


def repeat(target, runs, claude=None, agent_file=None):
    results = [run(target, claude=claude, agent_file=agent_file) for _ in range(runs)]
    return {"met": sum(1 for r in results if r["met"]), "total": runs, "runs": results}


def fisher_p(old_met, old_total, new_met, new_total):
    """One-sided Fisher exact test: how likely the new arm meets at least this often if both arms were alike."""
    successes, total = old_met + new_met, old_total + new_total
    denominator = math.comb(total, new_total)
    p = sum(math.comb(successes, k) * math.comb(total - successes, new_total - k)
            for k in range(new_met, min(successes, new_total) + 1)) / denominator
    return round(p, P_DIGITS)


def compare(target, runs, against, claude=None, agent_file=None):
    """The old definition (`against`) and the current one (or agent_file), alternating old, new, `runs` times each."""
    old, new = [], []
    for _ in range(runs):
        old.append(run(target, claude=claude, agent_file=against))
        new.append(run(target, claude=claude, agent_file=agent_file))
    arms = {name: {"met": sum(1 for r in rs if r["met"]), "total": runs, "runs": rs}
            for name, rs in (("old", old), ("new", new))}
    return {**arms, "p": fisher_p(arms["old"]["met"], runs, arms["new"]["met"], runs)}


def scenario_name(target):
    scenario_dir, scenario_file = locate(target)
    return scenario_dir.name if scenario_file.name == SCENARIO_FILE else f"{scenario_dir.name}-{scenario_file.stem}"


def parse_args(argv):
    """{"target", "agent_file", "repeat", "against", "save"}, or None on a usage error."""
    args, opts = list(argv), {"agent_file": None, "repeat": None, "against": None, "save": False}
    if "--save" in args:
        args.remove("--save")
        opts["save"] = True
    for flag, key in (("--agent-file", "agent_file"), ("--repeat", "repeat"), ("--against", "against")):
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args):
                return None
            opts[key] = args[i + 1]
            del args[i:i + 2]
    if len(args) != 1 or not locate(args[0])[1].is_file():
        return None
    if opts["repeat"] is not None and not (opts["repeat"].isdigit() and int(opts["repeat"]) > 0):
        return None
    if any(opts[k] is not None and not Path(opts[k]).is_file() for k in ("agent_file", "against")):
        return None
    return {**opts, "target": args[0]}


def main(argv, now=None, results=None, claude=None):
    opts = parse_args(argv)
    if opts is None:
        print(USAGE, file=sys.stderr)
        return 1
    runs = int(opts["repeat"]) if opts["repeat"] else None
    if opts["against"]:
        out = compare(opts["target"], runs or DEFAULT_RUNS, opts["against"], claude, opts["agent_file"])
        ok = out["new"]["met"] == out["new"]["total"]
    elif runs:
        out = repeat(opts["target"], runs, claude, opts["agent_file"])
        ok = out["met"] == out["total"]
    else:
        out = run(opts["target"], claude=claude, agent_file=opts["agent_file"])
        ok = out["met"]
    printed = json.dumps(out, ensure_ascii=False)
    print(printed)
    if opts["save"]:
        folder = Path(results) if results else RESULTS
        folder.mkdir(parents=True, exist_ok=True)
        stamp = (now or datetime.now()).strftime(STAMP)
        (folder / f"{scenario_name(opts['target'])}-{stamp}.json").write_text(printed + "\n", encoding="utf-8")
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
