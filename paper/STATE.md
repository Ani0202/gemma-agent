# Paper STATE (snapshot, 2026-11-05 ~17:45Z)
Role: PAPER WRITER. Brief: ops/decisions/005-E2.md (+006, 007, 008, 012, 013, 017, 019 for EV-1 facts). Write only under paper/.
Deadlines (UTC): outline DONE; full draft Nov 10 23:59; final + compliance pass Nov 11 18:00; Kaggle Nov 12 23:59.
Constraints (dec 013): title+abstract+body+captions+tables <= 2,800 words (limit 3,000). One Writeup. Public code repo with fast run path. 5 equal-weight criteria.

Status: draft.md v0.4, about 2,330 counted words (comments, [[PENDING]] and refs excluded). Only ~470 words left for §6/§7/results.
- Written: §1-5, §8, disclosure, references (9 lit refs plus 7 forum threads with titles and dates).
- §4.1/Table 1 now reflect the strict-isolation gold rerun (52 -> 43, 9 fastapi lost to the typing_inspection leak; results/gold_rerun_b5_compare.json) and dec 019 EV-1 (splits v2 kept, 48 clean).
  PENDING results/gold_calibration_ev1.jsonl: gold 48/48 and null 0/48 => unchanged; otherwise v2.1, so update the Clean/Holdout columns.
  Note: ops/jobs/gold-rerun-b5.status = failed 255 at 17:30Z (null phase?). That's the Builder's job; just watch for the result files.
- §5: the rule (5 x 125 + 30 = 655 <= 660), the p90 gate, test-time share and the wrong-hardware lesson are written. Measured numbers are PENDING the e4b timing results file (job e4b-timing-wait3).
- §6 (failure taxonomy) waits on agent runs. Cut §7 (31B) if there are no 31B files by Nov 9.

Builder evidence due Nov 9 (dec 007): (a) gold outcomes DONE (+EV-1 validation pending); (b) E4B timing RUNNING; (c) failure taxonomy (no runs yet).

Final gate for Aniket (dec 012: the Director batches these around Nov 11; I never ask Aniket directly):
 [ ] (a) disclosure wording vs the 'own original work' warranty
 [ ] (b) OK to publish the Apache-2.0 code release (list in OUTLINE.md)
 [ ] (c) click Submit on the Writeup before Nov 12 23:59 UTC

Open questions: none blocking. Daily Builder request not used today.
Next:
 1. Trim §4.1 (~100 words: tighten the failure-cause sentence and the community-figure repeats) to make room for results.
 2. Cite thread 742807 in the Disclosure (training-data policy) or drop it.
 3. When results land: fill the §5 Table 2 timing numbers and the EV-1 line; write the §6 skeleton (incl. the dec 019 item 4 collection-error class); cite the eval/ stats module path in §4.5.
