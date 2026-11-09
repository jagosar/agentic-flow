# A/B: 2.12.0 (agentic-flow--v2.12.0) vs 2.13.0 (.)

3 session(s) per arm and fixture, seed 0. Ratios are median(B) / median(A): below 1, B is cheaper, faster or shorter. Differences are B - A. Only OK and REVIEW sessions count.

| Fixture | Cost | Minutes | Output | Mutation | Oracle | Fix cycles | Callers | Confirmed |
|---|---|---|---|---|---|---|---|---|
| inventory | 0.98 | 0.89 | 0.91 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| pricing | 1.32 | 1.04 | 1.02 | 0.03 | 0.00 | 0.00 | 0.00 | 0.00 |

| Metric | Geometric mean | Interval | B better / worse / tie | Sign test p |
|---|---|---|---|---|
| cost_usd | 1.14 | 0.87–1.24 | 1 / 1 / 0 | 1.000 |
| minutes | 0.96 | 0.85–1.17 | 1 / 1 / 0 | 1.000 |
| output | 0.96 | 0.87–1.23 | 1 / 1 / 0 | 1.000 |
