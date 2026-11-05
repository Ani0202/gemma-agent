Implemented all three blockers, preserving rounds 1–4.

| Finding | Changed function/line | Regression test |
|---|---|---|
| Action-time recheck | [`action_eligible`, line 361](/home/ubuntu/work/gemma-wt/codex-memguard-fix5/bin/memguard:361): refreshes cmdline, environment and identity; checks fresh watchdog status before either action | `test_action_rechecks_watchdog_after_protection_scan` |
| Boot binding | `verified_records`:242, `provenance`:266, [`find_jobs`:285](/home/ubuntu/work/gemma-wt/codex-memguard-fix5/bin/memguard:285): rejects previous-boot provenance and history | `test_previous_boot_record_cannot_admit_unmarked_child` |
| Watchdog detection | [`watchdog_argv`:171](/home/ubuntu/work/gemma-wt/codex-memguard-fix5/bin/memguard:171), `watchdog_id`:167, `watchdog_record`:202: checks every argument, resolved paths, job-name prefixes and wrapper command records | `test_watchdog_any_argv_position_is_protected`, `test_wrapper_watchdog_command_record_is_protected`, `test_watchdog_argv_resolves_symlinks` |

Test output using installed Python 3.13:

- Offline: **87 passed, 1 skipped**
- `MEMGUARD_LIVE=1`: **88 passed**
- Syntax and `git diff --check`: passed

Open issues: re-parented wrappers with unavailable parents still fail closed; documented in code. Changes remain on supplied branch `codex/memguard-fix5`, based on `5cb49c2`; `codex/memguard-fix` is checked out elsewhere.

Sandbox prevented nothing. System Python lacks pytest. No commit made; `bin/job` and `ops/` untouched.
