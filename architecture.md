# Architecture: a brownfield bench fixture and review metrics, so the bench can measure the reviewer's callers (issue 69)
Type: feature · Size: standard

## 1. Goal
The bench cannot tell whether the reviewer's callers (roadmap 3.1, shipped in 2.2.0) help: its fixtures start from almost nothing, so every caller of changed code sits inside the diff (3 of 15 sessions of the 2.2.0 run gave the reviewer any caller, and none led to a finding). This change adds a fixture with existing code and tests, `pricing`, whose plan changes a function's signature while a caller that no package owns, has no test and the plan does not mention, depends on the old one. Only a reviewer that reads the callers can see the break; the oracle checks that the caller still works. The bench also records, per session, how many callers the reviewer received and how many findings it confirmed and refuted, and `bench.py ab` compares them, so an A/B of 2.1.0 (no callers) against 2.4.0 on this fixture measures 3.1.

## 2. Scope
### Included
- `bench/fixtures/pricing/`: `fixture.json`, `repo/` (existing code, tests and the plan), `oracle/`, `reference/good/`, `reference/bad/`.
- `bench/bench.py`: three review fields in each session record; two new difference metrics in `compare` and in the A/B Markdown.
- `docs/how-to/bench.md`: the fixture in the table, the new fields; the roadmap entry.
### Excluded (non-goals)
- Changing the reviewer, the `callers` step or any file under `.claude/`.
- A results column in `bench/RESULTS.md` (`report` is unchanged).
- Running the A/B: done by hand after merging (section 9).

## 3. Stack
Python 3.9+, standard library only, `unittest`. Fixture code uses `from __future__ import annotations`.
- Build: `python3 -m compileall -q bench`
- Tests: `python3 -m unittest discover -s bench -p "test_*.py"`
- Bench acceptance: `python3 -m unittest discover -s bench/acceptance` (about a minute; runs `selftest` and `install`)

## 4. Repository structure
```
bench/fixtures/pricing/fixture.json                     WP-01
bench/fixtures/pricing/repo/README.md                   WP-01
bench/fixtures/pricing/repo/architecture.md             WP-01 (the plan the flow implements in the bench)
bench/fixtures/pricing/repo/shop/__init__.py            WP-01
bench/fixtures/pricing/repo/shop/money.py               WP-01 (before the change)
bench/fixtures/pricing/repo/shop/cart.py                WP-01 (before the change)
bench/fixtures/pricing/repo/shop/receipt.py             WP-01 (the untested caller)
bench/fixtures/pricing/repo/tests/test_version.py       WP-01
bench/fixtures/pricing/repo/tests/test_money.py         WP-01 (before the change)
bench/fixtures/pricing/repo/tests/test_cart.py          WP-01 (before the change)
bench/fixtures/pricing/oracle/test_oracle.py            WP-01
bench/fixtures/pricing/reference/good/shop/money.py     WP-01
bench/fixtures/pricing/reference/good/shop/cart.py      WP-01
bench/fixtures/pricing/reference/bad/shop/money.py      WP-01
bench/fixtures/pricing/reference/bad/shop/cart.py       WP-01
bench/bench.py                                          WP-02
bench/test_bench.py                                     WP-02
docs/how-to/bench.md                                    WP-03
docs/roadmap/repo-review-2026-11.md                     WP-03
bench/acceptance/test_acceptance_pricing.py             AT
```

## 4b. Existing code context
| What an implementer needs to know | Where it is | Pattern or rule |
|---|---|---|
| A fixture's layout and rules | `docs/how-to/bench.md:78-92` ("Add a fixture") | `repo/` committed as is; `oracle/test_*.py` never copied before the run; `reference/good` passes the whole oracle; `reference/bad` is right on the happy path; import the module under test inside each test so every test fails on the bare repo |
| A simple fixture to copy in shape | `bench/fixtures/tempconv/repo/architecture.md:1-60` (sections 1-7), `bench/fixtures/tempconv/repo/tempconv/__init__.py`, `bench/fixtures/tempconv/repo/tests/test_version.py` | Same section order and voice for the fixture's plan; `python3 -m unittest discover -s tests`; no `__init__.py` in `tests/` or `acceptance/` |
| A trap fixture's manifest | `bench/fixtures/roster/repo/architecture.md:219-237` | `stack`, `allow_bash`, `acceptance` in `acceptance/`, `verify.tests`, `docs` zone `README.md`, `mirror` per WP |
| Oracle naming for traps | `bench/fixtures/roster/oracle/test_oracle.py` (`test_ctx_*`), `docs/how-to/bench.md:90` | The trap's tests are `test_ctx_*`; the bad reference fails only those |
| `selftest` | `bench/bench.py:419-431` | Bare repo passes 0 oracle tests, good passes all, bad passes fewer than all |
| Fixture acceptance helpers | `bench/acceptance/test_acceptance_fixtures.py:40-93` (`FixtureCase`: `selftest`, `oracle_counts`, `check_good`, `check_bad`, `run_plan_tests`; `manifest_of` at `:32-37`), `bench/acceptance/test_acceptance_bench.py:306-328` (`FixtureReady.prepare`: copy, git, install, validate) | The acceptance tests import and reuse them |
| What `callers` reports | `.claude/bin/agentic.py:1093-1104` (`changed_code_files`: modified since `HEAD` or untracked), `:1170-1180` (`callers`: one JSON line with `changed`, `symbols`, `callers`) | In a prepared copy, editing `shop/money.py` without committing makes `callers` list `shop/receipt.py` |
| The run result's review block | `.claude/bin/pipeline.py:460-461` (`run["review"] = {"confirmed": [...], "refuted": [...], "advisory": [...], "opened": ..., "callers": n}`); 2.1.0 results have no `callers` key | The last review of the run; a fix cycle's re-review replaces it |
| The session record | `bench/bench.py:465-479` (`_record`, `_count`), `bench/test_bench.py:303-306` (its test) | New fields next to `verification_failures`; garbage tolerated as `_count` does |
| A/B metrics | `bench/bench.py:600-603` (`RATIO_METRICS`, `DIFF_METRICS`, `COUNTED`), `:654-673` (`_metric`), `:680-710` (`compare`), `:742-756` (`ab_markdown` header and rows), `bench/test_bench.py:261-273` (compare tests) | A new difference metric is a name in `DIFF_METRICS`, a branch in `_metric` and a column in `ab_markdown` |
| The bench guide's fixture table and the roadmap entry | `docs/how-to/bench.md:22-28`, `docs/roadmap/repo-review-2026-11.md:109` ("The bench cannot measure the reviewer's callers") | One row; the entry gains "Shipped:" with what was added |

## 5. Data model
Session record (`bench/bench.py`, JSON), three new keys:
```json
{"review_callers": 2, "review_confirmed": 1, "review_refuted": 0}
```
Each is an `int`, or `null` when the run result has no review block, or the block lacks that key, or its value has the wrong type (`callers` must be an int and not a bool; `confirmed` and `refuted` must be lists, counted with `len`).

## 6. Contracts between modules
```python
# bench/bench.py
DIFF_METRICS = ("mutation", "oracle", "fix_cycles", "review_callers", "review_confirmed")
def _review_fields(result: dict | None) -> dict
    # {"review_callers": int|None, "review_confirmed": int|None, "review_refuted": int|None}, from result["review"].
def _record(...) -> dict          # existing; the dict gains the three keys of _review_fields(result)
def _metric(run, name)            # existing; "review_callers" and "review_confirmed" return run[name] (None if absent)
def ab_markdown(doc) -> str       # existing; the per-fixture table gains "Callers" and "Confirmed" columns, in DIFF_METRICS order
```

The fixture (`bench/fixtures/pricing/`), as the flow will see it in the bench:

Before the change (`repo/`):
```python
# shop/money.py
def parse_price(text: str) -> int:
    """'12.50' -> 1250 (cents). ValueError for empty text, a negative amount, more than two decimals or no number."""
def format_cents(cents: int) -> str:
    """1250 -> '12.50'; -5 -> '-0.05'."""

# shop/cart.py
class Cart:
    def add(self, name: str, price_text: str, qty: int = 1) -> None   # parse_price(price_text); qty >= 1 else ValueError
    def total(self) -> int
    def lines(self) -> list[tuple[str, int, int]]                     # (name, qty, line total in cents), insertion order

# shop/receipt.py   (no test anywhere; owned by no work package of the fixture's plan; never named in it)
def from_rows(rows: list[tuple[str, str, int]]) -> str:
    """rows of (name, price_text, qty) -> one line per row 'name x{qty}  {format_cents(parse_price(price_text) * qty)}'
    and a last line 'TOTAL  {format_cents(sum)}', joined with '\n'. Calls parse_price(price_text) with ONE argument."""
```

After the change, as the fixture's plan specifies it (the agents' target):
```python
# shop/money.py
CURRENCIES = ("EUR", "USD", "GBP")
class CurrencyMismatch(ValueError): ...
def parse_price(text: str, currency: str) -> int:
    """'12.50' or 'EUR 12.50' (prefix, one space) -> 1250. currency not in CURRENCIES -> ValueError. A prefix that is
    a known currency other than `currency` -> CurrencyMismatch. Old errors unchanged."""
def format_cents(cents: int) -> str   # unchanged

# shop/cart.py
class Cart:
    def __init__(self, currency: str = "EUR") -> None   # unknown currency -> ValueError
    currency: str
    def add(self, name: str, price_text: str, qty: int = 1) -> None   # parse_price(price_text, self.currency)
```
The plan's section 6 writes `parse_price(text, currency)` as above, without a default, and says nothing about defaults either way (it neither requires nor forbids one). `reference/good/shop/money.py` gives `currency` a default of `"EUR"` (the compatible implementation a reviewer who reads `receipt.py` would ask for); `reference/bad/shop/money.py` keeps it required, so `receipt.from_rows` raises `TypeError`. Both references share the same `cart.py`.

## 7. Conventions
- English; standard library only; no network; `python3` in the fixture's plan commands.
- The fixture's plan follows `/architect`'s section order (as `tempconv`'s does), is a valid manifest (`agentic.py validate` says "Manifest valid" after `install`), and never contains the words `receipt`, `oracle` or `reference` (any case). Neither does `repo/README.md`, which is the fixture plan's docs zone and which the agents read.
- Every behaviour a `test_ac_*` checks is stated in the fixture's plan (section 6 or an AC). For example: a prefix that is not one of `CURRENCIES` (`"JPY 1.00"`) is a plain `ValueError`, not `CurrencyMismatch`; `"EUR12.50"` without the space is a `ValueError`.
- Its section 4b lists `shop/cart.py` as the only caller of `parse_price`, with `file:line`, as an incomplete plan would.
- Every oracle test must fail on the bare repo: each one calls `parse_price` with a currency, `Cart(currency=...)` or the new error, even the `test_ctx_*` ones (they first assert `parse_price("EUR 1.00", "EUR") == 100`, then check `receipt.from_rows`). Tests of old errors use `assertRaises(ValueError)` with the two-argument call (never `TypeError`); the `"JPY 1.00"` test checks the exact type (`type(e) is ValueError`), because `CurrencyMismatch` is a subclass of `ValueError`.
- The bench's review fields never raise: a malformed result gives `null`s.

## 8. Work packages and acceptance criteria
### Acceptance criteria
- AC-001 · The fixture is sound
  - Scenario: `bench/fixtures/pricing/` after the change.
  - Action: `bench.py selftest --fixture pricing --source <repo>`; the oracle on `reference/good` and on `reference/bad`.
  - Expected: selftest prints `pricing: ok` and exits 0; `fixture.json` has `name` `pricing` and `difficulty` `trap`; the good reference passes every oracle test, at least 15, of which at least 3 are `test_ctx_*`; the bad reference fails at least 3 `test_ctx_*` tests and passes every other test.
  - Must not: have an oracle test that passes on the bare repo.
  - Check: `bench/acceptance/test_acceptance_pricing.py::SoundTests`
  - WP: WP-01
- AC-002 · The trap has the shape it needs
  - Scenario: the fixture's `repo/`, copied, committed and with the flow installed (`FixtureReady.prepare`).
  - Action: read the files; run the plan's `verify.tests`.
  - Expected: `shop/receipt.py` calls `parse_price(` with one argument; no file under `repo/tests/` mentions `receipt`; neither `repo/README.md` nor the plan contains `receipt`, `oracle` or `reference` (any case); no work package's `files` covers `shop/receipt.py`; a line of the plan contains both `shop/cart.py:` and `parse_price`; the plan has two work packages, both in wave 1; `validate` passes; the existing tests pass on the bare repo.
  - Must not: let the existing suite or the plan reveal the caller.
  - Check: `bench/acceptance/test_acceptance_pricing.py::TrapShapeTests`
  - WP: WP-01
- AC-003 · The flow's `callers` step sees the hidden caller
  - Scenario: a prepared copy; `reference/bad/shop/money.py` and `cart.py` copied over it, not committed.
  - Action: `python3 .claude/bin/agentic.py callers` in the copy (with `CLAUDE_PROJECT_DIR` set to it).
  - Expected: the JSON line lists `shop/money.py` as changed, `parse_price` among its symbols, and a caller entry in `shop/receipt.py`.
  - Must not: depend on the reviewer: the check is the deterministic step.
  - Check: `bench/acceptance/test_acceptance_pricing.py::CallersTests`
  - WP: WP-01
- AC-004 · Each session records the review
  - Scenario: run results whose `review` is: (a) `{"callers": 3, "confirmed": [{}], "refuted": [{}, {}]}`; (b) `{"confirmed": [{}], "refuted": [{}, {}]}` (2.1.0, no `callers`); (c) absent; (d) `"x"`; (e) `{"callers": "3", "confirmed": [{}], "refuted": []}`; (f) `{"callers": True, "confirmed": "x", "refuted": None}`.
  - Action: `bench._record(...)` on each.
  - Expected, as `(review_callers, review_confirmed, review_refuted)`: (a) `(3, 1, 2)`; (b) `(None, 1, 2)`; (c) `(None, None, None)`; (d) `(None, None, None)`; (e) `(None, 1, 0)`; (f) `(None, None, None)`.
  - Must not: raise on any of them.
  - Check: `bench/acceptance/test_acceptance_pricing.py::RecordTests`
  - WP: WP-02
- AC-005 · The A/B compares callers and confirmed findings
  - Scenario: runs of one fixture, all with `result` `"OK"` (other results are not measurements), arm A with `review_callers` `None` and `review_confirmed` 0, arm B with 2 and 1.
  - Action: `bench.compare(runs, seed=0)` and `bench.ab_markdown(doc)`.
  - Expected: the fixture row has `review_callers` `None` (arm A has no value) and `review_confirmed` `1.0`; the Markdown table header ends with `| Callers | Confirmed |`, its separator row has 9 columns, and the fixture's row has 9 cells.
  - Must not: change the ratio metrics or the overall table.
  - Check: `bench/acceptance/test_acceptance_pricing.py::CompareTests`
  - WP: WP-02
- AC-006 · The guide and the roadmap say it
  - Scenario: the repository after the change.
  - Action: read `docs/how-to/bench.md` and the roadmap.
  - Expected: the fixture table has a `pricing` row naming the trap (`test_ctx_*`, a caller outside the diff); the guide names `review_callers` and `review_confirmed`; the roadmap's line about the bench and the reviewer's callers contains "Shipped".
  - Must not: hard-code a flow version or a test count in `bench.md` (`qa/test_qa_docs.py:76-80`).
  - Check: `bench/acceptance/test_acceptance_pricing.py::DocsTests`
  - WP: WP-03

### Work packages
#### WP-01 · The `pricing` fixture
- Wave: 1.
- Files: `bench/fixtures/pricing/`.
- Contracts: the fixture's code and plan as in section 6.
- ACs: AC-001, AC-002, AC-003.
- **Patterns to mirror:** `bench/fixtures/tempconv/repo/architecture.md:1-60` (plan shape and voice), `bench/fixtures/roster/repo/architecture.md:219-237` (manifest), `bench/fixtures/tempconv/repo/tests/test_version.py` (test style), `bench/fixtures/roster/oracle/test_oracle.py` (oracle style).
- **Gotchas:**
  - The fixture's plan: two packages in wave 1, contracts first. WP-01 owns `shop/money.py` and `tests/test_money.py`; WP-02 owns `shop/cart.py` and `tests/test_cart.py` and consumes `parse_price` by signature. Acceptance in `acceptance/`, `verify.tests` `python3 -m unittest discover -s tests`, docs zone `README.md`, `mirror` pointing at the existing files (`validate` checks the line ranges exist).
  - Its ACs (at least 6) cover only `money` and `cart`: prefixes, mismatch, unknown currency, old errors, a cart in USD, a cart refusing a EUR price. None mentions the caller.
  - Its section 4b names `shop/cart.py:<line>` as the caller of `parse_price` (the line where `Cart.add` calls it), and nothing else.
  - The existing `tests/test_money.py` and `tests/test_cart.py` call the old one-argument API and pass on the bare repo; the fixture's packages own them and will update them, so they never protect `receipt.py`.
  - Oracle: `test_ac_*` (at least 12) and `test_ctx_*` (at least 3: two rows, a row whose price text has the `EUR ` prefix, the `TOTAL` line). Each imports inside the test, and each touches new behaviour (section 7), so the bare repo passes 0.
  - `reference/good` and `reference/bad` hold only `shop/money.py` and `shop/cart.py`; they differ only in `currency`'s default.
- **WP validation:** `python3 bench/bench.py selftest --fixture pricing`, and from the repo root `python3 -m unittest discover -s bench/acceptance -p test_acceptance_pricing.py -k SoundTests -k TrapShapeTests -k CallersTests`.

#### WP-02 · Review fields in the bench
- Wave: 1.
- Files: `bench/bench.py`, `bench/test_bench.py`.
- Contracts: implements the `bench.py` part of section 6.
- ACs: AC-004, AC-005.
- **Patterns to mirror:** `bench/bench.py:465-479` (`_record`, `_count`), `:654-673` (`_metric`), `:742-756` (`ab_markdown`), `bench/test_bench.py:261-273` and `:303-306`.
- **Gotchas:** `_as_dict` and `_number_or` (`bench.py:264-270`) already tolerate garbage; `bool` is an `int` in Python, so reject it for `callers`. The difference metrics are medians of B minus A; an arm with no value gives `None` (the existing rule in `compare`). The ab doc's schema stays `ab-1` (old files lack the new keys and read as `None`).
- **WP validation:** `python3 -m unittest discover -s bench -p "test_*.py"`, `python3 -m unittest discover -s qa -p "test_qa_bench.py"` (it checks that `_record` never raises), and from the repo root `python3 -m unittest discover -s bench/acceptance -p test_acceptance_pricing.py -k RecordTests -k CompareTests`.

#### WP-03 · The guide and the roadmap
- Wave: 1.
- Files: `docs/how-to/bench.md`, `docs/roadmap/repo-review-2026-11.md`.
- Contracts: none.
- ACs: AC-006.
- **Patterns to mirror:** `docs/how-to/bench.md:22-28` (fixture table), `docs/roadmap/repo-review-2026-11.md:105` (how a shipped entry is written).
- **Gotchas:** `bench.md` is capped at 160 lines (`qa/test_qa_docs.py:57`); no versions or test counts. Line 4 says the five fixtures were tested with a real `claude`: `pricing` has no real run until the A/B after merging, so reword it to "on the fixtures that have results in RESULTS.md" instead of changing the count. Line 76 says the sign test cannot go below p = 0.0625 with five fixtures: with six it is 0.03125; its list of B − A differences gains the callers and confirmed counts. Line 90 lists each fixture's test-name prefixes: add `pricing` (`test_ctx_*`). The roadmap line keeps its text and gains, at the end: "Shipped: the `pricing` fixture (an untested caller outside every package and outside the plan) and the review fields in each session record; the A/B that uses them runs after merging."
- **WP validation:** `python3 -m unittest discover -s qa -p "test_qa_docs.py"`, `python3 -m unittest discover -s acceptance`.

```json wp-manifest
{
  "stack": ["python"],
  "allow_bash": ["Bash(python3 -m unittest:*)", "Bash(python3 -m compileall:*)", "Bash(python3 bench/bench.py selftest:*)", "Bash(python3 bench/bench.py run:*)"],
  "acceptance": {"files": ["bench/acceptance/test_acceptance_pricing.py"], "command": "python3 -m unittest discover -s bench/acceptance -p test_acceptance_pricing.py"},
  "verify": {"build": "python3 -m compileall -q bench", "types": "python3 -m unittest discover -s qa", "lint": "python3 -m unittest discover -s acceptance", "tests": "python3 -m unittest discover -s bench -p \"test_*.py\""},
  "docs": {"files": ["docs/how-it-works.md"], "codemap": null},
  "ignore": ["bench/results/"],
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": ["bench/fixtures/pricing/"],
     "acs": ["AC-001", "AC-002", "AC-003"], "mirror": ["bench/fixtures/tempconv/repo/architecture.md:1-60", "bench/fixtures/roster/repo/architecture.md:219-237", "bench/fixtures/tempconv/repo/tests/test_version.py", "bench/fixtures/roster/oracle/test_oracle.py"]},
    {"id": "WP-02", "wave": 1, "depends_on": [], "files": ["bench/bench.py", "bench/test_bench.py"],
     "acs": ["AC-004", "AC-005"], "mirror": ["bench/bench.py:465-479", "bench/bench.py:654-673", "bench/bench.py:742-756", "bench/test_bench.py:261-273"]},
    {"id": "WP-03", "wave": 1, "depends_on": [], "files": ["docs/how-to/bench.md", "docs/roadmap/repo-review-2026-11.md"],
     "acs": ["AC-006"], "mirror": ["docs/how-to/bench.md:22-28", "docs/roadmap/repo-review-2026-11.md:105"]}
  ]
}
```

## 9. Test strategy
- Unit: WP-02 in `bench/test_bench.py` (each review-field case, `_metric` for the two names, the Markdown header and a row).
- Acceptance: `bench/acceptance/test_acceptance_pricing.py`, AC-001…AC-006, written first and red (no `pricing` fixture, no review fields, no columns, no docs). It imports `FixtureCase` and `manifest_of` from `test_acceptance_fixtures.py` and `FixtureReady` from `test_acceptance_bench.py` (add `bench/acceptance` to `sys.path`), and loads `bench.py` as `bench/test_bench.py:15-18` does.
- QA: the bench suites (`bench/acceptance` included), `selftest` on every fixture, and a dry check that `bench.py run --fixture pricing` with the fake `claude` (`testutil.install_fake_claude`) completes; that check is QA's, not an AC.
- After merging, by hand: `bench.py ab --a agentic-flow--v2.1.0 --b agentic-flow--v2.4.0 --fixture pricing --repeat 3`, as a background task of the session (detached runs die when the container is reclaimed); results committed under `bench/results/`.

## 10. Decisions
- **D1 · An untested caller that the plan omits (user's choice):** it isolates 3.1. A tested caller would be caught by verification against the baseline instead.
- **D2 · The signature gains a required parameter:** the smallest change that breaks a one-argument caller with a `TypeError`, and that has a compatible fix inside the changed package (a default). A return-type change was discarded: no compatible fix stays inside the package's files.
- **D3 · Review counts in the session record, compared by `ab` (user's choice);** `RESULTS.md` keeps its columns.
- **D4 · The last review's counts:** the run result keeps only the final review; a finding fixed in a cycle shows as a fix cycle and a passing `test_ctx_*`, not as a confirmed finding. Recorded as is; the oracle is the outcome measure.
- **D5 · Through `/implement`:** nothing under `.claude/`. In a session where `hooks-check` fails (as this cloud session), `/implement fallback`.
- **D6 · An A/B of 2.1.0 against 2.4.0 on `pricing` after merging (user's choice),** three sessions per arm.
- **D7 · `docs.files` is `docs/how-it-works.md`:** the default zone (`README.md`, `docs/`) overlaps WP-03; the doc-updater may only mention the review fields in the bench part of How it works, if at all.
- **D8 · `verify` runs `bench`, `qa` and `acceptance`:** `qa/test_qa_bench.py` checks `_record` and `acceptance/test_docs.py` checks `bench.md`'s headings; `bench/acceptance` (about a minute) runs in each WP's validation and in QA, not in `verify` (four slots).

## 11. Risks and open questions
- **The trap may never fire:** the common rules both arms install (`.claude/rules/agentic/common.md`, "Shared code: before editing a function other files call, grep every caller ... keep the callers your change breaks working", roadmap 4.1, shipped in 2.0.0) tell the implementers of 2.1.0 and 2.4.0 alike to find `receipt.py` and keep it working. If they do, both arms pass and the A/B shows no difference: then what it measures is that the reviewer's callers add nothing on top of that rule for this kind of break. If no implementer does, the reviewer's callers are what remains. The session records (`review_callers`, `review_confirmed`, `fix_cycles`, the `test_ctx_*` results) say which.
- **The callers cap is not a concern:** `callers` leaves out every changed file, and the pipeline never commits, so in a run the edited `cart.py`, the old test files and the agents' `acceptance/` files are excluded; `shop/receipt.py` is the only caller left.
- **The contract may stop the fix:** the fixture plan's section 6 writes `currency` without a default, and the common rules put section 6 first. A reviewer or a fix-cycle implementer may treat a default as a contract change and refuse it; then the trap measures the precedence rule, not the callers. Section 6 says nothing against a default (section 6 above) to keep the compatible fix open.
- **A finding the reviewer confirms cannot be fixed by deleting the caller:** `shop/receipt.py` is outside every zone, so the fix must happen in `money.py`; the hook blocks writes to `receipt.py`.
- **Three sessions per arm:** a difference on one fixture is a signal, not proof.
