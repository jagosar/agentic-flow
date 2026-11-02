# A/B: 2.1.0 (agentic-flow--v2.1.0) vs 2.3.0 (PR 43 head 6c63ce4; its .claude/ differs from agentic-flow--v2.3.0 only in flow-history.json)

Merged from two runs with the same arms, repeat and seed: inventory, roster, tally and tempconv ran on 2026-11-01 and the run stopped before vault when the container restarted; vault ran on 2026-11-02. All 30 sessions ended OK. Total cost about 17 USD.

3 session(s) per arm and fixture, seed 0. Ratios are median(B) / median(A): below 1, B is cheaper, faster or shorter. Differences are B - A. Only OK and REVIEW sessions count.

| Fixture | Cost | Minutes | Output | Mutation | Oracle | Fix cycles |
|---|---|---|---|---|---|---|
| inventory | 1.01 | 1.00 | 1.07 | 0.00 | 0.00 | 0.00 |
| roster | 0.96 | 0.91 | 0.96 | 0.00 | 0.00 | 0.00 |
| tally | 1.00 | 1.00 | 1.04 | -0.03 | 0.00 | 0.00 |
| tempconv | 0.99 | 0.38 | 0.99 | 0.00 | 0.00 | 0.00 |
| vault | 0.79 | 0.71 | 0.79 | 0.00 | 0.00 | 0.00 |

| Metric | Geometric mean | Interval | B better / worse / tie | Sign test p |
|---|---|---|---|---|
| cost_usd | 0.95 | 0.84–0.98 | 3 / 2 / 0 | 1.000 |
| minutes | 0.76 | 0.71–0.99 | 4 / 1 / 0 | 0.375 |
| output | 0.96 | 0.88–1.00 | 3 / 2 / 0 | 1.000 |
