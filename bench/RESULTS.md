# Bench results

Each row is one fixture in one bench run of one flow version; numbers are medians over the runs (Oracle also shows min–max). A `?` means no run had that value.

| Version | Commit | Date | Fixture | Runs | OK | Oracle | Fix cycles | Cost $ | Output tokens | Minutes |
|---|---|---|---|---|---|---|---|---|---|---|
| 1.1.4 | 5cfe498 | 2026-11-01 | tally | 3 | 3/3 | 1.00 (1.00–1.00) | 0 | 0.79 | 31903 | 3.4 |
| 1.1.4 | 5cfe498 | 2026-11-01 | vault | 3 | 3/3 | 1.00 (1.00–1.00) | 0 | 0.60 | 24757 | 2.6 |
| 1.1.4 | 30021f2 | 2026-11-01 | inventory | 3 | 3/3 | 1.00 (1.00–1.00) | 0 | 0.39 | 13917 | 2.0 |
| 1.1.4 | 30021f2 | 2026-11-01 | tempconv | 3 | 3/3 | 1.00 (1.00–1.00) | 0 | 0.36 | 14740 | 1.8 |
