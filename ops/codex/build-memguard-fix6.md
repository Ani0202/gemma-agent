Implemented Round 6 on `codex/memguard-fix6`, preserving rounds 1–5.

1. **Watchdog identity:** cached inode identity at [bin/memguard:24](/home/ubuntu/work/gemma-wt/codex-memguard-fix6/bin/memguard:24); updated `watchdog_argv()` at line 174, `runs_memguard()` at 199, and `watchdog_record()` at 224. Every argv position uses recipient-relative resolution, with unreadable cwd failing closed. Existing name triggers remain.
   Regressions: `test_watchdog_inode_identity_protects_aliases`, `test_unreadable_cwd_with_relative_argv_is_protected`.

2. **Permanent wrapper exclusion:** added `verified_wrapper()` at [line 218](/home/ubuntu/work/gemma-wt/codex-memguard-fix6/bin/memguard:218), enforced it in `eligible()` at 297 and `action_eligible()` at 366, and removed the grace window from `kill_tree()` at 454.
   Regression: `test_verified_wrapper_is_permanently_excluded` verifies no wrapper signal or OOM write while its child is killed.

Tests, using cached pytest offline:

- Standard: **93 passed, 1 skipped**
- `MEMGUARD_LIVE=1`: **94 passed**
- `git diff --check`: passed

Open issues: none. Sandbox prevented cross-mount hardlinks; regressions use a temporary installation under `/tmp`. System Python lacked pytest, so validation used an existing cached environment.

Only memguard and its tests changed. No commit created.
