# Rules findings (2026-11-04, from OFFICIAL sources; supersedes the earlier third-party version)
Sources: Kaggle CLI (`kaggle competitions pages list --content --format json gemma-4-developer-agent`,
`kaggle competitions topics list/show`). Authority: Director decision ops/decisions/004-002-001-v000-baseline-runtime-gate.md.

(a) **LLM-generated training data.** Staff (Ashley Oldacre, thread 742807, 2026-09-29): external-model outputs
    are usable if the model's own licence terms allow it and the result doesn't conflict with the competition
    licence (winner licence OSI-approved, e.g. Apache-2.0). Claude/GPT/Codex terms forbid training competing
    models, so Hard rule 2 stays. Permissively licensed open-weight teachers whose licence allows training
    other models are rules-legal.
(b) **External data/models.** Rules §2.6: allowed if publicly available and equally accessible at no/minimal
    cost (Reasonableness Standard). Runtime limited to the four QAT-w4a16-ct Gemma 4 variants, same model for
    every agent, PEFT LoRA in adapters/, harness tools only. L4 sessions have no internet. Data licence:
    "Competition Use and Commercial Apache 2.0". §2.4.b forbids giving Competition Data to non-participants.
    Hosted LLM APIs: OPEN (thread 755542, no staff answer). Practice: no new third-party services for task data.
(c) **Scorer timeout.** Evaluation page: 12 h covers all tasks incl. sandbox setup, excludes validation.
    Staff (Ryan Holbrook, thread 749597, 2026-10-15): naively setting unfinished tasks to 0 "could lead to
    inconsistent results on the public and private leaderboards"; he would "try to think of other ways" to let
    teams use the 12 hours better. That is NOT a ruling on the overrun outcome. Third-party reports say an overrun
    fails the whole submission. **No official ruling on overrun outcome; we assume worst case (failed submission).**
    11 h bound and p90 timing rule stay. (Corrects dec 004(c), per dec 008.)
(d) **No repo overlap.** Staff (Ryan Holbrook, thread 747248, 2026-10-09): none of the training-task repos are in
    the test set; every hidden task validates 100% with the gold patch. Generalization to unseen repos is the game.
(e) **Private LB multiple runs:** no staff answer (thread 754295). Plan for a single run.
(f) **Paper track:** separate competition `gemma-4-developer-agent-paper`, $35,000 Paper Submission Award,
    deadline Nov 12 2026 23:59 UTC (Timeline page). Escalated to Aniket (E2); no drafting until a decision.


## Rules sweep 2026-11-05 (Director decision ops/decisions/013-owner-rules-sweep-2026-11-05.md)
Confidence tags: **official** = Rules/Evaluation/Prizes pages; **host-forum** = host or Kaggle staff post;
**participant** = participant reports only.
- **M1 Submission limits** [official + host-forum]: Rules page: 1/day, up to 2 Final Submissions. Host Elan
  Markowitz (thread 752220, 2026-10-24): final private score "is the better of the two private leaderboard
  scores. There's no downside to selecting a second submission."
- **M2 Pending-submission cap: RESOLVED, one pending at a time** [host-forum]: Kaggle staff Dustin (thread
  747519, 2026-10-08): "If your team's previous submission is still scoring, you will need to wait until it
  finishes to submit again." Participants report 30–40 h+ queues [participant]. Planning: ~1 scored submission
  per 1.5–2 days; last reliable new score from a submission made ~Nov 27–28.
- **M3 12 h overrun** [official + host-forum + participant]: still no official ruling. Evaluation page: 12 h
  "inclusive of sandbox setup time, but excluding time for patch validation"; staff (Holbrook, 749597,
  2026-10-15) unchanged. Participant Nir Aberman (752017, 2026-10-23): a config adding only an extra test re-run
  step hit "Notebook Timeout after about 12 hours", no partial score, daily slot used; local timing on public
  repos underestimated test-run cost on hidden repos. Worst-case assumption stays, now with direct evidence.
- **M4 Private-LB multiple runs** [participant]: no staff answer (754295). Plan for a single run.
- **M5 Hosted LLM APIs** [participant]: no staff answer (755542). No new third-party services for task data.
- **M6 Small-model bonus** [official + host-forum + participant]: E2B or E4B base, must be one of the two finals,
  private test set, same rules/tie-breaks (Prizes page; host post 751104). Standings notebook:
  kaggle.com/code/ryanholbrook/gemma-4-developer-agent-small-model-leaderboard. **E4B validator acceptance:
  RESOLVED, E4B scores;** intermittent "incorrect format" reports on E4B bundles differing only in the model line
  remain OPEN (752128, Oct 23–25, no staff answer) [participant].
- **M7 LoRA** [participant]: thread 755677 (2026-11-04): some LoRA submissions score 0, others non-zero with
  rank-32 adapters. Consistent with our plan: validate on the exact base, prove outputs change, measure KV cache.
