# Report 011: plan 005 addendum A, a no-edit-timeout screen (Kaggle L4x4 request)
Builder, 2026-11-06T01:00Z, repo parent 4eeb441 (commit that adds this report).

## 1. Question for the Director
May I spend about 2.1 h of Kaggle L4x4 quota on one arm-B run of 31b-v003-p5t4 (the prompt-only fix) on the 8 plan-006 ids? It would run
only after review-plan005-light comes back clean. It is independent of the 31b-v002 submit, which stays gated by dec 055.

## 2. Pre-registration
Copied by reference: eval/plans/005.md "Addendum A", pre-registered 2026-11-06T00:59Z before any arm-B run.
- Hypothesis: the 4/8 empty diffs at cap 4.0 come mostly from tool-use traps, not from slow reasoning. A generic prompt fix cuts them.
- Expected: B empty diffs <= 2/8; write_file-outside-workspace and edit_file mangled-arg errors at least halved.
- Rule: PASS = gates a/b/d/e AND B empty <= 2/8 AND B-empty-only <= 1 AND write_outside_ws <= 2 AND edit_missing_param <= 9
  -> build 31b-v004 = v002 (cap 3.5) + prompt. MECHANISM-ONLY -> report, no ship. FAIL -> one revision, then stop.

## 3. What I did (CPU only)
- eval/trace_tool_errors.py classifies the tool responses in a run's traces. It writes counts only, no task text.
- results/trace_tool_errors_31b_v001.json (arm A = plan-006 run) and results/trace_tool_errors_e4b_v001_v5.json (comparison).
- bundles/31b/v003 = 31b-v001-t4 + prompts/system.md := bundles/drafts/plan005-system.md. pack PASS.
  dist/31b-v003.zip sha256=3fa08f768ab7052b9c225c8ec92dcd62743d760cdf32c5dd14e8ab139b18081a. Diff vs v001: prompts/system.md + MANIFEST only.
- Review launched: review-plan005-light (trace tool, bundle prompt facts vs harness code, decision-rule definability).

## 4. Results (arm A, existing traces; n=8, k=1; source results/trace_tool_errors_31b_v001.json)
| mechanism (31b-v001-t4, cap 4.0) | tasks (of 8) | calls | in the 4 empty-diff tasks |
|---|---|---|---|
| write_file to /tmp rejected "escapes workspace root" | 6 | 8 | 3 of 4 |
| edit_file args mangled ("old_string not present") | 2 | 19 | 1 (15 calls, never landed an edit) |
| shell-quoting syntax error | 2 | 2 | 2 |
| tool budget exhausted (40 calls; 22 read_file, 0 edits) | 1 | 1 | 1 |
| CommandError with empty message (grep exit 1) | 6 | 7 | 4 |
| "Error in sitecustomize: no module wrapt" stderr (non-fatal) | 6 | 23 | 3 |
- Empty diffs: 4/8 (rich_3063, rich_3067, rich_3535, fastapi_14851). Non-empty: first ok edit_file at calls 8, 10, 10 and 17.
- The prompt (v000 lineage, both tracks) tells the agent to put scratch files in /tmp, but write_file rejects /tmp. That's a direct
  contradiction, and it cost a repro script in 6/8 tasks. e4b-v001 v5 shows the same classes less often (results/trace_tool_errors_e4b_v001_v5.json).
- No paired B data yet. That is what the request is for.
- The sitecustomize/wrapt noise comes from the Kaggle host python. Under H1 the scorer probably shows it too. The prompt now says to ignore it.

## 5. Options
A. Approve the screen: one Kaggle L4x4 run (~2.1 h, quota 7.28/30 h this week, resets 2026-11-07T00:00Z) after a clean review.
   Pro: cheap, paired against existing arm A, and it also re-checks timing gates with the longer prompt. Con: n=8/k=1, so it's only a screen.
B. Skip the screen. Fold the prompt into 31b-v004 and test it only in the 33-dev pass-rate design. Pro: one fewer Kaggle run.
   Con: that design needs GCP GPU (not allowed now), so we'd learn nothing for days, and v004 couldn't be submitted on evidence.
C. Port to e4b first (e4b cap 1.0, cheaper per task). Con: e4b's arm-A errors are rarer, so the signal is weaker. The 31B track has the
   4/8 empty-diff problem.

## 6. Recommendation
Option A. Request: **Kaggle L4x4 ~2.1 h for plan 005 addendum A arm B (31b-v003-p5t4, sha 3fa08f76...081a), after review-plan005-light is clean.**
The dec 055 31B submission is untouched: v002 and its kernel are unchanged, and the veto/T procedure stands.
