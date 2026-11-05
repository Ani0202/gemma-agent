Implemented Docker-order editable install before injection, wheel/version-derived cache keys, matching-marker skips, and wheel-index refresh. Harness selection and sandbox limits remain unchanged. Added eight offline tests; no commit created.

Tests: **468 passed, 4 skipped, 1 failed**. New tests: **8 passed**. `git diff --check` passed.

Open issue: the unchanged memguard test expects `oom_score_adj=0`; this sandbox supplies inherited `1000`. Sandbox restrictions prevent resetting it, so full-suite acceptance remains blocked.
