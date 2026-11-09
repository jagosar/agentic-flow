"""A saved scenario for one agent: its inputs, a real `claude -p` run of that agent on them, and whether the report met
what the scenario expects.

A scenario folder holds scenario.json (the agent, the prompt key of pipeline-spec.json, the values that fill it and the
expectation) and the files the agent reads. run() copies those files and this checkout's .claude/agents and
.claude/workflows into a temporary folder, optionally with another definition of the agent (--agent-file, e.g. an older
release's), and runs the agent read-only with the bench's isolation, so a person's own settings do not leak in.
Each run spends a real agent session; the tests of this module use a fake `claude`.

    python3 bench/scenario.py DIR [--agent-file PATH]

prints {"report", "expect", "met"} as one JSON line; exit 0 if met, 3 if not, 1 on a usage error.
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKOUT = HERE.parent
sys.path.insert(0, str(CHECKOUT / ".claude" / "bin"))
import compat  # noqa: E402

sys.path.insert(0, str(HERE))
from bench import ISOLATION_ENV, ISOLATION_FLAGS  # noqa: E402

SPEC = CHECKOUT / ".claude" / "workflows" / "pipeline-spec.json"
READ_ONLY_TOOLS = ["Read", "Glob", "Grep", "StructuredOutput"]
MODEL = "sonnet"
TIMEOUT_S = 900
BLOCKING = ("critical", "high")
SCENARIO_FILE = "scenario.json"
USAGE = "Uso: scenario.py DIR [--agent-file PATH]"


def render(template, values):
    """The prompt with each {key} replaced; other braces (JSON in the template) stay as they are."""
    for key, value in values.items():
        template = template.replace("{" + key + "}", value)
    return template


def met(report, expect):
    """The status is the expected one and some blocking finding mentions every expected string."""
    if not isinstance(report, dict) or report.get("status") != expect.get("status"):
        return False
    mentions = expect.get("finding_mentions") or []
    if not mentions:
        return True
    blocking = [f for f in report.get("findings") or [] if isinstance(f, dict) and f.get("severity") in BLOCKING]
    return any(all(m in f"{f.get('problem', '')} {f.get('evidence', '')}" for m in mentions) for f in blocking)


def parse_report(stdout, schema):
    """The structured answer of a `--output-format json` run, or None (the shape the flow's launcher accepts)."""
    try:
        data = json.loads(stdout)
    except ValueError:
        return None
    report = data.get("structured_output") if isinstance(data, dict) else None
    if isinstance(report, str):
        try:
            report = json.loads(report)
        except ValueError:
            return None
    if not isinstance(report, dict) or any(k not in report for k in schema.get("required", [])):
        return None
    return report


def prepare(scenario_dir, work, agent, agent_file):
    """The agent's world: the scenario's files (not scenario.json) and the flow's agents and workflows."""
    shutil.copytree(scenario_dir, work, ignore=shutil.ignore_patterns(SCENARIO_FILE, "__pycache__"))
    for part in ("agents", "workflows"):
        shutil.copytree(CHECKOUT / ".claude" / part, work / ".claude" / part)
    if agent_file:
        shutil.copy(agent_file, work / ".claude" / "agents" / f"{agent}.md")


def run(scenario_dir, claude=None, agent_file=None):
    """One run of the scenario's agent; never raises on a bad report (report None, met False)."""
    scenario_dir = Path(scenario_dir)
    meta = json.loads((scenario_dir / SCENARIO_FILE).read_text(encoding="utf-8"))
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    agent, expect = meta["agent"], meta["expect"]
    schema = spec["schemas"][agent]
    prompt = render(spec["prompts"][meta["prompt"]], meta.get("values") or {})
    base = claude or compat.resolve(shlex.split(os.environ.get("AGENTIC_CLAUDE", "claude")))
    cmd = [*base, *ISOLATION_FLAGS, "-p", "--agent", agent, "--model", MODEL, "--output-format", "json",
           "--json-schema", json.dumps(schema, separators=(",", ":")), "--strict-mcp-config",
           "--allowedTools", *READ_ONLY_TOOLS]
    tmp = Path(tempfile.mkdtemp(prefix="scenario-"))
    try:
        work = tmp / "project"
        prepare(scenario_dir, work, agent, agent_file)
        env = dict(os.environ, **ISOLATION_ENV, CLAUDE_PROJECT_DIR=str(work))
        try:
            proc = subprocess.run(cmd, cwd=work, input=prompt, capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", env=env, timeout=TIMEOUT_S)
            report = parse_report(proc.stdout, schema)
        except (OSError, subprocess.TimeoutExpired):
            report = None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"report": report, "expect": expect, "met": met(report, expect)}


def main(argv):
    args, agent_file = list(argv), None
    if "--agent-file" in args:
        i = args.index("--agent-file")
        if i + 1 >= len(args):
            print(USAGE, file=sys.stderr)
            return 1
        agent_file = args[i + 1]
        del args[i:i + 2]
    bad_agent = agent_file is not None and not Path(agent_file).is_file()
    if len(args) != 1 or not (Path(args[0]) / SCENARIO_FILE).is_file() or bad_agent:
        print(USAGE, file=sys.stderr)
        return 1
    result = run(args[0], agent_file=agent_file)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["met"] else 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
