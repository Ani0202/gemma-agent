DECISION: approve-with-changes
SUBMIT: none
GPU_ALLOWANCE: none
ESCALATE: none
DIGEST: Small-model timing run failed at a setup step (missing offline tool package); fixed and verified locally, one re-run approved on Kaggle quota.
---
Option A is approved: one re-push as kernel v5. What I spot-checked:
- runs/e4b-v001-timing/timing.jsonl has 8/8 'Harness task failure' rows at 2.0-3.8 s Phase-1 wall each. That matches the report: v4 produced no measurement.
- ops/reviews/claude-rereview-vendor-fix.md says VERDICT: NO BLOCKING, and 87001e4 exists.
- results/plan003_kernel_setup_nostub_vendored.json has top-level status "failed". In fix mode, fastapi_14986 passed (setup 9.9 s, missing_tool_deps []). rich_3006 has editable_final_rc 1 with 5 Retrying lines, which is the known rich behaviour from dec 028. So the file supports the report, but its status label reads worse than the report's wording. Fix item 5 below.

1. Push kernel v5 from a clean worktree at EXACTLY 87001e4. Same bundle (dist/e4b-v001.zip sha256=f2ced9c97ee1447cb3a78c0ebf65f4ecaff90c84b18313645d5d043c62d277e9), same 8 ids (eval/plans/004-gpu-retime-ids.txt), concurrency 1, verification skipped, budget 3900 s, -t 5700 s, starter docker_image pinned, internet OFF, fail-fast 4xL4 guard on. Before pushing, confirm that `git status` is clean and that the embedded vendor wheels match eval/kaggle/vendor/SHA256SUMS. Log it in ops/budget/kaggle.md (SHA 87001e4, week before 3.73). If any code changes after 87001e4, there's no push until a fresh re-review.
2. Two-strike rule: this is the last re-push of the e4b-v001 re-time without a decision. If v5 fails again with harness errors, whatever the cause, stop and send a short report. Don't push v6.
3. Pre-registration added NOW, before results, for the image-emulation overhead. Gates (b) and (c) of dec 028 item 4 are evaluated on the TOTAL Phase-1 wall INCLUDING the image-emulation steps (conservative; that's the binding number). Also report phase1_minus_image_seconds per task, but it is NOT a gate. If (b) or (c) fails on the total but passes without the emulation steps, that is a gate FAIL, not a pass. Report 005 must then propose a lower cap computed from the total, per dec 030 item 5. A timeout loses the whole submission, so the conservative number is the one that binds.
4. Dec 029 item 3 is unchanged. Nothing from v5 goes into a SUBMIT request until the Codex fix5 review (23:08Z, medium, alone, targeting main...87001e4, and with no Claude findings in the prompt per dec 030 item 2) is clean. The cut-off in dec 030 item 4 is unchanged: report 005 with SUBMIT before ~23:45Z means I authorize at once. Otherwise e4b-v001 is the Nov 6 candidate under the same gate. Don't send partial reports.
5. Records hygiene: the vendored repro's top-level "status": "failed" comes from rich_3006's expected editable rc 1. Before this file is cited again (report 005 or the paper), add a schema-compatible field or a note that names which failures are expected and which are unexpected. Don't change the existing values.
6. Note for the Codex review prompt: ask it to check specifically that the vendored wheels and the pre-vLLM tool-source check can't change per-task timing in a way the scorer image wouldn't. The answer feeds the (b)/(c) interpretation in item 3.

Reasoning: v4 cost 0.25 quota-h and gave us nothing. v5 is a cheap, reversible measurement (≤3.17 quota-h; the week would be ≤6.9/30) on the only bundle that can pass the timing bound. The fix is reviewed, and it's verified without the stub that hid the bug. The two-strike stop keeps repeated setup failures from draining quota, and item 3 settles in advance how the emulation overhead counts, so the result can't be read post hoc.
