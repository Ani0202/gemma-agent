Implemented Round 3 on `codex/sandbox-limits`.

- Captures `wait4()` rusage for direct children and adopted descendants. Reports the maximum of polled tree RSS and reaped per-process peaks, converting Linux KiB to bytes.
- Documents the metric; keeps the 4 GiB kill logic poll-based.
- Adds timing-independent `/bin/true` regression tests.

Offline full suite: **459 passed, 4 skipped, 4 subtests passed**. [JUnit report](/tmp/sandbox-limits-round3-eval.xml).

Open issues: none identified. Sandbox blocked the bubblewrap probe; other skips were missing PyYAML alias support and two opt-in smoke tests. Normal-host execution remains unverified here.

No `ops/` edits or commits.
