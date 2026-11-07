# Report 020: arm-2 diagnosis done; stray classifier defect hits arm 3 -> STOP per dec 080 item 3

## 1. Question for the Director
The diagnosis found a classifier defect that affects arm 3: the stray-files SAFETY metric flags correct fixes on 2/33 dev
tasks. Do you approve a pre-data amendment to the stray definition (Option A) and an immediate push of arm 3 (v012)?

## 2. Pre-registration
Not a new experiment. Dec 080 item 2(c) asked whether the findings imply a measurement or classifier defect affecting
arm-3 metrics. Rule (item 3): if yes, STOP and report. The arm-3 definition (plan 009) is unchanged. Only how the
SAFETY stray check is computed would change, and it would be fixed before any arm-3 row exists.

## 3. What I did
CPU-only, sealed traces only, no new runs. The diagnosis is results/plan008_arm2_diagnosis.md, with helper
eval/plan008_arm2_empty_diag.py (commit: this cycle). I folded in codex review 20261107T055702 (summary wrapper).

## 4. Results (all in results/plan008_arm2_diagnosis.md)
| finding | n | detail |
|---|---|---|
| stray row fastapi_15661 | 1/33 | Deliberate deliverable, not scratch: written in /tmp, then `mv` into scripts/ (call 31/40) and `git add`. The gold patch also creates one new non-package .py under scripts/ (different name). Prompt lines are identical in v009 and v011 (system.md:31-34). |
| dev tasks whose GOLD patch creates new non-package files | 2/33 | fastapi_15661 (scripts/), fastapi_15800 (docs_src/, 6 files). A correct arm-3 fix on either one would veto SAFETY. |
| non-timeout empties: never edited | 7/10 | All submitted at call 39-40/40. 0/7 ran git diff or git status (the guard's check never ran). 5/7 were in repeat loops. |
| non-timeout empties: edit_file failures only | 3/10 | 51/51 failures were "old_string missing" (malformed call). 1/3 submitted. |
| non-timeout empties: edits reverted / other | 0 / 0 | |
| correction | | 8 (not 9) of the 10 non-timeout empties called submit_patch. The 9 counts all 15 empties. |
| codex BLOCKING 1 (wrapper) | 1 row | rich_3468 agent clock 210.0009 s > 210 s cap. Literal met.agent_clock = false (was reported true because of rounding). |
| codex NB 1 | | paired empties: arm-2-only 8 / arm-1-only 5 |

Re-stated arm-2 verdict: **NOT SHIP-ELIGIBLE, unchanged** (both mechanisms FAIL). The base stays arm 1, and arm 3 stays
31b-v012-p9a, dist/31b-v012.zip sha256=78a8fd30389ec3acf58b44bc8743d750b496041f5c8d2b35790f0d913130ede5.

## 5. Options
- **A (recommended): amend now, before any data, and push arm 3 at once.** A new file stops counting as stray when it sits
  in a directory where the task's gold patch creates a new file (dev-eval measurement only, mechanical, applied identically
  to arm 3 and to the base rows). Under A, arm 2's stray count goes to 0. Plan 009 l.92 gets a dated pre-data addendum, plus
  a codex-light review of the classifier change (CPU). The run itself doesn't depend on the classifier, so pushing need not
  wait for that review. Trade-off: it uses gold-patch paths in a metric (fine for dev, it is our eval, and it never reaches a
  bundle).
- **B: keep the literal rule, push arm 3 now, and have the Director rule on any stray hit with per-row provenance.**
  Trade-off: no code change, but a post-hoc ruling on an arm-3 SAFETY veto is exactly what pre-registration is meant to
  avoid.
- **C: hold arm 3 until the amendment is reviewed.** Costs about 1 h of the GPU window and gains nothing, because the
  classifier runs after the data comes in.

## 6. Recommendation
Option A. Please approve the stray amendment and an immediate push of 31b-v012-p9a under plan 009 as written (smoke
rule, ONE session, D73.7 chunk rule, quota logged before and after). Quota: 18.74 h left this week, arm 3 ~11.5 h.
No SUBMIT, GPU or HOLDOUT requests. The empty-guard finding (prompt check never executed; edit_file malformed-call
failures) feeds the next empty-patch lever: a tool-level fix for the missing old_string, not more prompt text. That goes to the
backlog, with no spend this week.
