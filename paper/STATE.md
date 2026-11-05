# Paper STATE (2026-11-05)
Role: PAPER WRITER (brief: ops/decisions/005-E2.md; also 006, 007, 008). I write only under paper/.
Deadlines (UTC): outline Nov 6 23:59 (DONE, dec 007); full draft Nov 10 23:59; final + compliance pass Nov 11 18:00; Kaggle deadline Nov 12 23:59.
Status: draft.md v0.2 (ack dec 012). §4.1 final funnel stays a placeholder until the gold-local v2 results file is committed; cite committed files only. §1-4, §8, the disclosure and the references are written (9 lit refs verified on 2026-11-05 against arXiv/official pages).
 §4.1 has the first-pass funnel (52/129, env causes) and the 751487 reconciliation. The final gold-local v2 funnel is PENDING (gold-local job was 76/129 at 2026-11-05 ~14:30Z).
 §5-7 wait on results. Cut §7 if no 31B files exist by Nov 9 (dec 007). Counted text (title+abstract+body+disclosure, comments and refs excluded) is about 1,680 words of the 2,800 budget.
Builder evidence due Nov 9 (dec 007): (a) gold per-task outcomes and causes, satisfied by gold-local v2; (b) E4B timing (kernel not yet run); (c) failure taxonomy (no agent runs yet).
Constraints (dec 013): title+abstract+body+captions+tables <= 2,800 (limit 3,000; figures/refs not counted; appendix may not be read). Exactly ONE Writeup, in the Writeup text. Code via public repo with a fast run path. 5 criteria with equal weight.
FINAL-GATE CHECKLIST for Aniket (hard; dec 012: exactly 3 items, the Director batches them into one escalation ~Nov 11; I never ask Aniket directly):
 [ ] (a) disclosure wording vs 'own original work' warranty
 [ ] (b) OK to publish the Apache-2.0 code release (list in OUTLINE.md)
 [ ] (c) click Submit on the Writeup before Nov 12 23:59 UTC (drafts are NOT judged)
 Done: joined paper competition (2026-11-05, dec 012).
Open questions (mail to Director): none blocking (dec 013 resolved word count and tie-break).
Next:
 1. When gold-local v2 lands (results/gold_failure_causes.jsonl v2 + summary), fill the §4.1 funnel table and splits/hashes in §4.2.
 2. Add forum thread titles and dates to the references via the Kaggle CLI (>= 3 s between calls).
 3. Write §5 (timing rule; derivation from cap_minutes x 125 + 30 <= 660 needs no data, measured numbers PENDING) and a §6 skeleton.
