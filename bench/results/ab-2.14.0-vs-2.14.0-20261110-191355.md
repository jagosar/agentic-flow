# A/B: 2.14.0 (.) vs 2.14.0 (variant:advisor-opus)

3 session(s) per arm and fixture, seed 0. Ratios are median(B) / median(A): below 1, B is cheaper, faster or shorter. Differences are B - A. Only OK and REVIEW sessions count.

| Fixture | Cost | Minutes | Output | Mutation | Oracle | Fix cycles | Agent calls | Callers | Confirmed |
|---|---|---|---|---|---|---|---|---|---|
| inventory | 1.10 | 0.91 | 1.04 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| pricing | 1.12 | 0.86 | 0.98 | 0.00 | 0.00 | 0.00 | 0.00 | ? | 0.00 |

| Metric | Geometric mean | Interval | B better / worse / tie | Sign test p |
|---|---|---|---|---|
| cost_usd | 1.11 | 0.83–1.25 | 0 / 2 / 0 | 0.500 |
| minutes | 0.88 | 0.78–1.01 | 2 / 0 / 0 | 0.500 |
| output | 1.01 | 0.85–1.12 | 1 / 1 / 0 | 1.000 |
