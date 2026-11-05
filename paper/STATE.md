# Paper STATE (snapshot, 2026-11-05 ~15:20Z)
Role: PAPER WRITER. Brief: ops/decisions/005-E2.md (+006, 007, 008, 012, 013, 017). Write only under paper/.
Deadlines (UTC): outline DONE; full draft Nov 10 23:59; final + compliance pass Nov 11 18:00; Kaggle Nov 12 23:59.
Constraints (dec 013): title+abstract+body+captions+tables <= 2,800 words (limit 3,000). One Writeup. Public code repo with fast run path. 5 equal-weight criteria.

Status: draft.md v0.3, about 1,880 counted words.
- Written: §1-4, §8, disclosure, references (9 lit refs verified).
- §4.1 Table 1 funnel and §4.2 splits filled from gold v2: 129 -> 52 gold pass -> 4 empty-patch pass excluded -> 48 clean (33 dev / 15 holdout); requests/httpx dropped.
- Open caveat: the Builder pre-registered a gold-local + null rerun under the fixed eval runner (journal 15:01Z). Update Table 1 if the pass set changes.
- §5 (timing) waits on the E4B timing kernel (Kaggle job e4b-timing-wait). §6 (failure taxonomy) waits on agent runs. Cut §7 (31B) if there are no 31B files by Nov 9.

Builder evidence due Nov 9 (dec 007): (a) gold outcomes DONE; (b) E4B timing RUNNING; (c) failure taxonomy (no runs yet).

Final gate for Aniket (dec 012: the Director batches these around Nov 11; I never ask Aniket directly):
 [ ] (a) disclosure wording vs the 'own original work' warranty
 [ ] (b) OK to publish the Apache-2.0 code release (list in OUTLINE.md)
 [ ] (c) click Submit on the Writeup before Nov 12 23:59 UTC

Open questions: none blocking.
Next:
 1. Add forum thread titles and dates to the references (Kaggle CLI, >= 3 s between calls).
 2. Write §5: derive cap_minutes x 125 + 30 <= 660 now; leave measured numbers PENDING the e4b-timing results file.
 3. §4.5: cite the eval/ stats module path once the Builder commits it. Write a §6 skeleton.
