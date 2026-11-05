# Paper STATE (snapshot, 2026-11-05 ~23:10Z)
Role: PAPER WRITER. Brief: ops/decisions/005-E2.md (+006, 007, 008, 012, 013, 017, 019 for EV-1 facts; 033/034 for timing facts). Write only under paper/.
Deadlines (UTC): outline DONE; full draft Nov 10 23:59; final + compliance pass Nov 11 18:00; Kaggle Nov 12 23:59.
Constraints (dec 013): title+abstract+body+captions+tables <= 2,800 words (limit 3,000). One Writeup. Public code repo with fast run path. 5 equal-weight criteria.

Status: draft.md v0.5, 2,723 counted words (comments, [[PENDING]] and refs excluded). ~77 words left under the self-imposed 2,800; trims needed before §6/§7.
- Written: §1-5, §8, disclosure, references.
- §5 rewritten from Director nudge 2026-11-05T22:50Z:
  5.1 rule now c+F+S per task (first baselines put setup in the fixed 30 min; v000 measured 208-212 s/task).
  5.2 Table 2 = results/kaggle_timing_e4b_v001.json, cites gate.status=FAIL (NOT legacy top-level 'decision'); cap 1.0 -> 631 min (F=7 s, dec 033).
  5.3 emulator lesson, H1/H2/H3 as OPEN question, no answer asserted (report 009; setup_py_cause_v5; stock_subprocess_setup_local).
  5.4 wrong-hardware lesson (shortened).
- §4.1: PENDING results/gold_calibration_ev1.jsonl (not present yet).
- PENDING in §5: first scored E4B LB result (expected Nov 6-7; one noisy number; times from ops/budget/kaggle.md); probe result (plan 006 / report 010, G1 per dec 034).
- §6 failure taxonomy: Builder runs trace-analyst on 8 v5 traces (small n) -> keep §6 very short or merge into §5.
- §7 31B: cut-able stub; 31B timing run (plan 006, cap 4.0) planned this week. Cut if no 31B files by Nov 9.

Final gate for Aniket (dec 012: the Director batches these around Nov 11; I never ask Aniket directly):
 [ ] (a) disclosure wording vs the 'own original work' warranty
 [ ] (b) OK to publish the Apache-2.0 code release (list in OUTLINE.md)
 [ ] (c) click Submit on the Writeup before Nov 12 23:59 UTC

Open questions: none blocking. Daily Builder request not used today.
Next:
 1. Trim ~150 words: §4.1 (failure-cause sentence, community-figure repeats with §1 line 23 and §3 line 40), §1 problem 3.
 2. Fill abstract/contributions PENDINGs with the timing finding (cap 5 -> 1.0 and the emulator question).
 3. When results land: EV-1 line, LB number, probe/G1 verdict in §5.3, short §6 from the trace-analyst output, §7 stub or cut; cite the eval/ stats module path in §4.5.
