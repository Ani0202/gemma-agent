DECISION: approve
SUBMIT: none
GPU_ALLOWANCE: none
ESCALATE: none
DIGEST: Reducing context-reset overhead: shorter state files, fewer unneeded resets, clearer role orientation.
---
Owner instruction (Aniket, 2026-11-05, Remote Control in the Director session): approved all three context-clear fixes below, including the router changes. This authorizes the Builder to edit bin/router and the orientation text for this purpose only.

To the Builder (do these after the current critical-path step; they're small and shouldn't delay the Kaggle timing push from dec 016):
1. Trim ops/STATE.md to a true current-state snapshot of ≤ 80 short lines: best bundles, running jobs, quota, open questions, next 3 steps, and only the live caveats (LORO weakness, paper evidence due Nov 9, GCP reminder due Nov 6). Move the per-cycle history (cycles 32-47) to ops/journal.md or ops/history/STATE-archive.md. Keep it this way from now on: every cycle rewrites the snapshot rather than appending to it.
2. bin/router changes:
   a. In maybe_clear, log a line "clear <role>" whenever a clear is actually sent.
   b. Skip the clear when a delivery is ONLY the router's periodic continue-nudge, so the Builder keeps its working context between steps of the same task. Still clear for every other delivery: Director decisions, job-finished notices, paper mail, ntfy replies. Safety valve: force a clear anyway if that role hasn't been cleared in the last 2 h.
   c. Make every orient() line name the role's own instructions file explicitly, e.g. for the Director: "You are the DIRECTOR. Your constitution is DIRECTOR.md; CLAUDE.md is the Builder's and does not apply to you except Hard rules and the Etho rules." Do the same for the PAPER WRITER.
   d. Safety: the router is a running bash loop, and bash reads scripts as it executes them. Write the new version to a temp file, run `bash -n` on it, then mv it into place atomically. Restart the router only through the existing bin/start/session mechanism, and only if that's needed. Check router.log afterwards to confirm delivery still works. Run the diff through codex-review (low effort is fine).
3. Add one line at the very top of CLAUDE.md: "If the router prefix says you are the DIRECTOR or the PAPER WRITER, your role file is DIRECTOR.md / ops/decisions/005-E2.md; the role sections of this file are the Builder's."

To the PAPER WRITER: keep paper/STATE.md a short current-state snapshot (same rule as item 1) so re-grounding after a clear stays cheap.

Reasoning: clears are by design, since state lives in files, and they work. But the cost of re-grounding grows with STATE.md size, the continue-nudge clears throw away in-task context for no benefit, and every session auto-loads the Builder's CLAUDE.md, which risks role confusion. All three fixes are cheap and reversible.
