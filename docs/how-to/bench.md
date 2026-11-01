# Guide: the measurement bench

**Goal:** know whether a change to the flow's agents or prompts makes real runs better or worse.
**Status:** not run with a real `claude` yet. Its own tests use a simulated one.

## What it measures

The bench runs the real pipeline (`agentic.py run-pipeline`, one `claude -p` per agent) on small fixture repos, three times each. For every run it records the result, the fix cycles, the tokens, the cost and the time. As an independent judge, it also counts how many of the fixture's hidden oracle tests the produced code passes. The oracle is never copied into the project before the pipeline ends.

Every agent session is isolated from the person running the bench: no user settings (`--setting-sources project,local`), no `CLAUDE.md` of the user or of a parent directory, no auto memory (`CLAUDE_CODE_DISABLE_CLAUDE_MDS`, `CLAUDE_CODE_DISABLE_AUTO_MEMORY`). Two people measure the same flow. A fixture that relies on a `CLAUDE.md` of its own would not see it either.

It does **not** measure:

- The native workflow (`/implement` through the Workflow tool), which needs an interactive session. The agents, prompts and rules it uses are the ones the bench measures.
- `/architect`: the fixtures' plans are fixed, so a run measures the implementation flow only.
- Statistical significance. The report gives medians and ranges; three runs show a spread, not proof.

## The fixtures

| Fixture | Difficulty | What it is | What it tests |
|---|---|---|---|
| `tempconv` | simple | Temperature conversion and parsing, one wave, two independent packages | The plain flow |
| `inventory` | trap | Stock keeping in two waves | Edge cases that tend to need a fix cycle |
| `vault` | trap | A file vault in one wave: storage paths, download tokens and a sqlite catalogue | Judgement about untrusted input: the plan states functional behaviour only and says once that users are not trusted, while the oracle attacks with adversarial input (tests named `test_adv_*`) |
| `tally` | trap | An expense-sharing library in three waves: money and dates, a ledger, settlement | A real `depends_on` chain and edge cases on money, dates and settlement (tests named `test_edge_*`) |

The oracle has no weights: the results count passed over total, and the per-test names in the oracle output say why a run lost points.

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

Before the first run it checks every fixture's instruments and stops, spending nothing, if one is broken. The same check on its own, with no `claude` involved:

```bash
python3 bench/bench.py selftest
```

A fixture is sound when its oracle has tests, passes none of them on the bare repo, all of them on `reference/good` and not all of them on `reference/bad`. An oracle that is green with no code, or that a plausible wrong implementation passes, measures nothing.

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
fixture.json      {"name": "<name>", "description": "<one line>", "difficulty": "simple" | "trap"}
repo/             the project the flow works on: code, tests and architecture.md (a valid plan); committed as is
oracle/           test_*.py (unittest); never copied into the project before run-pipeline returns
reference/good/   a correct implementation, copied over repo/ by selftest: the oracle must pass it whole
reference/bad/    a plausible wrong one (right on the happy path, wrong on the edge cases): the oracle must catch it
```

Name the oracle's tests so a reference can be judged by what it fails: `vault` uses `test_adv_*` for adversarial tests and `tally` uses `test_edge_*` for edge cases, and their acceptance tests (`bench/acceptance/test_acceptance_fixtures.py`) check that the bad reference fails only those. Import the module under test inside each test, so each test fails on the bare repo.

Write the code and the plan in English, with commands in the plan using `python3`, and no dependencies. Check it with `selftest --fixture <name>`, then try it with `--fixture <name> --repeat 1`.

## Commit results by hand

CI never commits. After a run you want to keep, add the results file and the regenerated report:

```bash
git add bench/results/*.json bench/RESULTS.md && git commit -m "Bench results"
```
