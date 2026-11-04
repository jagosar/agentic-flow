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
| 1.1 | **Isolate the bench.** Every `claude -p` the bench starts loads the user's `~/.claude/CLAUDE.md`, memory and user settings, so it measures the flow plus one person's preferences. Ponytail found that leaked context skewed its results. Shipped (bench): every session runs with `--setting-sources project,local` and without CLAUDE.md files or auto memory. | ponytail | Low  |
| 1.2 | **Self-test the instruments before any spend.** Each oracle ships a good reference that must pass and a bad one that must fail. Shipped (bench): `bench.py selftest`, also before every `run`. | ponytail | Low  |
| 1.3 | **Mutation score.** Inject small bugs (flipped comparison, dropped `if`, off-by-one) into the produced code and run the project's own tests: measures test quality, which the oracle does not. Shipped: `bench/mutate.py`, a `Mutation` column in `bench/RESULTS.md` and the `roster` fixture. | ponytail | Medium |
| 1.4 | **A/B in one run.** Two flow versions interleaved fixture by fixture; geometric mean of per-fixture ratios, bootstrap confidence interval, sign test. Shipped in 2.3.0 (bench only): `bench.py ab`; see `docs/architecture/0007-fix-sources-and-ab.md`. | ponytail | Medium  |
| 1.5 | **Implicit-safety fixtures.** The requirement is left implicit, the hidden check is adversarial: path traversal, SQL injection, tampered token. Shipped (bench): the `vault` fixture; see `docs/architecture/0001-harder-bench-fixtures.md`. | ponytail | Low  |

## 2. Fewer fix cycles, cheaper runs

| # | Improvement | From | Cost |
|---|---|---|---|
| 2.1 | **Stop gate.** When an implementer submits a finished report, a hook runs the acceptance command; if a failure is the package's own, the report is refused and the failing lines go back to the agent, twice at most. Shipped in 2.1.0 as a `PreToolUse` hook on `StructuredOutput`: measured here, a `Stop` or `SubagentStop` block cannot alter a `--json-schema` answer, which is already delivered when it fires. | impeccable | Medium |
| 2.2 | **Four implementer statuses:** DONE, DONE_WITH_CONCERNS, NEEDS_CONTEXT, BLOCKED, each with its handling. Never retry the same model unchanged. Shipped in 2.1.0. | superpowers | Low |
| 2.3 | **Resume the same implementer** in fix cycles 1-3 (its context is intact), then a fresh one on a more capable model. Optional `model` per WP in the manifest. | superpowers | Medium |
| 2.4 | **Scoped re-review:** only the open findings and the fix diff; verdict ADDRESSED / NOT ADDRESSED per finding; findings keep a stable fingerprint across cycles; anything new goes to the ledger and never extends the loop. | superpowers, cloudflare | Medium |
| 2.5 | **Run budget** in USD or agent calls, with review and QA reserved before fix cycles spend; a run that cannot fund them stops as REVIEW with the gap stated. | cloudflare | Medium |
| 2.6 | **Frontier scheduling:** a WP starts when its `depends_on` finish, not when its wave does. Highest impact on speed, highest cost: stage checks become per WP in both engines. | mattpocock | High |

## 3. A more reliable review

| # | Improvement | From | Cost |
|---|---|---|---|
| 3.1 | **Read beyond the diff.** The reviewer gets the callers of every changed signature (from `graphify affected` when installed, else by grepping). `reviewer.md` says "no problems in code that was not touched"; a change that breaks an untouched caller must be reported. Shipped in 2.2.0 (plain grep; no `graphify`): see `docs/architecture/0005-reviewer-callers.md`. Measured on the `pricing` fixture (A/B 2.1.0 vs 2.4.0, three sessions each, `bench/results/ab-2.1.0-vs-2.4.0-20261102-210456.md`): 2.4.0's reviewer received the callers and confirmed the broken caller in 3 of 3 sessions, citing its line; 2.1.0 ended OK with the caller broken in 2 of 3 and QA caught it once by exploration. | ponytail, graphify | Medium |
| 3.2 | **Stricter findings:** a concrete case for each; four parts (what it is, problem, fix, if skipped); severity anchors ("fully defeats a control or only weakens it"; "if you cannot state the damage, it is lower than it feels"); a third verdict `needs_validation` for findings blocked by an external fact, with no severity; a "cannot verify from diff" category resolved by the orchestrator. Shipped in 2.0.0. | ponytail, cloudflare, superpowers | Low  |
| 3.3 | **Two axes, Standards and Spec,** reviewed in parallel and never reranked against each other. | mattpocock | Medium |
| 3.4 | **One scale for every check:** Floor (never ships), Reflex (a default the model falls into; waivable with a reason on the record), Finish (never blocks). Waivers take the narrowest scope and a `"<who decided: evidence>"` reason; every WARN needs a one-line defence. | hallmark, impeccable, taste | Low-medium |
| 3.5 | **Provenance:** every fact in section 4b and every reviewer evidence is "read at file:line" or "inferred"; the plan-reviewer challenges the inferred ones first. | graphify | Low |

## 4. Agent prompts (cheap; measure with the bench)

| # | Improvement | From |
|---|---|---|
| 4.1 | Reuse ladder before writing: needed? already in the repo? standard library? installed dependency? one line? only then the minimum. "Grep every caller before editing shared code; fix the root cause once." Shipped in 2.0.0. | ponytail  |
| 4.2 | Every report ends with "not checked / skipped / risk". Shipped in 2.0.0 (`not_checked`). | ponytail  |
| 4.3 | No invented numbers, benchmarks or claims (doc-updater, architect). Shipped in 2.0.0. | taste, hallmark  |
| 4.4 | Print what must be followed into the prompt instead of pointing at a file ("a printed line is followed where an extra read gets skipped"); audit the workflow prompts for pasted history. Partly: the callers are printed in the reviewer's prompt (2.2.0); the audit of the workflow prompts is open. | impeccable, superpowers  |
| 4.5 | Move coding standards from the implementer to the reviewer. Only after measuring. | mattpocock, impeccable |

## 5. New deterministic checks in close-stage

- 5.1 Block the usual agent shortcuts: tests without `assert`, broad `except` that swallows the failure, `assert True`, `[DEBUG-…]` logs left behind. (anatomy, mattpocock, taste)
- 5.2 Clean UTF-8 in CI (no double encoding). (taste)

## 6. /architect and the plan

- 6.1 A deterministic HTML+SVG picture of the manifest (WPs, waves, `depends_on`, files, ACs) for the approval gate. (diagram-design)
- 6.2 Complexity warnings from `validate`: a WP with too many files or ACs, a wave too wide or with one WP. Thresholds calibrated with the bench. (diagram-design)
- 6.3 Pre-flight conflict scan before wave 1: one row per pair of WPs sharing an interface, one per WP (its tests vs its code); rulings recorded. (superpowers)
- 6.4 Fix plans: a command that reproduces the exact symptom, already run, before any hypothesis; then 3-5 falsifiable hypotheses. (mattpocock)
- 6.5 Expand-contract guidance for wide refactors. (mattpocock) Shipped in 2.0.0.
- 6.6 Tautological tests as an explicit test-auditor anti-pattern. (mattpocock) Shipped in 2.0.0.
- 6.7 "Design it twice" for contested section-6 contracts, large size only. (mattpocock)

## 7. Tools

- 7.1 A `doctor` command: what the flow left stale in a project, each finding as data with a severity that says what happens: `auto` (fixed by `--fix`), `mention`, `route` (names the command that repairs it). (impeccable)
- 7.2 A `retro` command: parallel analysts over a run (cost and time, repeated work, stumbles, plan adherence); every finding cites `path:line`; a mechanical mistake becomes a deterministic check, not a prompt line. (mattpocock, superpowers)
- 7.3 TDD for prompts: pressure scenarios run without the change (record the rationalisation verbatim), then with it, then close loopholes. (superpowers)
- 7.4 `shortcut: <limit>, <when to upgrade>` markers and a debt ledger. (ponytail)

## Later (high cost or low return now)

- Visual QA with a headless browser for plans whose stack has a UI. (anatomy, taste) A reference for the checks: heydamir/unslop (CC BY 4.0, a skill that audits AI-looking UI); several of its signs can be checked without a model (emoji in the interface, gradient text, spacing off a 4px scale, uppercase tracked labels, trailing periods on short strings). Not adopted as a skill of the flow: it stops to ask the user for a design direction, which the flow's agents cannot do.
- An optional security stage on the diff, and a clean environment (allowlisted env, scratch HOME, no network) when agents run project code. (cloudflare)
- A coverage ledger with a coverage critic for QA. (cloudflare)
- Rulings instead of stalls when a plan is ambiguous: a policy change to handle with care. (superpowers)
- A multi-session decision map (wayfinder). (mattpocock)
- A reuse metric (functions reused vs created). (ponytail)
- Screenshot freshness for the docs. (diagram-design)
- Candidates from awesome-claude-code (a list of 263 resources; only its table was read, not the projects), to review one by one as the first ten were: `agnix` and `Ctxlint` (linters of CLAUDE.md, skills, hooks and MCP config, a complement to `test_definitions.py`), `Agent Collab Skills` (acceptance gate, adversarial debate, output reconciler), `presence` (calibrated-confidence gate and outcome telemetry), `cc-thinking-skills` (publishes a replication-gated evaluation: relevant to the bench) and `Upkeep` (drift between docs, spec and assets with evidence: overlaps `docs-check`).
- Not worth a place: claude-mem (cross-session memory conflicts with `architecture.md` as the single source of truth and with the bench's isolation) and awesome-scalability (a reading list on distributed systems, no code).

## Versioning

The changes in sections 2-7 ship as 2.0: they change the agents, the report schemas and what a plan must contain, so projects upgrade with `agentic.py install` and read the notes. The bench (section 1) is not installed in projects and does not bump the version. The first package (3.2, 4.1, 4.2, 4.3, 6.5, 6.6) is 2.0.0; see `docs/architecture/0002-prompt-package-2-0.md`. The stop gate and the four statuses (2.1, 2.2) are 2.1.0: the implementer schema and `settings.json` change, no plan or command does; see `docs/architecture/0003-stop-gate-statuses.md`. The reviewer's callers (3.1) are 2.2.0: the reviewer prompt changes; see `docs/architecture/0005-reviewer-callers.md`. The hand fix sources, `--all` and `verification_failures` are 2.3.0, with the bench's A/B (1.4); see `docs/architecture/0007-fix-sources-and-ab.md`.

## Found while using the flow

- The one-off `run-wave --fix` reads `.claude/state/runs/QA.json` and `REVIEW.json`, but `run-pipeline` saves `QA-N.json` and `REVIEW-N.json`, so a hand fix cycle after a pipeline run stops with "run run-review or run-qa first"; and `--fix` takes blocking defects only, so medium and low ones have no path but the person. Fixed in 2.3.0: `run-wave --fix` reads the newest review and QA wherever they were saved, and `--all` adds medium and low.
- Project hooks did not fire for the Workflow tool's subagents in a cloud session: `claims.json` stayed empty in two `/implement` runs on this repo and no agent saw a hook message, so ownership held only through close-stage's file comparison. On 2026-11-02 a payload dump showed the hook did not run at all in that session, for the main thread or for an `implementer` subagent, which wrote outside its zone unblocked. The official documentation says a cloud session reads a repository's hooks only when it has one repository and is not a thread inside a Claude project; that session had two. Fixed in 2.4.0: `hooks-check` before the first agent (pre-flight and both engines' first gatekeeper call) and a stage check in `close-stage`, so the flow stops or marks the stage instead of running without guardrails.
- The test-auditor passed a wrong acceptance test: in the `roster` fixture (2.1.0 bench, session 2) a test expected 1440 minutes where the plan said 960; the implementer returned `BLOCKED` with the exact diagnosis instead of adapting its code.
- An old test pinned wording: `test_acceptance.py::test_ac_013_docs` requires a README paragraph that a docs rewrite had to keep; hidden constraints like this cost a fix cycle.
- The bench cannot measure the reviewer's callers (3.1): its fixtures start from almost nothing, so callers fall inside the diff (3 of 15 sessions of the 2.2.0 run had any, none led to a finding). A brownfield fixture, with existing code and tests and a plan that changes a signature used in files no package owns, is needed. Shipped: the `pricing` fixture (an untested caller outside every package and outside the plan) and the review fields in each session record. The A/B (2.1.0 vs 2.4.0, three sessions each) is in `bench/results/ab-2.1.0-vs-2.4.0-20261102-210456.md`: the oracle's `test_ctx_*` failed in all six sessions, 2.4.0 stopped in REVIEW with a confirmed high finding on the caller in 3 of 3, 2.1.0 ended OK in 2 of 3 (QA found it once). Not isolated to 3.1: the versions differ in more than the callers; and three sessions on one fixture are a signal, not proof.
- A confirmed finding on a file nobody owns cannot be fixed: in the `pricing` A/B every 2.4.0 fix cycle ended `BLOCKED`, the implementer asking for ownership of the caller instead of making a compatible change inside its own files (a default for the new parameter). The fix-cycle prompt should say that a caller outside every zone is kept working from the changed package's side, and the plan reviewer should flag a contract that forbids it (issue #83). Fixed in 2.4.1 for the prompts (the fix-cycle prompt and implementer.md); not measured yet, and the plan-reviewer check was not done. The bench itself copied a fixture's stale `__pycache__` into sessions, which close-stage reported as writes nobody owns: fixed (the bench ignores bytecode when it copies a fixture).
- Possible hole in the hook for the native workflow's subagents (not verified): claude-mem's source (`src/shared/subagent-predicate.ts`, `should-skip-agent-observation.ts`) says Claude Code sends both an agent id and an agent type on every subagent hook, and that the Workflow tool's fan-out subagents arrive with the type `workflow-subagent`. `guard` in `agentic.py` demands a claim only from the types `implementer`, `qa`, `test-author`, `reviewer`, `doc-updater` and the ones a plan declares; an unclaimed `workflow-subagent` would write without restrictions and only `close-stage`'s file comparison would catch it. To check in a trusted local session: what `agent_type` an `implementer` launched by `agentic-implement` carries. If it is `workflow-subagent`, require a claim from any event with an agent id and that type, before any write. Still open after 2.4.0: it needs a session where `hooks-check` passes; there, `.claude/state/hook-seen.json` records the `agent_type` the hook saw. If it is not a flow type, 2.4.0's stage check already ends those stages in REVIEW.
- The flow cannot implement itself: `validate` refuses a WP that owns a path under `.claude/` and the hook blocks agents' writes there, both on purpose. Shipped in 2.5.0: maintainer mode (`"maintainer": true`, only in this repository) lets packages own named flow files, judged by a frozen copy of the guard. In practice only by hand: Claude Code protects `.claude/` from `claude -p` agents and allow rules do not lift it (found in 2.7.0); moving the flow's source out of `.claude/` is open.

## Recommended order

1. Now: 1.1 and 1.2, then one real bench run of the current version as the baseline.
2. A cheap prompt package: 3.2, 4.1, 4.2, 4.3, 6.5, 6.6. Measured against that baseline.
3. Then 2.1 and 2.2, which should cut fix cycles; the bench says whether they do. Shipped in 2.1.0; the measurement goes in `bench/RESULTS.md`.
4. Each with its own `/architect`: 2.6, 2.3 with 2.4, 1.3 with 1.4. 1.3 and 1.4 shipped; the next measurement is a brownfield fixture for 3.1.
