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

Still unverified: E4B validator acceptance (needs our pack + starter validator cell), pending-submission cap.
