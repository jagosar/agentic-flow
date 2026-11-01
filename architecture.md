# Architecture: hand fixes that find their reports, failed verifications kept, and A/B in one bench run (agentic-flow 2.3)
Type: feature · Size: standard

## 1. Goal
Three gaps found while using the flow, plus roadmap item 1.4. First, `agentic.py run-wave N --fix` reads `REVIEW.json` and `QA.json`, which only the one-off `run-review`/`run-qa` write: after `run-pipeline` (which writes `REVIEW-<n>.json`, `QA-<n>.json`) or the native workflow (which writes only `workflow-result.json`) it stops with "run run-review or run-qa first"; and it takes only blocking defects. Second, both engines overwrite `run.verification` on every pass, so a verification failure that sent packages to a fix cycle leaves no trace in the result (the bench lost the reason for a fix cycle in `tally`). Third, every bench comparison so far is three sessions per fixture per version, read by eye; roadmap 1.4 adds an A/B mode that interleaves two flow versions and reports per-fixture ratios, a bootstrap interval and a sign test. The roadmap's "Shipped" markers are brought up to date. The flow-side changes ship as 2.3.0.

## 2. Scope
### Included
- `run-wave --fix` reads the newest review and QA among `workflow-result.json`, `REVIEW-<n>.json`/`QA-<n>.json` and `REVIEW.json`/`QA.json`; `--all` adds medium and low implementation defects.
- Both engines append each failed verification to `run.verification_failures`; conformance scenarios count them; the bench records the count per run.
- `bench.py ab`: two sources (a directory or a git ref), interleaved sessions, a results file of its own kind, a comparison (ratios, geometric mean, bootstrap interval, sign test) printed and saved as Markdown.
- `plugin.json` 2.3.0, `NOTES["2.3.0"]`, version pins, roadmap markers and three new "found while using" entries.
- Acceptance tests in `.claude/bin/test_acceptance_v23.py`.
### Excluded (non-goals)
- Changing how fix cycles run inside the engines, resuming implementers or scoped re-review (2.3, 2.4).
- A/B over more than two versions, or statistics beyond the three of section 6.
- Running a real A/B with `claude` here: by hand after merging (section 9).
- `RESULTS.md`'s table: unchanged (A/B results are a different kind of file).

## 3. Stack
Python 3.9+ standard library (`agentic.py`, `pipeline.py`, `bench/bench.py`; `random`, `math`, `statistics`); Node 22 for the native workflow. No new dependency. No type annotations in `agentic.py` (it has none and must import on 3.9: an explicit override of the python rules); `bench.py` keeps its own style (`from __future__ import annotations`, annotated).
- Build: `python3 -m compileall -q .claude/bin bench` (the manifest's `types` slot runs the bench's unit tests, so verify catches a bench regression; the bench acceptance suite runs by hand in WP-03, about a minute)
- Lint (both engines agree): `node .claude/bin/test_workflow.mjs`
- Tests: `python3 -m unittest discover -s .claude/bin -p "test_*.py"`; `python3 -m unittest discover -s bench -p "test_*.py"`; `python3 -m unittest discover -s bench/acceptance -p "test_acceptance_*.py"`
- Acceptance: `python3 -m unittest discover -s .claude/bin -p test_acceptance_v23.py`

## 4. Repository structure
```
.claude/bin/agentic.py                      WP-01  run-wave --fix sources and --all
.claude/bin/test_agentic.py                 WP-01
.claude/commands/implement.md               WP-01  --all in the stage-by-stage list; verification_failures in the report
.claude/workflows/agentic-implement.js      WP-02  verification_failures
.claude/bin/pipeline.py                     WP-02  the same, in Python
.claude/bin/conformance.json                WP-02  unchanged unless a scenario needs a field (none expected)
.claude/bin/test_pipeline.py                WP-02  summary key verification_failures
.claude/bin/test_workflow.mjs               WP-02  the same, in Node
bench/bench.py                              WP-03  ab subcommand, statistics, record count
bench/test_bench.py                         WP-03
.claude-plugin/plugin.json                  WP-04  2.3.0
.claude/bin/upgrade.py                      WP-04  NOTES["2.3.0"]
.claude/bin/test_upgrade.py                 WP-04
.claude/bin/test_acceptance_upgrade.py      WP-04  pin at :258
.claude/bin/test_acceptance_v2.py           WP-04  pin at :177
.claude/bin/test_acceptance_v21.py          WP-04  pin at :283
.claude/bin/test_acceptance_v22.py          WP-04  pin at :171
docs/roadmap/repo-review-2026-11.md         WP-04  markers and new entries
.claude/bin/test_acceptance_v23.py          AT
README.md, docs/how-to/, docs/how-it-works.md   docs (doc-updater)
```

## 4b. Existing code context
| What an implementer needs to know | Where it is | Pattern or rule |
|---|---|---|
| `run_wave` and its `--fix` check | `.claude/bin/agentic.py:822-850`: dies at `:832-834` unless `runs/REVIEW.json` or `runs/QA.json` exists; `:835-837` dies when a WP has no defect; `:838-846` the fix-cycle cap (exit 4) | The existence check moves into the new source lookup; the message names the three sources |
| Where defects come from | `fix_defects(spec, wp_id)` `:812-819`: `structured_report(STATE / "runs" / f"{name}.json", {})`, keys `findings` (REVIEW) and `defects` (QA), filtered by `wp`, `severity in blocking` and `kind == "implementation"` (default) | Becomes `fix_defects(spec, wp_id, include_all=False)` over the sources of section 6 |
| CLI dispatch | `:2337-2347`: `run_wave(require_valid(), int(label), only=[a for a in rest if a != "--fix"], fix="--fix" in rest)`; usage docstring `:8-10` | Strip `--all` from `only` too; `--all` without `--fix` dies with a usage message; the docstring gains `[--all]` |
| What `run-pipeline` writes per agent | `:1531` (`counter`, restarts at 1 on every `run-pipeline`), `:1539-1541`: `runs/{ident or agent_type}-{n}.json`; the reviewer, every verifier and the test-auditor (`pipeline.py:288-290`) all use ident `REVIEW`; QA uses `QA` | Choose by mtime among reports with both `findings` and `needs_validation` (the reviewer schema requires both, `pipeline-spec.json` `schemas.reviewer.required`; the auditor's does not) |
| The run record both engines save | `workflow-result.json` in `.claude/state/runs/`: `review.confirmed` (blocking, upheld by the verifier), `review.advisory` (medium and low), `review.refuted`, `qa.defects` (`pipeline.py:431`, `agentic-implement.js:490`); `run-pipeline` writes it, `/implement` saves it with `save-result` | From the run record: confirmed and, with `--all`, advisory; never refuted |
| Reading a structured report | `structured_report(path, schema)` `:1480` (returns the dict or `None`; with `{}` as schema no key is required) | Use it for the per-agent files; `workflow-result.json` is plain JSON (`json.loads`) |
| Tests of `run-wave` | `test_agentic.py:1411` (`LauncherTests`), `:1528-1540` (`test_fix_only_when_requested`, `test_fix_without_report_fails`: asserts `"run-review or run-qa"` in stderr) | The second test's message changes: update its assertion to the new message's key words |
| Verification in the engines | `pipeline.py:405-420` (`run["verification"] = lines_json(...)`; `if not self.ok(v)`: defects, stop or fix cycle); `agentic-implement.js:458-472` (the same); run records at `pipeline.py:126` and `agentic-implement.js:182` | Append to `verification_failures` right after `if not ok(v)`, before the defects check |
| Conformance | `conformance.json`: scenarios `verification fails on a package: it is fixed and verified again` (one failure, then green), `verification never gets fixed`, `verification fails with no owner`; summaries `test_pipeline.py:115-128` and `test_workflow.mjs:482-494`; compared keys `test_pipeline.py:153` | Summaries gain `verification_failures` (the count); the comparison tuple includes it |
| One bench run | `bench/bench.py:435-456` (`_run_once`), `:458-470` (`_record`), `:550-578` (`run`: results file, `SCHEMA`, `_summaries`), `:609-619` (`_load_results`: keeps only `schema == SCHEMA`), `:647-663` (`_build_parser`), `:703+` (`main`) | `ab` reuses `_run_once` and `_validate`; its file has `"schema": "ab-1"` so `report` ignores it |
| Bench tests | `bench/test_bench.py:1-33` (module by path, `make_run`, `TempCase`); `bench/acceptance/test_acceptance_bench.py:41-46` (`load_bench`), `:48+` (`make_fixture`), `:79-109` (`Sandbox`: fake `claude`, `FAKE_WRITE=1`, `run_args`) | The acceptance test reuses `Sandbox` and `load_bench` |
| Versions and notes | `upgrade.py:50` (`NOTES["2.2.0"]` first), pins at the four lines of section 4 | `NOTES["2.3.0"]` goes first |
| Roadmap | `docs/roadmap/repo-review-2026-11.md`: tables of sections 1-4 (only 1.3, 2.1, 2.2, 3.1 say "Shipped"), "Versioning", "Found while using the flow", "Recommended order" | Section 6 lists every marker |

**What must NOT change:** the fix-cycle cap and exit code 4; `run-wave` without `--fix`; the engines' fix logic; `RESULTS.md` and `SCHEMA = 1`; the bench's `run`, `report` and `selftest`.

## 5. Data model
Engines, appended per failed verification (both identical):
```json
"verification_failures": [{"fix_cycle": 0, "blocking": ["tests"], "suspects": {"WP-02": {"phases": ["tests"], "files": ["src/b/x.py"], "acs": ["AC-002"]}},
                           "failing": [{"name": "tests", "status": "fails", "tail": ["FAILED src/b/x.py test_ac_002"]}]}]
```
`fix_cycle` is `run.fix_cycles` at the moment of the failure; `blocking` and `suspects` copied from the verification JSON (`[]`/`{}` when absent); `failing` the phases whose `status` is `regression` or `fails`, with `name`, `status`, `tail` (as given). Starts as `[]`.

Bench `_record` gains `"verification_failures": <len of the result's list, or 0>`.

A/B results file `<out>/ab-<versionA>-vs-<versionB>-<YYYYmmdd-HHMMSS>.json`:
```json
{"schema": "ab-1", "a": {"spec": "HEAD~3", "version": "2.2.0", "commit": "acce95b", "dirty": false},
 "b": {"spec": ".", "version": "2.3.0", "commit": "1a2b3c4", "dirty": false},
 "started": "...", "repeat": 3, "auth": "subscription", "seed": 0,
 "runs": [{"arm": "a", ...the run dict of _record...}, {"arm": "b", ...}],
 "comparison": {"fixtures": {"tally": {"cost_usd": 1.04, "minutes": 0.97, "output": 1.01, "mutation": 0.02, "oracle": 0.0, "fix_cycles": 0.0}},
                "overall": {"cost_usd": {"geomean": 1.02, "interval": [0.95, 1.10], "wins": 2, "losses": 3, "ties": 0, "p": 1.0},
                            "minutes": {...}, "output": {...}}}}
```
Ratios (`cost_usd`, `minutes`, `output`) are median(B) / median(A); differences (`mutation`, `oracle`, `fix_cycles`) are median(B) − median(A). `null` when an arm has no value or A's median is 0. "Win" means B's ratio is below 1 (cheaper, faster, shorter); a ratio of exactly 1 is a tie. The Markdown file next to it (`<stem>.md`) holds one table per metric family.

## 6. Contracts between modules
`.claude/bin/agentic.py` (WP-01):
```python
def latest_reports(include_all=False):
    """{"REVIEW": (findings, origin), "QA": (defects, origin)} from the newest source of each kind, by file
    modification time (st_mtime_ns), among:
      - runs/workflow-result.json: REVIEW = review.confirmed (+ review.advisory when include_all); refuted findings
        are never read. QA = qa.defects. A kind whose part is null (a run that stopped before it) is not a source
        of that kind, so an older file can still provide it;
      - every runs/REVIEW-<n>.json whose structured report has both "findings" and "needs_validation" (only the
        reviewer's schema requires the latter; the test-auditor and the verifier also write REVIEW-<n>), and every
        runs/QA-<n>.json whose report has "defects" and "needs_validation"; n is not used to choose (the counter
        restarts on every run-pipeline);
      - runs/REVIEW.json and runs/QA.json (the one-off run-review / run-qa).
    Ties in mtime go to REVIEW.json/QA.json, then -<n>, then workflow-result.json. A kind with no source is absent.
    origin is the file name, for the messages. A file that cannot be read or parsed is skipped."""
def fix_defects(spec, wp_id, include_all=False, reports=None):
    """The implementation defects review and QA attribute to wp_id, tagged with "source" ("reviewer"/"qa").
    Blocking severities only unless include_all; reports defaults to latest_reports(include_all)."""
def run_wave(manifest, wave, only=None, fix=False, include_all=False)
```
Messages: no source at all: `--fix needs a review or QA report: .claude/state/runs/workflow-result.json, REVIEW-<n>.json / QA-<n>.json or REVIEW.json / QA.json. Run run-pipeline, run-review or run-qa first.`; a WP without defects: `<WP>: no <blocking|> defect from review or QA is attributed to it. Read from <origins>.` (`blocking ` dropped with `--all`; the first sentence is pinned by `test_acceptance.py:186`). `--all` without `--fix`: `die("Uso: run-wave N [WP...] [--fix [--all]]")`.

Engines (WP-02): `run.verification_failures = []` in the run record; right after `if (!ok(v))` / `if not self.ok(v):`:
```
run.verification_failures.push({ fix_cycle: run.fix_cycles, blocking: (V.blocking || []), suspects: (V.suspects || {}),
  failing: (V.phases || []).filter(p => p.status === 'regression' || p.status === 'fails').map(p => ({ name: p.name, status: p.status, tail: p.tail || [] })) })
```
where `V` is `run.verification || {}`; Python mirrors with dicts and the same keys and order. Conformance summaries gain `verification_failures: (result.verification_failures || []).length`.

`bench/bench.py` (WP-03):
```python
AB_SCHEMA = "ab-1"
BOOTSTRAP_ITERATIONS = 2000
CONFIDENCE = 0.95
DEFAULT_SEED = 0
RATIO_METRICS = ("cost_usd", "minutes", "output")
DIFF_METRICS = ("mutation", "oracle", "fix_cycles")

def geometric_mean(values: list[float]) -> float | None          # None for [] or any value <= 0
def sign_test(wins: int, losses: int) -> float                    # two-sided exact binomial p (p=0.5), ties excluded; 1.0 when wins + losses == 0; capped at 1.0
def bootstrap_interval(per_fixture: dict[str, tuple[list[float], list[float]]], seed: int,
                       iterations: int = BOOTSTRAP_ITERATIONS, confidence: float = CONFIDENCE) -> tuple[float, float] | None
    """per_fixture: {fixture: (values of arm A, values of arm B)}. Each iteration resamples each arm of each fixture
    with replacement (random.Random(seed)), takes the median of each, the ratio B/A per fixture and the geometric
    mean over fixtures; returns the (1-confidence)/2 and 1-(1-confidence)/2 percentiles (nearest rank on the sorted
    results). None when no fixture has values in both arms or a resampled median of A is 0 in every iteration."""
def compare(runs: list[dict], seed: int) -> dict                  # section 5's "comparison"
def resolve_source(spec: str, repo: Path, worktree: Path) -> tuple[Path, bool]
    """A directory holding .claude/bin/agentic.py is used as is: (path, False). Anything else is a git ref of repo,
    checked out with `git worktree add --detach <worktree> <ref>`, where worktree is the final path the caller chose
    (ab passes <tmp>/a and <tmp>/b): (worktree, True). BenchError if neither, or if repo is not a git repo."""
def ab(fixtures: list[Path], spec_a: str, spec_b: str, repeat: int, out_dir: Path, auth: str = "subscription",
       timeout_s: float = 3600, env: dict | None = None, seed: int = DEFAULT_SEED, repo: Path = HERE.parent) -> Path
    """Order: argument checks (repeat, timeout, auth, fixtures, as _validate does), selftest of every fixture, and only
    then resolve_source for each arm, so a broken oracle or a bad argument creates no worktree. For each fixture and index 1..repeat,
    one session of each arm: A first on odd indexes, B first on even ones; each arm keeps its session files in
    <out>/<stem>/<arm>/ (keep = path.with_suffix("") / arm), so B never overwrites A. Writes the results file after
    every session and the .md at the end; does not touch RESULTS.md. Removes the worktrees it created, also on
    error. Returns the results path."""
```
Only runs whose `result` is `OK` or `REVIEW` give values; a run recorded as `error` or `timeout` gives none for any metric (its minutes are a cap or a setup failure, not a measurement), so an arm made only of such runs yields `null` for every ratio and difference of that fixture. Values per metric for one counted run: `cost_usd` = `usage.cost_usd`, `minutes` = `seconds / 60`, `output` = `usage.output`, `mutation` = `killed / total` (only when both are numbers and `total > 0`), `oracle` = `passed / total` (0 when `total` is 0), `fix_cycles` as recorded; `None` values are skipped. CLI: `bench.py ab --a SPEC --b SPEC [--repo DIR] [--fixture NAME]... [--repeat N] [--out DIR] [--auth MODE] [--timeout-min M] [--seed S]` (`--repo` defaults to the repo holding `bench.py`); prints the run lines as `run` does (with the arm before the fixture) and the Markdown; exit 1 with one line on stderr for a `BenchError`.

## 7. Conventions
- Each file's existing style: `agentic.py` without annotations, `bench.py` annotated with `from __future__ import annotations`, `BenchError` for user errors, UPPER_CASE constants at the top.
- Messages name what is missing and what to run; paths relative to the repo.
- Both engines mirror each other; conformance proves it.
- Deterministic statistics: a seeded `random.Random`, never the global one; nearest-rank percentiles.
- Tests: `unittest`, one behaviour per test, temp dirs with cleanup, the fake `claude` for any run.
- Forbidden: counting a refuted finding as a defect; reading the oracle into a project before the pipeline ends; leaving a worktree behind; changing `RESULTS.md` or `SCHEMA`.

## 8. Work packages and acceptance criteria
### Acceptance criteria
- AC-001 · `--fix` finds the newest review and QA wherever they were saved
  - Scenario: a `Repo` (`test_agentic.py`) with the fake `claude`; `runs/` holds (a) only `workflow-result.json` with `review.confirmed` = one high finding on `WP-02`, `review.refuted` = one high finding on `WP-02` with problem `refuted one`, `qa.defects` = []; then (b) only `REVIEW-7.json` (a reviewer report with that high finding, `needs_validation: []`), `REVIEW-9.json` (a verifier report: `{"is_real": true, ...}`, no `findings`) and `REVIEW-2.json` written last (a test-auditor report: `findings` with one high item on `WP-02`, no `needs_validation`); then (c) `REVIEW.json` written after a `workflow-result.json` (newer mtime) with a different high finding.
  - Action: `agentic.py run-wave 1 WP-02 --fix` in each case.
  - Expected: exit 0 in each; the prompt sent to `WP-02` contains the confirmed finding's problem in (a), not `refuted one`; contains `REVIEW-7`'s finding and not the auditor's in (b); contains `REVIEW.json`'s finding and not the run record's in (c).
  - Must not: fail with "run run-review or run-qa first" when only `workflow-result.json` exists; read a verifier's or a test-auditor's `REVIEW-<n>.json` as the review; choose by the highest `n`.
  - Check: `test_acceptance_v23.py::FixTests::test_ac_001_newest_source`
  - WP: WP-01
- AC-002 · `--all` adds medium and low, blocking stays the default
  - Scenario: `workflow-result.json` with `review.advisory` = one medium finding on `WP-02` and `qa.defects` = one low implementation defect on `WP-02` and one high design defect on `WP-02`; no blocking implementation defect.
  - Action: `run-wave 1 WP-02 --fix`; then `run-wave 1 WP-02 --fix --all`; then `run-wave 1 WP-02 --all`; then, with no report at all, `run-wave 1 WP-02 --fix`.
  - Expected: the first exits 1 with `no blocking defect` and `workflow-result.json` in stderr; the second exits 0 and the prompt holds the medium finding and the low defect, not the design one; the third exits 1 with `--fix [--all]` in stderr; the fourth exits 1 with `run-pipeline, run-review or run-qa` in stderr.
  - Must not: count the design defect; bypass the fix-cycle cap (a WP at its cap still exits 4 with `--all`).
  - Check: `test_acceptance_v23.py::FixTests::test_ac_002_all_and_messages`
  - WP: WP-01
- AC-003 · Every failed verification stays in the run result
  - Scenario: the conformance scenarios `verification fails on a package: it is fixed and verified again`, `verification never gets fixed` and the happy path.
  - Action: both conformance runners.
  - Expected: `verification_failures` is 1, the fix-limit count (one per verify that failed: 3 with `max_fix_cycles` 2) and 0 respectively, equal in both engines; in Python, the first scenario's `result["verification_failures"][0]` has `fix_cycle` 0, `blocking` `["tests"]`, `suspects` with `WP-02`, and `failing[0]["name"]` `tests`.
  - Must not: drop the list when the run stops at verification with no owner (`verification fails with no owner`: 1).
  - Check: `test_acceptance_v23.py::EngineTests::test_ac_003_verification_failures`
  - WP: WP-02
- AC-004 · The A/B statistics are exact and deterministic
  - Scenario: no state.
  - Action: `geometric_mean([0.5, 2.0])`, `geometric_mean([])`, `geometric_mean([1.0, 0.0])`; `sign_test(5, 0)`, `sign_test(3, 3)`, `sign_test(0, 0)`, `sign_test(1, 0)`; `bootstrap_interval` twice with seed 0 on `{"f1": ([1, 1, 1], [2, 2, 2]), "f2": ([1, 1, 1], [2, 2, 2])}`, once with seed 1; and on `{"f": ([1.0, 1.1, 0.9], [1.0, 1.1, 0.9])}`.
  - Expected: `1.0`, `None`, `None`; `0.0625`, `1.0`, `1.0`, `1.0`; the two seed-0 intervals are equal and both are `(2.0, 2.0)`; the seed-1 interval is `(2.0, 2.0)` too; the identical-arms interval contains `1.0`.
  - Must not: use the global `random` state (calling `random.seed(99)` before does not change the result).
  - Check: `test_acceptance_v23.py::StatsTests::test_ac_004_statistics`
  - WP: WP-03
- AC-005 · `bench.py ab` interleaves two sources and leaves no worktree
  - Scenario: the bench's acceptance `Sandbox` (fake `claude`, `benchfix`) and a temporary git repo built by the test: `.claude/` (without `state/`, `rules/` and `__pycache__/`) and `.claude-plugin/` copied from this repo, `git init`, one commit made with an explicit identity (`-c user.name=t -c user.email=t@t -c commit.gpgsign=false`). Arm A = that temporary repo's directory, arm B = the git ref `HEAD` of it (`--repo` pointing at it), so no worktree is ever created in the developer's checkout.
  - Action: `bench.py ab --a <tmp repo> --b HEAD --repo <tmp repo> --fixture <benchfix> --repeat 2 --out <dir>`; then `bench.py report --out <dir>`; then `git worktree list` in the temporary repo.
  - Expected: exit 0; one `ab-*.json` file with `schema` `ab-1`, 4 runs whose arms in order are `a, b, b, a`, `a.spec` and `b.spec` as given, a `comparison` with `fixtures.benchfix` and `overall.cost_usd`; an `ab-*.md` next to it containing `benchfix`; stdout holds the Markdown; `RESULTS.md` written by `report` does not mention the A/B file (its table has no row for it); `git worktree list` prints exactly one line (the main worktree) afterwards; each run dict has `verification_failures`; the session files are under `<stem>/a/` and `<stem>/b/`, two in each.
  - Must not: spend before selftest (a fixture with a broken oracle exits 1 with nothing run and no worktree created); give a minutes ratio for an arm whose sessions all timed out (that fixture's `minutes` is `null`); accept `--repeat 0`; leave the worktree when a session fails (`--timeout-min 0.01` with `FAKE_SLEEP=30`: exit 0, runs recorded as `timeout`, no worktree left).
  - Check: `test_acceptance_v23.py::AbTests::test_ac_005_ab_run`
  - WP: WP-03
- AC-006 · Version, notes and roadmap
  - Scenario: the merged repo.
  - Action: read `plugin.json`, `upgrade.NOTES`, the roadmap.
  - Expected: version `2.3.0`; `NOTES["2.3.0"]` has at least two strings whose concatenation mentions `--fix`, `--all`, `workflow-result.json` and `verification_failures`; the earlier notes keep their counts (2.2.0: 2, 2.1.0: 4, 2.0.0: 7); in the roadmap the rows of 1.1, 1.2, 1.4, 1.5, 3.2, 4.1, 4.2, 4.3 and the bullets 6.5, 6.6 contain `Shipped`; the row of 4.4 contains `Partly`; the "Found while using the flow" section no longer describes the `run-wave --fix` gap as open (it contains `Fixed in 2.3.0`) and has new bullets containing `hooks`, `test-auditor` and `test_ac_013`.
  - Must not: change the older notes.
  - Check: `test_acceptance_v23.py::ReleaseTests::test_ac_006_version_notes_roadmap`
  - WP: WP-04

### Work packages
#### WP-01 · run-wave --fix finds its reports and takes --all
- Wave 1.
- Files: `.claude/bin/agentic.py`, `.claude/bin/test_agentic.py`, `.claude/commands/implement.md`.
- Implements `latest_reports`, `fix_defects(..., include_all, reports)`, `run_wave(..., include_all)`, the dispatch, the docstring line, and the `run-wave` line of `.claude/commands/implement.md:82` (`[--fix [--all]]`) (section 6). Consumes nothing.
- ACs: AC-001, AC-002.
- Patterns to mirror: `agentic.py:812-850` (`fix_defects`, `run_wave`), `:1480` (`structured_report`), `:2337-2347` (dispatch); `test_agentic.py:1528-1540` (the two `--fix` tests, the `prompt_of` helper at `:1525`).
- Gotchas: file modification times may be equal within a test: set `os.utime` explicitly in the tests; the comparison is `st_mtime_ns` with the tie order of section 6; `review: null` or `qa: null` in `workflow-result.json` means "not a source of that kind", not "no defects"; a refuted finding is only in `review.refuted`, so reading `confirmed` (+ `advisory` with `--all`) excludes it; a test-auditor `REVIEW-<n>` (findings but no `needs_validation`) is never a review; keep the existing test `test_fix_without_report_fails` passing by updating its expected words to `run-review or run-qa` (still present in the new message).
- WP validation: `python3 -m unittest discover -s .claude/bin -p test_agentic.py`; `python3 -m compileall -q .claude/bin`.

#### WP-02 · Failed verifications kept in both engines
- Wave 1.
- Files: `.claude/workflows/agentic-implement.js`, `.claude/bin/pipeline.py`, `.claude/bin/conformance.json`, `.claude/bin/test_pipeline.py`, `.claude/bin/test_workflow.mjs`.
- Implements `verification_failures` (sections 5 and 6). Consumes nothing. The launcher's presentation of it (one bullet next to `gate_denials` in `.claude/commands/implement.md:66`) is written by WP-01, which owns that file: "**Failed verifications (`verification_failures`):** each one's blocking phases and suspects, when a verification sent packages to a fix cycle."
- ACs: AC-003.
- Patterns to mirror: `pipeline.py:405-420` and `agentic-implement.js:458-472`; the 2.1.0/2.2.0 summary keys (`gate_denials`, `review_callers`) in `test_pipeline.py:115-128,153` and `test_workflow.mjs:482-494`.
- Gotchas: append before the "no owner" stop, so a stopped run keeps its failure; `stop()` in both engines spreads `run`, so the list travels into a stopped result; key order in the JS object and the Python dict must match (the conformance comparison of summaries uses only the count, but the bench reads the list); no new scenario is needed: the three existing ones cover 1, 3 and the no-owner case.
- WP validation: `node .claude/bin/test_workflow.mjs`; `python3 -m unittest discover -s .claude/bin -p test_pipeline.py`.

#### WP-03 · A/B in one bench run
- Wave 1.
- Files: `bench/bench.py`, `bench/test_bench.py`.
- Implements the constants, `geometric_mean`, `sign_test`, `bootstrap_interval`, `compare`, `resolve_source`, `ab`, the `ab` subcommand, and `verification_failures` in `_record` (sections 5 and 6). Consumes the engines' `verification_failures` by signature (WP-02).
- ACs: AC-004, AC-005.
- Patterns to mirror: `bench/bench.py:435-470` (`_run_once`, `_record`), `:533-578` (`_validate`, `run`), `:609-619` (`_load_results`), `:647-663` (parser), `:672-681` (`_print_runs`); `bench/test_bench.py:1-33`.
- Gotchas: `_record` must tolerate a `verification_failures` that is not a list (count it as 0, like a non-numeric `test_audit`); `geometric_mean` wraps `statistics.geometric_mean` (Python 3.8+) and returns `None` for `[]` or any value <= 0 instead of raising; `git worktree add` needs `--repo` to be a git repo (BenchError otherwise, before any spend); in a bootstrap iteration where a fixture's resampled A median is 0, that fixture is left out of that iteration's geometric mean (an iteration with no fixture left is skipped); `overall` holds only the ratio metrics (the differences are per fixture); `ab` does not regenerate `RESULTS.md`; create worktrees under a temp dir and remove them with `git worktree remove --force` in a `finally`, then `git worktree prune`; the results file of `ab` must not use `SCHEMA` (so `report` skips it); medians per arm and fixture use `statistics.median` on non-`None` values; `sign_test` p is `min(1.0, 2 * sum(comb(n, k) for k in range(0, min(w, l) + 1)) / 2**n)`; percentiles by nearest rank on the sorted bootstrap results (`ceil(q * N) - 1`, clamped); the bench's own runs exit 0 even when sessions fail, as `run` does.
- WP validation: `python3 -m unittest discover -s bench -p "test_*.py"`; `python3 -m unittest discover -s bench/acceptance -p "test_acceptance_*.py"`; `python3 -m unittest discover -s qa -p "test_qa_*.py"` (`qa/test_qa_bench.py:47-53` feeds `_record` malformed results); `python3 -m compileall -q bench`.

#### WP-04 · Version 2.3.0, notes and roadmap
- Wave 1.
- Files: `.claude-plugin/plugin.json`, `.claude/bin/upgrade.py`, `.claude/bin/test_upgrade.py`, `.claude/bin/test_acceptance_upgrade.py`, `.claude/bin/test_acceptance_v2.py`, `.claude/bin/test_acceptance_v21.py`, `.claude/bin/test_acceptance_v22.py`, `docs/roadmap/repo-review-2026-11.md`.
- ACs: AC-006.
- Patterns to mirror: `upgrade.py:50-60` (`NOTES["2.2.0"]`), `test_upgrade.py:93-99` (the 2.2 notes test).
- Notes to write: `run-wave --fix` reads the newest review and QA wherever they were saved (`workflow-result.json`, `REVIEW-<n>.json`/`QA-<n>.json`, `REVIEW.json`/`QA.json`) and `--all` adds medium and low; the run result gains `verification_failures`, so a fix cycle triggered by verification keeps its reason. Roadmap: the markers of AC-006; 1.4 "Shipped (bench only)"; 4.4 "Partly: the callers are printed in the reviewer's prompt; the prompt audit is open"; the `run-wave --fix` bullet ends "Fixed in 2.3.0"; new bullets: project hooks did not fire for the Workflow tool's subagents in a cloud session (claims stayed empty in two runs; ownership held only through close-stage's comparison); the test-auditor passed a wrong acceptance test (roster, session 2: the implementer returned BLOCKED with the exact diagnosis); an old test (`test_acceptance.py::test_ac_013_docs`) pinned README wording that a docs rewrite had to keep; the bench cannot measure 3.1 because its fixtures are greenfield (callers in 3 of 15 sessions of the 2.2.0 run, no finding): a brownfield fixture is needed.
- Gotchas: earlier acceptance tests read the roadmap: `test_acceptance_v22.py:180-181` needs the `| 3.1 |` row to keep `Shipped in 2.2.0`; `test_acceptance_v21.py:292` needs `## Versioning` before `## Found while using the flow`; `test_acceptance_v2.py:185-187` needs `## Versioning`, `2.0` and `run-wave --fix` somewhere in the file (keep the phrase in the fixed bullet).
- WP validation: `python3 -m unittest discover -s .claude/bin -p "test_*upgrade.py"`; `python3 -m unittest discover -s .claude/bin -p "test_acceptance_v2*.py"`.

```json wp-manifest
{
  "stack": ["python", "typescript"],
  "allow_bash": ["Bash(python3 -m unittest:*)", "Bash(python3 -m compileall:*)", "Bash(node .claude/bin/test_workflow.mjs)"],
  "acceptance": {"files": [".claude/bin/test_acceptance_v23.py"], "command": "python3 -m unittest discover -s .claude/bin -p test_acceptance_v23.py"},
  "verify": {"build": "python3 -m compileall -q .claude/bin bench", "lint": "node .claude/bin/test_workflow.mjs", "types": "python3 -m unittest discover -s bench -p test_*.py", "tests": "python3 -m unittest discover -s .claude/bin -p test_*.py"},
  "docs": {"files": ["README.md", "docs/how-to/", "docs/how-it-works.md"], "codemap": null},
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": [".claude/bin/agentic.py", ".claude/bin/test_agentic.py", ".claude/commands/implement.md"],
     "acs": ["AC-001", "AC-002"], "mirror": [".claude/bin/agentic.py:812-850", ".claude/bin/agentic.py:2337-2347", ".claude/bin/test_agentic.py:1525-1540"]},
    {"id": "WP-02", "wave": 1, "depends_on": [], "files": [".claude/workflows/agentic-implement.js", ".claude/bin/pipeline.py", ".claude/bin/conformance.json", ".claude/bin/test_pipeline.py", ".claude/bin/test_workflow.mjs"],
     "acs": ["AC-003"], "mirror": [".claude/bin/pipeline.py:405-420", ".claude/workflows/agentic-implement.js:458-472", ".claude/bin/test_pipeline.py:115-128"]},
    {"id": "WP-03", "wave": 1, "depends_on": [], "files": ["bench/bench.py", "bench/test_bench.py"],
     "acs": ["AC-004", "AC-005"], "mirror": ["bench/bench.py:435-470", "bench/bench.py:533-578", "bench/test_bench.py:1-33"]},
    {"id": "WP-04", "wave": 1, "depends_on": [], "files": [".claude-plugin/plugin.json", ".claude/bin/upgrade.py", ".claude/bin/test_upgrade.py", ".claude/bin/test_acceptance_upgrade.py", ".claude/bin/test_acceptance_v2.py", ".claude/bin/test_acceptance_v21.py", ".claude/bin/test_acceptance_v22.py", "docs/roadmap/repo-review-2026-11.md"],
     "acs": ["AC-006"], "mirror": [".claude/bin/upgrade.py:50-60"]}
  ]
}
```

## 9. Test strategy
- Unit: WP-01 in `test_agentic.py` (each source alone, mtime order and ties, a verifier `REVIEW-<n>`, `review: null`, `--all` with advisory and low QA, design defects excluded, the cap with `--all`); WP-02 through the three conformance scenarios in both runners; WP-03 in `test_bench.py` (each statistic's edges, `compare` with `None` values and a zero median, `resolve_source` for a directory, a ref and garbage, the arm order); WP-04 in `test_upgrade.py`.
- Acceptance: `.claude/bin/test_acceptance_v23.py`, AC-001…AC-006, written first and red; AC-003's Python check builds `pipeline.Pipeline` with `test_pipeline.world(decl)` to read the raw result (the conformance summary only has the count); AC-005 loads `bench.py` and `Sandbox` from `bench/acceptance/test_acceptance_bench.py` (add `bench/acceptance` to `sys.path`) and uses the fake `claude`, so nothing is spent.
- QA: exploratory over `--fix` (a corrupt `workflow-result.json`; a `REVIEW-<n>` with `n` not a number; a WP that appears only in refuted findings) and `ab` (a ref that does not exist; the same directory for both arms; a fixture where every session timed out; `--seed` changing only the interval).
- After merging, by hand: `flow-history`, release 2.3.0, `install` in finanzas-familiares; and the first real A/B: `bench.py ab --a agentic-flow--v2.1.0 --b agentic-flow--v2.3.0`, against the three-session tables of `bench/RESULTS.md`.

## 10. Decisions
- **D1 · Newest source by modification time, with a fixed tie order (from the evidence):** a person may run `run-review` after a pipeline run and expect that review to be used; the run record is preferred over per-agent files only when it is newer, because it already excludes refuted findings. Discarded: a fixed precedence (wrong after a later one-off review).
- **D2 · `--all` opt-in (user's choice):** blocking stays the default; medium and low reach a package only when a person asks.
- **D3 · `verification_failures` in the run record, not in the bench:** the engines are the only place that sees each verification; the bench keeps the whole session file already, so a count in `_record` is enough.
- **D4 · A/B with interleaving and alternating order (roadmap 1.4, user's choice):** A then B on odd indexes, B then A on even ones, so drift in the API's speed or in usage limits hits both arms equally. Discarded: two separate `run` calls (drift lands on one version).
- **D5 · Ratios for cost, minutes and output; differences for rates and counts:** a ratio of two rates near 1 is unstable and a ratio of zero fix cycles is undefined. Discarded: ratios everywhere.
- **D6 · Geometric mean, percentile bootstrap, exact sign test, standard library only:** the roadmap's three; no `numpy` or `scipy` (no new dependency). A seeded `random.Random` makes the interval reproducible.
- **D7 · Git refs through temporary worktrees:** comparing a release tag with the working tree needs no manual checkout; worktrees are removed in a `finally`.
- **D8 · Version 2.3.0:** `--all` and `verification_failures` are new behaviour in installed files; the bench part does not change projects.
- **D9 · Executed by hand:** WP-01, WP-02 and WP-04 own paths under `.claude/` (`validate` refuses them, `agentic.py:403`); the manifest stays truthful; acceptance tests first and red, one commit per WP.

## 11. Risks and open questions
- **Three sessions per arm is still small:** the bootstrap interval will be wide and the sign test over five fixtures cannot go below p = 0.0625; the A/B says "no detectable difference" more often than not. The value is that it says so with a number instead of a reading.
- **Cost of a real A/B:** twice a full run (the last full run cost 8.40 USD for 15 sessions: `bench/results/2.1.0-20261101-171319-bee023e.json`), about 17 USD at three sessions per arm; not run here.
- **mtime on some filesystems has coarse resolution:** ties are broken by the fixed order of D1; tests set `os.utime` explicitly.
- **A ref whose flow cannot install into a fixture** (an old version) makes every session of that arm fail at setup; `ab` records them as `error` and the comparison shows `null` ratios.
- **The bench cannot measure the reviewer's callers yet:** the 2.2.0 run (`bench/results/2.2.0-20261101-193221-acce95b.json`, PR 42) gave the reviewer callers in 3 of 15 sessions, all in `tally`, with no finding: the fixtures start from almost nothing, so callers fall inside the diff. A brownfield fixture (existing code and tests, a plan that changes a signature used in files no package owns) is the next fixture to add; WP-04 adds it to the roadmap's "Found while using the flow".
- **Docs stage:** `test_acceptance.py:292` (`test_ac_013_docs`) pins wording in `README.md` and tokens in `docs/how-it-works.md`; the doc-updater must keep them when it documents `--all` and `ab`.
- **Rollback:** revert the PR; a project on 2.3.0 keeps `--all` and the extra result key, harmless if the bench is older; the downgrade guard means a bad 2.3.0 needs a 2.3.1.
