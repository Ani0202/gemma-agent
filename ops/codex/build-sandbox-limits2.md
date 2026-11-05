Implemented all three blocking fixes: dedicated subreaper supervisors with zombie reaping, pidfd signaling with identity checks, and memory-failure classification during every monitoring scan, including cleanup.

Preserved calibration semantics, result schema, concurrency, peak-RSS logging, RLIMIT_AS, and single-file staging. Restored the three ops files exactly to `02a883d`. No commit created.

Tests: full offline `eval/tests` suite exited 0 — **453 passed, 3 skipped, 4 subtests passed**.

Open issues: none identified. Sandbox restrictions prevented bubblewrap and localhost socket tests; the third skip requires unavailable PyYAML.
