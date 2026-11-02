# A/B: 2.1.0 (agentic-flow--v2.1.0) vs 2.4.0 (agentic-flow--v2.4.0)

3 session(s) per arm and fixture, seed 0. Ratios are median(B) / median(A): below 1, B is cheaper, faster or shorter. Differences are B - A. Only OK and REVIEW sessions count.

| Fixture | Cost | Minutes | Output | Mutation | Oracle | Fix cycles | Callers | Confirmed |
|---|---|---|---|---|---|---|---|---|
| pricing | 1.04 | 1.13 | 1.01 | 0.00 | 0.00 | 1.00 | ? | 1.00 |

| Metric | Geometric mean | Interval | B better / worse / tie | Sign test p |
|---|---|---|---|---|
| cost_usd | 1.04 | 0.96–1.23 | 0 / 1 / 0 | 1.000 |
| minutes | 1.13 | 0.76–1.29 | 0 / 1 / 0 | 1.000 |
| output | 1.01 | 0.85–1.23 | 0 / 1 / 0 | 1.000 |

## Reading

Six sessions, all measurable. The oracle's three `test_ctx_*` tests (the untested caller `shop/receipt.py`) failed in every session: no implementer of either version kept the caller working. What differs is who noticed:

| Arm | Session | Result | Who saw the broken caller |
|---|---|---|---|
| 2.1.0 | 1 | OK | nobody |
| 2.1.0 | 2 | REVIEW | QA, by exploration |
| 2.1.0 | 3 | OK | nobody |
| 2.4.0 | 1, 2, 3 | REVIEW | the reviewer, with 5 callers received, a confirmed high finding citing `shop/receipt.py:12` |

In 2.4.0 the fix cycle ended `BLOCKED` three times: the implementer asked for ownership of `shop/receipt.py` instead of giving the new parameter a default inside `shop/money.py`. Cost, minutes and output are the same within noise. The versions differ in more than the callers (stop gate, implementer statuses), so this does not isolate 3.1; it shows 2.4.0 stopping where 2.1.0 shipped broken code.

