# Report 013: plan 005 arms C and D (thinking 1024 -> NO-GAIN; thinking OFF -> PASS)
Builder, 2026-11-06T04:45Z, repo parent 315a215 (the commit that adds this report).

## 1. Question for the Director
Arm D (thinking switched off) PASSES the Addendum D rule. Its rule says to "carry into the next 31B candidate design with the cap
question, codex-review". Do you approve that as the 31B design direction? Separately, there are 16.9 h of Kaggle quota that expire at
2026-11-07T00:00Z. May I spend about 1.2 h of it on one more screen, arm E (arm D at the shippable cap of 1.23 min), if it is
pre-registered, packed and codex-reviewed by 21:00Z?

## 2. Pre-registration (eval/plans/005.md, Addenda C/D + corrections 1-3, all written before either run)
- Arm C: not V -> INVALID. V and C empty <= 2/8 and C-empty-only <= 1 (vs B) -> PASS. Otherwise NO-GAIN. The enforcement label
  (CONSISTENT / NOT-SHOWN) is descriptive.
- Arm D: not V -> INVALID. V and not Md -> NOT-ENFORCED. V and Md and D empty <= C empty and D-empty-only <= 1 -> PASS. Otherwise
  NO-GAIN. Md = zero completed root thinking blocks in >= 7/8 tasks. V = gates a/b/d/e pass, plus every trace has a summary and at
  least one root usage turn.

## 3. What I did
- Arm C = aniket0202/gemma-31b-timing v3, bundle 31b-v005-p5c (dist/31b-v005.zip e8fbcfdc, thinking_budget 1024). Arm D = v4, bundle
  31b-v006-p5d (dist/31b-v006.zip b7b2eb3d, thinking_budget 0, which maps to enable_thinking=false). Both are arm B plus that one field,
  on the same plan-006 stack: same 8 ids, cap 4.0, 40 calls/50 turns, conc 1, 4x L4.
- Analysis per the plan: timing_summary.py (stock-path, vLLM 600, max phase1 277), trace_tool_errors.py and thinking_bound.py.
  The paired file was built by an inline script. Its first pass wrongly marked V false because the gate prefix matched the `b_note`
  text field. I fixed that before reading the verdict.
- Quota: 9.42 -> 11.43 h after C (+2.01), 13.09 h after D (+1.66), per `kaggle quota` (ops/budget/kaggle.md). GCP $0.

## 4. Results (n=8 ids, k=1 per arm; files: results/plan005_armC_vs_B.json, results/plan005_armD_vs_C.json)
| metric | arm B (4096) | arm C (1024) | arm D (off) |
|---|---|---|---|
| empty diffs (Wilson 95%) | 4/8 (0.22-0.78) | 3/8 (0.14-0.69) | 3/8 (0.14-0.69) |
| discordant vs previous arm (prev-empty-only / this-empty-only) | | B 1 / C 0, p1=0.5 | C 1 / D 1, p1=0.75, p2=1.0 |
| timeouts | 5 | 3 | 2 |
| tasks with max thinking LB > 1088 (descriptive) | 5/8 | 0/8 | 0/8 |
| tasks with zero root thinking blocks (Md) | 0/8 | 0/8 | **8/8** |
| max root per-turn completion tokens (all tasks) | see C file | 2105 | 545 |
| total tool calls | | 173 | 209 |
| sum of agent clock (s) | | 1599 | 925 |
| tasks whose agent run ended at <= 74 s (= cap 1.23 min) | | 0/8 | 3/8 (39, 42, 72 s) |
| gates a / b (s) / d (s) / e | PASS / 243.5 / 397 / 4 | PASS / 243.4 / 357 / 5 | PASS / 243.4 / 361 / 5 |
Agent clocks come from results/kaggle_timing_31b_v00{5,6}.json, tokens from results/thinking_bound_31b_v00{5,6}.json, and tool
calls/errors from results/trace_tool_errors_31b_v00{5,6}.json.

Per id, patch bytes C -> D: fastapi_14258 508->508, fastapi_14851 0->0, rich_3063 0->0, rich_3067 655->655, rich_3454 657->657,
rich_3535 465->465, **rich_3930 253->0** (D timed out), **rich_3953 0->684**. Four tasks have the same byte count in both arms. I have
not checked whether those patches are identical.

**Verdicts per the rules: arm C NO-GAIN (V; empty 3/8 > 2/8), label CONSISTENT. Arm D PASS (V; Md 8/8; empty 3 <= 3; D-empty-only 1).**

Failures and costs, reported with equal weight:
- With thinking off, the model makes more and shorter calls, and more of them fail. Tool errors per class, C -> D: cmd_error_shell
  0 -> 22, cmd_error_empty 10 -> 21, cmd_error_other 10 -> 15, sitecustomize_warn 32 -> 83. In return edit_missing_param 7 -> 0,
  write_outside_ws 1 -> 0 and read_file_error 6 -> 1.
- A non-empty diff is not a pass. Thinking off may lower fix quality in ways this screen cannot see. n=8, k=1: a ±1 empty is noise.
- Timeouts at cap 4.0 still give empty diffs (rich_3930 in D). Dec 056 item 6 remains open.
- e4b line (dec 058 item 2): **"thinking can be switched off on this stack (Md 8/8 on 31B via thinking_budget 0); it is a candidate e4b
  lever and would need its own screen."** Thinking-budget enforcement at 1024 is only "consistent", not proven.
- Required caveat (dec 057): v000-v002 on both tracks carry an inherited FastAPI/docs_src hint. Their LB scores may be tilted toward
  FastAPI-like tasks. Arms B/C/D inherit the same prompt, so this screen does not change that.

## 5. Options
A. **Adopt thinking off as the 31B design direction and draft on CPU now.** 31b-v004 = v002 + thinking_budget 0 + the /tmp fix +
   hint-line removal (dec 056 item 6 / dec 057), with the cap set under H3 (<= 1.23). Codex-review it. Ask for a slot only after
   31b-v002 scores. Cost: CPU only. Risk: its quality at 1.23 min has not been measured.
B. **A plus arm E today**: arm D at cap 1.23 (the shippable cap), same 8 ids, about 1.2 h of quota that expires at 00:00Z anyway.
   It would show whether edits still land within 74 s with thinking off (3/8 agent runs already end inside 74 s at cap 4). I would
   pre-register Addendum E before packing. The rule would be: E empty <= D empty + 2 = usable, otherwise cap-bound. Bundle 31b-v007 =
   v006 + cap only, codex-reviewed, pushed by 21:00Z or dropped. The dec 055 checklist at 00:00Z stays first.
C. Stop screening and keep C's 1024 setting. This throws away the one lever that measurably cut generation time (agent clock -42%).

## 6. Recommendation
**B.** Arm E is the most decision-relevant measurement for the 31B final (cap <= 1.23 under the finals rule), and it uses quota that
would otherwise expire. Requests: approval of the design direction (A), and Kaggle L4x4 of about 1.2 h for arm E within this week's
plan (GCP $0). No SUBMIT, no HOLDOUT.
