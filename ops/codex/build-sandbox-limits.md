Implemented process-tree tracking, RSS limits, timeout/orphan cleanup, calibration metrics, and `GOLD_CONCURRENCY`. Preserved executor output semantics and updated single-file kernel staging.

Tests: **76 passed, 1 skipped, 4 subtests passed in 8.55s**, using only the three requested files under `bin/job`.

Open issue: live bubblewrap verification remains pending; the sandbox blocked its NETLINK_ROUTE socket.

No calibration run or git commit performed.
