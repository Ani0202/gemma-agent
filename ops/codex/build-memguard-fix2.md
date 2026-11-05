Implemented both blockers in `bin/memguard`, with mocked regressions:

- Exact `GEMMA_JOB_ID` grouping and persistent legacy membership, shared by survivor checks.
- Fresh identity and eligibility checks before signals and OOM writes.

Tests: offline **41 passed, 1 skipped**; `MEMGUARD_LIVE=1` **42 passed**. `git diff --check` passed.

Open issues: neither blocker remains. Review findings concerning `bin/job` remain outside scope.

Sandbox prevented nothing. Used cached pytest because system Python lacks it. No changes to `bin/job` or `ops/`; no commit created.
