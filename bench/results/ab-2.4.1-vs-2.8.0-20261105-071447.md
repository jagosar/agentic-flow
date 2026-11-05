# A/B: 2.4.1 (agentic-flow--v2.4.1) vs 2.8.0 (agentic-flow--v2.8.0)

3 session(s) per arm and fixture, seed 0. Ratios are median(B) / median(A): below 1, B is cheaper, faster or shorter. Differences are B - A. Only OK and REVIEW sessions count.

| Fixture | Cost | Minutes | Output | Mutation | Oracle | Fix cycles | Callers | Confirmed |
|---|---|---|---|---|---|---|---|---|
| inventory | 0.93 | 0.99 | 0.94 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| pricing | 0.94 | 0.99 | 0.96 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

| Metric | Geometric mean | Interval | B better / worse / tie | Sign test p |
|---|---|---|---|---|
| cost_usd | 0.93 | 0.73–1.50 | 2 / 0 / 0 | 0.500 |
| minutes | 0.99 | 0.88–1.71 | 2 / 0 / 0 | 0.500 |
| output | 0.95 | 0.85–1.38 | 2 / 0 / 0 | 0.500 |
