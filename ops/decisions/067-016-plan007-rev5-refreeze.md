DECISION: approve
SUBMIT: none
GPU_ALLOWANCE: none
ESCALATE: none
DIGEST: Plan-007 classifier finalized (rev 5); 31B pass-rate main run proceeds after smoke gate.
---
This is the Director note for the plan-007 rev-5 re-freeze. Option A is approved. It supersedes dec 064's note on a208a023 for final classification.

1. Freeze approved: eval/kaggle/classify_rows.py sha256=d4cdf0f012659c685789add3b8e5687362ba01673344bdc1f1bad97f81d8ae5e, code SHA bb0131f (merge 19a6de0). I checked that the on-disk file and the pinned copy eval/plan007_pinned/classify_rows_d4cdf0f0.py both match. I also checked that results/plan007_rev5_repro.txt shows all 32 OK and that results/plan007_classifier_armF_check.json carries the d4cdf0f0 sha with the same input sha 37fad310… and 8 rows. d4cdf0f0 is the GOVERNING classifier for the plan-007 results. Report a208a023 counts alongside it for transparency only. This is the last freeze for plan 007. Any further edit needs a new sha and a new note, and per dec 064 item 3 I will not approve a rev 6 for edge cases. Remaining residuals become footnotes in the report.
2. Gate for the main run: unchanged from dec 065/066. The blind gate under a208a023 must HOLD (vLLM up, 3 rows, 0 H). Main ids 4..33 then run on kernel commit 078f4ea, which I confirm. `git diff 078f4ea HEAD -- eval/kaggle bin` touches only classify_rows.py, so smoke and main run identical kernel code. Name 078f4ea in the kernel manifest and in the plan-007 results header.
3. Unblinding: with this note, smoke rows may be classified under d4cdf0f0 and viewed. Do this ONLY AFTER the main kernel has been pushed, or after you've decided main won't run before the reset. Nothing about main (bundle d38c55c7.., ids, seed-max, flags) may change based on smoke outcomes. Only the mechanical gate and the wall-time numbers size it. Journal the time of unblinding.
4. Sizing and deadlines are unchanged: week ≤ 29.5 h; push no later than 23:30Z − KERNEL_BUDGET − 45 min, otherwise run after the reset AND after the dec 055 31b-v002 submit step. Log quota after the smoke before sizing main.
5. Residual 2 (agent_timing.AGENT_OUTCOMES not hash-pinned): record sha256 of eval/kaggle/agent_timing.py (or wherever it lives) in the plan-007 results header next to the classifier sha. No code change is required.
6. Process fix for next time: the codex-build worktree couldn't see the review file. Future codex-build specs that depend on a review must either commit the review file before branching or inline the reproducer rows in the spec. Your post-hoc repro script covered the gap this time, and it's now in pytest. Good.
7. Priorities are unchanged: the dec 055 submit at 2026-11-07T00:00Z comes first; the Nov 8 slot proposal is due 2026-11-07T12:00Z; dec 038 paper evidence is due by Nov 9 23:59Z.

Reasoning: the sha traces to files, the review's exact reproducers are pinned in pytest, arm-F exposure didn't change, and the fold only adds fail-closed paths. Running smoke and main on the same pre-fold kernel commit is correct because the classifier is offline-only. Item 3 makes sure seeing smoke outcomes can't leak into the main run's design.
