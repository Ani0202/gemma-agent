# Plan 007 appendix: repeat-guard design note (dec 062 item 3). CPU-only design. NOT built, NOT packed. Written 2026-11-06T06:32Z.

## Problem (evidence, counts only)
- Arm D (31b-v006, thinking off): 22 cmd_error_shell in one task, 21 of them byte-identical back-to-back repeats
  (results/shell_error_causes_31b_v005_v006.json).
- Arm F (31b-v008, T 0.6): tasks with identical consecutive run >= 5: F 3 (runs 22/10/8) vs D 2 (results/plan005_armF_vs_D.json).
  Temperature only moved loops between tasks (dec 062 item 1).
- Cost: with max_tool_calls 40 / max_turns 50, a run of 20 identical calls burns half the call budget and usually ends in a
  timeout or cap hit with no further progress.
- The harness has no loop detection (grep of swegemma/adk_submission: none). The bundle is declarative, so we can't add a Python
  callback or tool wrapper.

## Where it can live (declarative, allowed in the bundle)
| Option | Mechanism | Verdict |
|---|---|---|
| A. Prompt rule in prompts/system.md | the model is told the rule; it keeps its own recent calls in context | CHOSEN: zero runtime cost, generic, the only option that applies at every step |
| B. Skill (skills/recover/SKILL.md) | a recovery procedure the model must choose to load | rejected as primary: a looping model rarely changes course to load a skill; a skill load also costs a call |
| C. sampling presence/frequency_penalty (adk_submission/schema.py supports both) | penalises repeated tokens | rejected: it penalises legitimately repeated identifiers in code and edit anchors; it's not specific to repeated calls |
| D. Lower max_tool_calls | caps damage only | rejected: it cuts good trajectories too |

## Exact text (Option A; replaces the narrower v004 line "If a command fails with a shell error ... never re-run it unchanged")
> - Never make the same tool call with identical arguments twice in a row. If a call fails, or returns the same output as before,
>   the next call must be different: change the arguments (a different anchor, path, or command), switch tool (for example,
>   write a `/tmp` script instead of an inline command), or move on to the next step. If the same approach has failed three
>   times, stop trying it: either submit the best patch you have with `submit_patch`, or take a different approach.

Trigger as worded: 2 identical consecutive calls (the model is told never to make the 2nd), with a hard fallback at 3
failures of one approach. N=2, not 5, because the model can't count reliably over a long context, and "identical to my last call" is
a local check. Same-error repeats with different args are covered by the "three times" clause. It's generic: no repo, task, file or
tool-output wording.

## Interaction with caps
- The rule spends no calls itself. When it works, it frees calls inside the 40-call / 50-turn caps for edits and tests.
- Risk 1: the agent submits early ("submit the best patch you have") and skips the test run. Watch the submitted-without-test-run
  count.
- Risk 2: legitimate identical repeats (re-running the same pytest command after an edit is NOT identical-in-a-row, because an edit call
  comes between). Back-to-back identical reads/greps carry no new information, so there's nothing legitimate to lose.
- Interacts with dec 056 item 6 (a timeout must never yield an empty diff): the fallback text points to submit_patch, never to an empty submit.

## How it would be judged (if built later; needs its own pre-registration + Director OK)
- Bundle: arm-1 bundle + this line only (byte diff limited to prompts/system.md), paired on the same 33 dev ids, same order, k=1.
- Metric 1 (mechanism): tasks with max identical consecutive run >= 5 (same tool + byte-identical args; eval/plan005_armF_compare.py
  logic). Arm 1 supplies the base rate on 33.
- Metric 2: empty-patch count, paired (guard-only / base-only empties).
- Metric 3 (quality guard): resolved discordant pairs guard-only / base-only, exact sign test.
- Draft rule: HARM if base-only resolved - guard-only resolved >= 3 or guard empties > base empties + 2; ADOPT if run>=5 tasks fall by
  >= 50% (and >= 2 tasks) with no HARM; else NO-EFFECT. If arm 1 shows <= 1 task with run >= 5 on 33, the guard is not worth a GPU
  arm, and it would ride along only as an UNSCREENED line in a later draft with Director approval.
