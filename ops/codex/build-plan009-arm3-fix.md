Implemented B1–B3 in `eval/plan008_metrics.py`: pairing/base validity gates, smoke binding and thinking recomputation, identity/transport checks, and vLLM startup evidence. Identity-rejected runs are excluded; duplicate attempts include compact outcomes.

Added synthetic regressions. Legacy modes remain byte-identical; `test_plan008_metrics.py` is unchanged.

Full offline suite: **1,566 passed, 7 skipped, 4 subtests passed**. `git diff --check` passed.

Open issues: none. Sandbox prevented nothing. No commit created.
