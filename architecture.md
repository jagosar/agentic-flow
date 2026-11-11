# Architecture: fewer fix cycles, cheaper runs (agentic-flow 2.14.0)
Type: change · Size: large

## 1. Goal
A fix cycle costs less and converges more often. The last allowed fix attempt of a package goes to a stronger model (Opus) in both engines; the earlier attempts of the fallback engine resume the implementer's own session, so it keeps its context. After a fix, the reviewers no longer review everything again: each axis re-reviews only its open findings, identified by a stable fingerprint, against the fix's diff, and answers ADDRESSED or NOT_ADDRESSED; anything new is recorded and never extends the loop. A run can carry a budget in agent calls, which reserves the review and QA a fix cycle needs before spending on it. A measured experiment compares escalation with the Claude Code advisor tool. Issues 48, 49 and 50.

## 2. Scope
### Included
- Escalation to the spec's `escalation_model` (`opus`) on the last allowed fix attempt (attempt 2 or later), both engines; `escalation: false` in `agentic.json` turns it off.
- Resume of the implementer's session (`claude -p --resume`) on the non-escalated fix attempts, fallback engine only, with one fresh retry when a resumed call gives no report.
- Fingerprints for the reviewers' findings; a scoped re-review after every fix cycle (both axes, no verifiers); new findings to `pending`.
- `max_agent_calls` in `agentic.json` (opt-in), checked before a run and before each fix cycle, both engines; `agent_calls` in the run record.
- `advisor_model` in the spec (null) passed as `--advisor` by the fallback launcher; a bench variant `advisor-opus`; an `agent_calls` metric in the bench.
- A re-review bench scenario; version 2.14.0; `test_acceptance_v213.py` retired with its unique checks moved.

### Excluded (non-goals)
- A model per WP in the manifest (the user's choice): `validate` keeps requiring Sonnet in every agent definition; the escalation is the only runtime exception.
- Resume in the native workflow: its `agent()` cannot continue a session.
- A budget in USD (the native engine sees no cost); the fallback keeps recording USD in `usage`.
- Escalation, resume or scoped re-review for the one-off `run-wave --fix` and `run-review`: they keep today's behaviour.
- Cutting a stage in the middle: the budget is only checked at the two points of section 6.
- Worked examples in the judges' prompts (not chosen).

## 3. Stack
Python 3.9+ standard library only (`.claude/bin`, `bench`); JavaScript for the native workflow (`.claude/workflows/agentic-implement.js`, no imports, no disk, no `Date.now()`); Node 18+ for `test_workflow.mjs`. No package manager, no new dependency.
- Build: `python3 -m unittest discover -s bench -p "test_*.py"`
- Lint: `node .claude/bin/test_workflow.mjs`
- Types: `python3 -m unittest discover -s bench/acceptance`
- Tests: `python3 -m unittest discover -s .claude/bin -p "test_*.py"`
- Also before a push (not in `verify`, which keeps this repository's established four commands; the docs' line caps are enforced by the `acceptance/` suite and WP-07 runs it): `python3 -m unittest discover -s acceptance`, `python3 -m unittest discover -s qa`, `python3 .claude/bin/agentic.py quality`, `python3 .claude/bin/agentic.py docs-check`.

## 4. Repository structure
```
.claude/
  agents/reviewer.md standards-reviewer.md implementer.md          WP-02
  workflows/
    pipeline-spec.json          WP-02   prompt re_review, schema re-review, constants escalation_model and advisor_model
    agentic-implement.js        WP-05
  bin/
    findings.py test_findings.py                                    WP-01
    test_manifest_check.py                                          WP-01   receives v213's validate checks
    test_acceptance_v213.py                                         WP-01   deleted
    test_definitions.py                                             WP-02
    launch.py core.py testutil.py test_launcher.py test_guardrail.py test_repo_scan.py   WP-03
    pipeline.py conformance.json test_pipeline.py                   WP-04
    test_workflow.mjs                                               WP-05
    upgrade.py                                                      WP-07
    test_acceptance_v214.py                                         AT      new
bench/
  bench.py variant.py scenario.py test_bench.py test_variant.py test_scenario.py   WP-06
  scenarios/re-review/                                              WP-06   new
docs/
  how-to/bench.md                                                   WP-06
  how-to/README.md how-it-works.md roadmap/repo-review-2026-11.md   WP-07
.claude-plugin/plugin.json                                          WP-07
```

## 4b. Existing code context
| What an implementer needs to know | Where it is | Pattern or rule | Source |
|---|---|---|---|
| The fallback engine's fix wave: the attempt number is `fix_count[wp] + 1`; attempt 2 and later add `fix_retry` with the previous defects and the path `.claude/state/runs/<wp>.fix-<attempt-1>.diff`; the call is `self.call(<agent>, "<wp> (fix)", prompt, wp)` | `.claude/bin/pipeline.py:341-367` | Escalation and resume are decided here, per attempt; the prompt does not change | read |
| `fix_cycle` appends the defects to `fix_history[wp]`, runs the waves, then increments `fix_count[wp]`: during attempt n the count is still n-1 | `.claude/bin/pipeline.py:423-434` | After the cycle, `fix_count[wp]` is the number of the diff file just written | read |
| `Pipeline.call` is the only place an agent runs; it records `not_checked` | `.claude/bin/pipeline.py:173-183` | It counts `agent_calls` and passes the new options | read |
| The review stage (both axes, verifiers, the record per axis) and the judge loop that runs verification, review and QA again after every fix | `.claude/bin/pipeline.py:436-482`, `.claude/bin/pipeline.py:483-560` | The scoped re-review is a second method beside `review`; `judge` may not grow (ratchet) | read |
| The same in the native workflow: `report` wraps every model agent (the gatekeeper calls `agent()` directly and is not one), `launchWave`, `fixCycle` | `.claude/workflows/agentic-implement.js:225-231`, `.claude/workflows/agentic-implement.js:335-357`, `.claude/workflows/agentic-implement.js:417-430` | `report(prompt, {agentType, label, schema})`; it gains `model` | read |
| The native workflow's `agent()` takes `model` per call and cannot resume a session; its built-in `budget` counts output tokens, not calls | the Workflow tool's reference (not in the repo) | Escalation in both engines, resume only in the fallback | inferred |
| `run_agent`: the `claude -p` argv with `--model WORKER_MODEL`, the schema chosen by agent type, the output JSON at `out_path`; returns `{report, status, usage}` | `.claude/bin/launch.py:70-112` | Gains `model`, `resume`, `schema_name`; returns `session_id` | read |
| `run_pipeline`'s `agent` closure gives each call its own output file `runs/<id>-<n>.json` | `.claude/bin/launch.py:405-460` | The closure keeps the last `session_id` per package | read |
| `pipeline_plan` prints what the engines follow, `max_fix_cycles` from `load_config` | `.claude/bin/launch.py:462-475` | Gains `escalation_model` and `max_agent_calls` | read |
| `DEFAULT_CONFIG` and `load_config` (deep merge of `.claude/agentic.json`, env `AGENTIC_TIMEOUT_S`) | `.claude/bin/core.py:79-85`, `.claude/bin/core.py:192-205` | Two new keys, validated by `pipeline-plan` | read |
| The diff of a fix attempt is written by `close-stage --fix`, numbered by the ledger's count | `.claude/bin/stage.py:267-287` | The re-review reads `runs/<wp>.fix-<n>.diff`, n = the engine's `fix_count[wp]` after the cycle | inferred |
| The spec: constants, prompts and schemas; `fix` and `fix_retry` texts | `.claude/workflows/pipeline-spec.json:3-11` | New prompt `re_review`, schema `re-review`, two constants | read |
| `findings.py`: `tier_of`, `waiver_for`, `blocks`, `text_sum` (code points, so the JS agrees without byte encoding) | `.claude/bin/findings.py:1-61` | `fingerprint` follows `text_sum`'s pattern | read |
| The engine test world: a declaration becomes fake `gate` and `agent`; `summarize` is what both engines must agree on | `.claude/bin/test_pipeline.py:28-135` | The fake `agent` accepts `**opts` and records them | read |
| The JS test's mock `agent` records `{type, label, prompt}` | `.claude/bin/test_workflow.mjs:40-100` | It records `model` too | read |
| The hub's configuration block, at its 260-line cap | `docs/how-to/README.md:152-168` | The new keys replace the "Models" line: net zero lines | read |
| `bench/variant.py` builds a flow variant by editing a copy | `bench/variant.py:1-83` | A second variant, `advisor-opus` | read |
| The bench's session record and the A/B metrics | `bench/bench.py:470-495`, `bench/bench.py:615-620` | `agent_calls` joins both (the file may grow 30 lines at most) | read |
| What v213 checks, test by test | `.claude/bin/test_acceptance_v213.py:1-436` | Moved by the packages that own the target suites (section 8) | read |

What must NOT change: the result of every existing conformance scenario (see WP-04's gotchas for the ones whose second review becomes a re-review); the shape `review.spec` / `review.standards` / the union lists; the one-off commands; `validate`'s model rules.

## 5. Data model
```python
# A reviewer finding gains, from the engine:
"fingerprint": "F" + 8 lowercase hex digits   # stable across cycles; "-2", "-3"... when two collide in one review

# The re-review report (schema "re-review", either reviewer)
{"status": "PASS" | "FAIL",                     # FAIL when any verdict is NOT_ADDRESSED
 "verdicts": [{"fingerprint": str, "verdict": "ADDRESSED" | "NOT_ADDRESSED", "evidence": str}],
 "new_findings": [{"tier": "floor" | "reflex" | "finish", "wp": str, "file": str, "problem": str, "evidence": str}],
 "not_checked": [str]}
# required: all four; new_findings items require all five fields

# The run record
"agent_calls": int                              # model agents called (the gatekeeper is not one)
"review": {... as in 2.13.0 ...,
           "scoped": bool,                      # True for a re-review
           "spec": {..., "addressed": [finding]}, "standards": {..., "addressed": [finding]},
           "new": [finding]}                    # scoped only; also in pending as {"type": "new finding", ...}
# pending items gain the types "new finding" and "over budget"

# pipeline-plan gains
"escalation_model": "opus" | None, "max_agent_calls": int | None

# agentic.json gains (both optional)
"escalation": true,        # false: no escalation
"max_agent_calls": null    # a positive int: the run's budget in agent calls

# pipeline-spec.json constants gain
"escalation_model": "opus", "advisor_model": None
```

## 6. Contracts between modules
```python
# findings.py (WP-01)
def fingerprint(finding) -> str:
    """"F" + 8 hex digits of FNV-1a (32-bit, offset 2166136261, prime 16777619) over the code points of
    "<axis>|<tier>|<rule>|<file>|<problem>", each part the finding's field as text ("" when missing), problem being
    stripped of " \t\r\n" at both ends, lowered with str.lower() (not casefold: it must equal JS toLowerCase), then cut to its
    first 80 code points. Per code point: h = ((h ^ cp) * 16777619) & 0xFFFFFFFF."""

def with_fingerprints(findings) -> list:
    """Copies of the findings, each with "fingerprint"; the second and later of a repeated value get "-2", "-3"."""
```
JS copies (WP-05): `fingerprint(f)` with `h = Math.imul(h ^ cp, 16777619) >>> 0`, iterating `for (const ch of text)`, stripping with `replace(/^[ \t\r\n]+|[ \t\r\n]+$/g, '')`, lowering with `toLowerCase()` and cutting with `Array.from(problem).slice(0, 80).join('')` (code points, not UTF-16 units); `withFingerprints(findings)`. Both engines must give the same strings: a conformance scenario carries them in a prompt.

**The engine's agent callable** (consumed by WP-03, produced by WP-04): `agent(prompt, agent_type, label, id, **opts)`. `Pipeline.call(agent_type, label, prompt, id=None, model=None, resume=False, schema=None)` passes only the options that are set (`model=...`, `resume=True`, `schema=<name>`), so a callable with four parameters keeps working when none is set. Every call adds 1 to `run["agent_calls"]` (0 in both engines' initial run record), before the call, even when it fails. JS: `report(prompt, {agentType, label, schema, model})`; `model` is passed to `agent()` only when set; `run.agent_calls += 1` in `report`.

**Escalation and resume** (`launch_wave`, fix branch, both engines): with `attempt = fix_count[wp] + 1` and `last = plan.max_fix_cycles`:
- `attempt >= 2 and attempt == last and plan.escalation_model`: the call carries `model=plan.escalation_model` and no resume.
- otherwise, Python only: `resume=True`. The native engine passes nothing.
The prompt is the same in both cases and in both engines.

**The fallback launcher** (WP-03):
```python
def run_agent(manifest, cfg, spec, agent_type, ident, label, prompt, out_path, final=False, entity=None,
              model=None, resume=None, schema_name=None) -> dict:
    """As in 2.13.0, plus: --model is `model` or WORKER_MODEL; with `resume` (a session id), ["--resume", resume] after
    "-p"; with spec constants advisor_model set, ["--advisor", <it>]; the schema is spec["schemas"][schema_name or
    agent_type] (falling back to the implementer's as today). Returns {"report", "status", "usage", "session_id"}: the
    output JSON's "session_id" or None."""
```
`run_pipeline`'s closure: `agent(prompt, agent_type, label, ident, model=None, resume=False, schema=None)` keeps `sessions = {}`; after every call whose `ident` is a package id it stores `sessions[ident] = result["session_id"]` when not None. With `resume=True` and a stored session it calls `run_agent(..., resume=sessions[ident])`; if that returns no report it calls once more without `resume` (a fresh agent). Without a stored session it calls fresh.

`pipeline_plan` (WP-03): `"escalation_model": <spec constants escalation_model> if cfg.get("escalation", True) is not False else None`; `"max_agent_calls": cfg.get("max_agent_calls")`. Before printing, it checks the config: `max_agent_calls` must be null or an int >= 1 (a `bool` is refused), `escalation` a bool; otherwise `die` with `agentic.json: max_agent_calls must be a whole number of agent calls (1 or more), or null` or `agentic.json: escalation must be true or false` (exit 1).

**The scoped re-review** (WP-04 `Pipeline.re_review(post)`, WP-05 `reReviewStage(post)`), used for every review after the first full one of the run (a flag `reviewed`, set by the first full review):
1. `open[axis]` = the previous review's `confirmed` of that axis whose `wp` is a package fixed in any fix cycle since that review (the engines keep `fixed_since_review`, the set of packages of every cycle since the last review, and `fix_count_at_review`, a copy of `fix_count` taken at each review; both are reset by each review). Every other finding of the previous review's `confirmed` (a package not fixed since, or a `wp` that is no package) is carried into the new `confirmed` unchanged, so the "no WP" pending items and the fix limit still see it. Findings carry their fingerprint from the full review that found them: `with_fingerprints` runs once per full review, over both axes' findings together, spec first, before verification.
2. For each axis with open findings, spec then standards, one call (in parallel): agent type `reviewer` / `standards-reviewer`, label `reviewer (re-review)` / `standards-reviewer (re-review)`, schema `re-review`, prompt `prompts.re_review` rendered with `axis` (`Spec` or `Standards`), `findings` (the open findings as `pipeline.compact` writes them, `.claude/bin/pipeline.py:29-31`: no spaces after separators, non-ASCII kept; the JS `JSON.stringify` gives the same), `diffs` (comma-separated `.claude/state/runs/<wp>.fix-<n>.diff`, sorted by package then n, for each package in `fixed_since_review` and each n from `fix_count_at_review[wp] + 1` to `fix_count[wp]`) and `rules`. An axis with no open findings makes no call.
3. A call with no report: `stop('review', 'the reviewer returned no re-review report')` or `stop('review', 'the standards reviewer returned no re-review report')`.
4. Per open finding: its verdict by fingerprint; a missing verdict counts as NOT_ADDRESSED. NOT_ADDRESSED stays in `confirmed`; ADDRESSED goes to `addressed`. No verifier runs. Verdicts for unknown fingerprints are ignored.
5. `new_findings` of both reports, each with `axis`, go to `run.review.new` and to the pending items as `{"type": "new finding", "source": "<agent type>", ...}`; they never start a fix cycle. A new floor finding makes the result `REVIEW` through the existing pending rule.
6. `run.review` = `{"scoped": True, "spec": {"confirmed", "refuted": [], "advisory": [], "addressed"}, "standards": {the same, "waived": []}, the union lists, "waived": [], "new", "opened": ok(post[1]), "callers": 0}`; a full review records `"scoped": False`. `needsReview` stays as the last full review left it. `close-stage review REVIEW=fail` when the union `confirmed` is not empty (else `pass`), in one `seq` with `open-stage qa`, as the full review does; if it fails: `stop('review', 'files changed during the review stage (the reviewer must not write)')`.

The prompt (`pipeline-spec.json`, key `re_review`): `Re-review the fix, on the {axis} axis only. These findings were confirmed before the fix, each with its fingerprint, as JSON:\n{findings}\nThe fix's diffs are {diffs}: read them and the code they changed. For each fingerprint say ADDRESSED or NOT_ADDRESSED, with the line that shows it. Report anything new in new_findings: it is recorded and does not block this run.{rules}`.

**The budget** (both engines; nothing happens when `plan.max_agent_calls` is null):
- At prepare, after the plan is read: `minimum = wave0 + packages + 2 + 1 + docs`, where `wave0` is 2 when `start_wave` is null, the plan has acceptance and its type is not `refactor`, else 0; `packages` the number of packages in the waves that will run; `docs` 1 when `plan.docs`. If `minimum > max_agent_calls`: `stop('budget', 'the budget of <max> agent calls cannot fund the run: it needs at least <minimum>')`.
- Before each fix cycle (from verification or from the judges): `needed = <packages in the cycle> + <reviewers the next review will call> + 1 + docs`, the reviewers being 2 when no full review has happened yet, else the number of axes with open findings for the packages of the cycle together with `fixed_since_review` (exactly the calls the re-review will make). If `agent_calls + needed > max_agent_calls`: the cycle's defects go to pending as `{"type": "over budget", ...d}` and the run returns `stop('budget', 'the budget of <max> agent calls cannot fund another fix cycle and the review and QA after it: <needed> needed, <max - agent_calls> left')` with that pending list.
- Verifiers are never reserved (their number is unknown); a stage is never cut. A budget stop after QA happens once the next fix stage is open (the judges' path opens it in the same `seq` that closes QA): accepted, the stopped run ends `REVIEW` and the next run opens its stages again.

## 7. Conventions
- English everywhere; no type annotations in `.claude/bin`, an explicit exception to the Python rules' "type annotations on every public signature" (the existing modules have none); `bench/` keeps `from __future__ import annotations`.
- Every `open`, `read_text` and `write_text` in `.claude/bin` names `encoding="utf-8"`.
- The ratchet: functions up to 60 lines (100 in tests), nesting 4, lines up to 120 characters, files up to 800 lines; a file already over may grow 30 lines; `Pipeline.judge`, `runAfterPlan` and `test_agentic.py` may not grow.
- Both engines change together: every behaviour of section 6 is a conformance scenario; the JS copies of schemas, prompts and constants equal the spec's.
- A prompt or agent definition says what to do, in the present; no versions, issue numbers or stories.
- Fixtures write non-ASCII as escapes and split the shortcut tokens the hook blocks.
- No real `claude` in tests. Real sessions only in QA, by hand.
- Commits are the maintainer's; agents do not commit.

## 8. Work packages and acceptance criteria
### Acceptance criteria
Engine criteria run the Python engine through `test_pipeline.run_scenario` on the named conformance scenario, and expect `node .claude/bin/test_workflow.mjs` to exit 0 (skipped with a message when `node` is missing). The summary of both engines gains `"agent_calls"`, `"models"` (sorted `"<agent type>:<label>#<n>=<model>"` for the calls that carried a model) and `"re_review"` (`null`, or `{"spec": [addressed, open, new], "standards": [addressed, open, new]}` for the last review when it was scoped).

- AC-001 · Fingerprints are stable and equal in both engines
  - Scenario: the finding `{"axis": "spec", "tier": "floor", "file": "src/a.py", "problem": "  Off by ONE in total  "}`, the same with `problem` "off by one in total" and a different `line` and `evidence`, the same with `file` "src/b.py", and a list of three findings where the first two are equal.
  - Action: `findings.fingerprint`, `findings.with_fingerprints`; the scenario `a fix is re-reviewed on its open findings only`.
  - Expected: the first two give the same fingerprint, matching `^F[0-9a-f]{8}$`; the third a different one; the list gives `X`, `X-2` and a third value; the scenario's re-review prompt holds the fingerprint the Python function computes for its finding; node agrees.
  - Must not: depend on dict order, the line number or the evidence text.
  - Check: `test_acceptance_v214.FingerprintTests.test_ac_001_fingerprints`
  - WP: WP-01, WP-04, WP-05
- AC-002 · After a fix, only the open findings are re-reviewed
  - Scenario: the conformance scenario `a fix is re-reviewed on its open findings only`: the first review has one spec floor finding on WP-01 and no standards finding; the fix; the re-review answers ADDRESSED.
  - Action: run it.
  - Expected: `OK` with 1 fix cycle; the agents include `reviewer:reviewer (re-review)` once and no `standards-reviewer:standards-reviewer (re-review)`; one `verifier` call in the whole run; the re-review prompt holds `.claude/state/runs/WP-01.fix-1.diff`; `re_review` is `{"spec": [1, 0, 0], "standards": [0, 0, 0]}`.
  - Must not: call a full reviewer a second time; verify again.
  - Check: `test_acceptance_v214.ReReviewTests.test_ac_002_scoped`
  - WP: WP-04, WP-05
- AC-003 · NOT_ADDRESSED loops, new findings never do, nothing open is lost
  - Scenario: the scenarios `a finding not addressed is fixed again`, `a missing verdict counts as not addressed`, `a new finding in a re-review goes to pending` and `a finding fixed before a verification failure is still re-reviewed` (review finds a floor finding on WP-01, it is fixed, verification then fails on WP-02, WP-02 is fixed, then the re-review).
  - Action: run each.
  - Expected: the first two end with 2 fix cycles on WP-01 (the cap) and a `fix limit reached` pending item; the third ends with 1 fix cycle, a `new finding` pending item and result `REVIEW` (its new finding is floor); in the fourth the re-review prompt holds WP-01's fingerprint and both `WP-01.fix-1.diff` and `WP-02.fix-1.diff`.
  - Must not: start a fix cycle for a new finding; drop a confirmed finding that was not re-reviewed (one on a `wp` that is no package stays a `no WP` pending item).
  - Check: `test_acceptance_v214.ReReviewTests.test_ac_003_verdicts`
  - WP: WP-04, WP-05
- AC-004 · The last fix attempt goes to the stronger model
  - Scenario: `the last fix attempt escalates` (plan `escalation_model: "opus"`, `max_fix_cycles: 2`, a finding on WP-03 that is never addressed) and `without an escalation model no attempt escalates` (the same without it).
  - Action: run both.
  - Expected: `models` is `["implementer:WP-03 (fix)#2=opus"]` in the first and `[]` in the second; the implementer prompts are the same in both.
  - Must not: escalate the first attempt; escalate when `max_fix_cycles` is 1.
  - Check: `test_acceptance_v214.EscalationTests.test_ac_004_escalation`
  - WP: WP-04, WP-05
- AC-005 · The fallback resumes the implementer, and escalates fresh
  - Scenario: a project with the fake `claude` (which answers `"session_id": "s-<its process id>"`), `FAKE_REVIEW_FINDING=WP-02`, `FAKE_RE_REVIEW=NOT_ADDRESSED`, `max_fix_cycles` 2.
  - Action: `agentic.py run-pipeline`.
  - Expected: WP-02's first fix call has `--resume` with the session id of WP-02's implement call; its second fix call has `--model opus` and no `--resume`; every other call has `--model sonnet`.
  - Must not: resume another package's session; resume in the escalated attempt.
  - Check: `test_acceptance_v214.EscalationTests.test_ac_005_fallback_resume`
  - WP: WP-03, WP-04
- AC-006 · A resumed call that fails is retried fresh once
  - Scenario: the same project with `FAKE_RESUME_FAILS=1` (the fake answers nothing when it sees `--resume`).
  - Action: `agentic.py run-pipeline`.
  - Expected: WP-02's first fix attempt runs twice (with `--resume`, then without) and the run goes on; the record's `agent_calls` counts that attempt once.
  - Must not: retry more than once; stop the run because the resume failed.
  - Check: `test_acceptance_v214.EscalationTests.test_ac_006_resume_retry`
  - WP: WP-03, WP-04
- AC-007 · The budget reserves the review and QA
  - Scenario: the scenarios `a budget too small for the run stops before any agent`, `a budget that cannot fund a fix cycle stops with the gap` and `no budget runs as before`.
  - Action: run each.
  - Expected: the first is `REVIEW`, `failed_stage` `budget`, no non-gatekeeper agent called, its detail names the minimum; the second is `REVIEW`, `failed_stage` `budget`, `over budget` in pending, its detail says how many calls were needed and left, and no `(fix)` call ran; the third ends as the same declaration without a budget; in each, `agent_calls` equals the number of non-gatekeeper agents in the summary.
  - Must not: cut a stage in the middle; count the gatekeeper.
  - Check: `test_acceptance_v214.BudgetTests.test_ac_007_budget`
  - WP: WP-04, WP-05
- AC-008 · Configuration is validated and reaches the plan
  - Scenario: projects whose `agentic.json` holds `{"max_agent_calls": 40}`, `{"escalation": false}`, `{"max_agent_calls": 0}`, `{"max_agent_calls": "ten"}`, `{"max_agent_calls": true}`, `{"escalation": "no"}`.
  - Action: `agentic.py pipeline-plan`.
  - Expected: the first prints `max_agent_calls` 40 and `escalation_model` `opus`; the second `escalation_model` null; the last four exit 1 with the messages of section 6.
  - Must not: accept `true` as a number of calls.
  - Check: `test_acceptance_v214.ConfigTests.test_ac_008_config`
  - WP: WP-03
- AC-009 · The advisor experiment is wired and off by default
  - Scenario: this checkout's spec; a variant built with `bench/variant.py advisor-opus`.
  - Action: read the spec; build the variant; `launch.run_agent` with the fake `claude` and each spec.
  - Expected: `constants.advisor_model` is null here and the call has no `--advisor`; the variant's is `"opus"`, its `escalation_model` null, and the call has `--advisor opus`.
  - Must not: change this checkout.
  - Check: `test_acceptance_v214.AdvisorTests.test_ac_009_advisor`
  - WP: WP-02, WP-03, WP-06
- AC-010 · The bench measures calls, and the re-review has a scenario
  - Scenario: `bench/scenarios/re-review/`; two fake bench session lists.
  - Action: load the scenario files; `bench.compare` on sessions with `agent_calls` 10 and 14.
  - Expected: `fixed.json` expects `{"status": "PASS", "all_verdicts": "ADDRESSED"}` and `unfixed.json` `{"status": "FAIL", "all_verdicts": "NOT_ADDRESSED"}`, both with agent `reviewer`, prompt `re_review` and `schema_name` `re-review`; the comparison reports an `agent_calls` difference of 4.
  - Must not: hold an `__init__.py` under `bench/scenarios/`.
  - Check: `test_acceptance_v214.BenchTests.test_ac_010_bench`
  - WP: WP-06
- AC-011 · Shipped, documented, versioned, and 2.13.0's checks kept
  - Scenario: this checkout.
  - Action: read `plugin.json`, `upgrade.NOTES`, the hub, `docs/how-it-works.md`; list the acceptance files; look up each test the moves table names.
  - Expected: version `2.14.0`; `NOTES["2.14.0"]` mentions `escalation`, `--resume`, `re-review`, `fingerprint` and `max_agent_calls`; the hub names `max_agent_calls` and `escalation` and has at most 260 lines; the only acceptance file is `test_acceptance_v214.py`; every moved test class exists.
  - Must not: keep `test_acceptance_v213.py`.
  - Check: `test_acceptance_v214.ReleaseTests.test_ac_011_release`
  - WP: WP-01, WP-07

### Work packages
Three waves. Wave 1 changes no code another package runs (new functions in findings.py, the spec, the agents, the retired file). Wave 2 needs them: the launcher and the fallback engine. Wave 3 needs the fallback engine's scenarios (JS), the launcher (bench) and everything shipped (release). The plan is for the flow's own repository: executed by hand.

**Where 2.13.0's acceptance checks go** (each class must exist when the release ships):
| v213 test | Moves to | By |
|---|---|---|
| `AxesTests` (AC-001, AC-002), `RulesTests`' scenarios (AC-006 b), the scenario of `MeasureTests.test_ac_009_variant` | `test_pipeline.ReviewAxesTests` | WP-04 |
| `TierTests` (AC-003), `RulesTests`' plan and `run-wave` (AC-006 a), the `run-review` part of `StandardsAgentTests` (AC-007) | `test_launcher.ReviewAxesLaunchTests` | WP-03 |
| The hook claims of `StandardsAgentTests` (AC-007) | `test_guardrail.SharedReviewClaimTests` | WP-03 |
| `PlanTests` (AC-004, AC-005), through the commands | `test_manifest_check.ValidateCommandTests` | WP-01 |
| `DefinitionTests` (AC-008) | `test_definitions.ReviewDefinitionTests` | WP-02 |
| The variant of `MeasureTests.test_ac_009_variant`, `test_ac_010`, `test_ac_011` | `bench/test_variant.BuildTests` (extended), `bench/test_scenario.ScenarioSetTests` | WP-06 |
| `ReleaseTests` (AC-012) | dropped: version and notes pins | — |

#### WP-01 · Fingerprints, and 2.13.0's validate checks
- Wave: 1.
- Files: `.claude/bin/findings.py`, `.claude/bin/test_findings.py`, `.claude/bin/test_manifest_check.py`, `.claude/bin/test_acceptance_v213.py` (deleted).
- Implements: `fingerprint`, `with_fingerprints`; `ValidateCommandTests` (v213's `PlanTests`, through `agentic.py validate`, `pipeline-plan` and `briefs`); the deletion of v213, last.
- ACs: AC-001, AC-011.
- Patterns to mirror: `.claude/bin/findings.py:55-61` (`text_sum`); `.claude/bin/test_acceptance_v213.py:135-206` (what `PlanTests` checks).
- Gotchas: the deletion is in wave 1 because `test_layout` allows one acceptance file; the checks it held come back in waves 2 and 3 (the moves table), so between those waves 2.13.0's behaviour is guarded only by the suites already there. Accepted: this plan runs by hand, and AC-011 checks every moved class exists before release. CLI tests use `test_agentic.Repo`, copying the rules library as v213 does. No type annotations.
- Validation: `python3 -m unittest discover -s .claude/bin -p test_findings.py`; the same for `test_manifest_check.py` and `test_layout.py`.

#### WP-02 · The spec and the agents
- Wave: 1.
- Files: `.claude/workflows/pipeline-spec.json`, `.claude/agents/reviewer.md`, `.claude/agents/standards-reviewer.md`, `.claude/agents/implementer.md`, `.claude/bin/test_definitions.py`.
- Implements: the prompt `re_review` and the schema `re-review` of sections 5 and 6; the constants `escalation_model: "opus"` and `advisor_model: null`; in both reviewers a `# Re-review` section (when the prompt is a re-review: judge only the fingerprints given, against the diffs; ADDRESSED needs the line that shows it; anything else goes to `new_findings`); in the implementer one line in `# Process`: a fix attempt may continue your earlier session or start fresh on another model, so read the diff of the previous attempt when the prompt names it; `ReviewDefinitionTests` (v213's `DefinitionTests`) and the new phrases (`# Re-review`, `ADDRESSED`, `new_findings`).
- ACs: AC-009.
- Patterns to mirror: `.claude/workflows/pipeline-spec.json:3-11`; `.claude/agents/reviewer.md:1-100`.
- Gotchas: from this package until WP-04 and WP-05 land, `test_pipeline` and `test_workflow.mjs` compare the spec with engines that lack the new keys: expected. Keep every phrase `test_definitions.py` pins.
- Validation: `python3 -m unittest discover -s .claude/bin -p test_definitions.py`.

#### WP-03 · The fallback launcher and the configuration
- Wave: 2, after WP-01 and WP-02.
- Files: `.claude/bin/launch.py`, `.claude/bin/core.py`, `.claude/bin/testutil.py`, `.claude/bin/test_launcher.py`, `.claude/bin/test_guardrail.py`, `.claude/bin/test_repo_scan.py`.
- Implements: `run_agent`'s new parameters and `session_id`; the closure's sessions and the fresh retry; `pipeline_plan`'s two fields and the config check; `DEFAULT_CONFIG` gains `"escalation": True` (a missing `max_agent_calls` means null); the fake `claude` answers `"session_id": "s-<its process id>"`, knows the `re-review` schema (a verdict `FAKE_RE_REVIEW`, default `ADDRESSED`, for every fingerprint found in the prompt with the regex `"fingerprint":"(F[0-9a-f]{8}(?:-\d+)?)"`) and answers nothing to a call with `--resume` when `FAKE_RESUME_FAILS` is set; `ReviewAxesLaunchTests`, `SharedReviewClaimTests` and v213's printed-rules check (`test_repo_scan`).
- Consumes: `findings` and the spec (by implementation); `Pipeline.call`'s options (by signature: WP-04).
- ACs: AC-005, AC-006, AC-008, AC-009.
- Patterns to mirror: `.claude/bin/launch.py:70-112`; `.claude/bin/launch.py:405-460`; `.claude/bin/test_launcher.py:33-70`.
- Gotchas: `--resume` goes right after `-p`; a re-review call uses the `re-review` schema, not the agent type's. The fresh retry is a second `run_agent`, with its own output file `runs/<id>-<n>.json` (the next counter value) and its own usage record, but one call for the engine. `run-pipeline --resume` (skip finished waves, `launch.py:405-420`) is unrelated to `claude --resume`: do not mix them. `launch.py` and `testutil.py` are near the long-line allowance.
- Validation: `python3 -m unittest discover -s .claude/bin -p test_launcher.py`; the same for `test_guardrail.py`, `test_repo_scan.py`, `test_agentic.py`.

#### WP-04 · The fallback engine and the scenarios
- Wave: 2, after WP-01 and WP-02.
- Files: `.claude/bin/pipeline.py`, `.claude/bin/conformance.json`, `.claude/bin/test_pipeline.py`.
- Implements: `call`'s options and `agent_calls`; escalation and resume in `launch_wave`; fingerprints on full reviews; `re_review`; the budget at prepare and before fix cycles; the scenarios named in the criteria (`a fix is re-reviewed on its open findings only`, `a finding not addressed is fixed again`, `a missing verdict counts as not addressed`, `a new finding in a re-review goes to pending`, `a finding fixed before a verification failure is still re-reviewed`, `a finding outside every package survives the re-review`, `the last fix attempt escalates`, `without an escalation model no attempt escalates`, `a budget too small for the run stops before any agent`, `a budget that cannot fund a fix cycle stops with the gap`, `no budget runs as before`); the test world's `re_review` reports (a list picked per call, like `review`; the fake dispatches a re-review by its `schema` option, not by agent type, so it never consumes a `review` round), the `**opts` record and the summary fields; `ReviewAxesTests` (v213's engine checks).
- ACs: AC-001, AC-002, AC-003, AC-004, AC-005, AC-006, AC-007.
- Patterns to mirror: `.claude/bin/pipeline.py:341-367`; `.claude/bin/pipeline.py:436-482`; `.claude/bin/test_pipeline.py:28-135`.
- Gotchas: existing scenarios with two reviews (a fix after a review) now get a re-review the second time, and their declared second `review` reports are no longer used. For each, add `re_review` reports that reproduce today's result (an open finding the old second review no longer reported is ADDRESSED; one it still reported is NOT_ADDRESSED) so their `result`, `fix_cycles` and `pending` stay the same; their agents and prompts change, which is the point. `judge` may not grow: put the choice between `review` and `re_review` in a small method. `fix_count` is incremented after the cycle, so the diff numbers in the re-review use the counts after it. The budget check before a cycle belongs in `fix_cycle`, which already returns `{"stopped": ...}` and `judge` already handles it, so `judge` does not grow.
- Validation: `python3 -m unittest discover -s .claude/bin -p test_pipeline.py`, all of it except `ConformanceTests`, which compares with the JS engine and is green only once WP-05 lands (run `python3 -m unittest test_pipeline.EngineTests test_pipeline.ReviewAxesTests` from `.claude/bin` in wave 2).

#### WP-05 · The native workflow
- Wave: 3, after WP-04.
- Files: `.claude/workflows/agentic-implement.js`, `.claude/bin/test_workflow.mjs`.
- Implements: the same as WP-04 without resume: `fingerprint`, `withFingerprints`, `report`'s `model` and `agent_calls`, escalation in `launchWave`, `reReviewStage`, the budget; the schema and prompt copies; the mock's `model` record, `re_review` reports (dispatched by `opts.schema` being the re-review schema, and recorded under a `re-review` key so `schemas[agentType]` keeps the full review's) and the summary fields.
- ACs: AC-001, AC-002, AC-003, AC-004, AC-007.
- Patterns to mirror: `.claude/workflows/agentic-implement.js:335-357`; `.claude/workflows/agentic-implement.js:417-430`; `.claude/bin/test_workflow.mjs:40-100`.
- Gotchas: `runAfterPlan` may not grow. `agent()` gets `model` only when set. `Math.imul` and `>>> 0` keep the hash unsigned 32-bit; `toLowerCase` matches Python's `str.lower()`, which the contract uses.
- Validation: `node .claude/bin/test_workflow.mjs`; `python3 -m unittest discover -s .claude/bin -p test_pipeline.py` (its `ConformanceTests` must now pass).

#### WP-06 · The bench: advisor variant, calls metric, re-review scenario
- Wave: 3, after WP-02 and WP-03.
- Files: `bench/bench.py`, `bench/variant.py`, `bench/scenario.py`, `bench/test_bench.py`, `bench/test_variant.py`, `bench/test_scenario.py`, `bench/scenarios/re-review/`, `docs/how-to/bench.md`.
- Implements: the variant `advisor-opus` (constants `advisor_model: "opus"`, `escalation_model: null`); `agent_calls` in the session record and in `DIFF_METRICS`; the expectation `all_verdicts` in `scenario.py` (the report has at least one verdict and every one has that value); a scenario key `schema_name` (the schema is `spec["schemas"][meta.get("schema_name", meta["agent"])]`, wherever `scenario.py` picks it today); `bench/scenarios/re-review/` (a plan, `fixed/` and `unfixed/` code each with its diff, `fixed.json` and `unfixed.json` carrying the open finding with its fingerprint in `values.findings`, agent `reviewer`, prompt `re_review`, `schema_name` `re-review`); v213's variant and scenario-set checks; `bench.md` lines for the variant and the metric.
- ACs: AC-009, AC-010.
- Patterns to mirror: `bench/variant.py:1-83`; `bench/bench.py:470-495`.
- Gotchas: `bench.py` is over its size limit and may grow 30 lines at most. The variant edits the spec only, and raises `ValueError` when the spec has no `advisor_model` or `escalation_model` constant (never half-applied, as `variant.py` does).
- Validation: `python3 -m unittest discover -s bench -p "test_*.py"`.

#### WP-07 · Version, notes and docs
- Wave: 3, after WP-03 and WP-04.
- Files: `.claude-plugin/plugin.json`, `.claude/bin/upgrade.py`, `docs/how-to/README.md`, `docs/how-it-works.md`, `docs/roadmap/repo-review-2026-11.md`.
- Implements: 2.14.0; `NOTES["2.14.0"]`; in the hub, the line `- **Models:** not configurable; set by alias.` becomes ``- **`escalation`, `max_agent_calls`:** the last fix attempt of a package runs on Opus (false turns it off); a budget in agent calls that reserves review and QA before a fix cycle (null: none). Models are otherwise set by alias.`` (net zero lines); in `how-it-works.md`, the fix cycle and the re-review; the roadmap's 2.3, 2.4 and 2.5 marked shipped.
- ACs: AC-011.
- Patterns to mirror: `.claude/bin/upgrade.py:147-170`; `docs/how-to/README.md:152-168`.
- Gotchas: the hub is at its 260-line cap. The history is regenerated as the release's last commit.
- Validation: `python3 -m unittest discover -s acceptance`; `python3 .claude/bin/agentic.py docs-check`.

```json wp-manifest
{
  "maintainer": true,
  "stack": ["python"],
  "allow_bash": ["Bash(python3 -m unittest:*)", "Bash(node .claude/bin/test_workflow.mjs)"],
  "acceptance": {"files": [".claude/bin/test_acceptance_v214.py"], "command": "python3 -m unittest discover -s .claude/bin -p test_acceptance_v214.py"},
  "verify": {"build": "python3 -m unittest discover -s bench -p \"test_*.py\"", "lint": "node .claude/bin/test_workflow.mjs", "types": "python3 -m unittest discover -s bench/acceptance", "tests": "python3 -m unittest discover -s .claude/bin -p \"test_*.py\""},
  "docs": {"files": ["docs/assets/"], "codemap": null},
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": [".claude/bin/findings.py", ".claude/bin/test_findings.py", ".claude/bin/test_manifest_check.py", ".claude/bin/test_acceptance_v213.py"],
     "acs": ["AC-001", "AC-011"], "mirror": [".claude/bin/findings.py:55-61", ".claude/bin/test_acceptance_v213.py:135-206"]},
    {"id": "WP-02", "wave": 1, "depends_on": [], "files": [".claude/workflows/pipeline-spec.json", ".claude/agents/reviewer.md", ".claude/agents/standards-reviewer.md", ".claude/agents/implementer.md", ".claude/bin/test_definitions.py"],
     "acs": ["AC-009"], "mirror": [".claude/workflows/pipeline-spec.json:3-11", ".claude/agents/reviewer.md:1-100"]},
    {"id": "WP-03", "wave": 2, "depends_on": ["WP-01", "WP-02"], "files": [".claude/bin/launch.py", ".claude/bin/core.py", ".claude/bin/testutil.py", ".claude/bin/test_launcher.py", ".claude/bin/test_guardrail.py", ".claude/bin/test_repo_scan.py"],
     "acs": ["AC-005", "AC-006", "AC-008", "AC-009"], "mirror": [".claude/bin/launch.py:70-112", ".claude/bin/launch.py:405-460", ".claude/bin/test_launcher.py:33-70"]},
    {"id": "WP-04", "wave": 2, "depends_on": ["WP-01", "WP-02"], "files": [".claude/bin/pipeline.py", ".claude/bin/conformance.json", ".claude/bin/test_pipeline.py"],
     "acs": ["AC-001", "AC-002", "AC-003", "AC-004", "AC-005", "AC-006", "AC-007"], "mirror": [".claude/bin/pipeline.py:341-367", ".claude/bin/pipeline.py:436-482", ".claude/bin/test_pipeline.py:28-135"]},
    {"id": "WP-05", "wave": 3, "depends_on": ["WP-04"], "files": [".claude/workflows/agentic-implement.js", ".claude/bin/test_workflow.mjs"],
     "acs": ["AC-001", "AC-002", "AC-003", "AC-004", "AC-007"], "mirror": [".claude/workflows/agentic-implement.js:335-357", ".claude/workflows/agentic-implement.js:417-430", ".claude/bin/test_workflow.mjs:40-100"]},
    {"id": "WP-06", "wave": 3, "depends_on": ["WP-02", "WP-03"], "files": ["bench/bench.py", "bench/variant.py", "bench/scenario.py", "bench/test_bench.py", "bench/test_variant.py", "bench/test_scenario.py", "bench/scenarios/re-review/", "docs/how-to/bench.md"],
     "acs": ["AC-009", "AC-010"], "mirror": ["bench/variant.py:1-83", "bench/bench.py:470-495"]},
    {"id": "WP-07", "wave": 3, "depends_on": ["WP-03", "WP-04"], "files": [".claude-plugin/plugin.json", ".claude/bin/upgrade.py", "docs/how-to/README.md", "docs/how-it-works.md", "docs/roadmap/repo-review-2026-11.md"],
     "acs": ["AC-011"], "mirror": [".claude/bin/upgrade.py:147-170", "docs/how-to/README.md:152-168"]}
  ]
}
```

## 9. Test strategy
- **Unit:** each package in its own files, `unittest`, `test_agentic.Repo` projects, a fake `claude`. Both engines through the conformance scenarios.
- **Acceptance:** `.claude/bin/test_acceptance_v214.py`, written first and red, AC-001 to AC-011.
- **Teeth:** after green, mutate (a missing verdict read as ADDRESSED; the first attempt escalated; resume on the escalated attempt; the gatekeeper counted; the reserve ignored; a full review on the second pass) and see the tests go red.
- **QA with real sessions, by hand, in the pull request:**
  1. The re-review scenario, `fixed.json` and `unfixed.json`, 5 runs each (no old arm: the prompt is new). Cost not measured.
  2. A/B 1, the package: `bench.py ab --a agentic-flow--v2.13.0 --b .` on `pricing` and `inventory`, 3 sessions per arm and fixture (12 sessions). `pricing` had a fix cycle in every 2.13.0 session (`bench/results/ab-2.12.0-vs-2.13.0-20261109-221352.md`), so resume and the re-review are exercised there; the native engine's escalation is not (the bench runs the fallback).
  3. A/B 2, the experiment: `--a .` against `--b <variant advisor-opus>` on the same fixtures and sessions. Whether the advisor ran is read from each session's output; if no session shows it, the experiment is reported as not measured.
- The user sees both A/Bs before merging.

## 10. Decisions
- **Escalation in both engines, resume only in the fallback** (the user's choice). The native `agent()` takes a model per call but cannot resume a session. The engines diverge on purpose: resume is not in the conformance scenarios, and the prompts stay identical.
- **The last allowed attempt escalates** (the user's choice): with the default of 2 cycles, attempt 1 is Sonnet and attempt 2 Opus. With `max_fix_cycles` 1 nothing escalates.
- **No model per WP** (the user's choice): a hard package is split by the architect, not given Opus.
- **The escalation model is a spec constant, the switch is in `agentic.json`**: a bench variant can change the constant; a project turns escalation off without editing the flow.
- **A resumed call that gives nothing is retried fresh once**, inside the launcher: a stale session must not cost the attempt. The engine sees one call.
- **Scoped re-review for both reviewers, full QA** (the user's choice). QA tests behaviour end to end; the reviewers judge code, and the diff is where a fix changes it.
- **Fingerprints are computed by the engine**, from fields that do not depend on wording that changes between reviews (axis, tier, rule, file, the start of the problem). Discarded: asking the reviewer for an id (it would invent one) and hashing the evidence (it changes every time).
- **A missing verdict is NOT_ADDRESSED**: uncertainty never closes a finding.
- **New findings in a re-review never extend the loop** but still count for the result: a new floor finding makes the run `REVIEW`, so a person sees it.
- **No re-review call for an axis without open findings**: a fix that came only from QA or verification is checked again by QA and verification, not by the reviewers. Accepted cost of the saving; section 11.
- **The budget counts model agent calls** (the user's choice), opt-in (the user's choice), checked at prepare and before each fix cycle with the review and QA reserved; verifiers are not reserved because their number is unknown, and a stage is never cut.
- **The advisor is a measured experiment, fallback and bench only**: the native engine inherits the person's own advisor setting and cannot set one per agent.
- **v213's unique checks move to the suites of the packages that own them**, by module, as design 0017 asks; the deletion is in wave 1.
- **Reused:** `text_sum`'s pattern, the conformance harness, `bench.py ab`'s directory arms, `variant.py`, the `.fix-N.diff` files.

## 11. Risks and open questions
- **`claude -p --resume` with `--json-schema` and `--agent` is not verified** in this repository; A/B 1 exercises it on `pricing`. If a resumed session refuses the schema, the fresh retry keeps the run going and the A/B shows the cost.
- **The advisor may not run** in `claude -p` (it needs feature-flag fetching and a supported pairing) and its use may not be visible in the output. Then the experiment is reported as not measured.
- **The scoped re-review can miss a regression a fix introduces outside its findings.** Verification and the full QA run after every fix; the bench's oracle and mutation score show whether quality drops.
- **Opus costs more per call**: escalation only happens on a second attempt; A/B 1 shows the effect.
- **A budget too tight stops runs with fix cycles left**: it is opt-in and states the gap.
- **Existing conformance scenarios change agents and prompts** (the second review becomes a re-review); their results must not change. WP-04 says how.
- **Rollback:** revert the release commit and publish a patch; projects reinstall the previous tag. `agentic.json` keys the old version does not know are ignored by it.
