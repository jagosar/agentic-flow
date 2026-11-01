# Approved designs

| # | Date | Title | Type | Key decisions |
|---|---|---|---|---|
| 0001 | 2026-11-01 | [Two harder bench fixtures](0001-harder-bench-fixtures.md) | feature | A file vault with implicit safety (one sentence of context, no attack named); `tally` in three real waves; oracle names `test_adv_*` / `test_edge_*` so the bad reference must fail only for the intended reasons |
| 0002 | 2026-11-01 | [The prompt package (agentic-flow 2.0)](0002-prompt-package-2-0.md) | change | Four-part findings with severity anchors; `needs_validation` as a separate list routed to `pending` without blocking; `not_checked` as a required report field; the reuse ladder in the common rules; executed by hand because `validate` protects `.claude/` |
| 0003 | 2026-11-01 | [The stop gate and the four implementer statuses (agentic-flow 2.1)](0003-stop-gate-statuses.md) | feature | A `PreToolUse` gate on `StructuredOutput` (measured: `Stop` cannot alter a structured answer) that runs the acceptance command and refuses a `DONE` whose own tests fail, twice at most; `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT` (one re-dispatch with the whole document) and `BLOCKED` mapped deterministically; executed by hand because `validate` protects `.claude/` |
