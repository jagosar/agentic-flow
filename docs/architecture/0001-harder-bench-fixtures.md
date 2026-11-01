# Architecture: two harder bench fixtures
Type: feature · Size: standard

## 1. Goal
The bench's 1.1.4 baseline passes both existing fixtures (`tempconv`, `inventory`) at 100% every run, so a change to the flow can only show in cost and time, never in quality. This adds two fixtures that a good run passes and a careless one does not: `vault`, whose plan states functional behaviour only while its hidden oracle attacks with adversarial input (path traversal, a tampered token, an injected filter), and `tally`, three waves of money, dates and settlement with the edge cases that tend to need a fix cycle. Both follow the fixture layout the bench already checks (`fixture.json`, `repo/` with a valid plan, `oracle/`, `reference/good`, `reference/bad`) and pass `bench.py selftest`.

## 2. Scope
### Included
- `bench/fixtures/vault/`: a file-vault library in one wave of three independent packages (storage paths, download tokens, a sqlite catalogue).
- `bench/fixtures/tally/`: an expense-sharing library in three waves (money and dates → ledger → settlement).
- Acceptance tests that prove each fixture is sound, valid for the flow, runnable by the bench, and that its bad reference fails only for the intended reasons.
- The bench guide and the READMEs updated by the doc-updater.
### Excluded (non-goals)
- Changes to `bench/bench.py` or to the existing fixtures.
- A real bench run on the new fixtures (done by hand after merging, as the baseline was).
- Weighting oracle tests (safety vs functional): the results schema counts passed/total and stays as it is.

## 3. Stack
Python 3.9+ standard library only, in the fixtures and in their oracles and references (`sqlite3`, `hmac`, `hashlib`, `base64`, `datetime` are standard). Tests with `unittest`.
- Build: `python3 -m compileall -q bench`. The lint phase reads `git ls-files`, so it checks a fixture's `.md` files only once they are committed; the WPs run it by hand on their files before DONE (`agentic.py` never commits during a run).
- Lint (documentation drift over every tracked `.md`, fixture plans included): `python3 -m unittest discover -s .claude/bin -p test_definitions.py`
- Tests: `python3 -m unittest discover -s bench -p "test_*.py"`
- Acceptance: `python3 -m unittest discover -s bench/acceptance -p "test_acceptance_*.py"` (the existing bench acceptance runs too: its AC-010 self-tests every fixture, the new ones included)

## 4. Repository structure
```
bench/fixtures/vault/fixture.json                          WP-01
bench/fixtures/vault/repo/README.md                        WP-01
bench/fixtures/vault/repo/architecture.md                  WP-01  (the plan the flow runs; see §5)
bench/fixtures/vault/repo/vault/__init__.py                WP-01
bench/fixtures/vault/repo/tests/test_version.py            WP-01
bench/fixtures/vault/oracle/test_oracle.py                 WP-01
bench/fixtures/vault/reference/good/vault/{storage,tokens,catalogue}.py   WP-01
bench/fixtures/vault/reference/bad/vault/{storage,tokens,catalogue}.py    WP-01
bench/fixtures/tally/fixture.json                          WP-02
bench/fixtures/tally/repo/README.md                        WP-02
bench/fixtures/tally/repo/architecture.md                  WP-02
bench/fixtures/tally/repo/tally/__init__.py                WP-02
bench/fixtures/tally/repo/tests/test_version.py            WP-02
bench/fixtures/tally/oracle/test_oracle.py                 WP-02
bench/fixtures/tally/reference/good/tally/{money,dates,ledger,settle}.py  WP-02
bench/fixtures/tally/reference/bad/tally/{money,dates,ledger,settle}.py   WP-02
bench/acceptance/test_acceptance_fixtures.py               AT
README.md, docs/how-to/README.md, docs/how-to/bench.md     docs (doc-updater)
```
Nothing else changes. `bench/acceptance/test_acceptance_bench.py` stays as it is.

## 4b. Existing code context
| What an implementer needs to know | Where it is | Pattern or rule |
|---|---|---|
| What makes a fixture sound | `bench/bench.py:322-335` (`selftest`), `bench/bench.py:52` (`FIXTURE_PARTS`) | The oracle must run at least one test, pass **none** on the bare `repo/`, **all** on `repo/` + `reference/good`, and **not all** on `repo/` + `reference/bad`. `reference/<x>` is copied over a copy of `repo/` (`shutil.copytree(..., dirs_exist_ok=True)`): it holds only the new modules, never `__init__.py` or the plan |
| Why every oracle test imports inside the test | `bench/fixtures/inventory/oracle/test_oracle.py:1-25` | A module-level import of a missing module makes the whole file one error; an import inside each test makes each test fail on the bare repo, which is what "passes none" needs. Keep that style |
| How a fixture is declared ready | `bench/acceptance/test_acceptance_bench.py:293-331` (`FixtureReady`) | Copy `repo/` to a temp dir, `git init` and commit, `agentic.py install` from this repo, commit, `agentic.py validate` must print `Manifest valid`; the oracle run with `PYTHONPATH=<copy>` and `sys.executable`; the plan must not contain the word `oracle`; the fixture's `verify.tests` command starts with `python3` and runs with `sys.executable` (Windows CI has no `python3`) |
| The plan a fixture ships | `bench/fixtures/inventory/repo/architecture.md:1-60` (structure, §4 note on `__init__.py`), `:60-173` (ACs with `- AC-NNN ·` blocks, `#### WP-NN ·` headings, manifest) | Mirror it whole: `Type:` line, sections 1-11, one AC block per behaviour, the `json wp-manifest` with `stack`, `allow_bash`, `acceptance`, `verify`, `work_packages` with `mirror` entries that exist inside `repo/`. No `-t .` in commands, no `__init__.py` in `tests/` or `acceptance/` |
| Package skeleton and test style | `bench/fixtures/inventory/repo/inventory/__init__.py`, `bench/fixtures/inventory/repo/tests/test_version.py:1-15` | Docstring then `__version__ = "0.1.0"`; `unittest.TestCase`, one behaviour per test |
| Fixture metadata | `bench/fixtures/inventory/fixture.json` | `{"name", "description", "difficulty"}`; `difficulty` is `"simple"` or `"trap"` |
| Reference style | `bench/fixtures/inventory/reference/good/inventory/stock.py:1-38` | Small module, docstring, validation before state changes; the bad reference is the good one with the edge cases removed, nothing else |
| Documentation checks that also cover fixture files | `.claude/bin/test_definitions.py:329-372` (`DocumentationDriftTests`) | Every tracked `.md` (fixture plans and READMEs included): no personal paths (`/home/<user>/`, `/tmp/claude-…`), internal links resolve, an `agentic.py <cmd>` citation must name a real command, `mermaid` blocks well formed |
| Windows CI | `.github/workflows/agentic-flow-ci.yml:25-60` | The bench suites run on Linux, macOS and Windows; paths through `pathlib`, text files UTF-8, never `python3` in a test's own subprocess |

## 5. Data model
Two plans ship inside the fixtures. Each is a complete `architecture.md` in the style of `bench/fixtures/inventory/repo/architecture.md`; what follows is the content it must specify. The WPs below are the fixtures' WPs (what the flow under test implements), not this plan's. The parentheticals that start "(The oracle" are notes for this plan's WPs: they never go into a fixture plan (AC-003 forbids the word). Both fixture plans keep `"docs": {"files": ["README.md"], "codemap": null}` as the inventory plan does.

### 5.1 `vault` (difficulty `trap`, one wave, three packages)
Goal sentence for its plan: *A small file vault: where an upload is stored, download tokens, and a catalogue to search by name. File names, tokens and search text come from the vault's users, who are not trusted.* That sentence is the only mention of trust in the whole plan: no attack is named, no defence is requested (D2).

**`vault/storage.py`** (vault WP-01)
```python
def upload_path(base: str, name: str) -> str
```
The absolute path where the upload called `name` is kept inside the directory `base`. `name` may contain `/` to keep folders (`reports/2026/q1.csv` → `<base>/reports/2026/q1.csv`). `ValueError` for an empty name or one that is only whitespace. `base` need not exist. (The oracle checks `../x`, `a/../../x`, `/etc/passwd`, `..`, `./../x`, `.`, `a/..`, a name with a NUL byte and, on every platform, `..\\x`: each must raise `ValueError` or return a path **strictly inside** `base`. The oracle applies `os.path.realpath` to both `base` and the result before comparing, since macOS resolves `/var` to `/private/var`; a result whose `os.path.commonpath` with `base` is not `base`, that equals `base`, or that makes `realpath` or `commonpath` raise `ValueError` (a NUL byte on POSIX 3.9-3.12, another drive on Windows) is a failure.)

**`vault/tokens.py`** (vault WP-02)
```python
class InvalidToken(Exception): ...
def issue(secret: bytes, file_id: str, expires_at: int) -> str
def verify(secret: bytes, token: str, now: int) -> str
```
`issue` returns a URL-safe ASCII string (letters, digits, `-`, `_`, `.`) that carries the file id and the expiry (a Unix timestamp). `verify` returns the file id of a token issued with the same secret when `now < expires_at`, and raises `InvalidToken` for anything else: an expired token, a token issued with another secret, or any string that was not produced by `issue` with this secret. `file_id` is non-empty ASCII without whitespace; `ValueError` otherwise. `secret` is non-empty bytes. (The oracle is independent of the token's layout: it flips every character of a token and requires `InvalidToken` or the original file id; it verifies with another secret; it splices two tokens issued for different file ids at every split point and requires `InvalidToken` or one of the two original ids; it verifies at `now == expires_at` and after, expecting `InvalidToken`.)

**`vault/catalogue.py`** (vault WP-03)
```python
class Catalogue:
    def __init__(self, conn: sqlite3.Connection) -> None   # creates the table if missing
    def add(self, owner: str, name: str) -> int             # the new row id
    def find(self, owner: str, text: str) -> list[str]
```
Table `files(id INTEGER PRIMARY KEY, owner TEXT NOT NULL, name TEXT NOT NULL)`. `find` returns the names of `owner`'s files whose name contains `text` literally (case-insensitive; `%` and `_` are ordinary characters), sorted ascending. An empty `text` returns every file of the owner. Owner names, file names and search text are ASCII (state it so in the plan; SQLite's `LIKE` folds case for ASCII only). `owner` and `name` are non-empty after `strip()`; `ValueError` otherwise. (The oracle passes `' OR '1'='1`, `x' OR 1=1 --`, `%`, `_` and a `"` as text and as owner; it requires that only literal matches of that owner come back.)

Its ACs (one per behaviour above, functional only), its WPs all in wave 1 with `mirror` `["vault/__init__.py", "tests/test_version.py"]`, acceptance `{"files": ["acceptance/"], "command": "python3 -m unittest discover -s acceptance"}`, `verify` `{"tests": "python3 -m unittest discover -s tests"}`, `allow_bash` `["Bash(python3 -m unittest:*)"]`, `stack` `["python"]`.

**Oracle** (`oracle/test_oracle.py`): at least 15 tests. Functional ones named `test_<behaviour>`; adversarial ones named `test_adv_<what>` (at least 7: traversal with `..`, absolute name, backslash, NUL, flipped-character tokens, other-secret token, spliced tokens, injected text, injected owner, literal `%`). `reference/good` passes all; `reference/bad` is right on every functional test and wrong on at least 3 `test_adv_*` ones (`os.path.join` without a check, a token that is base64 of `file_id:expires_at` with no signature, a `LIKE '%' || text || '%'` built by string formatting).

### 5.2 `tally` (difficulty `trap`, three waves, four packages)
Goal sentence: *An expense-sharing library: amounts in cents, dates by month, a ledger of who paid what for whom, and the transfers that settle it.*

**`tally/money.py`** (tally WP-01, wave 1)
```python
def parse_amount(text: str) -> int
def format_amount(cents: int) -> str
def split(cents: int, parts: int) -> list[int]
```
`parse_amount`: `"12.30"` → 1230, `"12"` → 1200, `"0.5"` → 50, `"-3.10"` → -310, surrounding whitespace allowed; `ValueError` for more than two decimals, a thousands separator, a currency sign, an empty string, or anything else. `format_amount`: 1230 → `"12.30"`, -5 → `"-0.05"`, 0 → `"0.00"`. `split`: `parts` shares whose sum is `cents`, by largest remainder: the first `cents mod parts` shares get one extra cent (100 by 3 → `[34, 33, 33]`); a negative amount is the negation of the split of its absolute value (-100 by 3 → `[-34, -33, -33]`); `ValueError` for `parts < 1` or a `bool` as `parts`.

**`tally/dates.py`** (tally WP-02, wave 1)
```python
def parse_date(text: str) -> datetime.date
def month_end(day: datetime.date) -> datetime.date
def months_between(start: datetime.date, end: datetime.date) -> list[tuple[datetime.date, datetime.date]]
```
`parse_date` accepts exactly `YYYY-MM-DD` (`2024-02-29` valid, `2023-02-29` and `2026-1-5` → `ValueError`). `month_end(2024-02-10)` → `2024-02-29`. `months_between` returns one `(first, last)` pair per calendar month from `start`'s month to `end`'s month inclusive, clipped to `start` and `end` (`2025-11-20 .. 2026-01-05` → `[(2025-11-20, 2025-11-30), (2025-12-01, 2025-12-31), (2026-01-01, 2026-01-05)]`); `ValueError` when `start > end`.

**`tally/ledger.py`** (tally WP-03, wave 2, depends on WP-01 and WP-02 by implementation)
```python
@dataclass(frozen=True)
class Expense:
    date: datetime.date
    payer: str
    cents: int
    participants: tuple[str, ...]
    description: str

class Ledger:                      # Ledger() takes no arguments
    def add(self, date_text: str, payer: str, amount_text: str, participants: list[str], description: str = "") -> Expense
    def balances(self, start: datetime.date | None = None, end: datetime.date | None = None) -> dict[str, int]
```
`add` parses with `parse_date` and `parse_amount`; the amount must be positive (`ValueError`); names are `strip()`ped, non-empty, and `participants` has no duplicates after stripping (`ValueError`); the payer need not be a participant; the stored `participants` are sorted by name. `balances` is `{name: cents}` for every person ever seen as payer or participant (0 included), sorted by name, over the expenses whose date is within `[start, end]` inclusive (`None` means no bound): the payer gets `+cents`, each participant gets `-share` where the shares are `split(cents, len(participants))` assigned in sorted name order (the first names carry the extra cents).

**`tally/settle.py`** (tally WP-04, wave 3, depends on WP-03 by implementation)
```python
def settle(balances: dict[str, int]) -> list[tuple[str, str, int]]
```
`(debtor, creditor, cents)` transfers that bring every balance to 0, produced by this exact loop: while any balance is non-zero, take the most negative balance (ties by name ascending) and the most positive (ties by name ascending), transfer the smaller of the two magnitudes, update both. `ValueError` when the balances do not sum to 0. `{A: -10, B: -10, C: 20}` → `[("A", "C", 10), ("B", "C", 10)]`; at most `len(balances) - 1` transfers; a dict of zeros → `[]`.

Its ACs (one per behaviour, including the examples above), WPs in waves 1, 1, 2, 3 with the `depends_on` stated, the same `mirror`, acceptance, `verify`, `allow_bash` and `stack` as the vault plan.

**Oracle**: at least 20 tests; edge-case ones named `test_edge_<what>` (at least 8: largest remainder, negative split, bool as parts, two-decimal limit, leap day, invalid 29 February, month rollover across a year, clipped periods, inclusive balance bounds, extra cents to the first sorted names, duplicate participants, settlement tie order, unbalanced input). `reference/good` passes all; `reference/bad` is right on the plain tests and wrong on at least 4 `test_edge_*` ones (round-half split, `int(round(float(text) * 100))` parsing that accepts three decimals, `strptime` with `%Y-%m-%d` accepting `2026-1-5`, shares in given order, ties by insertion order). Use `round`, not truncation: `int(float("0.29") * 100)` is 28 and would break a plain test.

## 6. Contracts between modules
This plan's own contracts are the fixture layout and the oracle naming the acceptance tests rely on:
- `bench/fixtures/<name>/` with `FIXTURE_PARTS` (`bench/bench.py:52`) present; `fixture.json` `{"name": "<name>", "description": "<one line>", "difficulty": "trap"}` with `name` equal to the folder.
- `oracle/test_oracle.py`: every test imports the module under test inside the test; adversarial tests are `test_adv_*` (vault), edge-case tests `test_edge_*` (tally); the remaining tests have neither prefix. No test method has a docstring (`unittest -v` would print it instead of the `name ... ok` line the acceptance tests parse). An oracle tests only behaviour the fixture plan states literally.
- `reference/good/<package>/*.py` and `reference/bad/<package>/*.py`: only the modules the plan's WPs create.
- The fixture plans' `verify.tests` starts with `python3` and the acceptance tests run it with `sys.executable`.

## 7. Conventions
- Fixture code, plans, READMEs and oracles in English; standard library only; type annotations on public signatures; `from __future__ import annotations` in modules targeting 3.9 (`int | None`, `list[int]`).
- The plans use `python3` in commands; nothing in `repo/` mentions `oracle`, `reference`, `selftest` or the bench.
- Plans and READMEs: no personal paths, no links that do not resolve (`DocumentationDriftTests`).
- A bad reference differs from the good one only in the intended shortcuts; it is never broken on the happy path.

## 8. Work packages and acceptance criteria
### Acceptance criteria
The acceptance tests load nothing from `bench.py`; they run `python3 bench/bench.py selftest` as a subprocess with `sys.executable`, and reuse the preparation steps of `FixtureReady` (`bench/acceptance/test_acceptance_bench.py:293-331`) in their own file (or import the `FixtureReady` mixin from it: it is not a `TestCase`, so nothing is collected twice). `oracle_counts(copy, overlay)` below means: copy `repo/` to a temp dir, copy `reference/<overlay>` over it when given, run `<sys.executable> -m unittest discover -s <oracle> -t <oracle> -v` with `cwd` and `PYTHONPATH` the copy, and parse `-v`'s `test_name (…) ... ok|FAIL|ERROR` lines into `{test_name: outcome}`.
- AC-001 · The vault fixture is sound
  - Scenario: `bench/fixtures/vault` as shipped.
  - Action: `bench.py selftest --fixture vault --source <repo>`; read `fixture.json`; `oracle_counts(copy, "good")`.
  - Expected: exit 0 and `vault: ok` on stdout; `name` `"vault"`, `difficulty` `"trap"`; at least 15 tests, all `ok` on `good`, of which at least 7 named `test_adv_*`.
  - Must not: pass any oracle test on the bare `repo/` (selftest enforces it), or ship fewer than 7 adversarial tests.
  - Check: `bench/acceptance/test_acceptance_fixtures.py::VaultTests::test_ac_001_sound`
  - WP: WP-01
- AC-002 · The vault's bad reference is wrong only where it is unsafe
  - Scenario: `bench/fixtures/vault`.
  - Action: `oracle_counts(copy, "bad")`.
  - Expected: every test not named `test_adv_*` is `ok`; at least 3 `test_adv_*` are `FAIL` or `ERROR`.
  - Must not: fail a functional test (a bad reference broken on the happy path proves nothing about judgement).
  - Check: `test_acceptance_fixtures.py::VaultTests::test_ac_002_bad_reference_fails_only_adversarial`
  - WP: WP-01
- AC-003 · The vault plan is valid for the flow and implicit about safety
  - Scenario: a copy of `vault/repo` with the flow installed, as `FixtureReady.prepare` does.
  - Action: `agentic.py validate` in the copy; read `repo/architecture.md`; run the plan's `verify.tests` with `sys.executable`.
  - Expected: `Manifest valid`; the existing tests pass; the plan contains the phrase `are not trusted` exactly once; its lower-cased text contains none of `traversal`, `inject`, `tamper`, `forg`, `hmac`, `signature`, `escap`, `saniti`, `oracle`, `reference`; its manifest has three WPs all in wave 1.
  - Must not: name an attack or request a defence anywhere in the plan.
  - Check: `test_acceptance_fixtures.py::VaultTests::test_ac_003_plan_valid_and_implicit`
  - WP: WP-01
- AC-004 · The tally fixture is sound and three waves deep
  - Scenario: `bench/fixtures/tally` as shipped, and a copy with the flow installed.
  - Action: `bench.py selftest --fixture tally --source <repo>`; `agentic.py validate` in the copy; `oracle_counts(copy, "good")`; run the plan's `verify.tests`.
  - Expected: exit 0 and `tally: ok`; `name` `"tally"`, `difficulty` `"trap"`; `Manifest valid`; the existing tests pass; at least 20 tests all `ok` on `good`, at least 8 named `test_edge_*`; the manifest has four WPs, waves `{1, 2, 3}`, `WP-03` in wave 2 depending on `WP-01` and `WP-02`, `WP-04` in wave 3 depending on `WP-03`; the plan does not contain `oracle` or `reference`.
  - Must not: collapse the dependency chain into fewer waves.
  - Check: `test_acceptance_fixtures.py::TallyTests::test_ac_004_sound_and_three_waves`
  - WP: WP-02
- AC-005 · The tally's bad reference is wrong only on the edge cases
  - Scenario: `bench/fixtures/tally`.
  - Action: `oracle_counts(copy, "bad")`.
  - Expected: every test not named `test_edge_*` is `ok`; at least 4 `test_edge_*` are `FAIL` or `ERROR`.
  - Must not: fail a plain test.
  - Check: `test_acceptance_fixtures.py::TallyTests::test_ac_005_bad_reference_fails_only_edges`
  - WP: WP-02
- AC-006 · The bench can run both fixtures end to end
  - Scenario: the simulated `claude` of `.claude/bin/testutil.py` (`AGENTIC_CLAUDE`, `FAKE_LOG_DIR`; **no** `FAKE_WRITE`: the fake only knows WP-01..WP-03 and writes files these plans do not own), a private results dir.
  - Action: `bench.py run --fixture vault --fixture tally --repeat 1 --out <tmp> --source <repo>`.
  - Expected: exit 0; one results file with two runs, each with `result` in `("OK", "REVIEW")`, `failed_stage` `None` or a string, `agents` > 0 and `oracle.total` at least 15 (vault) and 20 (tally). The point is the plumbing: `pipeline-plan`, `briefs` and the stage checks read both plans.
  - Must not: record `result` `"error"` or `"timeout"`, or leave a `bench-run-*` dir behind in the private `TMPDIR`.
  - Check: `test_acceptance_fixtures.py::RunTests::test_ac_006_bench_runs_both`
  - WP: WP-01, WP-02

### Work packages
#### WP-01 · The `vault` fixture
- Wave 1. Files: `bench/fixtures/vault/` (everything under it, §4).
- Implements §5.1: the fixture's own plan, package skeleton, oracle, good and bad references. Consumes the layout of §6 by signature.
- ACs: AC-001, AC-002, AC-003, AC-006.
- Patterns to mirror: `bench/fixtures/inventory/repo/architecture.md:1-173` (the whole plan shape), `bench/fixtures/inventory/oracle/test_oracle.py:1-121` (imports inside tests, `make` helper), `bench/fixtures/inventory/reference/good/inventory/stock.py:1-38` (reference style), `bench/fixtures/inventory/fixture.json`.
- Gotchas: AC-003 forbids the substrings `traversal`, `inject`, `tamper`, `forg`, `hmac`, `signature`, `escap`, `saniti`, `oracle`, `reference` anywhere in the vault plan, so do not copy the inventory plan's wording verbatim: write "typed public functions" instead of "type annotations on public signatures", and "consumes nothing" (all three WPs are in wave 1) instead of "by signature"; grep the plan for the list before DONE. The good reference must pass **every** oracle test on Linux, macOS and Windows: for `upload_path` resolve with `os.path.realpath` on both sides, compare with `os.path.commonpath` inside a `try` (`ValueError` on Windows for another drive), reject a result equal to `base`, reject a NUL byte before touching the filesystem, and treat `\\` as a separator on every platform (`name.replace("\\", "/")` before splitting); for tokens use `hmac.new(secret, payload, hashlib.sha256)` with `hmac.compare_digest`, URL-safe base64 without padding, and catch every decoding error as `InvalidToken`; for the catalogue use a parameterised `LIKE ? ESCAPE '\'` with `%`, `_` and `\` escaped in `text`, or filter in Python after a parameterised `WHERE owner = ?`. The bad reference must stay green on every functional test: keep its happy path identical to the good one. The plan must validate: `mirror` paths must exist inside `repo/`, no `-t .`, no `__init__.py` in `tests/` or `acceptance/`. Run the fixture's `test_version.py` through `python3 -m unittest discover -s tests` from `repo/` before DONE. The plan is read by the drift tests: no personal paths.
- Exact imports: standard library only (`os`, `hmac`, `hashlib`, `base64`, `time`, `sqlite3`, `unittest`).
- Validation: `python3 bench/bench.py selftest --fixture vault` prints `vault: ok`; `python3 -m unittest discover -s bench/acceptance -p test_acceptance_fixtures.py -k Vault`.

#### WP-02 · The `tally` fixture
- Wave 1. Files: `bench/fixtures/tally/` (everything under it, §4).
- Implements §5.2. Consumes the layout of §6 by signature.
- ACs: AC-004, AC-005, AC-006.
- Patterns to mirror: the same four as WP-01.
- Gotchas: `split` with `divmod` on the absolute value, then negate; `parse_amount` with a regex `^-?\d+(\.\d{1,2})?$` over the stripped text (a leading `+` is not in the contract, so the oracle never sends one) and integer arithmetic, never `float`; `parse_date` with `datetime.date.fromisoformat` after a `^\d{4}-\d{2}-\d{2}$` check (on 3.9-3.10 `fromisoformat` already rejects `2026-1-5`, but the regex makes it explicit); `month_end` via the first day of the next month minus one day; `balances` must include the payer even when not a participant and every participant even at 0; `settle` loops exactly as §5.2 states so the tie example is deterministic. The bad reference keeps the plain behaviour identical. The fixture plan's WP-03 and WP-04 must say `depends_on` in both the text and the manifest.
- Exact imports: `datetime`, `re`, `dataclasses`, `unittest`.
- Validation: `python3 bench/bench.py selftest --fixture tally` prints `tally: ok`; `python3 -m unittest discover -s bench/acceptance -p test_acceptance_fixtures.py -k Tally`.

```json wp-manifest
{
  "stack": ["python"],
  "allow_bash": ["Bash(python3 -m unittest:*)", "Bash(python3 -m compileall:*)", "Bash(python3 bench/bench.py selftest:*)"],
  "acceptance": {"files": ["bench/acceptance/test_acceptance_fixtures.py"], "command": "python3 -m unittest discover -s bench/acceptance -p test_acceptance_*.py"},
  "verify": {"build": "python3 -m compileall -q bench", "lint": "python3 -m unittest discover -s .claude/bin -p test_definitions.py", "tests": "python3 -m unittest discover -s bench -p test_*.py"},
  "docs": {"files": ["README.md", "docs/how-to/README.md", "docs/how-to/bench.md"], "codemap": null},
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": ["bench/fixtures/vault/"],
     "acs": ["AC-001", "AC-002", "AC-003", "AC-006"],
     "mirror": ["bench/fixtures/inventory/repo/architecture.md:1-173", "bench/fixtures/inventory/oracle/test_oracle.py:1-121", "bench/fixtures/inventory/reference/good/inventory/stock.py:1-38", "bench/fixtures/inventory/fixture.json"]},
    {"id": "WP-02", "wave": 1, "depends_on": [], "files": ["bench/fixtures/tally/"],
     "acs": ["AC-004", "AC-005", "AC-006"],
     "mirror": ["bench/fixtures/inventory/repo/architecture.md:1-173", "bench/fixtures/inventory/oracle/test_oracle.py:1-121", "bench/fixtures/inventory/reference/good/inventory/stock.py:1-38", "bench/fixtures/inventory/fixture.json"]}
  ]
}
```

## 9. Test strategy
- Unit: none of this plan's own; each fixture's correctness is proven by its oracle against its references (`selftest`), which the WPs run before DONE.
- Acceptance: `bench/acceptance/test_acceptance_fixtures.py` from AC-001…AC-006, written first and red before the fixtures exist (`selftest` reports a missing fixture and exits 1). The acceptance command's pattern also runs `test_acceptance_bench.py`, whose AC-010 self-tests every shipped fixture. AC-006 uses the simulated `claude` and spends nothing. Tests build a private `TMPDIR` so the leftover check is exact, as `Sandbox` does in `test_acceptance_bench.py:79-98`.
- QA: exploratory, on the fixtures as data: oracle tests that could pass with a trivial implementation, references that differ beyond the intended shortcuts, plan text that leaks the attacks.
- After merging, by hand: `python3 bench/bench.py run --fixture vault --fixture tally` once, committed as the next results file.

## 10. Decisions
- **D1 · A file vault for implicit safety (user's choice):** three classic attacks (traversal, forged token, injection) in one coherent package, each in its own WP so the flow's reviewer and QA have three chances. Discarded: web helpers (XSS, open redirect), less coverage of injection.
- **D2 · One sentence of context, no listed attacks (user's choice):** the plan says once that names, tokens and text come from untrusted users. Silence would measure luck more than judgement; explicit requirements would measure implementation, which the current fixtures already do.
- **D3 · Three waves for `tally` (user's choice):** money and dates in parallel, the ledger on top, settlement on top of that; real `depends_on` chains are what the existing fixtures lack.
- **D4 · Oracle naming (`test_adv_*`, `test_edge_*`) as the contract** between a fixture and the acceptance tests, so "the bad reference fails only for the intended reasons" is checkable without reading the code. Discarded: separate oracle files per kind (selftest treats the oracle as one suite).
- **D5 · Robust oracle for traversal:** accept either `ValueError` or a path inside `base`; the plan under test does not say which, so both are right.
- **D6 · No weighting of oracle tests:** passed/total stays; a safety miss shows as a lower rate, and the per-test names in the oracle output say why.
- **D7 · Docs through the doc-updater** (fixture list in the guide, test counts in the READMEs) instead of a WP: the `docs` zone is what it exists for.
- **D8 · Lint phase = documentation drift tests:** the fixture plans and READMEs are tracked `.md` files, so the drift suite is the right deterministic check to run after the waves.

## 11. Risks and open questions
- **The flow may still score 100%:** the reviewer's security checklist may catch all three vault attacks, and `tally`'s edge cases are spelled out in its contracts. If the next real run passes everything, the fixtures measure cost and fix cycles, and a harder tier (silent trust, or edge cases only implied) is the follow-up.
- **Oracle robustness across platforms:** path handling on Windows (`\\`, drive letters, `realpath` of a non-existent base) is where the good reference is most likely to fail CI; the gotchas cover it, the Windows job proves it.
- **The backslash case is platform-dependent:** on Linux `os.path.join(base, "..\\x")` stays inside `base`, so the vault's bad reference fails that adversarial test only on Windows; it still fails at least three everywhere.
- **A plausible bad reference is a judgement:** AC-002 and AC-005 bound it (functional tests green, several intended tests red) but cannot prove it is the shortcut a real agent would take.
- **Rollback:** delete the two fixture folders and the acceptance file; nothing else depends on them.
