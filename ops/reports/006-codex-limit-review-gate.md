# Report 006: Codex usage limit blocks the dec 028 merge-diff review (critical path)

## 1. Question for the Director
Codex hit its usage limit at 19:28Z (resets ~23:04Z), and both pending reviews died with no findings. Should I
(B) push the e4b-v001 re-time now from the unmerged fix5 branch after a Claude review, and merge/rely on it only
once the Codex review is clean, or (A) wait for Codex at 23:08Z, which in practice gives up today's submission slot?

## 2. Pre-registration
Nothing new. The dec 028 item 4 gate (a)-(e) is unchanged. Option B changes only the ORDER: re-time before
merge. The result is not used for any decision (report 005 / SUBMIT) until the Codex merge-diff review is clean.

## 3. What I did (main 4e1aa3c)
- review-kernel-setup-fix5-light and review-memguard-fix6-light both exited 0 but codex failed:
  ops/codex/review-20261105T192750.log and ops/codex/review-20261105T192658.log end with "You've hit your usage
  limit ... try again at 11:04 PM". (The fix6 run had passed 10 of its own probes before dying. It has no verdict.)
- Both reviews will rerun automatically at 23:08Z with the same prompts (jobs review-kernel-setup-fix5b-light and
  review-memguard-fix6b-light, via ops/codex/relaunch-after-limit.sh).
- No merge, no push, no deploy. memguard (pid 7933) is still the watchdog, with 0 kills.

## 4. Results
No eval numbers. Timeline if we wait (A): review ~23:08-23:25Z, merge, then the re-time (~1.5 h wall) finishes
around 01:00Z. Today's slot is lost.

## 5. Options
- **A. Wait for Codex.** Strict dec 028 order. Cost: today's submission slot, plus ~4 h idle on the critical path.
- **B. Claude review now, re-time from the branch, Codex gate before relying on it.** A fresh Claude subagent
  reviews main...codex/kernel-setup-fix5. If it finds nothing BLOCKING, push e4b-v001 on 004-gpu-retime-ids
  from the fix5 worktree (-t ~3 quota-h; week so far 3.48 of ~30). The Codex review at 23:08Z is still required
  before the merge, before report 005, and before any SUBMIT request. If Codex finds something BLOCKING that
  affects the measurement, the run is discarded (cost ≤3 quota-h). This keeps a SUBMIT before 23:59Z possible,
  but tight.
- **C. Like B, but no Claude review.** Saves Claude usage. Higher risk of wasting quota on a kernel bug.

## 6. Recommendation
**B.** The quota risk is small, and the ordering change doesn't weaken the codex-before-rely rule.
memguard-fix6 has no deadline, so it waits for Codex either way. If Codex's limit keeps biting, we may need
cheaper review prompts (CODEX_EFFORT=medium) or Claude reviews for non-eval code. That's your call.
