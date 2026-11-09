# A/B: 2.13.0 (.) vs 2.13.0 (/tmp/claude-0/-home-user/b58ac183-3cc2-5117-a349-f6ea1d3c987e/scratchpad/no-standards)

3 session(s) per arm and fixture, seed 0. Ratios are median(B) / median(A): below 1, B is cheaper, faster or shorter. Differences are B - A. Only OK and REVIEW sessions count.

| Fixture | Cost | Minutes | Output | Mutation | Oracle | Fix cycles | Callers | Confirmed |
|---|---|---|---|---|---|---|---|---|
| inventory | 0.95 | 0.90 | 0.97 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| pricing | 1.01 | 1.10 | 1.05 | -0.01 | 0.00 | 0.00 | 0.00 | 0.00 |

| Metric | Geometric mean | Interval | B better / worse / tie | Sign test p |
|---|---|---|---|---|
| cost_usd | 0.98 | 0.94–1.06 | 1 / 1 / 0 | 1.000 |
| minutes | 1.00 | 0.95–1.16 | 1 / 1 / 0 | 1.000 |
| output | 1.01 | 0.93–1.05 | 1 / 1 / 0 | 1.000 |
