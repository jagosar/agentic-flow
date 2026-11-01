# Architecture: the bench measures quality (mutation score and the roster fixture)
Type: feature · Size: standard

## 1. Goal
Three flow versions have scored 100% on the oracle with zero fix cycles and zero gate denials (`bench/RESULTS.md`), so the bench tells cost and time apart but not quality. Two instruments fix that. A **mutation score**: after the pipeline, small bugs are injected one at a time into the code the agents produced and the agents' own tests (unit tests plus acceptance tests) must fail; the share of mutants killed measures the tests the agents wrote, and the same mutants run against the fixture's oracle give a ceiling to compare with. A **fifth fixture, `roster`**, whose plan carries two traps: edge cases and contract errors stated in the contracts but absent from the acceptance criteria (acceptance passes, reviewer, QA and the oracle catch them: fix cycles), and one decision a package needs that sits only in section 10 of the plan, which the brief does not include (`NEEDS_CONTEXT`, or an invented reading the oracle penalises). The bench cannot force the stop gate: it fires only when an implementer reports `DONE` with red acceptance tests.

## 2. Scope
### Included
- `bench/mutate.py`: deterministic mutant generation over Python sources with `ast`, five operators, an even deterministic sample capped at 40, and a scorer that runs test commands per mutant.
- `bench/bench.py`: a `mutation` block per run (agents' kill rate and the oracle ceiling), summary medians, a `Mutation` column in `RESULTS.md`, one more field in the per-run line.
- The `roster` fixture: `fixture.json`, `repo/` (seed package, version test, `architecture.md` with the two traps), `oracle/` (`test_edge_*` and `test_ctx_*` names), `reference/good`, `reference/bad`.
- Unit tests of the new module and of the bench changes; acceptance tests in `bench/acceptance/test_acceptance_quality.py`.
### Excluded (non-goals)
- Mutating non-Python files (every fixture is Python; a non-`.py` file yields no candidates).
- A mutation check in `selftest` (decision D5), A/B runs (roadmap 1.4), statistical tests.
- Changing the flow installed in projects: nothing under `.claude/` changes and the plugin version stays 2.1.0.
- Running the bench with a real `claude` here: by hand after merging (section 9).

## 3. Stack
Python 3.9+ standard library only (`ast.unparse` exists from 3.9). Tests with `unittest`. No new dependency.
- Build: `python3 -m compileall -q bench`
- Tests: `python3 -m unittest discover -s bench -p "test_*.py"` (does not descend into `bench/acceptance/`, which has no `__init__.py`)
- Lint slot, used for the existing acceptance suites of the bench and its fixtures, which `_run_once`/`_record`/report changes must keep green: `python3 -m unittest discover -s bench/acceptance -p "test_acceptance_*.py"`
- Acceptance: `python3 -m unittest discover -s bench/acceptance -p test_acceptance_quality.py`
- Fixture instruments: `python3 bench/bench.py selftest --fixture roster`

## 4. Repository structure
```
bench/mutate.py                                   WP-01  mutants and the scorer
bench/test_mutate.py                              WP-01
bench/bench.py                                    WP-02  mutation per run, summary, report column
bench/test_bench.py                               WP-02
bench/fixtures/roster/fixture.json                WP-03
bench/fixtures/roster/repo/README.md              WP-03
bench/fixtures/roster/repo/architecture.md        WP-03  the fixture's plan (two traps)
bench/fixtures/roster/repo/roster/__init__.py     WP-03
bench/fixtures/roster/repo/tests/test_version.py  WP-03
bench/fixtures/roster/oracle/test_oracle.py       WP-03
bench/fixtures/roster/reference/good/roster/      WP-03  intervals.py shifts.py schedule.py rules.py
bench/fixtures/roster/reference/bad/roster/       WP-03  the same four files, wrong on the edges and the bait
bench/acceptance/test_acceptance_quality.py       AT
qa/                                               QA
docs/how-to/bench.md, docs/roadmap/repo-review-2026-11.md, README.md   docs (doc-updater)
```

## 4b. Existing code context
| What an implementer needs to know | Where it is | Pattern or rule |
|---|---|---|
| One run of a fixture: prepare, pipeline, read the result, keep the session, oracle, record | `bench/bench.py:345-363` (`_run_once`), `:366-376` (`_record`: the run dict's keys) | The mutation block is computed in `_run_once` after `_run_oracle` and passed to `_record` as a new argument |
| How the oracle runs over the project | `:297-305` (`_run_oracle` copies `fixture/oracle` to `project/.bench_oracle`), `:275-294` (`oracle_counts`: `python -m unittest discover -s <oracle> -t <oracle>` with `PYTHONPATH=project`, `cwd=project`) | The oracle ceiling uses the same command with `-s`/`-t` on `fixture/oracle` itself; `_run_oracle` removes `.bench_oracle` after counting so the agents' suites do not see it (the bench's own test fixture `acc.py` exits 1 when that folder exists: `test_acceptance_bench.py:25-28`) |
| The project's own commands | the plan's manifest inside `project/architecture.md`: `verify.tests` and `acceptance.command` (e.g. `bench/fixtures/tally/repo/architecture.md:269-284`) | Read with the regex of `bench/acceptance/test_acceptance_fixtures.py:34-38` (`manifest_of`); run with `shlex.split`, `cwd=project`, no shell, as `run_command()` in `.claude/bin/agentic.py:1224-1243` does |
| Which files to mutate | the manifest's `work_packages[*].files` | Production files only: every `.py` under the listed paths (a directory expands with `rglob`), minus any path whose first segment is `tests`, any file named `test_*.py` (tests kept beside the code), and anything under `acceptance.files` or `qa.files` (default `qa/`); a listed file that does not exist is skipped; `__init__.py` files are included like any other |
| Summary and report | `:412-423` (`_summarize`: medians via `_rounded`/`_non_null`), `:425-427` (`_summaries`), `:59-60` (`TABLE_HEADER`), `:488-502` (`_rows`), `:481-486` (`_number`) | New keys `mutation_median`, `mutation_oracle_median`; the column `Mutation` shows `agents / oracle` with two decimals (`0.72 / 0.90`), `?` when absent |
| The per-run line printed after a run | `:566-572` (`_print_runs`) | Append ` mutation k/n` when the run has one |
| Constants and errors | `:28-66` (UPPER_CASE constants, `BenchError`) | New constants live in `mutate.py` (`OPERATORS`, `MUTANTS_MAX`, `MUTANT_TIMEOUT_S`) |
| Unit tests of the bench | `bench/test_bench.py:1-33` (module loading by path, `make_run`, `TempCase`), `:80-90` (`SelftestTests.fixture`: a fixture built in a temp dir), `:102-110` (`SummaryTests`) | `make_run` gains a `mutation=None` argument; summary tests cover runs with and without it |
| Acceptance tests of the bench | `bench/acceptance/test_acceptance_bench.py:1-60` (fake `claude`, `make_fixture`, `ACC_PY`, `ORACLE_PY`), `:306-336` (`FixtureReady.prepare`: copy, git, install, validate) | `test_acceptance_quality.py` imports `make_fixture`, `load_bench` and `FixtureReady` from there and `FixtureCase`/`manifest_of` from `test_acceptance_fixtures.py` |
| Acceptance tests of a fixture | `bench/acceptance/test_acceptance_fixtures.py:95-141` (sound, bad reference fails only `test_adv_`/`test_edge_`, plan valid, waves), `:143-171` (an end-to-end bench run with the fake `claude`) | Mirror for `roster`, with the `test_edge_`/`test_ctx_` prefixes |
| What a brief contains | `.claude/bin/brief.py:14` (`WP_SECTIONS = ("1", "2", "3", "4b", "5", "6", "7", "9", "11")`), `:81-90` (`slice_architecture`) | Section 10 (Decisions) and the other packages' `#### WP-NN` blocks are **not** in an implementer's brief: the bait goes in section 10 |
| Writing the briefs of a plan | `python3 .claude/bin/agentic.py briefs` writes `.claude/state/briefs/<ID>.md` in a project where the flow is installed (`FixtureReady.prepare` installs it) | The acceptance test reads `WP-04.md` to prove the bait is absent from the brief |
| A fixture's plan, oracle and references | `bench/fixtures/tally/repo/architecture.md:1-284` (plan structure, contracts with concrete values, ACs with `Check` paths, manifest), `bench/fixtures/tally/oracle/test_oracle.py:1-60` (imports inside each test, `test_edge_*`), `bench/fixtures/tally/reference/bad/tally/money.py:1-24` (right on the happy path, wrong on the edges) | `roster` mirrors all three |
| Fixture metadata and difficulty | `bench/fixtures/vault/fixture.json` (`name`, `description`, `difficulty`) | `{"name": "roster", "description": "...", "difficulty": "trap"}` |
| The fake `claude` writes one file per package | `.claude/bin/testutil.py:71-74` (`FAKE_WRITE`: `{"WP-01": "src/a.py", "WP-02": "src/b/x.py", "WP-03": "src/c.py"}`) | A fake run of `roster` writes nothing useful: its end-to-end acceptance checks the run completes and records a mutation block with `total` 0 or more, not a score |
| Docs | `docs/how-to/bench.md` ("What it measures", "The fixtures" table, "Read RESULTS.md", "Add a fixture"), `README.md:108` (test counts), `docs/roadmap/repo-review-2026-11.md:30` (item 1.3) | The doc-updater marks 1.3 shipped and documents the column and the fixture |

**What must NOT change:** the results schema version (`SCHEMA = 1`; a missing `mutation` key reads as `None`), the oracle's isolation (never copied before the pipeline ends), `selftest`'s four checks, the existing fixtures.

## 5. Data model
```python
@dataclass(frozen=True)
class Mutant:
    file: str          # path relative to the project, forward slashes
    line: int          # 1-based line of the mutated node
    operator: str      # one of OPERATORS
    description: str   # "< -> <=", "+ -> -", "and -> or", "drop not", "3 -> 4"
```
Per run, in the results file and in `doc["runs"][i]`:
```json
"mutation": {"total": 31, "killed": 24, "oracle_killed": 29, "timeouts": 1,
             "survived": [{"file": "roster/intervals.py", "line": 18, "operator": "compare", "description": "< -> <="}]}
```
`total` is the number of mutants run (after the cap). `killed` counts the agents' suite; `oracle_killed` the oracle over the same mutants. **Baseline first:** before any mutant, each suite runs once on the unmutated code; a suite that is already red (or times out) there measures nothing, so its count is `null` (`killed: null` makes `survived` `[]`). A mutant whose test run exceeds `MUTANT_TIMEOUT_S` counts as killed (an infinite loop is a detected change) and in `timeouts`. The whole block is `null` when no production file yields a candidate. Summary: `mutation_median` (median of `killed/total` over the runs where `killed` is a number) and `mutation_oracle_median` likewise, `None` when no run has a number.

The `roster` fixture, repo seed: `roster/__init__.py` (docstring, `__version__ = "0.1.0"`), `tests/test_version.py`, `README.md`, `architecture.md`.

## 6. Contracts between modules
`bench/mutate.py` (WP-01):
```python
OPERATORS = ("compare", "arith", "boolop", "not", "const")
MUTANTS_MAX = 40
MUTANT_TIMEOUT_S = 120

def candidates(source: str, file: str) -> list[tuple[Mutant, str]]
    """Every single-point mutant of a Python source: (mutant, mutated source). Deterministic order: by line, column,
    then OPERATORS order. compare: < <-> <=, > <-> >=, == <-> != (one operator per Compare node, the first op).
    arith: + <-> - (BinOp only, not augmented assignment). boolop: and <-> or. not: `not x` -> `x`.
    const: an int literal n (not bool) -> n + 1. A source that does not parse yields []."""

def sample(items: list, cap: int) -> list
    """The whole list when len(items) <= cap; otherwise exactly cap items, evenly spaced (indices
    i * len(items) // cap for i in range(cap)), in order, the same every time."""

def score(project: Path, files: list[str], suites: dict[str, list[list[str]]], cap: int = MUTANTS_MAX,
          timeout_s: float = MUTANT_TIMEOUT_S, env: dict | None = None) -> dict | None
    """Runs every sampled mutant of the given production files against each suite. suites maps a name ("agents",
    "oracle") to the commands (argv lists) that must all exit 0 for the mutant to survive; one of them failing or
    timing out kills it. Each suite first runs once on the unmutated code: red or timed out there, its count is
    None and it is not run again. The original file is restored after each mutant, also on error. env None means
    os.environ. Commands run through compat.resolve and, on timeout, compat.kill_tree (whole process group), with
    cwd=project. Returns the block of section 5 with "killed" for the "agents" suite and "oracle_killed" for the
    "oracle" suite (None when that suite is missing or red at baseline), or None when there are no candidates.
    Every suite runs with PYTHONDONTWRITEBYTECODE=1 in its env, and the mutated file's __pycache__/<stem>.*.pyc
    files are deleted before each mutant and after the restore: a .pyc is validated by mtime in whole seconds and
    size, and same-size mutants written within one second would otherwise run the previous mutant's bytecode.
    Raises MutationError if a file cannot be read or written back."""

class MutationError(Exception)
```
`bench/bench.py` (WP-02):
```python
def manifest_of(project: Path) -> dict          # the json wp-manifest block of project/architecture.md; {} if absent or invalid
def production_files(project: Path, manifest: dict) -> list[str]    # section 4b rule; existing .py files, sorted, relative
def project_commands(manifest: dict) -> list[list[str]]             # verify.tests and acceptance.command, shlex-split, in that order
def _mutation(fixture: Path, project: Path, env: dict) -> dict | None
    """mutate.score(project, production_files, {"agents": project_commands, "oracle": [the oracle command of
    oracle_counts with -s/-t on fixture/oracle, cwd=project]}, env with PYTHONPATH=project). Called after
    _run_oracle has read its counts and removed project/.bench_oracle (so the agents' suites never see the oracle
    folder), only when the pipeline ended (not on timeout) and the result is OK or REVIEW; None otherwise.
    A MutationError is printed to stderr and yields None: a run is never lost to its instrument."""
```
`_run_oracle` removes `project/.bench_oracle` once it has its counts. The run's `seconds` keeps measuring the pipeline only (it is taken before the oracle runs today, `:356`): oracle and mutation time are the bench's, not the flow's. `_record(..., mutation: dict | None)` stores it under `"mutation"`. `_summarize` adds `mutation_median` and `mutation_oracle_median`. `TABLE_HEADER` gains `"Mutation"` after `"Oracle"`; `_rows` renders each half with two decimals or `?` (`0.72 / 0.90`, `0.00 / ?`, `?` when both are missing). `_print_runs` appends ` mutation {killed}/{total}` when present. `make_run(..., mutation=None)` in `test_bench.py`.

The `roster` fixture's plan (WP-03 writes it; these are its contracts, which the oracle and the references follow). Minutes since midnight as `int`; an interval is half-open `[start, end)`.
```python
# roster/intervals.py  (fixture WP-01, wave 1)
@dataclass(frozen=True)
class Interval:
    start: int
    end: int           # start < end, both in 0..2880 (an overnight shift ends on the next day: end > 1440)
def overlaps(a: Interval, b: Interval) -> bool          # touching intervals ([540, 720) and [720, 900)) do not overlap
def merge(intervals: list[Interval]) -> list[Interval]  # sorted by start; overlapping OR touching intervals become one; input not changed
def gaps(intervals: list[Interval], window: Interval) -> list[Interval]   # the parts of window not covered, sorted
# roster/shifts.py  (fixture WP-02, wave 1)
def parse_shift(text: str) -> Interval     # "09:00-17:30" -> Interval(540, 1050); "22:00-06:00" -> Interval(1320, 1800)
def format_shift(shift: Interval) -> str   # the inverse; an end past midnight prints as "06:00"
# roster/schedule.py  (fixture WP-03, wave 2, depends on fixture WP-01 and WP-02)
class ConflictError(ValueError)
class Schedule:                               # Schedule() takes no arguments
    def assign(self, person: str, day: date, shift_text: str) -> Interval
    def shifts(self, person: str) -> list[tuple[date, Interval]]      # sorted by day then start
    def coverage_gaps(self, day: date, window: Interval) -> list[Interval]
    def minutes(self, person: str) -> int
# roster/rules.py  (fixture WP-04, wave 2, depends on fixture WP-01 only, consumes Schedule.shifts by signature)
def rest_violations(shifts: list[tuple[date, Interval]], min_rest: int) -> list[tuple[date, date]]
```
Rules stated in the fixture plan's section 6/7 but **absent from its ACs** (trap a; the oracle's `test_edge_*` check them): `Interval` with `start >= end`, a negative start or an end above 2880 raises `ValueError` at construction; `overlaps` and `merge` treat touching intervals as not overlapping / as one; `parse_shift` rejects `"24:00-01:00"`, `"9:00-17:00"` (two digits each), `"09:00-09:00"` and `"09:60-10:00"` with `ValueError`; `assign` raises `ConflictError` when the new shift overlaps one of the same person on the same day, and a failed `assign` changes nothing; names are stripped and must be non-empty; `coverage_gaps` merges before computing; `minutes` sums lengths. The ACs cover the happy paths and at most two error cases, written so that the acceptance tests pass against the bad reference's happy path.

The bait (trap b; the oracle's `test_ctx_*` check it): two choices `rest_violations` cannot make from section 6 alone. (1) The boundary: a rest **equal** to `min_rest` is enough; only a strictly shorter rest is a violation. (2) The rest between consecutive shifts of a person is measured from the **real end** of the earlier shift, so an overnight shift that ends at `1800` on day D ends at `06:00` on D+1, and a shift starting `08:00` on D+1 leaves 120 minutes of rest. The fixture plan states both **only in its section 10** (`D3`), not in section 6, not in WP-04's block, not in any AC; section 6 for `rest_violations` says only "returns the `(day, day)` pairs of consecutive shifts of the list, in `(day, start)` order, with insufficient rest between them", and the ACs for WP-04 use rests far from the boundary and no overnight shift. The boundary is undecidable from the document an implementer gets: it must ask (`NEEDS_CONTEXT`) or guess, and a guess is wrong half the time. The bad reference uses `<=` and measures from `min(end, 1440)` (the same day's midnight).

## 7. Conventions
- The bench's style: `from __future__ import annotations`, type annotations on public signatures, UPPER_CASE constants at the top, small functions, errors as `BenchError`/`MutationError` with a one-line message; no shell (`argv` lists), `cwd=project`, timeouts on every subprocess.
- `mutate.py` imports nothing from `bench.py`; it may import `compat` the way `bench.py` does (`bench/bench.py:28-30`: `.claude/bin` on `sys.path`), for `compat.resolve` (so `python3` resolves on Windows) and `compat.kill_tree` (a timed-out suite dies with its grandchildren). `bench.py` imports `mutate` with `HERE` on `sys.path`, the same pattern.
- The fixture's plan and code in English, `python3` in its commands, no dependencies, the `#### WP-NN` and `- AC-NNN` headings exactly, `Check` paths under `acceptance/`. The words `oracle`, `reference`, `bait`, `trap` and `mutation` never appear in the fixture's plan or README.
- Tests: `unittest`, one behaviour per test; temp dirs via `tempfile.mkdtemp` and `addCleanup`; no real `claude` (the fake one from `testutil`).
- Forbidden: a mutation operator that changes several nodes at once; writing the oracle into the project before the pipeline ends; a `mutation` block without `total`, `killed`, `oracle_killed`, `timeouts`, `survived`.

## 8. Work packages and acceptance criteria
### Acceptance criteria
- AC-001 · Mutants are generated deterministically with the five operators
  - Scenario: the source `def f(a, b):\n    if a < b and not a:\n        return a + 3\n    return b` as `m.py`.
  - Action: `mutate.candidates(source, "m.py")` twice.
  - Expected: the two results are equal; the operators found, in order, are `["compare", "boolop", "not", "arith", "const"]`; the `compare` mutant's source contains `a <= b`, the `arith` one `a - 3`, the `const` one `return a + 4`, the `not` one `a < b and a`, the `boolop` one `a < b or not a`; every mutant has `line` 2 or 3 and `file == "m.py"`.
  - Must not: mutate `True`/`False` as integers; produce a mutant for a source that does not parse (`candidates("def (", "x.py") == []`); change two nodes in one mutant (each mutated source differs from `ast.unparse(ast.parse(source))` in exactly one line).
  - Check: `bench/acceptance/test_acceptance_quality.py::MutantTests::test_ac_001_candidates_are_deterministic`
  - WP: WP-01
- AC-002 · The sample is even, capped and deterministic
  - Scenario: `list(range(100))`.
  - Action: `mutate.sample(items, 40)`, `mutate.sample(items, 200)`, `mutate.sample([], 40)`.
  - Expected: 40 items, strictly increasing, first `0`, the gap between neighbours 2 or 3; the whole list, equal to `items`; `[]`.
  - Must not: use randomness (two calls give the same list).
  - Check: `bench/acceptance/test_acceptance_quality.py::MutantTests::test_ac_002_sample_is_even_and_capped`
  - WP: WP-01
- AC-003 · The score tells a strong suite from a weak one and restores the file
  - Scenario: a temp project with `src/calc.py` (`def add(a, b):\n    return a + b\n\n\ndef small(x):\n    return x < 3\n`: three candidates, `arith`, `compare`, `const`, none equivalent), `tests/test_strong.py` asserting `add(2, 3) == 5`, `small(2)` and `not small(3)`, `tests/test_weak.py` that only imports both, and `tests/test_red.py` asserting `add(1, 1) == 3` (red on the original code).
  - Action: `mutate.score(project, ["src/calc.py"], {"agents": [strong command], "oracle": [weak command]})`, with each command `[sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_<name>.py"]` and `PYTHONPATH` set to the project in `env`.
  - Expected: `total == 3`, `killed == 3`, `oracle_killed == 0`, `survived == []`, `timeouts == 0`; `src/calc.py` has its original bytes afterwards; with `{"agents": [weak command]}` alone, `killed == 0`, `len(survived) == 3` and each survived item has `file`, `line`, `operator`, `description`; with `{"agents": [red command]}` alone, `killed is None`, `survived == []` and `total == 3`.
  - Must not: leave a mutated file behind; return `None` when there are candidates; count a passing suite as a kill; count a suite that is red at baseline as killing anything.
  - Check: `bench/acceptance/test_acceptance_quality.py::ScoreTests::test_ac_003_strong_kills_weak_survives`
  - WP: WP-01
- AC-004 · A mutant that hangs is killed by the timeout, and no candidates means None
  - Scenario: `src/loop.py` with `def count(n):\n    i = 0\n    while i < n:\n        i = i + 1\n    return i` and a suite asserting `count(3) == 3` and `count(0) == 0`; and a second project whose only production file is `x = "a"`.
  - Action: `mutate.score(..., timeout_s=5)` on each.
  - Expected: first: `timeouts >= 1` and `killed == total` (the `+` to `-` mutant never ends and dies by timeout; `<` to `<=` returns 4; `i = 0` to `i = 1` fails `count(0) == 0`; `+ 1` to `+ 2` returns 4); second: `None`.
  - Must not: hang the bench; count the timeout as survived.
  - Check: `bench/acceptance/test_acceptance_quality.py::ScoreTests::test_ac_004_timeout_kills_and_empty_is_none`
  - WP: WP-01
- AC-005 · Each bench run records a mutation block and the report shows the column
  - Scenario: the `benchfix` fixture and the fake `claude` as `test_acceptance_bench.Sandbox` sets them up (`FAKE_WRITE=1`: the agents write `x = 1` into `src/a.py`, `src/b/x.py`, `src/c.py`; `acc.py` passes when those exist and no `.bench_oracle` folder is present; the oracle's `test_d` always fails because nobody writes `src/d.py`).
  - Action: `bench.py run --fixture benchfix --repeat 1 --out <dir>`; then `bench.py report --out <dir>`.
  - Expected: `runs[0]["mutation"]` is a dict with `total == 3` (one `const` mutant per `x = 1`), `killed == 0` (the acceptance script checks existence only), `oracle_killed is None` (the oracle is red at baseline), `survived` of length 3, `timeouts == 0`; `summary["benchfix"]["mutation_median"] == 0.0` and `mutation_oracle_median is None`; `RESULTS.md` has `Mutation` in its header and `0.00 / ?` in the row; the printed run line ends with ` mutation 0/3`.
  - Must not: run the mutation when the pipeline timed out (`--timeout-min 0.01` on the same fixture: `mutation` is `None` and the run is recorded as `timeout`); leave `.bench_oracle` in the project when the mutation runs (`acc.py` would be red and `killed` `None`); make a results file written by 2.1.0 (no `mutation` key) unreadable: `report` over a copy of `bench/results/2.1.0-20261101-145223-dcc313a.json` shows `?` in the column.
  - Check: `bench/acceptance/test_acceptance_quality.py::BenchTests::test_ac_005_mutation_in_results_and_report`
  - WP: WP-02
- AC-006 · The roster fixture is sound and names its traps
  - Scenario: the shipped `bench/fixtures/roster/`.
  - Action: `bench.py selftest --fixture roster`; the oracle over `reference/good` and over `reference/bad` with `-v`.
  - Expected: selftest prints `roster: ok`; the oracle has at least 24 tests, of which at least 8 named `test_edge_*` and at least 2 named `test_ctx_*`; `reference/good` passes all; `reference/bad` fails at least 4, and every failing test is named `test_edge_*` or `test_ctx_*` and at least one `test_ctx_*` fails.
  - Must not: pass any oracle test on the bare repo.
  - Check: `bench/acceptance/test_acceptance_quality.py::RosterTests::test_ac_006_sound_and_traps_named`
  - WP: WP-03
- AC-007 · The roster plan is valid, has the right shape, and hides the bait from the brief
  - Scenario: a copy of `repo/` with the flow installed (`FixtureReady.prepare("roster")`).
  - Action: `agentic.py validate`; read the manifest; `agentic.py briefs`; read `architecture.md` and `.claude/state/briefs/WP-04.md`.
  - Expected: `Manifest valid`; four packages, `WP-01` and `WP-02` in wave 1, `WP-03` in wave 2 depending on both, `WP-04` in wave 2 depending on `WP-01` only; the plan's section 10 contains `D3` and the phrase `real end`; `WP-04.md` does not contain `real end` and does not contain `D3 ·`; the plan contains none of `oracle`, `reference`, `bait`, `trap`, `mutation` (case-insensitive); the repo's own tests pass (`python3 -m unittest discover -s tests`).
  - Must not: state the rest rule in section 6, in WP-04's block or in an AC (`architecture.md` has exactly one occurrence of `real end`).
  - Check: `bench/acceptance/test_acceptance_quality.py::RosterTests::test_ac_007_plan_valid_and_bait_hidden`
  - WP: WP-03
- AC-008 · The bench runs roster end to end with the simulated agents
  - Scenario: the fake `claude` with `FAKE_WRITE` unset.
  - Action: `bench.py run --fixture roster --repeat 1 --out <dir>`.
  - Expected: exit 0; one results file with one run of fixture `roster`, `oracle.total >= 24`, a `mutation` key present (a dict or `null`).
  - Must not: write the oracle into the project before the pipeline (the run's `result` is what the engine said, and the oracle's `.bench_oracle` folder is not in the fixture's `repo/`).
  - Check: `bench/acceptance/test_acceptance_quality.py::RosterTests::test_ac_008_bench_runs_roster`
  - WP: WP-03

### Work packages
#### WP-01 · The mutation module
- Wave 1.
- Files: `bench/mutate.py`, `bench/test_mutate.py`.
- Implements `Mutant`, `OPERATORS`, `MUTANTS_MAX`, `MUTANT_TIMEOUT_S`, `MutationError`, `candidates`, `sample`, `score` (section 6). Consumes nothing.
- ACs: AC-001, AC-002, AC-003, AC-004.
- Patterns to mirror: `bench/bench.py:28-66` (constants, `BenchError`), `:275-294` (`oracle_counts`: `subprocess.run` with `cwd`, `env`, `capture_output`, `timeout`, `stdin=DEVNULL`, the `(OSError, subprocess.SubprocessError)` catch), `:167-183` (`remove_tree`: retry and restore patterns), `bench/test_bench.py:1-33` (module loading, `TempCase`).
- Gotchas: stale bytecode (section 6): set `PYTHONDONTWRITEBYTECODE=1` and delete the mutated module's `.pyc` files before each mutant and after the restore; a unit test with two same-size mutants of one line (`x = 1` and `x = 2` against a weak-then-strong pair of asserts) proves the code is really reloaded. `ast.unparse` loses comments and formatting, so the mutated source is the unparsed tree; write it with `encoding="utf-8"` and restore the **original bytes** (read them once with `read_bytes`) in a `finally`. Candidates come from the original tree: collect `(lineno, col_offset, operator, node_id)` on one walk, then for each candidate `copy.deepcopy` the tree and mutate that node only (match by the walk index, not by identity across copies). `Compare` nodes may have several `ops`: mutate `ops[0]` only. `const` skips `bool` (a subclass of `int`) and skips constants inside annotations and docstrings. `not` applies to `UnaryOp(Not)` only. `arith` applies to `BinOp` with `Add`/`Sub`, not `AugAssign`. Run each command as `subprocess.Popen(compat.resolve(argv), cwd=project, env=env, stdin=DEVNULL, stdout=PIPE, stderr=STDOUT, **compat.group_kwargs())`, then `communicate(timeout=timeout_s)`; on `TimeoutExpired`, `compat.kill_tree(proc.pid)` and `communicate()` again, and the mutant counts as killed. No `subprocess.run(timeout=)`: it leaves grandchildren alive. Commands run from `cwd=project` with the given `env` (the caller sets `PYTHONPATH`). Python 3.9 compatible: no `match`, no `X | Y` at runtime outside annotations under `from __future__ import annotations`.
- Exact imports and APIs: `ast`, `copy`, `dataclasses`, `os`, `pathlib`, `subprocess`, `sys`; `compat.resolve` and `compat.kill_tree` from `.claude/bin/compat.py` (`sys.path` as `bench.py:28-30`). On timeout: `subprocess.Popen(...)` in its own group (`compat.group_kwargs()`), `communicate(timeout=)`, then `compat.kill_tree(proc.pid)`, as `run_command()` in `.claude/bin/agentic.py:1224-1243` does.
- WP validation: `python3 -m unittest discover -s bench -p test_mutate.py`; `python3 -m compileall -q bench`.

#### WP-02 · Mutation per run, summary and report
- Wave 2, `depends_on: ["WP-01"]`.
- Files: `bench/bench.py`, `bench/test_bench.py`.
- Implements `manifest_of`, `production_files`, `project_commands`, `_mutation`, the `_run_oracle` cleanup, the `_record`/`_summarize`/`_rows`/`_print_runs` changes (section 6). Consumes `mutate.score` by implementation (WP-01, wave 1: `import mutate` at the top of `bench.py` needs the module to exist); the unit tests stub `mutate.score` with `unittest.mock.patch.object(bench.mutate, "score", ...)`.
- ACs: AC-005.
- Patterns to mirror: `bench/bench.py:345-376` (`_run_once`, `_record`), `:412-427` (`_summarize`, `_summaries`), `:488-502` (`_rows`), `:566-572` (`_print_runs`), `:28-30` (how `compat` is imported, for `mutate`), `bench/acceptance/test_acceptance_fixtures.py:34-38` (`manifest_of` regex), `bench/test_bench.py:102-130` (`SummaryTests`, `ReportTests`).
- Gotchas: `_mutation` runs after `_run_oracle`, which now removes `.bench_oracle` once it has counted (`remove_tree`); the oracle ceiling points `-s`/`-t` at `fixture/oracle` directly; it must not run on a timed-out pipeline (the project may be half-written and the test commands may hang) and must swallow `MutationError` into `None` with a line on stderr. The oracle command is the one of `oracle_counts` (`[sys.executable, "-m", "unittest", "discover", "-s", str(fixture / "oracle"), "-t", str(fixture / "oracle")]`) with `PYTHONPATH=project` in `env`; the agents' commands run with the same env. `production_files` follows the section 4b rule (every `.py` under the listed paths, minus `tests/`, `test_*.py`, `acceptance.files`, `qa.files`; `__init__.py` included). `_summarize` must accept runs without the key (`make_run` default) and 2.1.0 results files (`_rows` renders `?`). Keep `SCHEMA = 1`. The `Mutation` column goes right after `Oracle` in `TABLE_HEADER` and in the row.
- Exact imports and APIs: `import mutate` after `sys.path.insert(0, str(HERE))` next to the `compat` import (`:28-30`), `shlex.split`, `re`.
- WP validation: `python3 -m unittest discover -s bench -p test_bench.py`; `python3 -m compileall -q bench`.

#### WP-03 · The roster fixture
- Wave 1.
- Files: `bench/fixtures/roster/` (everything under it).
- Implements the fixture of section 6: `fixture.json`, `repo/` (README, `roster/__init__.py`, `tests/test_version.py`, `architecture.md`), `oracle/test_oracle.py`, `reference/good/roster/{intervals,shifts,schedule,rules}.py`, `reference/bad/roster/` (the same four). Consumes nothing.
- ACs: AC-006, AC-007, AC-008.
- Patterns to mirror: `bench/fixtures/tally/repo/architecture.md:1-284` (the plan: sections, contracts with concrete values, one AC per behaviour with `Check` under `acceptance/`, `#### WP-NN` blocks, the manifest with `stack`, `allow_bash`, `acceptance`, `verify`, `docs`), `bench/fixtures/tally/oracle/test_oracle.py:1-60` (imports inside each test, `test_edge_*`), `bench/fixtures/tally/reference/bad/tally/money.py:1-24` (plausible and wrong on the edges), `bench/fixtures/tally/repo/tests/test_version.py`, `bench/fixtures/vault/fixture.json`.
- Gotchas: the fixture's plan must pass `agentic.py validate` once the flow is installed in a copy (`FixtureReady.prepare` does that): `mirror` entries must point at existing lines of the seed files (`roster/__init__.py:1-3`, `tests/test_version.py:1-15`), `acs` listed per package, the `docs` zone `["README.md"]` with `"codemap": null`, no `__init__.py` in `tests/` or `acceptance/`. The bait: section 10 of the fixture plan, decision `D3`, is the **only** place with the rest rule and the phrase `real end`; section 6 describes `rest_violations` without it; WP-04's block and ACs stay silent (AC-007 counts the phrase once). The fixture plan's ACs cover happy paths and at most two error cases so the acceptance tests pass against `reference/bad`'s happy path; every edge rule of section 6 is checked by a `test_edge_*` oracle test, the bait by `test_ctx_*` tests (a rest of exactly 480 with `min_rest` 480 is not a violation; an overnight shift followed by an early shift: 120 minutes of rest with `min_rest` 480 is a violation, which the bad reference misses). `reference/bad` must pass every oracle test that is not `test_edge_*` or `test_ctx_*`. Dates are `datetime.date`; `shifts` sorts by `(day, start)`. The fake `claude` writes nothing for this fixture, so AC-008 only checks the run completes.
- Exact imports and APIs: standard library only in the fixture (`dataclasses`, `datetime`, `re`).
- WP validation: `python3 bench/bench.py selftest --fixture roster`; `python3 -m unittest discover -s bench/fixtures/roster/repo/tests`.

```json wp-manifest
{
  "stack": ["python"],
  "allow_bash": ["Bash(python3 -m unittest:*)", "Bash(python3 -m compileall:*)", "Bash(python3 bench/bench.py selftest:*)"],
  "acceptance": {"files": ["bench/acceptance/"], "command": "python3 -m unittest discover -s bench/acceptance -p test_acceptance_quality.py"},
  "verify": {"build": "python3 -m compileall -q bench", "tests": "python3 -m unittest discover -s bench -p test_*.py", "lint": "python3 -m unittest discover -s bench/acceptance -p test_acceptance_*.py"},
  "docs": {"files": ["README.md", "docs/how-to/", "docs/roadmap/"], "codemap": null},
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": ["bench/mutate.py", "bench/test_mutate.py"],
     "acs": ["AC-001", "AC-002", "AC-003", "AC-004"], "mirror": ["bench/bench.py:28-66", "bench/bench.py:275-294", "bench/test_bench.py:1-33"]},
    {"id": "WP-02", "wave": 2, "depends_on": ["WP-01"], "files": ["bench/bench.py", "bench/test_bench.py"],
     "acs": ["AC-005"], "mirror": ["bench/bench.py:345-376", "bench/bench.py:412-427", "bench/bench.py:488-502", "bench/acceptance/test_acceptance_fixtures.py:34-38"]},
    {"id": "WP-03", "wave": 1, "depends_on": [], "files": ["bench/fixtures/roster/"],
     "acs": ["AC-006", "AC-007", "AC-008"], "mirror": ["bench/fixtures/tally/repo/architecture.md:1-284", "bench/fixtures/tally/oracle/test_oracle.py:1-60", "bench/fixtures/tally/reference/bad/tally/money.py:1-24", "bench/fixtures/vault/fixture.json"]}
  ]
}
```

## 9. Test strategy
- Unit: WP-01 in `bench/test_mutate.py` (each operator on a one-line source, bool and docstring constants skipped, `Compare` with two ops mutates the first, unparseable source, `sample` edges, `score` with stub commands such as `python -c "import sys; sys.exit(1)"`, restore on error); WP-02 in `bench/test_bench.py` (`production_files` on a manifest with a directory, a tests path and a missing file; `project_commands`; `_summarize` with and without `mutation`; `_rows` with `?`; `_mutation` with `mutate.score` patched to return a block, to return `None`, to raise `MutationError`); WP-03 through `selftest` and its own version test.
- Acceptance: `bench/acceptance/test_acceptance_quality.py`, AC-001…AC-008, written first and red. AC-005 and AC-008 use the fake `claude` (no spend); AC-008 takes about as long as the existing end-to-end run of two fixtures (`test_acceptance_fixtures.py:143-171`, not measured here).
- QA: exploratory over `mutate` (a file with syntax error after the agents, a mutant that writes to disk, a test command that is missing, a production file deleted by an agent, a non-UTF-8 source) and over the fixture (the bad reference against every `test_edge_*`; a plan whose `Check` paths are consistent with the manifest's `acceptance.files`).
- After merging, by hand: `python3 bench/bench.py run` (five fixtures, three sessions) with the real `claude`; the new columns are the first quality signal; the roster rows say whether fix cycles or `NEEDS_CONTEXT` appear.

## 10. Decisions
- **D1 · Agents' suite plus an oracle ceiling (user's choice):** a kill rate alone has no scale; the oracle, written by a person, says what a strong suite kills on the same mutants. Discarded: agents' tests only; unit tests only (the acceptance tests are the flow's judge and belong in the measure).
- **D2 · Five classic operators, cap 40, even sample (user's choice):** enough signal at a bounded cost (40 runs of a suite that takes seconds). Discarded: no cap (minutes per run on a large suite); three operators (too coarse to tell suites apart).
- **D3 · Fix-cycle trap plus a NEEDS_CONTEXT bait (user's choice):** the gate cannot be forced by a fixture (section 1); fix cycles come from reviewer/QA findings the acceptance tests do not see; the bait tests the one status the plan can provoke. Discarded: a cross-WP ambiguity (would mostly produce false gate denials on the first finisher).
- **D4 · The bait lives in section 10:** `brief.py` leaves Decisions out of an implementer's brief (`WP_SECTIONS`), so a well-behaved implementer must ask (`NEEDS_CONTEXT`) and finds the answer in the whole document; an implementer that invents a reading is caught by `test_ctx_*`. Discarded: hiding it in another package's block (unnatural in a real plan; section 10 is where such a decision belongs).
- **D5 · No mutation check in `selftest`:** a check "the oracle kills at least one mutant of reference/good" would flag the bench's own test fixtures (`x = 1` files, existence-only oracles) and every fixture with a trivial seed. The instrument is covered by its unit and acceptance tests instead; the ceiling in each run shows whether the oracle is strong.
- **D6 · A separate module `mutate.py`:** `bench.py` is 618 lines and one purpose; mutation is another. `bench.py` loads it by path, as it does `compat`.
- **D7 · Mutation only on a finished pipeline:** a timed-out run may have half-written code; a hanging suite would cost 40 timeouts. `None` says "not measured".
- **D8 · `ast.unparse` rather than text patching:** exact, single-node, standard library; the lost formatting does not matter in a throwaway copy. Python 3.9 is the floor the bench already states.
- **D9 · This plan is run by `/implement`:** nothing it owns is under `.claude/`, so for the first time the flow implements a change of its own repo. The docs zone is the doc-updater's.

## 11. Risks and open questions
- **The traps may not bite:** the roster fixture is designed so that acceptance passes while the oracle fails on the edges, but Sonnet implementers may read section 6 carefully and handle every edge; then roster behaves like tally and the fix-cycle signal stays at zero. That is a result too; the mutation score still measures test quality regardless.
- **The bait may be answered by guessing:** an implementer may pick `<` or `<=` without `NEEDS_CONTEXT`; half the guesses are wrong and the oracle penalises them (`test_ctx_*`), which is the measurable outcome either way. The overnight half of the bait can be inferred by a careful reader from `end > 1440`; it is the boundary half that cannot.
- **Mutation cost:** up to 40 runs of two suites plus 40 of the oracle per session; on these fixtures a suite takes about a second (not measured), so about two minutes per session. A project with a slow suite would pay more; `MUTANTS_MAX` and `MUTANT_TIMEOUT_S` bound it.
- **Equivalent mutants:** some mutants do not change behaviour (a `+ 1` on an unused constant) and can never be killed; the rate is comparative across versions, not absolute, and the oracle ceiling shows the share that is killable.
- **Time:** the mutation adds up to 40 suite runs per session to every end-to-end acceptance run and to CI (the fake-claude fixtures have 3 or 0 candidates, so seconds there; the roster fixture with real agents, about two minutes per session, not measured). The existing bench acceptance suites take 51 s together (measured here, 19 tests), so `verify.lint` fits the flow's 900 s limit with room for the new runs.
- **Fake-claude runs produce no meaningful score:** AC-005 checks the plumbing (keys, zeroes, column), not the measure; the measure is only visible with a real `claude`.
