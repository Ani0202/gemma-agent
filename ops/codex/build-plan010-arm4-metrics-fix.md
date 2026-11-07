Implemented F1–F4 with arm4-only helpers; legacy behavior remains unchanged.

- Tests: **1,814 passed, 8 skipped**; all 65 prior arm4 cases pass.
- All 73 new cases fail against `57484e4`.
- Real base headers: kernel `match`, concurrency `ok`.
- Open issues: none in scope. Sandbox prevented nothing. No commit created.

[Report with changes, commands, and test output](/tmp/plan010-metrics-report.md)
