# Ideas from ten skill repos (November 2026)

A code review of the ten fastest-growing Claude skill repos of October 2026, looking for features the flow could borrow. Each repo was cloned and read; none was run. Numbers quoted from a repo's own benchmark are theirs, not verified here.

The list is ordered by what to do first. An idea is only worth building if the bench (`docs/how-to/bench.md`) can measure it before and after, or if it fixes a defect seen in a real run: that is the bar `mattpocock/skills` applies to its own changes, and it is the right one here.

## The repos

| # | Repo | What it is | Useful for the flow |
|---|---|---|---|
| 1 | mattpocock/skills | ~40 prompt-only skills: spec, tickets, TDD, review, debugging, design | Method: frontier scheduling, retro, two-axis review, debugging loop |
| 2 | DietrichGebert/ponytail | One prompt ("lazy senior dev") plus a serious agentic benchmark and a cost band | The benchmark design; the reviewer that reads beyond the diff; the reuse ladder |
| 3 | cloudflare/security-audit-skill | Six-phase audit with coverage ledger, critics, verifiers and deterministic validators | Third verdict `needs_validation`; severity anchors; finding fingerprints; run budget |
| 4 | pbakaus/impeccable | UI design skill with a Rust engine and 62 deterministic rules | Stop-time gate; `doctor`; findings as data; waivers with reasons |
| 5 | wheresryan22/anatomy | Interactive isometric figures, zero-dependency browser kit | Visual QA; audits "to zero" with an anti-gaming rule |
| 6 | cathrynlavery/diagram-design | HTML+SVG diagrams, 45 types, ~70 verify scripts | A plan diagram; complexity budgets |
| 7 | Graphify-Labs/graphify | Code knowledge graph from tree-sitter, Apache-2.0 | Blast radius for the reviewer and for blame; provenance tags |
| 8 | obra/superpowers | Plan -> subagent per task -> review -> fix loop; every rule backed by a real session failure | Closest to the flow: fix-loop design, model per task, implementer statuses, dispatch hygiene |
| 9 | Leonxlnx/taste-skill | Web design with a browser inspector and `evals.json` | Eval format; the WARN rule; no invented facts |
| 10 | Nutlope/hallmark | Web design by Together AI, 50 themes | Three gate tiers: Floor, Reflex, Finish |

## 1. First: make the bench measure well

Without this, every prompt or agent change is decided by reasoning.

| # | Improvement | From | Cost |
|---|---|---|---|
| 1.1 | **Isolate the bench.** Every `claude -p` the bench starts loads the user's `~/.claude/CLAUDE.md`, memory and user settings, so it measures the flow plus one person's preferences. Ponytail found that leaked context skewed its results. | ponytail | Low |
| 1.2 | **Self-test the instruments before any spend.** Each oracle ships a good reference that must pass and a bad one that must fail. | ponytail | Low |
| 1.3 | **Mutation score.** Inject small bugs (flipped comparison, dropped `if`, off-by-one) into the produced code and run the project's own tests: measures test quality, which the oracle does not. | ponytail | Medium |
| 1.4 | **A/B in one run.** Two flow versions interleaved fixture by fixture; geometric mean of per-fixture ratios, bootstrap confidence interval, sign test. | ponytail | Medium |
| 1.5 | **Implicit-safety fixtures.** The requirement is left implicit, the hidden check is adversarial: path traversal, SQL injection, tampered token. | ponytail | Low |

## 2. Fewer fix cycles, cheaper runs

| # | Improvement | From | Cost |
|---|---|---|---|
| 2.1 | **Stop gate.** When an implementer stops, a `SubagentStop` hook runs its WP's validation; if red, the stop is blocked and the failures go back to the agent. Check first that Claude Code lets a `SubagentStop` hook block. | impeccable | Medium |
| 2.2 | **Four implementer statuses:** DONE, DONE_WITH_CONCERNS, NEEDS_CONTEXT, BLOCKED, each with its handling. Never retry the same model unchanged. | superpowers | Low |
| 2.3 | **Resume the same implementer** in fix cycles 1-3 (its context is intact), then a fresh one on a more capable model. Optional `model` per WP in the manifest. | superpowers | Medium |
| 2.4 | **Scoped re-review:** only the open findings and the fix diff; verdict ADDRESSED / NOT ADDRESSED per finding; findings keep a stable fingerprint across cycles; anything new goes to the ledger and never extends the loop. | superpowers, cloudflare | Medium |
| 2.5 | **Run budget** in USD or agent calls, with review and QA reserved before fix cycles spend; a run that cannot fund them stops as REVIEW with the gap stated. | cloudflare | Medium |
| 2.6 | **Frontier scheduling:** a WP starts when its `depends_on` finish, not when its wave does. Highest impact on speed, highest cost: stage checks become per WP in both engines. | mattpocock | High |

## 3. A more reliable review

| # | Improvement | From | Cost |
|---|---|---|---|
| 3.1 | **Read beyond the diff.** The reviewer gets the callers of every changed signature (from `graphify affected` when installed, else by grepping). `reviewer.md` says "no problems in code that was not touched"; a change that breaks an untouched caller must be reported. | ponytail, graphify | Medium |
| 3.2 | **Stricter findings:** a concrete case for each; four parts (what it is, problem, fix, if skipped); severity anchors ("fully defeats a control or only weakens it"; "if you cannot state the damage, it is lower than it feels"); a third verdict `needs_validation` for findings blocked by an external fact, with no severity; a "cannot verify from diff" category resolved by the orchestrator. | ponytail, cloudflare, superpowers | Low |
| 3.3 | **Two axes, Standards and Spec,** reviewed in parallel and never reranked against each other. | mattpocock | Medium |
| 3.4 | **One scale for every check:** Floor (never ships), Reflex (a default the model falls into; waivable with a reason on the record), Finish (never blocks). Waivers take the narrowest scope and a `"<who decided: evidence>"` reason; every WARN needs a one-line defence. | hallmark, impeccable, taste | Low-medium |
| 3.5 | **Provenance:** every fact in section 4b and every reviewer evidence is "read at file:line" or "inferred"; the plan-reviewer challenges the inferred ones first. | graphify | Low |

## 4. Agent prompts (cheap; measure with the bench)

| # | Improvement | From |
|---|---|---|
| 4.1 | Reuse ladder before writing: needed? already in the repo? standard library? installed dependency? one line? only then the minimum. "Grep every caller before editing shared code; fix the root cause once." | ponytail |
| 4.2 | Every report ends with "not checked / skipped / risk". | ponytail |
| 4.3 | No invented numbers, benchmarks or claims (doc-updater, architect). | taste, hallmark |
| 4.4 | Print what must be followed into the prompt instead of pointing at a file ("a printed line is followed where an extra read gets skipped"); audit the workflow prompts for pasted history. | impeccable, superpowers |
| 4.5 | Move coding standards from the implementer to the reviewer. Only after measuring. | mattpocock, impeccable |

## 5. New deterministic checks in close-stage

- 5.1 Block the usual agent shortcuts: tests without `assert`, broad `except` that swallows the failure, `assert True`, `[DEBUG-…]` logs left behind. (anatomy, mattpocock, taste)
- 5.2 Clean UTF-8 in CI (no double encoding). (taste)

## 6. /architect and the plan

- 6.1 A deterministic HTML+SVG picture of the manifest (WPs, waves, `depends_on`, files, ACs) for the approval gate. (diagram-design)
- 6.2 Complexity warnings from `validate`: a WP with too many files or ACs, a wave too wide or with one WP. Thresholds calibrated with the bench. (diagram-design)
- 6.3 Pre-flight conflict scan before wave 1: one row per pair of WPs sharing an interface, one per WP (its tests vs its code); rulings recorded. (superpowers)
- 6.4 Fix plans: a command that reproduces the exact symptom, already run, before any hypothesis; then 3-5 falsifiable hypotheses. (mattpocock)
- 6.5 Expand-contract guidance for wide refactors. (mattpocock)
- 6.6 Tautological tests as an explicit test-auditor anti-pattern. (mattpocock)
- 6.7 "Design it twice" for contested section-6 contracts, large size only. (mattpocock)

## 7. Tools

- 7.1 A `doctor` command: what the flow left stale in a project, each finding as data with a severity that says what happens: `auto` (fixed by `--fix`), `mention`, `route` (names the command that repairs it). (impeccable)
- 7.2 A `retro` command: parallel analysts over a run (cost and time, repeated work, stumbles, plan adherence); every finding cites `path:line`; a mechanical mistake becomes a deterministic check, not a prompt line. (mattpocock, superpowers)
- 7.3 TDD for prompts: pressure scenarios run without the change (record the rationalisation verbatim), then with it, then close loopholes. (superpowers)
- 7.4 `shortcut: <limit>, <when to upgrade>` markers and a debt ledger. (ponytail)

## Later (high cost or low return now)

- Visual QA with a headless browser for plans whose stack has a UI. (anatomy, taste)
- An optional security stage on the diff, and a clean environment (allowlisted env, scratch HOME, no network) when agents run project code. (cloudflare)
- A coverage ledger with a coverage critic for QA. (cloudflare)
- Rulings instead of stalls when a plan is ambiguous: a policy change to handle with care. (superpowers)
- A multi-session decision map (wayfinder). (mattpocock)
- A reuse metric (functions reused vs created). (ponytail)
- Screenshot freshness for the docs. (diagram-design)

## Versioning

The changes in sections 2-7 ship as 2.0: they change the agents, the report schemas and what a plan must contain, so projects upgrade with `agentic.py install` and read the notes. The bench (section 1) is not installed in projects and does not bump the version. The first package (3.2, 4.1, 4.2, 4.3, 6.5, 6.6) is 2.0.0; see `docs/architecture/0002-prompt-package-2-0.md`.

## Found while using the flow

- The one-off `run-wave --fix` reads `.claude/state/runs/QA.json` and `REVIEW.json`, but `run-pipeline` saves `QA-N.json` and `REVIEW-N.json`, so a hand fix cycle after a pipeline run stops with "run run-review or run-qa first"; and `--fix` takes blocking defects only, so medium and low ones have no path but the person.
- The flow cannot implement itself: `validate` refuses a WP that owns a path under `.claude/` and the hook blocks agents' writes there, both on purpose. Plans that change the flow are executed by hand; a maintainer mode for the flow's own repo is an open idea.

## Recommended order

1. Now: 1.1 and 1.2, then one real bench run of the current version as the baseline.
2. A cheap prompt package: 3.2, 4.1, 4.2, 4.3, 6.5, 6.6. Measured against that baseline.
3. Then 2.1 and 2.2, which should cut fix cycles; the bench says whether they do.
4. Each with its own `/architect`: 2.6, 2.3 with 2.4, 1.3 with 1.4.
