DECISION: approve
SUBMIT: none
GPU_ALLOWANCE: none
ESCALATE: none
DIGEST: Rules sweep from official pages and host forum answers: paper word limit clarified; main track allows only one pending submission at a time, so expect fewer usable slots.
---
Owner asked the Director to resolve the open rules questions from the competition website. I read the official pages and forum threads on 2026-11-05 with the Kaggle CLI (`competitions pages list --content`, `competitions topics show --format json`). Hosts: Elan Markowitz (wrote the bonus-prize post), Ryan Holbrook and Dustin (Kaggle). Quote rules and forum text only, never task content.

FINDINGS
Main track
M1. Submission limits (Rules page): 1 per day and up to 2 Final Submissions. Host (Elan Markowitz, thread 752220, 2026-10-24): the final private score "is the better of the two private leaderboard scores. There's no downside to selecting a second submission."
M2. Pending-submission limit (Kaggle staff Dustin, thread 747519, 2026-10-08): "If your team's previous submission is still scoring, you will need to wait until it finishes to submit again." Several participants report queue times of 30–40 h or more. As a result, the "~28 slots" figure in the slot policy is too high. Plan on roughly one scored submission every 1.5–2 days. The last reliable new score now comes from a submission made about Nov 27–28, not Nov 29.
M3. 12 h overrun: still no official ruling. Evaluation page: 12 h "inclusive of sandbox setup time, but excluding time for patch validation". Staff (Holbrook, 749597, 2026-10-15) is unchanged. A new participant data point (Nir Aberman, 752017, 2026-10-23): a config that added only an extra test re-run step ended in "Notebook Timeout after about 12 hours: no partial score, and the daily slot was used". They also reported that local timing on public repos underestimated the cost of test-running steps on the hidden repos. The worst-case assumption stays, and we now have direct evidence for it.
M4. Private-LB multiple runs (754295): no staff answer. Plan for a single run.
M5. Hosted LLM APIs (755542): no staff answer, and the only comment is the asker's follow-up. The rule stays as is: no new third-party services for task data.
M6. Small-model bonus (Prizes page + host post 751104): E2B or E4B as base, and the entry must be one of the team's two selected finals. Scoring uses the private test set, with the same rules and tie-breaking. There is an official daily standings notebook: kaggle.com/code/ryanholbrook/gemma-4-developer-agent-small-model-leaderboard. Thread 752128 (Oct 23–25) has at least two reports of an intermittent "incorrect format" error on E4B bundles that differ from scoring bundles only in the model line, with no staff answer yet. Validator acceptance of E4B itself is not in doubt: E4B entries score.
M7. LoRA (755677, 2026-11-04, participants only): some report LoRA submissions scoring 0, others report non-zero scores with rank-32 adapters. This fits our plan to validate LoRA on the exact base and measure the KV cache first. Nothing changes now.

Paper track
P1. Word count (host, threads 743255 and 749546, 2026-10-27): counted: title, abstract, captions, tables and all other judged text. Not counted: figures and references. The appendix is supplementary and "not guaranteed" to be read. If a PDF is attached, the PDF is judged on its own (same limit) and the Writeup text isn't judged. There's no official word counter yet.
P2. Tie-break (host, 750338): "it would likely be by original submission time". Ties are expected to be extremely rare because there are multiple judges. Not definitive.
P3. Writeups: at most 2 per team (host, 743255). Participants report the form allows only one submitted at a time (753195, no host answer). Plan for one.
P4. Auto-selection when no final is chosen (754899): no host answer. The rules text says Kaggle auto-selects. Mitigation: submit exactly one Writeup.
P5. Code: a public GitHub repo is fine for sharing code (host, 751804). An earlier GitHub repo does not count as prior publication (host, 755867). A private Kaggle notebook or resource attached to the Writeup becomes public automatically after the deadline. Judges "will likely look at any code" but may not run it, so a fast run path is recommended (750338).
P6. A deadline extension was requested (755176), with no answer. Nov 12 23:59 UTC stands.

TO THE BUILDER (low effort, next cycle, no compute):
1. Update docs/RULES_FINDINGS.md and docs/COMPETITION.md with M1–M7, each with its thread id, author, date and confidence tag (official / host-forum / participant). Mark "pending-submission cap" as resolved (one pending at a time). E4B validator acceptance is resolved as "E4B scores; intermittent incorrect-format reports open (752128)".
2. Timing: take M3's point about local timing on public repos underestimating test-running costs into the E4B/31B timing plan (plan 001). Measure the per-task time share spent in test runs, and keep the p90 rule.
3. Add the small-model standings notebook to docs/COMPETITION.md as a reference. Don't change experiment order.

TO THE PAPER WRITER:
1. Update paper/RULES.md: move word count, tie-break, code sharing and prior publication out of "Open questions" with the P1–P5 citations.
2. Word budget: title + abstract + body + captions + tables ≤ 2,800 words total (margin kept). Don't rely on the appendix for anything the rubric needs, because it may not be read. Put the verifiability essentials (data provenance, analysis method, how to reproduce) in the main text, and put code in a public repo or notebook.
3. Plan for exactly one Writeup. Writeup vs PDF is your choice, but judging is on whichever is primary. Keep it in the Writeup unless there's a reason not to.

DIRECTOR NOTE (slot policy, my own planning): with one pending submission at a time and long queues, I'll treat each slot as scarce. The first submission should go in as soon as the Submission Gate passes, so we learn the queue time early.

Reasoning: the owner asked for answers from the website. These come from the official pages and host statements, quoted with sources. The pending limit is the only finding that changes plans, and only for submission cadence.
