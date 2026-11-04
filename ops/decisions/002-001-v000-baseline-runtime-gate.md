DECISION: approve-with-changes
SUBMIT: none
GPU_ALLOWANCE: none
ESCALATE: Could you read the Kaggle Rules tab + pinned threads and reply with anything on (a) LLM-generated training data, (b) external models/data, (c) what happens on a scorer timeout? Recommended: reply "nothing beyond secondary sources" if none. Default if no reply by Nov 6 18:00 UTC: we keep our stricter in-house rules (no proprietary-model training data, timing bound enforced).
DIGEST: Report 001 approved: v000 baselines go to free Kaggle L4x4 smoke/timing checks; no GCP spend (cumulative $0). Asked Aniket for a rules-tab read.
---
Instructions to the Builder (option 1, Kaggle only, $0):

1. **Kaggle access is yours to verify.** Aniket's Kaggle credentials are on this VM, so use the `kaggle` CLI (it reads the creds itself; never print them). Check with a cheap call (`kaggle kernels list --mine`, `kaggle competitions files <comp>`). If the CLI can't push a kernel with GPU L4x4 or attach the competition data, report BLOCKED with the exact error. Don't assume someone else will do it.
2. **Pre-register first.** Write eval/plans/001.md before any run: the measurements (vLLM startup, sandbox setup, per-task wall time at concurrency 1, tokens/sec, non-empty-diff rate, no test edits, nothing outside /tmp), the decision rule from your report, and a quota budget.
3. **Order of work.**
   a. Gold calibration on CPU: use a Kaggle CPU session (it's free and doesn't count against GPU quota) or this VM via bin/job if the snapshots fit (RAM ≤ 4 GB, disk ≥ 15 GB free). No GCP. Then produce the clean list and hash, plus frozen dev/holdout splits (stratified by repo) in eval/splits/, with the hashes journaled.
   b. **E4B v000** smoke + timing on Kaggle L4x4 at concurrency 1: ≥ 2 tasks for the smoke, and enough tasks (about 5–8) for a per-task wall-time distribution. Use dev tasks only.
   c. **31B v000**, same protocol, in a separate session.
   Budget for this week (quota resets Sat Nov 7 00:00 UTC): ≤ 10 L4x4 hours in total, ≤ 4 h per session, chunked and resumable. Log every session in ops/budget/kaggle.md.
4. **Timing rule.** Use the measured p90 per-task wall time, not the mean, as the cap check: if `p90 × 125 + startup` doesn't fit, or `cap_minutes × 125 + 30 > 660`, lower the caps and repack before you ask for any submission.
5. **The next report (002)** should go out as soon as E4B passes smoke + timing. Include a `SUBMIT` request for e4b-v000 as a deliberate baseline. Unused daily slots are lost, so I want the first baseline on the board within ~1–2 days. 31B can follow in a later report.
6. Rules: keep working from docs/RULES_FINDINGS.md under our stricter Hard rules. I've escalated the official rules read to Aniket and will forward his answer.

Reasoning: everything you asked for is free and reversible, and the only remaining v000 blocker is runtime evidence, which Kaggle L4x4 measures on the exact scorer hardware. I'm sequencing E4B first because it's cheaper on quota and it's the fastest route to a baseline submission. I'm using p90 instead of the mean because a timeout fails the whole submission.
