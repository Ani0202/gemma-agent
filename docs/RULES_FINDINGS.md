# Rules findings (2026-11-04, scout). SECONDARY SOURCES ONLY: Kaggle pages are JS-rendered and were unreadable.
Main source: reconscribe.com/gemma-4-developer-agent-competition-2026 (third-party). Everything is UNCONFIRMED until read on Kaggle.

1. External data/models: allowed if public at no cost or "Reasonableness Standard". Runtime: only the chosen Gemma model, no internet. No stated ruling on LLM-generated training data (as of 17 Oct). Our Hard rule 2 is stricter; keep it. Teams <=5; merge/entry deadline Nov 25, finals Dec 2. Winners' code must be Apache-2.0 (startupgrantsindia). UNCONFIRMED.
2. Models: 31B, 12B, E4B, E2B QAT-w4a16-ct all listed as allowed (multiple third-party sources). Bonus is E2B/E4B only (not 12B). 12B needs vLLM hf-overrides. Validator acceptance of E4B NOT proven; only our pack + starter validator cell can show it.
3. Submission: notebook writing /kaggle/working/submission.zip; 1 submission/day, wait for previous to finish; select up to 2 finals (Kaggle auto-picks if none). Queue waits >15h reported; pending cap number unknown.
4. 12h overrun: reportedly errors the whole submission. Staff said scoring unfinished tasks as 0 was "being reconsidered" (early Oct). No final ruling. Keep 11h cap.
5. Hidden set: ~120 tasks "from private repositories", split evenly public/private LB. Likely not the 4 public repos -> do leave-one-repo-out. Low-medium confidence.
6. Private LB multiple runs: unknown (open thread). Plan for a single run.

Follow-ups needing a browser/human: Rules and Data tabs; threads on multiple runs, unfinished tasks, LLM-data; starter validator cell for E4B.
