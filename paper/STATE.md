# Paper STATE (2026-11-05)
Role: PAPER WRITER (brief: ops/decisions/005-E2.md; also 006, 007, 008). I write only under paper/.
Deadlines (UTC): outline Nov 6 23:59 (DONE, dec 007); full draft Nov 10 23:59; final + compliance pass Nov 11 18:00; Kaggle deadline Nov 12 23:59.
Status: draft.md v0.2. §1-4, §8, the disclosure and the references are written (9 lit refs verified on 2026-11-05 against arXiv/official pages).
 §4.1 has the first-pass funnel (52/129, env causes) and the 751487 reconciliation. The final gold-local v2 funnel is PENDING (gold-local job was 76/129 at 2026-11-05 ~14:30Z).
 §5-7 wait on results. Cut §7 if no 31B files exist by Nov 9 (dec 007). Body is about 1,280 words of a 2,800 budget.
Builder evidence due Nov 9 (dec 007): (a) gold per-task outcomes and causes, satisfied by gold-local v2; (b) E4B timing (kernel not yet run); (c) failure taxonomy (no agent runs yet).
Constraints: 3,000 words (body <= 2,800, refs excluded; open question), Kaggle Writeup or arXiv-ready PDF link, 5 criteria with equal weight.
ANIKET CHECKLIST (hard; route any questions about these via the Director, not Aniket):
 [x] Joined paper competition (Aniket confirmed 2026-11-05)
 [ ] Review AI-disclosure paragraph vs 'own original work' warranty
 [ ] OK public Apache-2.0 code release (list in OUTLINE.md)
 [ ] Click SUBMIT on the Writeup before Nov 12 23:59 UTC (drafts are NOT judged); select final submission
Open questions: word-count scope for refs; resubmit tie-break timestamp (no official answer).
Next:
 1. When gold-local v2 lands (results/gold_failure_causes.jsonl v2 + summary), fill the §4.1 funnel table and splits/hashes in §4.2.
 2. Add forum thread titles and dates to the references via the Kaggle CLI (>= 3 s between calls).
 3. Write §5 (timing rule; derivation from cap_minutes x 125 + 30 <= 660 needs no data, measured numbers PENDING) and a §6 skeleton.
