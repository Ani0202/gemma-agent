# Plan (the Director may revise it; log revisions in the journal)

Today is Nov 4. The final deadline is Dec 2, 23:59 UTC. Each phase ends in a gate report to the
Director.

## P0: Foundation and baselines (Nov 4–7)
Follow `docs/KICKOFF.md`.

**Gate 0:**
- The harness is verified and the facts are corrected.
- Gold calibration has produced the clean task list.
- The splits are frozen.
- `pack` and the eval runners work.
- 31B and E4B baseline bundles exist.
- The first baseline submission is authorized.

## P1: Scaffold iteration, both tracks (Nov 7–18)
- Use the E4B track as a cheap testbed: a 1×L4 runs about 4× cheaper than 4×L4. Port its wins to
  31B and confirm them there.
- Work on the failure taxonomy, harness-trap fixes, the prompt workflow, skills, the localizer
  sub-agent and sampling.
- Submit daily when there's an eligible candidate.

**Gate 1:** each track's best bundle beats its baseline on paired dev, and the timing bound holds.

## P2: Post-training (Nov 12–25)
- Collect trajectories on dev tasks (never holdout).
- Use rejection-sampling SFT, plus scripted trajectories built from the reference patches.
- Train LoRA for E4B first, then 31B on an A100.
- Run 1–2 rounds of expert iteration.
- Ship only if it wins paired on dev **and** holdout, in the exact vLLM base.

**Gate 2:** for each track, decide adapter vs no adapter.

## P3: Hardening (Nov 24–29)
- Freeze candidates.
- Run leave-one-repo-out checks, variance runs, and a timing rehearsal on 4×L4.
- Get the last scored submissions in by about Nov 29.

## P4: Finals (Nov 30–Dec 2)
- Run the Director's selection analysis.
- Escalate to Aniket on Dec 1.
- Lock the selection by Dec 2, 18:00 UTC.

## Budget plan ($150 hard cap; the Director releases it in increments)
| Use | Approx. |
|---|---|
| CPU x86 VM for gold calibration and Phase-2 checks | $5 |
| E4B on 1×L4 (spot) | $30 |
| 31B on 4×L4 (spot) | $65 |
| LoRA training (A100/H100 spot, few hours) | $30 |
| Reserve | $20 |

Kaggle L4x4 gives about 15 h/week, reserved for exact-environment smoke tests and timing.
