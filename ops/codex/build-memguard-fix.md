Changed only `bin/memguard` and `eval/tests/test_memguard.py`: recipient allowlisting, identity checks with pidfds, orphan-aware discovery, repeated kill scans, independent survivor inventory, status-based names, and asynchronous mail with a 10-second timeout.

Test output on Python 3.12:

- Offline: **22 passed, 1 skipped**.
- `MEMGUARD_LIVE=1`: **23 passed**, under an unchanged temporary copy of `bin/job`.
- One-pass dry run: passed; printed `targets=[] jobs=[]`.
- `git diff --check`: passed.

Open issues: no supplied finding remains unfixed. The referenced review file is empty, so additional findings could not be checked.

Sandbox limits: `/proc` exposes only sandbox processes, preventing host-wide validation. System Python lacked pytest; tests used an existing local package offline. No commit was made.
