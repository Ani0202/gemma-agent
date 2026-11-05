Implemented Round 3 on `codex/memguard-fix`.

- Preserved legacy membership history across polls and temporary ineligibility, including survivor inventory.
- Protected all memguard jobs and wrappers during discovery and action-time revalidation.
- Added deterministic regressions; retained exact job-ID grouping and earlier eligibility fixes.

Tests: **62 passed, 1 skipped** offline; **63 passed** with `MEMGUARD_LIVE=1`. Diff checks passed.

Open issues: none. Sandbox prevented nothing; pytest required the existing local installation via `PYTHONPATH`.

Only `bin/memguard` and its tests changed. No commit created.
