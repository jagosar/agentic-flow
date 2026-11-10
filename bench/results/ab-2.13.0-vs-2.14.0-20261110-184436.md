# A/B: 2.13.0 (agentic-flow--v2.13.0) vs 2.14.0 (.)

3 session(s) per arm and fixture, seed 0. Ratios are median(B) / median(A): below 1, B is cheaper, faster or shorter. Differences are B - A. Only OK and REVIEW sessions count.

| Fixture | Cost | Minutes | Output | Mutation | Oracle | Fix cycles | Agent calls | Callers | Confirmed |
|---|---|---|---|---|---|---|---|---|---|
| inventory | 1.10 | 1.15 | 1.09 | 0.00 | 0.00 | 0.00 | ? | 0.00 | 0.00 |
| pricing | 0.99 | 0.93 | 0.93 | 0.03 | 0.00 | 0.00 | ? | ? | 0.00 |

| Metric | Geometric mean | Interval | B better / worse / tie | Sign test p |
|---|---|---|---|---|
| cost_usd | 1.05 | 0.84–1.15 | 1 / 1 / 0 | 1.000 |
| minutes | 1.03 | 0.90–1.11 | 1 / 1 / 0 | 1.000 |
| output | 1.01 | 0.89–1.09 | 1 / 1 / 0 | 1.000 |
