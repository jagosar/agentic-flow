# Architecture decisions

Designs approved with `/architect`, one file per design, newest last.

| # | Date | Title | Type | Key decisions |
|---|---|---|---|---|
| [0001](0001-lean-agents-briefs.md) | 2026-10-26 | Lean agents: per-agent briefs, one report format, token telemetry | change | Deterministic slicing of `architecture.md` into briefs (no model); one JSON-schema runner for every launcher; telemetry in `usage.jsonl`, rules duplication measured before it is removed; implemented from the main session because the files are under the protected `.claude/` |
