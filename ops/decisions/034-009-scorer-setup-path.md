DECISION: approve-with-changes
SUBMIT: none
GPU_ALLOWANCE: none
ESCALATE: May the Director's drafted question asking Kaggle staff whether scoring uses the subprocess or Docker sandbox be posted from your account? Recommended: yes, post it as drafted. Default if no reply by Nov 7 12:00 UTC: not posted; we proceed on our own measurements.
DIGEST: Found evidence that the scorer's per-task setup may be ~15x shorter than we budgeted; a safe, staged way to give the main-prize entry ~3x more thinking time is approved.
---
Spot-checks:
- The Evaluation-page quote is in docs/RULES_FINDINGS.md:39.
- container_setup.py:512 and :529 both early-return for the subprocess backend.
- results/stock_subprocess_setup_local.json shows rich_3063 at 2.19 s total, with install_editable_package and install_test_dependencies at 0.0 s.
Option C is approved, with the step-up rule replaced as follows.

1. Forum question: I've escalated the section-6 draft to Aniket. Post it only if he says yes. If he hasn't replied by Nov 7 12:00Z, it is not posted and nothing waits on it.
2. Plan 006 (31B timing): the addendum is approved, including max_output_tokens 8192 at both occurrences. It is a pre-run change, documented before any result, so it is acceptable. CHANGE: run at cap 4.0, not 1.0. This is a kernel quota run, not a submission, so a higher cap only costs quota (~2.4 quota-h, week ~7.6/30). It also measures exactly the bundle we would step up to. The cap-1.0 behaviour is just a truncation of it, and vLLM startup is the same. Gates for this run:
   (a) 8/8 complete, no harness error;
   (b) max(Phase-1 minus setup.py emulation) <= 4.0 x 60 + 37 s = 277 s;
   (d) vLLM startup <= 10 min;
   (e) >= 1 non-empty source diff.
   Also report full Phase-1 including emulation, mean agent seconds, the timeout-fired count, and P1-P3. Probes P1-P3 are approved. P2 sends no payload, does a DNS lookup plus a 10 s TCP connect only, and internet stays OFF. The kernel change goes through codex-review AFTER fix5c and the v002 review (Codex capacity). Push as soon as it's clean. No further decision is needed.
3. Ruling on option B: REJECTED as written. A blind submission with an estimated ~15% chance of timing out breaks our hard constraint. Replace it with a gated step-up.
   - G1 (evidence): P2 finds no docker binary and no /var/run/docker.sock on the Kaggle GPU image, AND P1 stock-path setup is <= 30 s on all 8 tasks, AND the plan-006 cap-4.0 run passes its gates.
   - If G1 holds, request SUBMIT for 31b-v001-hicap with cap <= 3.5 min. Check: under H2 with S = 60 s (double the estimate), (3.5x60 + 7 + 60)/60 x 125 + 30 = 607 min <= 660.
   - It's legitimate: we're checking that our own bundle fits the runtime, which tells us nothing about hidden tasks, so Hard rule 3 is respected.
   - If it scores, H3 is falsified on the real scorer. If it fails, we lose one dev slot and revert to the H3 cap. A staff answer, if it comes, overrides G1 either way.
4. FINALS RULE (pre-registered now): no bundle whose cap exceeds the H3 bound (31B 1.23 min; e4b 1.0) may be a final unless a submission at the same or a higher cap, on the same model, has been SCORED successfully on the real scorer. Plan the slot calendar so that a validation exists for each track well before Nov 29.
5. For e4b-v002 when it's submitted: record the submit time, the completion time, and any runtime field the Kaggle API/CLI exposes, in ops/budget/kaggle.md. Queue time confounds it, so this is weak evidence only. Never act on it alone.
6. Your fidelity side note (under H1, test deps come from the scorer's own site-packages): put it in STATE as an open eval-design question. Don't act on it before local pass-rate evals start. Then pre-register which environment the local sandbox models, and why.
7. Order of work: fix5c + v002 reviews -> v002 SUBMIT mail -> the P1-P3 kernel change + review -> plan 006 push at cap 4.0 -> report 010 (31B timing + G1 verdict).

Reasoning: at a ~1 min cap the 31B entry is close to worthless, so the main prize depends on this question. A blind gamble is unnecessary because P1/P2 come at no extra quota and can settle most of it. After that, a validation submission falsifies H3 on the actual scorer at the cost of one dev slot. The finals rule means we can never ship an unvalidated cap.
