# Plan 010 arm-4 metrics: fix spec for codex review 20261107T114429 (BLOCKING x4)

Scope: `eval/plan008_metrics.py` arm4 mode (`arm4_metrics`, the helpers it calls) and
`eval/tests/test_plan010_metrics.py`. Read `ops/codex/review-20261107T114429.md` (the review) and
`eval/plans/010-arm4-metrics-spec.md` (the original spec) first. Do NOT change arm3 / plan-008 / plan-009
verdict behaviour: existing arm3 tests must still pass unchanged. Do not edit eval/plans/010.md.
If a shared helper must change, add an arm4-only variant instead.

## F1 Kernel pairing must be enforced from recorded commits
Real headers (`runs/31b-v012-p9a-{smoke,main}/timing.jsonl` first line, `_schema: kaggle_timing_v1`) carry
`git_sha` (repo commit the kernel was pushed from) and no kernel fingerprint fields. The kernel code is
generated from these repo files at that commit:
`eval/kaggle/agent_timing.py`, `eval/kaggle/timing_push.sh`, `eval/kaggle/vendor/SHA256SUMS`.
- For every contributing header of arm4 AND arm3 (all dirs), compute
  `kernel_fingerprint = {path: sha256(git show <git_sha>:<path>)}` for those 3 paths (subprocess `git show`,
  cwd = repo root; make the git reader injectable for tests).
- Missing/non-string `git_sha`, an unresolvable commit, or a missing path -> INVALID with reason
  `kernel evidence missing` (never treat absent == absent as a match).
- Any fingerprint differing between any arm4 header and any arm3 header (or within an arm) -> INVALID
  `pairing voided: kernel agent/verification path differs`. Different `git_sha` with identical file
  hashes is a MATCH (that is the expected real case).
- Report per-dir `git_sha` and the fingerprint in the output (`environment.kernel_code`).
- Tests: real header layout (copy the real header keys; no `kernel_code*` keys) with identical file hashes
  at different shas -> not voided; differing agent_timing.py -> INVALID; missing git_sha -> INVALID;
  unresolvable sha -> INVALID.

## F2 Timeout evidence must be complete
For arm4 and arm3 rows: `timed_out` AND `agent_timeout_fired` must both be present and bool, else the row
is in `missing` (-> INVALID `missing row evidence`). (All real task rows carry both; non-task rows
`_vllm`/`_done` are not task rows.) Test: the review's case — fixture whose 17th timeout comes only from
`agent_timeout_fired`; deleting that key must give INVALID, not 2048-ADOPT.

## F3 Concurrency 1 enforced
Every contributing header of arm4 and arm3 must have `concurrency` == 1 (int, not bool). Missing or any
other value -> INVALID `concurrency evidence missing or != 1`. Report concurrency per dir in `environment`.
Tests: concurrency=8 on one arm4 header -> INVALID; key missing -> INVALID; real-layout 1 -> passes.

## F4 Gold-data provenance
The tasks file actually read by `gold_created_dirs` / `_tasks_path()` (honouring `PLAN008_TASKS_PATH`)
must be added to `input_shas` (resolved path -> sha256) in arm4 output. If it cannot be read -> the S81
stray evidence is already failing; also add reason `gold tasks file unreadable` to INVALID. Test: changing
only the synthetic gold file changes the recorded `input_shas` entry (and the verdict as before).

## Acceptance
- `cd eval && PYTHONPATH=... pytest` per repo convention: full eval/tests suite passes (was 1742 pass /
  7 skip); all 65 prior arm4 tests still pass; new tests for every bullet above, each failing on 57484e4.
- Real-data smoke (no verdict needed): the arm4 helpers for F1/F3 run on the two real base headers and
  return "match"/"ok".
- Summarize changes and test output in the report.

## Real header key list (runs/ is gitignored and absent in the worktree)
main push header keys: _schema, git_sha, task_ids, concurrency, created_utc, caps, bundle_sha256, agent_yaml_sha256, gpu_names, gpu_count, mcp_import_ok, vllm_startup_seconds, platform_probe, fields. git_sha main=47243d10cc2f5a884937c2eca84b5a72e68685de, smoke=69613587 (resolve full sha via git rev-parse); both concurrency=1. The 3 kernel files hash identically at both commits and at HEAD.
