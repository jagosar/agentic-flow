# Guide: the measurement bench

**Goal:** know whether a change to the flow's agents or prompts makes real runs better or worse.
**Status:** not run with a real `claude` yet. Its own tests use a simulated one.

## What it measures

The bench runs the real pipeline (`agentic.py run-pipeline`, one `claude -p` per agent) on small fixture repos, three times each. For every run it records the result, the fix cycles, the tokens, the cost and the time. As an independent judge, it also counts how many of the fixture's hidden oracle tests the produced code passes. The oracle is never copied into the project before the pipeline ends.

It does **not** measure:

- The native workflow (`/implement` through the Workflow tool), which needs an interactive session. The agents, prompts and rules it uses are the ones the bench measures.
- `/architect`: the fixtures' plans are fixed, so a run measures the implementation flow only.
- Statistical significance. The report gives medians and ranges; three runs show a spread, not proof.

## Run it locally

You need the `claude` CLI on your `PATH` (or `AGENTIC_CLAUDE` pointing at it), `git` and `python3` 3.9 or later. It runs on your subscription by default:

```bash
python3 bench/bench.py run
```

Useful options: `--fixture NAME` (repeatable), `--repeat N`, `--timeout-min M`, `--auth inherit`. To limit cost, run one fixture once:

```bash
python3 bench/bench.py run --fixture tempconv --repeat 1
```

It prints one line per run and the path of the results file, then regenerates `bench/RESULTS.md`.

## Run it from GitHub Actions

1. In GitHub, go to `Settings → Secrets and variables → Actions → New repository secret`, name it `ANTHROPIC_API_KEY` and paste a Console API key. Never paste it in a chat or commit it.
2. Open the `agentic-bench` workflow in the Actions tab and choose **Run workflow**, with the number of repeats.
3. Download the `bench-results` artifact when it ends.

**Cost warning:** this bills the API. A rough guess is a few dollars per run, so two fixtures with three repeats may cost 10-30 $. The workflow is manual on purpose: it never runs on its own, on pull requests or on a schedule. The flow's CI only runs the bench's own tests, with a simulated `claude`.

## Read `RESULTS.md`

One row per results file and fixture, newest first. Columns: Version, Commit (`-dirty` if the source had uncommitted changes), Date, Fixture, Runs, OK (`ok/runs`), Oracle (median and range of the share of oracle tests passed), Fix cycles, Cost $, Output tokens and Minutes (medians). A `?` means no run had that value. Compare rows of the same fixture across versions, and treat a small difference as noise.

## Add a fixture

Create `bench/fixtures/<name>/`:

```
fixture.json   {"name": "<name>", "description": "<one line>", "difficulty": "simple" | "trap"}
repo/          the project the flow works on: code, tests and architecture.md (a valid plan); committed as is
oracle/        test_*.py (unittest); never copied into the project before run-pipeline returns
```

Write the code and the plan in English, with commands in the plan using `python3`, and no dependencies. Try it with `--fixture <name> --repeat 1`.

## Commit results by hand

CI never commits. After a run you want to keep, add the results file and the regenerated report:

```bash
git add bench/results/*.json bench/RESULTS.md && git commit -m "Bench results"
```
