# Architecture: a more reliable review (agentic-flow 2.13.0)
Type: change · Size: large

## 1. Goal
The code review becomes two reviewers that run in parallel and never share a ranking: `reviewer` keeps the Spec axis (contracts, correctness, security, callers) and a new `standards-reviewer` takes the Standards axis (section 7 and the printed rules). Every judge's finding carries a tier that says what happens to it, on one scale: Floor never ships, Reflex blocks unless the plan waives it with a recorded reason, Finish never blocks. Facts state where they come from: section 4b of a plan and every reviewer's evidence are `read` (at a `file:line`) or `inferred`, `validate` checks the `read` ones and the plan-reviewer challenges the `inferred` ones first. The rules are printed into the prompts instead of being named as files, and prompt changes are tested like code: saved pressure scenarios run against the old and the new definition. Issues 52, 53, 54, 55, 56 (measurement only) and 66.

## 2. Scope
### Included
- `standards-reviewer` (new agent), wired in both engines, the hook, the one-off `run-review` and the fix sources.
- `tier` on the findings of both reviewers, the test-auditor and QA's defects; blocking decided by tier in both engines and in `run-wave --fix`; `waivers` in the manifest, validated.
- `provenance` on reviewer findings; a `Source` column in section 4b, checked by `validate`; the plan-reviewer and the verifier use it.
- The text of the rules in every prompt that carried their paths, with an integrity check and a fall-back to the paths.
- A constant that keeps the rules away from the implementer, and `bench/variant.py`, so an A/B can measure issue 56. The implementer keeps its standards in 2.13.0.
- `bench/scenario.py`: repeat, old-against-new, saved results, more kinds of expectation; five new scenarios.
- Version 2.13.0, upgrade notes, docs; `test_acceptance_v212.py` retired with its unique checks moved.

### Excluded (non-goals)
- Moving the standards out of the implementer (issue 56 proper): decided after the A/B, in the next package.
- Finding fingerprints, scoped re-review, run budgets, resuming implementers (issues 48, 49, 50).
- A tier or a waiver for the deterministic checks (the hook's shortcuts, the ratchet, ownership): they are Floor by definition and nobody waives them.
- Rule ids in the rules library: a waiver names a rule by its words.
- Changing the bench fixtures' plans (their 4b tables keep no `Source` column: a warning, not an error).
- Real agent sessions in CI or in any test.

## 3. Stack
Python 3.9+ standard library only (`.claude/bin`, `bench`); JavaScript for the native workflow (`.claude/workflows/agentic-implement.js`, no imports, no disk); Node 18+ for `test_workflow.mjs`. No package manager, no new dependency.
- Build: `python3 -m unittest discover -s bench -p "test_*.py"`
- Lint: `node .claude/bin/test_workflow.mjs`
- Types: `python3 -m unittest discover -s bench/acceptance`
- Tests: `python3 -m unittest discover -s .claude/bin -p "test_*.py"`
- Also in CI and to run before a push: `python3 -m unittest discover -s acceptance`, `python3 -m unittest discover -s qa`, `python3 .claude/bin/agentic.py quality`, `python3 .claude/bin/agentic.py docs-check`.

## 4. Repository structure
```
.claude/
  agents/
    reviewer.md                 WP-06   the Spec axis
    standards-reviewer.md       WP-06   new: the Standards axis
    verifier.md qa.md test-auditor.md implementer.md test-author.md plan-reviewer.md   WP-06
  commands/architect.md implement.md                                                    WP-06
  workflows/
    pipeline-spec.json          WP-06   schemas, prompts, constants
    agentic-implement.js        WP-05
  bin/
    findings.py                 WP-01   new: tiers, waivers, blocking
    test_findings.py            WP-01   new
    manifest_check.py           WP-02   waivers, section 4b provenance, the agent names
    test_manifest_check.py      WP-02
    repo_scan.py launch.py guardrail.py installer.py agentic.py                        WP-03
    test_repo_scan.py test_launcher.py test_guardrail.py test_agentic.py testutil.py   WP-03
    core.py                     WP-03   stage_of knows the STANDARDS job
    pipeline.py conformance.json test_pipeline.py                                      WP-04
    test_workflow.mjs           WP-05
    test_definitions.py         WP-06
    test_doctor.py test_plan_picture.py test_install.py                                WP-08
    test_acceptance_v212.py     WP-08   deleted
    upgrade.py                  WP-09
    test_acceptance_v213.py     AT      new
bench/
  scenario.py variant.py test_scenario.py test_variant.py                              WP-07 (variant.py, test_variant.py new)
  scenarios/                    WP-07   review-style/, review-contract/, verifier-inferred/, plan-inferred-row/ new
docs/
  how-to/bench.md               WP-07
  how-it-works.md roadmap/repo-review-2026-11.md                                       WP-09
README.md                       WP-09
.claude-plugin/plugin.json      WP-09
```

## 4b. Existing code context
| What an implementer needs to know | Where it is | Pattern or rule | Source |
|---|---|---|---|
| The review block of the fallback engine: concerns and callers text, one `reviewer` call, one `verifier` per blocking finding in parallel, `confirmed`/`refuted`/`advisory`, `run["review"]`, `close-stage review`, then QA and how defects become fix cycles or `pending` | `.claude/bin/pipeline.py:441-495` | It lives inside `Pipeline.judge`, which is over the ratchet's function limit (96 lines in the baseline) and may not grow: the new review goes in a new method | read |
| The same block in the native workflow | `.claude/workflows/agentic-implement.js:489-536` | Inside `runAfterPlan` (150 lines in the baseline, may not grow): the new review goes in a new function. The script has no disk access: everything it knows comes from `plan` | read |
| `BLOCKING` is the set of severities `critical`, `high`, and every "does it block" test is `BLOCKING.has(x.severity)` / `x["severity"] in self.blocking` | `.claude/workflows/agentic-implement.js:162`, `.claude/bin/pipeline.py:452-491`, `.claude/bin/pipeline.py:308-310` | Replace each by the tier test of section 6; a finding with no `tier` falls back to its severity, so old reports and the existing conformance scenarios keep their result | read |
| The engines build the rules sentence from `plan.rules` (paths) | `.claude/bin/pipeline.py:250`, `.claude/workflows/agentic-implement.js:403` | Becomes the printed text when it arrives intact, else this sentence | read |
| `rule_files(manifest)` and `rules_hint(manifest)`: the installed rule paths and the sentence ` Rules you must follow (language and common): <paths>.` | `.claude/bin/repo_scan.py:58-67` | `rules_text` is added beside them; `rules_hint` stays as the fall-back | read |
| `pipeline_plan` prints the plan both engines follow, as one JSON line | `.claude/bin/launch.py:430-440` | Gains `waivers`, `rules_text`, `rules_sum`, `implementer_rules` | read |
| The one-off stages: `run_stage(manifest, label, jobs, expected)` runs `jobs` `(id, agent type, prompt)` in parallel; the id is the entity (`AGENTIC_WP`), the ledger key and the report file `runs/<id>.json`; `run_review` has one job | `.claude/bin/launch.py:118-138`, `.claude/bin/launch.py:255-256` | A job may carry a fourth element, the entity, when its id is not one | read |
| `--fix` sources: `REPORT_FILE_RE`, `REPORT_KEYS`, `_report_items` (a shared `REVIEW-<n>.json` counts only with the key `needs_validation`), `_record_items` (`review.confirmed`, plus `advisory` with `--all`), `latest_reports`, `fix_defects` (keeps `severity in blocking`) | `.claude/bin/launch.py:27-30`, `.claude/bin/launch.py:145-212` | A third kind, `STANDARDS`; blocking by tier; waived findings never reach a fix | read |
| `pipeline_tools`: the reviewer gets `REVIEW_TOOLS` plus the manifest's bash | `.claude/bin/launch.py:318-324` | `standards-reviewer` gets the same | read |
| The hook's claim table and the types that must claim | `.claude/bin/guardrail.py:63-64`, `.claude/bin/guardrail.py:118-121` | Add `standards-reviewer` to both, claiming `REVIEW` | read |
| A claim is refused when another agent holds the same id in the stage: `<id> was already claimed by another agent in this stage.` | `.claude/bin/guardrail.py:92-110` | Two reviewers now claim `REVIEW` at once: that id, which owns no file, may be held by several agents | read |
| `validate` knows the flow's agent names | `.claude/bin/manifest_check.py:255` | Add `standards-reviewer` | read |
| `validate(manifest)` returns the errors; `complexity_warnings(manifest)` the warnings `cmd_validate` prints as `warning: <text>` | `.claude/bin/manifest_check.py:62-78`, `.claude/bin/agentic.py:153-157` | Waiver errors join `validate`; provenance is checked by `cmd_validate` and `cmd_pipeline_plan` only | read |
| `mirror_errors`: how a `path:start-end` reference is checked (no `..`, not absolute, file exists, `1 <= a <= b <= lines`) | `.claude/bin/manifest_check.py:281-302` | The provenance check of section 4b reuses the same test | read |
| `owns(pattern, path)`: exact path, or a directory prefix when the pattern ends in `/` | `.claude/bin/core.py:261-263` | Waiver scopes use it | read |
| `brief.split(text)` cuts `architecture.md` into `## N.` sections, fenced lines never start one | `.claude/bin/brief.py:18-28` | The provenance check finds section `4b` with it | read |
| The spec: constants `blocking`, `refute_confidence`, `audit_rounds`; prompts keyed by name with `{placeholders}`; one schema per agent type | `.claude/workflows/pipeline-spec.json:3-9` (constants), `.claude/workflows/pipeline-spec.json:269-280` (where the reviewer's schema starts) | The JS keeps its own copies of schemas and constants; `test_workflow.mjs` compares them with the spec | read |
| The engine test world: a declaration (`review`, `verifier`, `qa`, `audit`, `reports`, `plan`, `gate_fail`) becomes fake `gate` and `agent` functions; `summarize` is what both engines must agree on | `.claude/bin/test_pipeline.py:28-135` | A scenario's `plan` is merged over the base plan; add `standards` (a list of reports like `review`) and the new summary fields | read |
| A conformance scenario's shape | `.claude/bin/conformance.json:260-282` | Its findings carry no `tier`, `fix` or `if_skipped`: they must keep working | read |
| `reviewer.md`: process, confidence filter (four parts, false positives), checklist (Security, Correctness, Contracts, Maintainability), severity anchors, needs validation, report | `.claude/agents/reviewer.md:20-69` | Maintainability and "breaches of section 7" move to the Standards axis | read |
| `test_definitions.py` pins text of the agents: the `AGENTS` table, the judges' anchors and `needs_validation`, the reviewer's callers sentences, the implementer's ladder | `.claude/bin/test_definitions.py:34-44`, `.claude/bin/test_definitions.py:132-171` | Every pinned phrase stays where it is; `standards-reviewer` joins the table | read |
| `test_definitions.py` lists the manifest fields `/architect` must document | `.claude/bin/test_definitions.py:46` | Add `waivers` | read |
| `plan-reviewer.md`: thirteen checklist items, the report `VERDICT`/`CRITICAL`/`IMPROVEMENTS`; item 9 opens the references of 4b | `.claude/agents/plan-reviewer.md:16-40` | A new first item for provenance, one for waivers | read |
| `/architect`'s template for 4b and the "No invented figures" rule | `.claude/commands/architect.md:138-140`, `.claude/commands/architect.md:189` | The table gains the `Source` column | read |
| `bench/scenario.py`: one run of one agent, `met` = status and a blocking finding with every mention; `prepare` copies the scenario minus `scenario.json` | `bench/scenario.py:42-129` | Extended, the single-run output unchanged | read |
| `bench.py ab` takes a directory that holds `.claude/bin/agentic.py` as an arm, as it is | `bench/bench.py:728-733` | `variant.py` builds such a directory | read |
| The rules a Python project gets printed: `common.md` 3,916 bytes and `python.md` 1,805 bytes | `.claude/rules-library/common.md:1-59`, `.claude/rules-library/python.md:1-45` | Measured with `wc -c`; the cost per prompt in tokens is not measured | read |
| The native engine gets every command's output through the `gatekeeper` agent, which copies it into its structured answer | `.claude/agents/gatekeeper.md:1-31` | A long `rules_text` may arrive altered: hence the checksum. How often it does is not measured | inferred |

The line ranges of this table and of the packages' patterns describe the code before this change; they stay inside each file's length after it (no reference reaches the last lines of a file a package shortens, and none points at a file a package deletes).

What must NOT change: the result of the existing conformance scenarios (44 today; one is replaced, the other 43 keep their result); the top-level `review.confirmed`, `review.refuted`, `review.advisory` (they become the union of both axes); `scenario.py`'s output for a plain single run; every phrase `test_definitions.py` pins; the hook's deterministic checks.

## 5. Data model
```python
# A finding of either reviewer (pipeline-spec.json; the JS keeps a copy)
{"tier": "floor" | "reflex" | "finish",   # reviewer: floor | finish; standards-reviewer: reflex | finish
 "severity": "critical" | "high" | "medium" | "low",   # reviewer only: the damage, as today
 "rule": str,                  # standards-reviewer only, required: the rule's opening words, copied
 "provenance": "read" | "inferred",       # read: the evidence quotes code at file:line; inferred: deduced, not opened
 "wp": str, "file": str, "line": int, "problem": str, "evidence": str, "fix": str, "if_skipped": str}
# required, reviewer: tier, severity, provenance, wp, file, problem, evidence, fix, if_skipped
# required, standards-reviewer: tier, rule, provenance, wp, file, problem, evidence, fix, if_skipped

# The standards-reviewer's report
{"status": "PASS" | "FAIL", "axis": "standards", "findings": [finding], "not_checked": [str]}
# required: all four. "axis" is an enum of one value: it is how a shared REVIEW-<n>.json is told from the others.

# test-auditor findings and QA defects gain  "tier": "floor" | "finish"  (required)

# A waiver, in the manifest's optional "waivers" list
{"rule": str,      # words of a rule, found in the installed rules
 "scope": str,     # one file, or a folder ending in "/", inside one package's zone
 "reason": str}    # "<who decided>: <evidence>"

# The engines add to each reviewer finding:  "axis": "spec" | "standards"
# and to a waived one:                        "waiver": <the waiver's reason>

# The run record
"review": {"spec":      {"confirmed": [], "refuted": [], "advisory": []},
           "standards": {"confirmed": [], "refuted": [], "advisory": [], "waived": []},
           "confirmed": [], "refuted": [], "advisory": [],   # spec's, then standards'; never sorted
           "waived": [], "opened": bool, "callers": int}
"rules": "printed" | "pointed" | "none"

# pipeline-plan gains
"waivers": [waiver], "rules_text": str, "rules_sum": int, "implementer_rules": bool

# pipeline-spec.json constants gain   "implementer_rules": true
```
Tier semantics, the same words in every agent: **floor** never ships (it breaks a contract of section 6, a criterion, correctness or security; a critical or high severity); **reflex** is a breach of a written rule, a default the model falls into, and blocks unless the plan waives it; **finish** is worth knowing and never blocks. The deterministic checks (the hook, ownership, the ratchet) are Floor and carry no field.

## 6. Contracts between modules
```python
# findings.py (WP-01): pure functions, no imports from the flow
TIERS = ("floor", "reflex", "finish")

def tier_of(item, blocking) -> str:
    """item["tier"] when it is one of TIERS; else "floor" if item.get("severity") is in blocking, else "finish"."""

def in_scope(path, scope) -> bool:
    """path is the scope, or lies under it when the scope ends in "/". False for a path that is not a string."""

def waiver_for(item, waivers):   # a waiver dict, or None
    """The first waiver that covers a reflex finding: item["file"] in its scope and the rule names agree (after
    casefold and strip, both non-empty, one contains the other). None for any other tier."""

def blocks(item, blocking, waivers=()) -> bool:
    """floor: True. reflex: True unless waiver_for finds one. finish: False."""

def text_sum(text) -> int:
    """sum of the code points of text, modulo 1000000007."""

# repo_scan.py (WP-03)
def render_rules(paths, root) -> str:
    """"" for no paths. Else "\nRules you must follow (common and language). They are printed here, so do not read
    them from disk:\n" followed, for each path, by "\n--- <path> ---\n<body>\n", where body is the file's text
    without a leading "---" frontmatter block, stripped."""

def rules_text(manifest) -> str:
    """render_rules(rule_files(manifest), ROOT)."""

# manifest_check.py (WP-02)
def waiver_errors(manifest) -> list:
    """Errors of the optional "waivers" list (messages below). [] when it is absent."""

def provenance_problems(text) -> tuple:
    """(errors, warnings) for section 4b of an architecture.md text. ([], []) when there is no 4b or no table."""
```
`validate(manifest)` appends `waiver_errors(manifest)` only. The provenance of section 4b is checked in exactly two places, both before any agent runs: `cmd_validate` and `cmd_pipeline_plan` (WP-03, `agentic.py`), after the plan is loaded and valid (`require_valid()` in the first, `require_runnable()` in the second), on `ARCH`'s text when the file exists. Errors end the command as `require_valid` does (`Invalid manifest:` and one indented line per error, exit 1); `cmd_validate` prints the warnings after the complexity ones, as `warning: <text>`. `require_valid()` itself never checks provenance: `claim`, `open-stage`, `close-stage`, `verify` and `briefs` call it during a run, and a package that shortens a file a `read` row cites must not stop the run it belongs to.

Waiver errors, at most one per waiver (the first row of this table that applies), each starting `waivers[<i>]: ` (i from 0):
| Problem | Message after the prefix |
|---|---|
| not an object with exactly the string fields `rule`, `scope`, `reason` | `must be {"rule", "scope", "reason"}, all text` |
| `rule` (casefold) is shorter than 3 characters or appears in no installed rule file (`RULES_DIR/*.md`, else `RULES_LIBRARY/*.md`; skipped when neither folder exists) | `rule "<rule>" is not in the installed rules` |
| `scope` is empty, `.`, `./`, absolute, holds `..` or one of `*?[` | `scope "<scope>" must be one file or one folder ending in "/"` |
| `scope` is not inside one package's zone: no entry `f` of any package's `files` with `scope == f` or (`f` ends in `/` and `scope` starts with `f`) | `scope "<scope>" is wider than any package's files` |
| `reason` does not match `^[^:\s][^:]*: \S.{9,}$` | `reason must be "<who decided>: <evidence>"` |
| the same `rule` (casefold) and `scope` as an earlier waiver | `repeats waivers[<j>]` |
A rule of section 7 of the plan is not waivable: change the plan instead.

Provenance of section 4b (`provenance_problems`): the table is the lines of section `4b` that start with `|`; cells are split on `|` outside backticks. With no header cell equal to `source` (casefold): one warning, `section 4b has no Source column: mark each row read or inferred`. Otherwise, per data row (numbered from 1, the separator row skipped):
- Source (backticks and spaces stripped, casefold) is not `read` or `inferred`: error `section 4b, row <n>: Source must be read or inferred`.
- `read`: every backticked token of the row that matches `^[\w./-]+\.\w+:\d+(-\d+)?$` is checked as `mirror` references are; a bad one gives `section 4b, row <n>: <token> does not exist or is out of range`; none at all gives `section 4b, row <n>: read needs a file:line`.
- `inferred`: nothing is checked.

**The review stage, identical in both engines** (a new `Pipeline.review(post)` in `pipeline.py`, a new `reviewStage(post)` in the JS; `judge`/`runAfterPlan` call it and keep everything after `close-stage review`):
1. Build `concerns` and `callers` as today. Launch in parallel: `reviewer` (label `reviewer`) with `prompts.reviewer`, and `standards-reviewer` (label `standards-reviewer`) with `prompts.standards_reviewer` = `Review the integrated code against section 7 of architecture.md and the rules below. Report only breaches of a written rule: name it in "rule".{rules}`. Both use the entity `REVIEW`.
2. No report from the first: `stop('review', 'the reviewer returned no report')`. None from the second: `stop('review', 'the standards reviewer returned no report')`.
3. Add `axis` to every finding. `waived` = the standards findings for which `waiver_for` finds a waiver of `plan.waivers`, each with `waiver: <reason>`.
4. `graves` = the spec findings that block, then the standards findings that block (`blocks`, with the plan's waivers). One `verifier` per grave finding, in parallel, as today (label `verify <file>`).
5. Per axis: `confirmed` = its graves not refuted with confidence (the rule of today); `refuted` = the rest of its graves; `advisory` = its findings that do not block and are not waived.
6. `run.review` as in section 5. `needsReview` from the spec reviewer's `needs_validation`, as today. `close-stage review REVIEW=fail` when the union `confirmed` is not empty.
7. Downstream, `confirmed` of the Spec axis is tagged `source: 'reviewer'` and of the Standards axis `source: 'standards-reviewer'`. Every other `BLOCKING.has(x.severity)` test (QA's defects, the test audit's `weak`, `pending`) becomes `blocks(x)` with the same fall-back.

**Rules in the prompts, both engines:** `intact` = `plan.rules_text` is a non-empty string and `text_sum(plan.rules_text) == plan.rules_sum`. `RULES` = `plan.rules_text` when intact; else the paths sentence of today when `plan.rules` is not empty; else `""`. `run.rules` = `printed`, `pointed` or `none` accordingly. `IMPLEMENTER_RULES` = `""` when `plan.implementer_rules === false`, else `RULES`: the prompts `implement`, `fix` and `implement_full` use it; every other prompt uses `RULES`. The JS sums code points (`for (const ch of text) sum = (sum + ch.codePointAt(0)) % 1000000007`).

`pipeline_plan` (WP-03): `waivers` = the manifest's list or `[]`; `rules_text` = `rules_text(manifest)`; `rules_sum` = `text_sum` of it; `implementer_rules` = the spec constant. `render_prompt` (the one-off commands) uses `rules_text(manifest)`, and `""` for the implementer's prompts when the constant is false. `pipeline.render(template, **values)` (WP-04) replaces every `{name}` in one pass over the template, leaving unknown names as they are, so text that is inserted (a printed rule, a caller's line) is never expanded again; the comment about the order of `callers` goes.

**One-off commands and fix sources (WP-03):**
- `run_review` runs two jobs: `("REVIEW", "reviewer", <prompt>)` and `("STANDARDS", "standards-reviewer", <prompt>, "REVIEW")`. In `run_stage` a job's fourth element is its entity (default: its id): the entity is what the hook sees (`AGENTIC_WP`), the id names the report file, the summary line and the ledger entry. `run_agent` gains `entity=None` for it. So the `STANDARDS` job has its own ledger entry (its own pid, which `stop` reaches) and never writes the `REVIEW` entry. Reports: `runs/REVIEW.json` and `runs/STANDARDS.json`.
- `REPORT_KEYS` gains `"STANDARDS": "findings"`. `latest_reports` returns up to three kinds. A shared `REVIEW-<n>.json` is `STANDARDS` when its report has `axis == "standards"`, `REVIEW` when it has `needs_validation`, else ignored. The one-off `STANDARDS.json` is `STANDARDS`.
- `_record_items`: `REVIEW` reads `review.spec.confirmed` (+ `advisory` with `--all`) when the record has `review.spec`, else `review.confirmed` as today; `STANDARDS` reads `review.standards.confirmed` (+ `advisory`), `None` when the record has no `review.standards`.
- `fix_defects(spec, wp_id, include_all=False, reports=None, waivers=())` tags `reviewer`, `standards-reviewer`, `qa`; without `--all` it keeps an item when `blocks(item, blocking, waivers)`; with `--all` everything but waived items. `run_wave` passes the manifest's waivers.
- `pipeline_tools` gives `standards-reviewer` what it gives `reviewer`.
- The hook's claim (`guardrail.py`): the review entity's id (`REVIEW`) may be claimed by several agents in one stage, because it owns no file; every other id keeps the refusal of today. An agent that already claimed another id is still refused.

**Conformance (WP-04 writes the scenarios, WP-05 makes the JS agree; the spec is WP-06's).** The test world gains `standards`: a list of reports picked like `review` (a `null` entry means no report); default `{"status": "PASS", "axis": "standards", "findings": [], "not_checked": []}`. `summarize` gains `"review_axes": {"spec": [confirmed, refuted, advisory], "standards": [confirmed, refuted, advisory, waived]}` (counts of the last review of the run, since each review replaces `run.review`; `null` when there was none) and `"rules": <run.rules>`. New scenarios, by exact name:
| Name | Declaration | Ends as |
|---|---|---|
| `the two axes keep separate lists` | spec: one floor finding on WP-01; standards: one reflex finding on WP-02; then both pass | fix cycle 1, `OK`; the fix prompt of WP-01 holds its finding with `"axis":"spec"` and `"source":"reviewer"`, WP-02's holds its own with `"axis":"standards"` and `"source":"standards-reviewer"`; the last review's axes are all zero |
| `a reflex finding blocks until it is fixed` | standards: one reflex, then pass | `OK`, `fix_cycles` 1 |
| `a waived reflex finding does not block and is recorded` | the same finding, `plan.waivers` covering it | `OK`, `fix_cycles` 0, no `verifier` call, axes standards `[0,0,0,1]` |
| `a finish finding never blocks` | spec: `tier: finish` with `severity: high` | `OK`, no verifier, axes spec `[0,0,1]` |
| `the standards reviewer returned no report` | `standards: [null]` | `REVIEW`, `failed_stage` `review` |
| `printed rules reach the agents` (replaces `language rules reach the agents`) | `plan.rules`, `plan.rules_text` = `"\nRules you must follow (common and language). RULE-TEXT"`, its right `rules_sum` | every agent prompt but the gatekeeper's and the verifier's holds `RULE-TEXT`; `rules` `printed` |
| `rules text that arrives damaged falls back to the paths` | the same with a wrong `rules_sum` | prompts hold the paths sentence, not `RULE-TEXT`; `rules` `pointed` |
| `the implementer can be left without the rules` | intact rules and `plan.implementer_rules: false` | the implementer's prompt has no `RULE-TEXT`; the reviewers' have it |

```python
# bench/scenario.py (WP-07). run() keeps its signature and its keys, plus "text" (the agent's text answer or None).
def repeat(target, runs, claude=None, agent_file=None) -> dict:
    """{"met": <how many runs met>, "total": runs, "runs": [run() results]}, runs one after another."""

def compare(target, runs, against, claude=None, agent_file=None) -> dict:
    """{"old": repeat-shape, "new": repeat-shape, "p": float}: runs of the agent defined by `against` and of the
    current definition (or agent_file), alternating old, new. p is the one-sided Fisher exact probability of the
    new arm meeting at least as often as it did if both arms were alike, rounded to 3 digits."""

def fisher_p(old_met, old_total, new_met, new_total) -> float

#   python3 bench/scenario.py TARGET [--agent-file PATH] [--repeat N] [--against PATH] [--save]
#   TARGET: a scenario folder (its scenario.json) or one .json file inside a scenario folder.
#   No --repeat and no --against: one run, the output of 2.12.0 plus "text". --repeat N alone: repeat().
#   --against PATH: compare(), N defaulting to 3. --save: also writes the printed JSON to
#   <results>/<name>-<YYYYMMDD-HHMMSS>.json (the reports, verbatim, are the record). <results> is
#   bench/results/scenarios of this checkout; <name> is the scenario folder's name for scenario.json, and
#   "<folder>-<file stem>" for another file (review-style/standards.json -> review-style-standards).
def main(argv, now=None, results=None) -> int:
    """now: a datetime (default: the clock); results: the folder --save writes in (default as above, created)."""
#   Exit 0 when every run of the new (or only) arm met, 3 otherwise, 1 on a usage error.

# bench/variant.py (WP-07)
def build(name, dst, src=CHECKOUT) -> Path:
    """Copies src's files (git ls-files --cached --others --exclude-standard: tracked or new, never ignored) to dst, which must not exist, applies the variant and returns dst.
    Raises ValueError for an unknown name."""
#   python3 bench/variant.py NAME DST      exit 0, prints DST; exit 1 with "Uso: variant.py NAME DST" otherwise
#   NAME "implementer-no-standards": pipeline-spec.json's constants.implementer_rules becomes false; in
#   .claude/agents/implementer.md the whole "# Before writing" section is removed and the one line matching
#   ^\d+\. \*\*Conventions\.\*\* becomes "4. **Conventions.** Follow section 7 and the style of the existing code."
#   A definition with no such section or no such line raises ValueError: the variant never builds half-applied.
```
Scenario files (`scenario.json`, or any other top-level `.json` of the folder; `prepare` copies none of them). New optional keys: `model` (default `sonnet`), `schema` (default true; false: no `--json-schema`, the answer is text), `prompt_text` (a literal prompt, instead of `prompt`), `suffix` (appended to the prompt), `rules` (rule names: `{rules}` becomes `render_rules` of those files of this checkout's `.claude/rules-library`). `expect` may hold, all of which must hold: `status`; `finding_mentions` (some blocking finding, by `blocks` with the spec's `blocking`, whose `problem`, `evidence` and `rule` together contain every string, casefolded); `tier` (that finding's tier); `no_blocking: true` (no blocking finding); `equals` (`{field: value}` of the report); `min` (`{field: number}`); `text_mentions` (every string is in the text answer, casefolded).

## 7. Conventions
- English everywhere; no type annotations in `.claude/bin` (the existing modules have none; an exception to the generic Python rule). `bench/` keeps `from __future__ import annotations`.
- Every `open`, `read_text` and `write_text` in `.claude/bin` names `encoding="utf-8"`.
- The ratchet: functions up to 60 lines (100 in tests), nesting 4, lines up to 120 characters, files up to 800 lines; a function or file already over its limit may not grow. `Pipeline.judge`, `runAfterPlan`, `test_agentic.py` and `bench/bench.py` are over: add nothing to them.
- Both engines change together: every behaviour of section 6 is a conformance scenario, and the JS copies of schemas and constants equal the spec's.
- A prompt or an agent definition says what to do, in the present; no version numbers, issue numbers or stories of past runs.
- Fixtures write non-ASCII characters as escapes and split the shortcut tokens the hook blocks.
- No real `claude` in tests: a fake script per test. Real sessions only in QA, by hand.
- The manifest's `stack` is `python` only: the workflow script is plain JavaScript with no build step, and the `typescript` rules do not describe it.
- Commits are the maintainer's; agents do not commit.

## 8. Work packages and acceptance criteria
### Acceptance criteria
Engine criteria run the Python engine through `test_pipeline.run_scenario` on the named conformance scenario; the JS engine's agreement is `node .claude/bin/test_workflow.mjs`, which the same test runs and expects to exit 0 (skipped with a message when `node` is not installed).

- AC-001 · Two axes, two lists
  - Scenario: the conformance scenario `the two axes keep separate lists`.
  - Action: run it in the Python engine.
  - Expected: result `OK` after 1 fix cycle; two reviewer agents ran in the first review (`reviewer:reviewer` and `standards-reviewer:standards-reviewer`); the fix prompt of WP-01 holds the spec finding's problem with `"axis":"spec"` and not the standards one, and WP-02's the opposite with `"axis":"standards"`; `node .claude/bin/test_workflow.mjs` exits 0.
  - Must not: put a standards finding in `review.spec`, or sort the union by severity.
  - Check: `test_acceptance_v213.AxesTests.test_ac_001_two_axes`
  - WP: WP-04, WP-05
- AC-002 · The tier decides what blocks
  - Scenario: the scenarios `a reflex finding blocks until it is fixed`, `a waived reflex finding does not block and is recorded`, `a finish finding never blocks`, `the standards reviewer returned no report`.
  - Action: run each.
  - Expected: `OK` with 1 fix cycle; `OK` with 0 fix cycles, no `verifier` call and `review_axes.standards == [0, 0, 0, 1]`; `OK` with no verifier call and `review_axes.spec == [0, 0, 1]`; `REVIEW` with `failed_stage` `review`.
  - Must not: verify or fix a waived finding; block on a `finish` finding whatever its severity.
  - Check: `test_acceptance_v213.AxesTests.test_ac_002_tiers`
  - WP: WP-01, WP-04, WP-05
- AC-003 · Old reports keep their meaning, and a hand fix sees both axes
  - Scenario: (a) items `{"severity": "high"}`, `{"severity": "low"}`, `{"tier": "finish", "severity": "critical"}`, `{"tier": "reflex", "rule": "No magic numbers", "file": "src/a.py"}`; a waiver `{"rule": "magic numbers", "scope": "src/", "reason": "ana: constants of the tax table"}`. (b) a project whose `runs/` holds a one-off `REVIEW.json` (one floor finding on WP-02) and `STANDARDS.json` (one reflex finding on WP-02 with rule `No magic numbers` on `src/b/x.py`, one finish finding).
  - Action: (a) `findings.blocks(item, ["critical", "high"], waivers)`; (b) `run-wave 1 WP-02 --fix` with a fake `claude`, then the same after adding that waiver for `src/b/` to the manifest.
  - Expected: (a) True, False, False, and for the reflex item True with no waivers and False with the waiver; (b) the first prompt holds both blocking problems and not the finish one; with the waiver, only the floor one.
  - Must not: (b) read a `refuted` list; hand a waived finding to the implementer, even with `--all`.
  - Check: `test_acceptance_v213.TierTests.test_ac_003_fallback_and_fix_sources`
  - WP: WP-01, WP-03
- AC-004 · validate judges the waivers
  - Scenario: a project with the rules library copied in and a manifest whose WP-01 owns `src/a.py` and WP-02 `src/b/`.
  - Action: `agentic.py validate` with, in turn: no waivers; `{"rule": "No magic numbers", "scope": "src/b/x.py", "reason": "ana: tax table constants are the spec"}`; then one bad waiver at a time: scope `src/`, scope `**`, reason `because`, rule `no such rule at all`, and the valid one twice.
  - Expected: exit 0 for the first two; exit 1 for each bad one, with `waivers[0]: scope "src/" is wider than any package's files`, `waivers[0]: scope "**" must be one file or one folder ending in "/"`, `waivers[0]: reason must be "<who decided>: <evidence>"`, `waivers[0]: rule "no such rule at all" is not in the installed rules`, `waivers[1]: repeats waivers[0]`.
  - Must not: accept a scope outside every package's zone.
  - Check: `test_acceptance_v213.PlanTests.test_ac_004_waivers`
  - WP: WP-02
- AC-005 · validate checks where the plan's facts come from
  - Scenario: a project with `src/a.py` of 3 lines and an `architecture.md` whose section 4b table is, in turn: without a `Source` column; with one `read` row citing `` `src/a.py:1-3` `` and one `inferred` row with no reference; with a `read` row citing `` `src/a.py:1-9` ``; with a `read` row citing nothing; with a row whose Source is `seen`.
  - Action: `agentic.py validate` each time; for the `src/a.py:1-9` table also `agentic.py pipeline-plan` and `agentic.py briefs`.
  - Expected: exit 0 and `warning: section 4b has no Source column: mark each row read or inferred`; exit 0 with no warning; exit 1 with `section 4b, row 1: src/a.py:1-9 does not exist or is out of range`; exit 1 with `section 4b, row 1: read needs a file:line`; exit 1 with `section 4b, row 1: Source must be read or inferred`. With the out-of-range row, `pipeline-plan` exits 1 with the same message and `briefs` exits 0.
  - Must not: fail a plan with no section 4b, or one whose 4b has no table; stop a command other than `validate` and `pipeline-plan`.
  - Check: `test_acceptance_v213.PlanTests.test_ac_005_provenance`
  - WP: WP-02, WP-03
- AC-006 · The rules are printed, and pointed at when the text arrives damaged
  - Scenario: (a) a project with the rules library, `rules-sync` run, stack `python`; (b) the scenarios `printed rules reach the agents` and `rules text that arrives damaged falls back to the paths`.
  - Action: (a) `agentic.py pipeline-plan`, and `run-wave 1` with a fake `claude`; (b) run both scenarios.
  - Expected: (a) the plan's `rules_text` starts with `\nRules you must follow (common and language). They are printed here, so do not read them from disk:`, holds `--- .claude/rules/agentic/common.md ---` and the text `No magic numbers`, holds no `paths:` frontmatter line, and `rules_sum == findings.text_sum(rules_text)`; the implementer's prompt holds `No magic numbers`; (b) `rules` is `printed` and the implementer's and both reviewers' prompts hold `RULE-TEXT`; then `rules` is `pointed` and they hold `Rules you must follow (language and common): .claude/rules/agentic/common.md` and no `RULE-TEXT`.
  - Must not: give the gatekeeper or the verifier any rules; print rules in a project with none installed (`rules_text` is `""`).
  - Check: `test_acceptance_v213.RulesTests.test_ac_006_printed_rules`
  - WP: WP-03, WP-04, WP-05
- AC-007 · The standards reviewer is an agent of the flow
  - Scenario: this checkout; a temporary project.
  - Action: read `.claude/agents/standards-reviewer.md`; send the hook a `claim REVIEW` from an agent of type `reviewer` and then, in the same stage, a `claim REVIEW` and a `Write` from another agent of type `standards-reviewer`; two implementers claim `WP-01`; `run-review` with a fake `claude`.
  - Expected: frontmatter `model: sonnet` and tools `Read, Glob, Grep, Bash, StructuredOutput`; both `REVIEW` claims exit 0 and the write exits 2; the second implementer's claim of `WP-01` exits 2 with `was already claimed`; `run-review` starts one `reviewer` and one `standards-reviewer`, exits 0, writes `runs/REVIEW.json` and `runs/STANDARDS.json`, and its summary names both ids.
  - Must not: let the standards reviewer write a file; write the ledger's `REVIEW` entry from the `STANDARDS` job (the ledger holds both entries).
  - Check: `test_acceptance_v213.StandardsAgentTests.test_ac_007_agent`
  - WP: WP-03, WP-06
- AC-008 · The agents speak the scale and say where facts come from
  - Scenario: the agent and command definitions.
  - Action: read them.
  - Expected: `reviewer.md` holds `# Tiers`, `` `tier` ``, `` `provenance` ``, `the Standards axis` and no `breaches of section 7`; `standards-reviewer.md` holds `# Tiers`, `reflex`, `` `rule` ``, `the rule's opening words`, `Never report a floor`, `No concrete case, no finding`; `qa.md` and `test-auditor.md` hold `` `tier` ``, `floor` and `finish`; `verifier.md` holds `inferred` and still `Uncertainty never downgrades a blocker`; `plan-reviewer.md` holds `inferred` before its `blind implementer` item, and `waivers`; `architect.md` holds `| Source |`, `read`, `inferred` and `` `waivers` ``; `implement.md` holds `Spec`, `Standards` and `waived`; `implementer.md`, `test-author.md` and `qa.md` hold `the rules printed in your prompt`.
  - Must not: keep `the rules your prompt points to` in any agent; drop any phrase `test_definitions.py` pinned before this change.
  - Check: `test_acceptance_v213.DefinitionTests.test_ac_008_definitions`
  - WP: WP-06
- AC-009 · The implementer can be measured without its standards
  - Scenario: the scenario `the implementer can be left without the rules`; this checkout.
  - Action: run the scenario; `bench/variant.py`'s `build("implementer-no-standards", <tmp>/v)`.
  - Expected: the implementer's prompt has no `RULE-TEXT` and the reviewers' have it; the built folder holds `.claude/bin/agentic.py`, its spec's `constants.implementer_rules` is `false`, its `implementer.md` has no `# Before writing`, no `standard library`, no `grep every caller`, holds `4. **Conventions.** Follow section 7 and the style of the existing code.` and still `# Statuses`; this checkout's spec says `true` and its `implementer.md` is unchanged.
  - Must not: change the checkout; build over an existing folder (`ValueError`).
  - Check: `test_acceptance_v213.MeasureTests.test_ac_009_variant`
  - WP: WP-04, WP-05, WP-07
- AC-010 · A prompt change is tested old against new
  - Scenario: a scenario folder made by the test (agent `verifier`, expecting `equals {"is_real": false}` and `min {"confidence": 0.7}`); two fake `claude` scripts chosen by the agent file they find: with the old definition the answer is `is_real: true`, with the new one `is_real: false, confidence: 0.9`.
  - Action: `scenario.compare(target, 2, against=<old file>, claude=<fake>)`; `scenario.fisher_p(2, 5, 5, 5)`; `main` with `--repeat 2 --save` and a fixed clock.
  - Expected: `old` is `{"met": 0, "total": 2, ...}`, `new` `{"met": 2, "total": 2, ...}`, four runs alternating old, new; `fisher_p` is `0.083`; with `now=datetime(2026, 1, 2, 3, 4, 5)` and `results=<tmp>`, `--save` writes `<tmp>/<scenario folder name>-20260102-030405.json`, holding the printed JSON; exit 0.
  - Must not: call a real `claude`; change the keys of a plain single run (`report`, `expect`, `met`, plus `text`).
  - Check: `test_acceptance_v213.MeasureTests.test_ac_010_old_against_new`
  - WP: WP-07
- AC-011 · The saved scenarios are sound
  - Scenario: `bench/scenarios/`.
  - Action: load every scenario file.
  - Expected: `auditor-wrong-expected/scenario.json`, `review-style/standards.json`, `review-style/spec.json`, `review-contract/scenario.json`, `verifier-inferred/scenario.json`, `plan-inferred-row/scenario.json` exist; each names an agent with a definition in `.claude/agents`, and a `prompt` that is a key of the spec or a `prompt_text`; `review-style/src/pricing.py` holds `0.85` and `review-style/standards.json` expects `{"status": "FAIL", "tier": "reflex", "finding_mentions": ["magic"]}`; `spec.json` expects `{"status": "PASS", "no_blocking": true}`; `verifier-inferred` expects `{"equals": {"is_real": false}, "min": {"confidence": 0.7}}`; `plan-inferred-row` has `"schema": false`, `"model": "opus"` and expects `{"text_mentions": ["FIX", "parse"]}`, and its `architecture.md` has a 4b row marked `inferred`.
  - Must not: hold an `__init__.py` under `bench/scenarios/`; tell the agent the answer in a file it reads.
  - Check: `test_acceptance_v213.MeasureTests.test_ac_011_scenarios`
  - WP: WP-07
- AC-012 · Shipped, documented and versioned
  - Scenario: this checkout.
  - Action: read `installer.INSTALL_GLOBS`, `plugin.json`, `upgrade.NOTES`, `README.md`, `docs/how-it-works.md`, `docs/how-to/bench.md`; list `.claude/bin/test_acceptance*.py`.
  - Expected: `.claude/bin/findings.py` is shipped; version `2.13.0`; `NOTES["2.13.0"]` mentions `standards-reviewer`, `tier`, `waivers`, `Source` and `printed`; the module tree names `findings.py`; `README.md`'s agents table names `standards-reviewer`; `bench.md` documents `scenario.py` (`--against`) and `variant.py`; the only acceptance file is `test_acceptance_v213.py`; `test_doctor.ProjectStateTests` and `test_plan_picture.CommandTests` exist.
  - Must not: keep `test_acceptance_v212.py`.
  - Check: `test_acceptance_v213.ReleaseTests.test_ac_012_release`
  - WP: WP-03, WP-07, WP-08, WP-09

### Work packages
Three waves. Wave 1 has no code dependency between its packages; WP-08 is there so the old acceptance file goes as soon as the new one exists. Wave 2 imports `findings.py` and `manifest_check.py` and reads the spec, which WP-06 changes in wave 1. Wave 3 needs the spec and the scenarios of WP-04 (WP-05), `render_rules` of WP-03 (WP-07) and the shipped modules and agents (WP-09). The plan is for the flow's own repository: executed by hand.

#### WP-01 · findings.py: tiers, waivers, blocking
- Wave: 1.
- Files: `.claude/bin/findings.py` (new), `.claude/bin/test_findings.py` (new).
- Implements: `TIERS`, `tier_of`, `in_scope`, `waiver_for`, `blocks`, `text_sum` (section 6).
- ACs: AC-002, AC-003.
- Patterns to mirror: `.claude/bin/brief.py:1-40` (a sibling module: docstring, pure functions).
- Gotchas: the module imports nothing from the flow, so `bench/scenario.py` and both test suites can load it alone. A `tier` that is not one of `TIERS` is ignored (fall back to the severity). `waiver_for` never matches an empty rule on either side. An item whose `file` is missing is in no scope.
- Validation: `python3 -m unittest discover -s .claude/bin -p test_findings.py`.

#### WP-02 · validate: waivers and the provenance of section 4b
- Wave: 1.
- Files: `.claude/bin/manifest_check.py`, `.claude/bin/test_manifest_check.py`.
- Implements: `waiver_errors` and its call from `validate`; `provenance_problems` (called by WP-03's commands); `standards-reviewer` in the agent names of `manifest_check.py:255`.
- ACs: AC-004, AC-005.
- Patterns to mirror: `.claude/bin/manifest_check.py:281-302` (reference checks and message style); `.claude/bin/manifest_check.py:78-110` (a list of warnings).
- Gotchas: split a table row on `|` only outside backticks (cells quote code that holds pipes); drop the empty first and last cells. The reference check must resolve against `ROOT`, as `mirror_errors` does. `provenance_problems` takes text, so tests call it without a file; `validate` never calls it. Import `split` from `brief` (a sibling: `from brief import split`). `RULES_DIR` and `RULES_LIBRARY` come from `core`. `owns` is not the test for scopes: use the rule of section 6's table.
- Validation: `python3 -m unittest discover -s .claude/bin -p test_manifest_check.py`.

#### WP-03 · Printed rules, the one-off review and the fix sources
- Wave: 2, after WP-01, WP-02 and WP-06.
- Files: `.claude/bin/repo_scan.py`, `.claude/bin/launch.py`, `.claude/bin/guardrail.py`, `.claude/bin/installer.py`, `.claude/bin/agentic.py`, `.claude/bin/test_repo_scan.py`, `.claude/bin/test_launcher.py`, `.claude/bin/test_guardrail.py`, `.claude/bin/test_agentic.py`, `.claude/bin/testutil.py`, `.claude/bin/core.py`.
- Implements: `render_rules`, `rules_text`; `pipeline_plan`'s four fields; `render_prompt` with the printed rules; `run_review` with two jobs and `run_stage`'s optional entity; the `STANDARDS` kind in the fix sources and `fix_defects` by tier; `pipeline_tools`; `CLAIM_KINDS` and `claim_required_types`; `.claude/bin/findings.py` in `INSTALL_GLOBS`; the provenance check in `cmd_validate` and `cmd_pipeline_plan`.
- Consumes: `findings.blocks`, `findings.text_sum`, `manifest_check.provenance_problems` (by implementation).
- ACs: AC-003, AC-005, AC-006, AC-007, AC-012.
- Patterns to mirror: `.claude/bin/repo_scan.py:58-67`; `.claude/bin/launch.py:118-212`; `.claude/bin/test_launcher.py:33-70` (a project whose agents are the fake `claude`).
- Gotchas: `launch.py` and `agentic.py` are near their long-line allowance: no new long lines. The fake `claude` of `testutil` answers every schema with empty lists, so a `STANDARDS.json` test writes its report files by hand, as `test_launcher.FixSourceTests` does. The ledger is keyed by the job's id: `core.stage_of` (`core.py:399-401`) knows `QA`, `AT`, `REVIEW` and `DOCS` only, so add `STANDARDS` there, giving `review`; and `tracked` in `run_agent` must test the entity, not the id. `--all` still never includes waived findings. `testutil.py`'s fake `claude` answers `DONE` to an agent it does not know as a judge (`testutil.py:86`): add `standards-reviewer` to `judges` and make it answer `"axis": "standards"`. `test_agentic.py:1664-1671` reads the last call with the id `REVIEW` and expects the `reviewer`: both reviewers now run under that id, so select the call by its `--agent`; `test_agentic.py` is over its size limit, so edit lines in place and add none.
- Validation: `python3 -m unittest discover -s .claude/bin -p "test_launcher.py"`; the same for `test_repo_scan.py`, `test_guardrail.py`, `test_agentic.py`.

#### WP-04 · The spec and the fallback engine
- Wave: 2, after WP-01 and WP-06.
- Files: `.claude/bin/pipeline.py`, `.claude/bin/conformance.json`, `.claude/bin/test_pipeline.py`.
- Implements: `Pipeline.review(post)` and the rules logic of section 6; the eight scenarios and the test world's `standards` and summary fields.
- Consumes: `findings.py` and the spec of WP-06 (by implementation).
- ACs: AC-001, AC-002, AC-006, AC-009.
- Patterns to mirror: `.claude/bin/pipeline.py:441-495`; `.claude/bin/test_pipeline.py:28-135`; `.claude/bin/conformance.json:260-282`.
- Gotchas: `Pipeline.judge` may not grow: move the review block out into `review`, which returns what `judge` needs (`confirmed`, or a stop). `self.parallel` runs thunks in order in tests, so the reviewer's call is recorded before the standards reviewer's: the JS must launch them in that order too. Scenario findings without `tier` must behave as before: do not add tiers to the existing scenarios. `conformance.json` is shared with the JS test: `node .claude/bin/test_workflow.mjs` is red from this package until WP-05 lands, which is expected. The replaced scenario's name changes: update every test that names it.
- Validation: `python3 -m unittest discover -s .claude/bin -p test_pipeline.py`.

#### WP-05 · The native workflow
- Wave: 3, after WP-04.
- Files: `.claude/workflows/agentic-implement.js`, `.claude/bin/test_workflow.mjs`.
- Implements: the same behaviour as WP-04: `reviewStage`, tier helpers (`tierOf`, `waiverFor`, `blocks`, `textSum`), the rules logic, the schema and constant copies, the mock `standards-reviewer` and the summary fields in the test.
- ACs: AC-001, AC-002, AC-006, AC-009.
- Patterns to mirror: `.claude/workflows/agentic-implement.js:489-536`; `.claude/workflows/agentic-implement.js:87-110` (schema copies).
- Gotchas: `runAfterPlan` may not grow. The script cannot read files: waivers, rules text and the constant all come from `plan`. `for (const ch of text)` iterates code points, matching Python's `ord`. The conformance test compares the two engines' summaries key by key: a field one engine omits fails every scenario.
- Validation: `node .claude/bin/test_workflow.mjs`.

#### WP-06 · The agents, the commands and the spec
- Wave: 1.
- Files: `.claude/workflows/pipeline-spec.json`, `.claude/agents/reviewer.md`, `.claude/agents/standards-reviewer.md` (new), `.claude/agents/verifier.md`, `.claude/agents/qa.md`, `.claude/agents/test-auditor.md`, `.claude/agents/implementer.md`, `.claude/agents/test-author.md`, `.claude/agents/plan-reviewer.md`, `.claude/commands/architect.md`, `.claude/commands/implement.md`, `.claude/bin/test_definitions.py`.
- Implements, text and data only:
  - `pipeline-spec.json`: the schemas of section 5 (the reviewer's and the test-auditor's findings, QA's defects, and a new schema under the exact key `standards-reviewer`), the prompt `standards_reviewer` of section 6, the constant `implementer_rules: true`. It is in wave 1 because `launch.py` and the test projects read the real file: WP-03 and WP-04 need it in place.
  - `reviewer.md`: it is the Spec axis; its Maintainability list and "breaches of section 7" go (a line says style and rules belong to the Standards axis and are not reported here); a `# Tiers` section (floor for critical and high, finish for medium and low; no reflex); `tier` and `provenance` in the report, with what `read` and `inferred` mean; the rules sentence reads "the rules printed in your prompt".
  - `standards-reviewer.md`: frontmatter as the reviewer's; the defence section; role (the Standards axis: section 7 and the printed rules, on the diff and the packages' files); process starting with `python3 .claude/bin/agentic.py claim REVIEW`; the confidence filter with `No concrete case, no finding`; `# Tiers` (reflex: a written rule is broken; finish: worth knowing; `Never report a floor`: a contract, correctness or security problem belongs to the Spec axis); `rule` is `the rule's opening words`, copied (for a rule of the plan, `section 7: <words>`); the report with `axis`, `tier`, `rule`, `provenance`, the four parts and `not_checked`.
  - `verifier.md`: a finding whose `provenance` is `inferred` was not read by the reviewer: open the code first and refute it with the line that contradicts it.
  - `qa.md`, `test-auditor.md`: `tier` (`floor`, `finish`) in their reports and severity lines.
  - `implementer.md`: rule 4 becomes exactly ``4. **Conventions.** Follow section 7, the style of the existing code and the rules printed in your prompt (if it names files instead, read them). If they clash, this order wins: `architecture.md`, the existing code, and finally the rules.`` Nothing else of it changes.
  - `test-author.md`, `qa.md`: "the rules printed in your prompt (if it names files instead, read them)" where they said "the rules your prompt points to".
  - `plan-reviewer.md`: a new first checklist item (rows of 4b marked `inferred`: open the code and confirm or refute each before anything else; a false one is critical; a 4b table with no `Source` column is critical), and one for `waivers` (each has the narrowest scope, a reason naming who decided and the evidence, and is not a way around a contract).
  - `architect.md`: the 4b table with `| Source |`, the meaning of `read` and `inferred`, `waivers` among the manifest's fields.
  - `implement.md`: the review is presented per axis (Spec, Standards), with the waived findings and their reasons, and whether the rules were printed or pointed.
  - `test_definitions.py`: `standards-reviewer` in `AGENTS` (claim `REVIEW`) and in the lists of `test_report_is_json_by_schema` and `test_reports_say_what_was_not_checked` (and of the read-only agents' test, if it lists the reviewer), `waivers` in the manifest fields, the three test-auditor phrases of the retired acceptance file (`**Wrong:**`, `contradicts the criterion's Expected`, `wrong expected value`), and the new phrases of AC-008.
- ACs: AC-007, AC-008.
- Patterns to mirror: `.claude/agents/reviewer.md:1-69`; `.claude/agents/plan-reviewer.md:16-40`; `.claude/commands/architect.md:138-140`.
- Gotchas: from this package until WP-04 and WP-05 land, the tests that compare the spec with the engines (`test_pipeline.py`, `test_workflow.mjs`) are red: expected. Keep every phrase of `test_definitions.py:132-171` in its file. Reports stay "under N words" and name the schema. No version or issue numbers in the text.
- Validation: `python3 -m unittest discover -s .claude/bin -p test_definitions.py`.

#### WP-07 · Prompt tests: the scenario runner, the variant and the scenarios
- Wave: 3, after WP-01, WP-03, WP-04 and WP-06.
- Files: `bench/scenario.py`, `bench/variant.py` (new), `bench/test_scenario.py`, `bench/test_variant.py` (new), `bench/scenarios/`, `bench/results/scenarios/` (new: what `--save` writes in QA, committed like the bench's results), `docs/how-to/bench.md`.
- Implements: section 6's runner and variant; the scenarios:
  - `review-style/`: `architecture.md` (a small plan: section 6 gives `discount(total_cents: int) -> int`, 15% off above 25000 cents, never mutating its input; section 7 says "follow the rules"; a manifest with WP-01 owning `src/`), `src/pricing.py` (correct by the contract, with the literals `25000` and `0.85` inline and a second function nested five levels deep), and two scenario files: `standards.json` (agent `standards-reviewer`, prompt `standards_reviewer`, rules `common` and `python`) and `spec.json` (agent `reviewer`, the same files: must pass with nothing blocking). Each has the suffix sentence " There is no git here: the change is the files under src/."
  - `review-contract/`: the same plan and a `src/pricing.py` that returns a float where the contract says `int`; `scenario.json` (agent `reviewer`, the same suffix) expects `{"status": "FAIL", "tier": "floor", "finding_mentions": ["int"]}`.
  - `verifier-inferred/`: `src/store.py` whose `save()` cleans the name through a helper defined below it; the finding (in `values.finding`, compact JSON) says, with `provenance: inferred`, that `save()` stores the name unvalidated.
  - `plan-inferred-row/`: `lib/parse.py` whose `parse()` returns `None` for bad input; an `architecture.md` whose 4b has a true `read` row and an `inferred` row saying `parse()` raises `ValueError`, and a package that relies on it.
  - `auditor-wrong-expected/`: unchanged files; its expectation still holds by tier or by severity.
  - `bench.md`: a section on `scenario.py` (what a scenario is, `--repeat`, `--against`, `--save`, that each run is a real session) and on `variant.py`.
- Consumes: `findings.blocks`, `repo_scan.render_rules` (by implementation).
- ACs: AC-009, AC-010, AC-011, AC-012.
- Patterns to mirror: `bench/scenario.py:42-129`; `bench/test_scenario.py:1-60` (a fake `claude` per test).
- Gotchas: `importlib` loading, as `bench/test_scenario.py` does. `finding_mentions` is now compared casefolded: the existing scenario's `AC-009` and `960` still match. With `schema` false the runner passes no `--json-schema` and reads the answer's `result` text. A scenario's `model` replaces the constant. `variant.build` lists files with `git ls-files --cached --others --exclude-standard`, so new files not yet committed are in the arm and `.claude/state/` (ignored) is not. When `prepare` installs another definition for an agent (`--against`, `--agent-file`), it rewrites that file's frontmatter `name:` to the scenario's agent, or `--agent` would not find it (the old arm of `standards.json` is a `reviewer.md`). `fisher_p` uses `math.comb`.
- Validation: `python3 -m unittest discover -s bench -p "test_*.py"`.

#### WP-08 · Retire the previous acceptance file
- Wave: 1.
- Files: `.claude/bin/test_doctor.py`, `.claude/bin/test_plan_picture.py`, `.claude/bin/test_install.py`, `.claude/bin/test_acceptance_v212.py` (deleted).
- Implements: `test_acceptance_v212.py`'s checks moved, then the file deleted: `DoctorTests` to `test_doctor.ProjectStateTests` (with its `stale` and `clean` helpers), `PictureTests` to `test_plan_picture.CommandTests`, and, only if no test already asserts it, `test_install`: every non-test module beside `agentic.py` is in `INSTALL_GLOBS`. The test-auditor phrases are WP-06's; the scenario checks are superseded by AC-011; the version and notes pins are dropped.
- ACs: AC-012.
- Patterns to mirror: `.claude/bin/test_doctor.py:1-45` (the suite the doctor checks join).
- Gotchas: it is in wave 1 because `test_layout` allows one acceptance file: from the moment `test_acceptance_v213.py` exists, the suite is red until the old one goes. `clean` reads the version from `plugin.json`, never a literal.
- Validation: `python3 -m unittest discover -s .claude/bin -p test_doctor.py`; the same for `test_plan_picture.py`, `test_install.py`, `test_layout.py`.

#### WP-09 · Version, notes and docs
- Wave: 3, after WP-03 and WP-06.
- Files: `.claude-plugin/plugin.json`, `.claude/bin/upgrade.py`, `README.md`, `docs/how-it-works.md`, `docs/roadmap/repo-review-2026-11.md`.
- Implements: version 2.13.0; `NOTES["2.13.0"]` (the two axes and the new agent, to merge if `reviewer.md` was edited; tiers and what blocks; `waivers`; the `Source` column and the warning old plans get; printed rules; the constant); in `README.md`, the agents table's review row names `standards-reviewer` and the review bullet says two reviewers, with no net new lines; in `how-it-works.md`, the module tree line `findings.py  tiers, waivers and what blocks` and the review described per axis; the roadmap's items 3.3, 3.4, 3.5, 4.4 and 7.3 marked shipped and 4.5 as "measured in 2.13.0, decided next".
- ACs: AC-012.
- Patterns to mirror: `.claude/bin/upgrade.py:147-170`; `README.md:77-83` (the agents table).
- Gotchas: `docs/how-to/README.md` sits at its 260-line cap and is not touched. The `acceptance/` suite checks the docs' shape (no hard-coded test counts or flow versions, headings, caps): run it. The history is regenerated as the release's last commit.
- Validation: `python3 -m unittest discover -s .claude/bin -p "test_*.py"`; `python3 -m unittest discover -s acceptance`; `python3 .claude/bin/agentic.py docs-check`.

```json wp-manifest
{
  "maintainer": true,
  "stack": ["python"],
  "allow_bash": ["Bash(python3 -m unittest:*)", "Bash(node .claude/bin/test_workflow.mjs)"],
  "acceptance": {"files": [".claude/bin/test_acceptance_v213.py"], "command": "python3 -m unittest discover -s .claude/bin -p test_acceptance_v213.py"},
  "verify": {"build": "python3 -m unittest discover -s bench -p \"test_*.py\"", "lint": "node .claude/bin/test_workflow.mjs", "types": "python3 -m unittest discover -s bench/acceptance", "tests": "python3 -m unittest discover -s .claude/bin -p \"test_*.py\""},
  "docs": {"files": ["docs/assets/"], "codemap": null},
  "work_packages": [
    {"id": "WP-01", "wave": 1, "depends_on": [], "files": [".claude/bin/findings.py", ".claude/bin/test_findings.py"],
     "acs": ["AC-002", "AC-003"], "mirror": [".claude/bin/brief.py:1-40"]},
    {"id": "WP-02", "wave": 1, "depends_on": [], "files": [".claude/bin/manifest_check.py", ".claude/bin/test_manifest_check.py"],
     "acs": ["AC-004", "AC-005"], "mirror": [".claude/bin/manifest_check.py:281-302", ".claude/bin/manifest_check.py:78-110"]},
    {"id": "WP-03", "wave": 2, "depends_on": ["WP-01", "WP-02", "WP-06"], "files": [".claude/bin/repo_scan.py", ".claude/bin/launch.py", ".claude/bin/guardrail.py", ".claude/bin/installer.py", ".claude/bin/agentic.py", ".claude/bin/test_repo_scan.py", ".claude/bin/test_launcher.py", ".claude/bin/test_guardrail.py", ".claude/bin/test_agentic.py", ".claude/bin/testutil.py", ".claude/bin/core.py"],
     "acs": ["AC-003", "AC-005", "AC-006", "AC-007", "AC-012"], "mirror": [".claude/bin/repo_scan.py:58-67", ".claude/bin/launch.py:118-212", ".claude/bin/test_launcher.py:33-70"]},
    {"id": "WP-04", "wave": 2, "depends_on": ["WP-01", "WP-06"], "files": [".claude/bin/pipeline.py", ".claude/bin/conformance.json", ".claude/bin/test_pipeline.py"],
     "acs": ["AC-001", "AC-002", "AC-006", "AC-009"], "mirror": [".claude/bin/pipeline.py:441-495", ".claude/bin/test_pipeline.py:28-135", ".claude/bin/conformance.json:260-282"]},
    {"id": "WP-05", "wave": 3, "depends_on": ["WP-04"], "files": [".claude/workflows/agentic-implement.js", ".claude/bin/test_workflow.mjs"],
     "acs": ["AC-001", "AC-002", "AC-006", "AC-009"], "mirror": [".claude/workflows/agentic-implement.js:489-536", ".claude/workflows/agentic-implement.js:87-110"]},
    {"id": "WP-06", "wave": 1, "depends_on": [], "files": [".claude/workflows/pipeline-spec.json", ".claude/agents/reviewer.md", ".claude/agents/standards-reviewer.md", ".claude/agents/verifier.md", ".claude/agents/qa.md", ".claude/agents/test-auditor.md", ".claude/agents/implementer.md", ".claude/agents/test-author.md", ".claude/agents/plan-reviewer.md", ".claude/commands/architect.md", ".claude/commands/implement.md", ".claude/bin/test_definitions.py"],
     "acs": ["AC-007", "AC-008"], "mirror": [".claude/agents/reviewer.md:1-69", ".claude/agents/plan-reviewer.md:16-40", ".claude/commands/architect.md:138-140"]},
    {"id": "WP-07", "wave": 3, "depends_on": ["WP-01", "WP-03", "WP-04", "WP-06"], "files": ["bench/scenario.py", "bench/variant.py", "bench/test_scenario.py", "bench/test_variant.py", "bench/scenarios/", "bench/results/scenarios/", "docs/how-to/bench.md"],
     "acs": ["AC-009", "AC-010", "AC-011", "AC-012"], "mirror": ["bench/scenario.py:42-129", "bench/test_scenario.py:1-60"]},
    {"id": "WP-08", "wave": 1, "depends_on": [], "files": [".claude/bin/test_doctor.py", ".claude/bin/test_plan_picture.py", ".claude/bin/test_install.py", ".claude/bin/test_acceptance_v212.py"],
     "acs": ["AC-012"], "mirror": [".claude/bin/test_doctor.py:1-45"]},
    {"id": "WP-09", "wave": 3, "depends_on": ["WP-03", "WP-06"], "files": [".claude-plugin/plugin.json", ".claude/bin/upgrade.py", "README.md", "docs/how-it-works.md", "docs/roadmap/repo-review-2026-11.md"],
     "acs": ["AC-012"], "mirror": [".claude/bin/upgrade.py:147-170", "README.md:77-83"]}
  ]
}
```

## 9. Test strategy
- **Unit:** each package in its own test files, `unittest`, temporary projects from `test_agentic.Repo`, a fake `claude` where an agent would run. Both engines through the conformance scenarios.
- **Acceptance:** `.claude/bin/test_acceptance_v213.py`, written first and red, AC-001 to AC-012.
- **Teeth:** after green, mutate the code (a waived finding still verified; a finish finding blocking; a damaged rules text printed anyway; a 4b `read` row not checked; the standards reviewer writing the ledger) and see the tests go red.
- **QA with real sessions, by hand, results in the pull request:**
  1. Each new scenario with `--against` its 2.12.0 definition (`git show agentic-flow--v2.12.0:<file>`; for `standards.json`, the old `reviewer.md`), `--repeat 5 --save`: 5 scenario files (`review-style` has two), 10 sessions each. Their cost is not measured.
  2. A/B 1, the whole package: `bench.py ab --a agentic-flow--v2.12.0 --b <this branch's folder>` on `pricing` and `inventory`, 3 sessions per arm and fixture (12 sessions; the last such run cost 6.1 USD in total at 2.8.0's prices, the new one is not measured). It answers what the second reviewer and the blocking Reflex tier cost, and whether quality moves.
  3. A/B 2, issue 56: `--a <this branch's folder> --b <variant.py implementer-no-standards>`, the same fixtures and sessions.
- The user sees A/B 1 before merging: it is the release gate (section 11).

## 10. Decisions
- **The design was written with Fable 5.2, not Opus.** The model gate paused, and the user chose it explicitly.
- **`reviewer` stays as the Spec axis; `standards-reviewer` is new** (the user's choice). Discarded: two new files (more churn on upgrade) and one file launched twice (mixed checklists).
- **Reflex exists only on the Standards axis.** A reflex is a breach of a written rule, and only that reviewer applies the rules; the Spec reviewer, QA and the test-auditor use floor and finish. Discarded: reflex for every judge, which needs a rule for findings that have none.
- **The tier is explicit in every judge's report** (the user's choice), with a fall-back to the severity for a finding without one, so old reports, the one-off files of a project in mid-flight and the existing conformance scenarios keep their result. For the Spec reviewer, QA and the auditor the tier repeats what the severity already said; when they disagree the tier wins.
- **The scale does not reach the deterministic checks** (the user's choice): they are Floor and unwaivable.
- **Waivers live in the plan's manifest** (the user's choice): they are reviewed with the design and end with it. Discarded: a project file that outlives designs.
- **A waiver names a rule by its words**, matched without case by containment, and must appear in the installed rules. Discarded: rule ids across the eleven rule files, a larger change for the same effect. A section 7 rule is not waivable.
- **A waiver's scope must lie inside one package's zone.** "Narrowest scope" needs a test a machine can run.
- **The engines apply the waivers, not the reviewer.** A waived finding is still reported and recorded with its reason; the standards reviewer is not told about waivers.
- **The union lists stay** (`review.confirmed`, `refuted`, `advisory`), Spec first, never sorted: `run-wave --fix`, `/implement` and the bench's review metrics keep reading them.
- **Provenance: a column, checked** (the user's choice). Missing column: a warning, so plans written before this change still validate; a wrong `read` reference: an error. The plan-reviewer treats a missing column as critical for new plans.
- **`provenance` on a finding changes no engine decision.** Every blocking finding is already verified; the field tells the verifier what to open first.
- **The rules are printed for every agent that received their paths** (the user's choice). In the native engine the text travels in the plan, through the gatekeeper; a checksum detects damage and the engine falls back to the paths. Discarded: appending the rules to the briefs (the reviewers and QA have none) and passing them as workflow arguments (the same copy risk, with no check).
- **Issue 56 is measured, not shipped** (the user's choice): a spec constant and `bench/variant.py` build the arm; the implementer is untouched.
- **`variant.py` edits the implementer by heading and by one line, at build time.** Discarded: a committed copy of `implementer.md`, which drifts.
- **Scenarios compare an agent's old and new definition under the new schema.** For the standards scenario the old arm is the 2.12.0 `reviewer.md` answering the standards schema: imperfect, and the only old definition there is.
- **`finding_mentions` becomes case-insensitive**, so a scenario does not depend on how an agent capitalises a rule.
- **Reused:** `mirror_errors`' reference test, `brief.split`, the conformance harness, `bench.py ab`'s directory arms, `math.comb`.

## 11. Risks and open questions
- **Cost.** One more reviewer per review, one verifier per blocking reflex finding, and the rules text in every prompt. Not measured; A/B 1 measures it. **Release gate:** the user sees A/B 1 before merging and may ask for the Reflex tier to ship as non-blocking, which is one constant away (not built unless asked).
- **More fix cycles.** Every unwaived rule breach now blocks. The verifier, the reviewers' confidence filter and the fix-cycle cap bound it; A/B 1 shows the real number.
- **The gatekeeper may alter a long `rules_text`.** Then the run falls back to the paths and says so (`rules: pointed`). How often is not measured; the A/B runs record it.
- **Rule matching by words is fuzzy.** A waiver for "No magic numbers" also covers a finding whose rule text merely contains those words. Accepted: the scope bounds it.
- **A/B noise.** Three sessions per arm and fixture gave intervals as wide as 0.73 to 1.50 in the last run. A/B 2 may not settle issue 56; then it stays open with the numbers.
- **The scenarios' old arms** may pass too, as the first version of the auditor scenario did: then the scenario is rebuilt harder or reported as not reproducing, never tuned until it passes.
- **Projects with an edited `reviewer.md`** keep theirs on upgrade and get the new one beside it: the notes say what to merge. A project plan in mid-flight keeps working: no tier means the old rule, no `Source` column means a warning.
- **Rollback:** revert the release commit and publish a patch version; projects reinstall the previous tag with `agentic.py install`. The record's new keys are additive, so an older `run-wave --fix` still reads a newer record's union lists.
