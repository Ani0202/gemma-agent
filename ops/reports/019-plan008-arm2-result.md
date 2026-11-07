# Report 019: plan 008 arm 2 (31b-v011-p8b) result

## 1. Question for the Director
Arm 2 returns **NOT SHIP-ELIGIBLE**. Both guards failed, and one SAFETY row tripped (stray file), which also fires the pre-registered
HARM clause ("do not adopt; diagnose before any further arm"). Meanwhile resolved went 4 -> 8 /33 (A-only 4, B-only 0, p = 0.125).
Does the HARM clause hold arm 3 (plan 009, base mechanically = arm 1 / v009, so bundle 31b-v012-p9a) until a diagnosis, or may arm 3 run now?

## 2. Pre-registration (eval/plans/008.md l.53-82, written before data; unchanged)
- SHIP-ELIGIBLE iff ALL of: (1) pass delta >= 0; (2) MECH 1 empties <= 4/33; (3) MECH 2 run>=5 tasks <= 6/33; (4) every SAFETY metric met
  (test edits 0, **stray files 0 rows**, agent clock <= 3.5 min, total wall p90 <= 876.5 s, submitted-without-test <= arm-1 + 3 = 26).
- GUARD FAILED: per mechanism not met. HARM: B-only - A-only >= 3 **or any SAFETY metric missed** -> do not adopt; diagnose before any further arm.
- Power caveat (pre-stated): k=1, n=33; pass delta >= 0 is a do-no-harm floor, not evidence of a gain.
- Plan 009 l.17-19: arm-3 BASE = arm 2 iff SHIP-ELIGIBLE, else arm 1 -> **BASE = arm 1 (v009) -> arm-3 bundle 31b-v012-p9a** (dist/31b-v012.zip 78a8fd30...).

## 3. What I did
gemma-31b-passrate v3, pushed 00:08:09Z from main cefb420, COMPLETE 05:53Z (one session, 33/33 ids, fixed order). Outputs sealed on
download: runs/31b-v011-p8b-arm2/SEAL.sha256 (212 files, sha256sum -c OK). Quota 0.00 -> 11.26 h (ops/budget/kaggle.md).
Metrics: eval/plan008_metrics.py arm2 (codex-reviewed pre-data) -> results/plan008_arm2.json. Frozen classifiers d4cdf0f0 (governing) and
a208a023 -> results/plan008_arm2_{d4cdf0f0,a208a023}.json. Pairing + SAFETY: new wrapper eval/plan008_arm2_summary.py (reuses the
plan-007 arm-1 summary code unchanged, swaps PARTS) -> results/plan008_arm2_summary.json. Commit 4de6787. **Wrapper codex review RUNNING**
(codex-review-arm2sum-light). The verdict does not depend on it, because MECH 1/2 come from the pre-reviewed script.

## 4. Results (n = 33 dev, k = 1, same ids/order/seed-max as arm 1; A = arm 2 v011, B = arm 1 v009)
| metric | arm 1 (B) | arm 2 (A) | rule | met | file |
|---|---|---|---|---|---|
| PRIMARY resolved | 4/33 (W 4.8-27.3%) | **8/33 = 24.2% (W 12.8-41.0%)** | delta >= 0 | YES | results/plan008_arm2_summary.json `plan008_primary` |
| paired discordant A-only / B-only | | **4 / 0** (both 4), sign p = 0.125 | | | same |
| MECH 1 empty final patch | 12/33 (2 to + 10) | **15/33** (5 to + 10); paired A-only 8 / B-only 5 | <= 4 | **NO** | results/plan008_arm2.json `totals.mechanism1_empty` |
| MECH 2 tasks max run >= 5 | 17/33 (max 38, 366 rep) | **16/33** (max 28, 285 rep) | <= 6 | **NO** | results/plan008_arm2.json `totals.mechanism2` |
| submitted without test | 23 | 25 | <= 26 | yes | results/plan008_arm2.json |
| no successful submit | 7 | 6 | descr. | | same |
| test-file edits rows | 0 | 0 | 0 | yes | summary `plan008_safety` |
| **stray files rows** | 0 | **1** (fastapi_15661: patch = only a new file outside the package source; unresolved) | 0 | **NO** | summary `plan008_safety` |
| agent clock max | 210.0 s | 210.0 s | <= 210 s | yes | same |
| total wall p90 | 796.8 s | 807.2 s | <= 876.5 s | yes | same |
| timeouts | 4 | 5 | descr. | | summary `secondary` |
| H-VERIFY rows (d4cdf0f0) | (arm 1 ruled VALID, dec 069) | 9, **all empty-patch** (same l.239 false-positive pattern; a208a023 counts them NO_PATCH) | descr. | | results/plan008_arm2_d4cdf0f0.json |

Per repo (descriptive): rich 8/27, fastapi 0/6. Unscreened 25: 6/25; screened 8: 2/8. Thinking blocks 0 (expected: thinking off).
Sensitivity: c (excl all H) 8/24; d' 8/33 (every H row is an empty patch, so no resolved row moves).

**Reading.** The prompt-level guards did not do what they were designed to do. Empties went UP 12 -> 15, and 12 of the 15 empties also have
a run >= 5. Repeats moved only 17 -> 16. The resolved gain (4 new, 0 lost) is the largest paired swing we have, but at k=1 it is
p = 0.125. Pre-registration says it is not evidence, and I am not claiming it. It is consistent with the shorter-anchor/`/tmp`-script edit
rule helping on tasks the agent does finish. That is a hypothesis for a pre-registered repeat, not a finding. The stray row is a real
scratch-file-in-/workspace leak. Lever 1 (scratch files belong in /tmp) is violated once in 33.

## 5. Options
A. **Apply the rule literally: HARM -> diagnose first.** CPU-only trace diagnosis of (i) the stray row and (ii) why the empty guard
   did not fire on the 10 non-timeout empties (9 of the 15 empties called submit_patch). No GPU until done (~1 cycle). Arm 3 (v012) after.
   Cost: delays arm 3 by roughly one cycle. Quota 18.74 h is left this week, and arm 3 needs about 11.5 h.
B. **Run arm 3 now (base v009 per plan 009).** The HARM stray row concerns v011's prompt text, and the arm-3 bundle (v009 + thinking) does
   not contain it. Diagnosis runs on CPU in parallel. Cost: departs from the literal "before any further arm" wording.
C. **Pre-register a v011 k=2 repeat** (or v011 minus the empty-guard text plus a /tmp-scratch hardening line) to test the 4/0 swing.
   That spends ~11 h of quota on a hypothesis the pre-registration called underpowered, and it competes with arm 3 for this week's quota.

## 6. Recommendation
**A then B.** The diagnosis is cheap and CPU-only, and I can finish it this cycle or next. Then arm 3 on v009 (31b-v012-p9a, packed + load
check PASS, review 144907 CLEAN), within the existing quota (no new GPU request). v011 is not adopted and the 31B default draft stays
v009. I log the 4/0 swing as a candidate for a later pre-registered repeat (Option C), not acted on now.
No SUBMIT / GPU / HOLDOUT request. The Nov 8 slot proposal (due 12:00Z) follows separately. U2 = arm-2 verdict NOT SHIP-ELIGIBLE; U1 v002
LB still PENDING (last poll 05:36Z).
