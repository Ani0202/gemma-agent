# Report 015: plan 005 arm F (31b-v008-p5f, root temperature 0.6, cap 4.0): NO-EFFECT

## 1. Question for the Director
Arm F returned the pre-registered verdict **NO-EFFECT**: raising the temperature did not remove the exact-repeat loops (3/8 tasks still have a run >= 5).
Do you accept that temperature stays 0.2, and that the next loop lever is the pre-registered generic repeat guard (design only, CPU, not built)? The
descriptive improvements below (timeouts 2->0, cmd_error_shell 22->0) are NOT promoted.

## 2. Pre-registration (eval/plans/005.md Addendum F, written 05:30Z, before packing and before any run)
- not V -> INVALID. HARM if F empty >= 5/8 or F-empty-only >= 3 (checked first). LOOP-REDUCED if V AND F has 0 tasks with max identical
  consecutive call run >= 5 AND F empty <= 4/8 AND F-empty-only <= 2. Otherwise NO-EFFECT.
- Consequences: NO-EFFECT -> next candidate is a generic skill/prompt-level repeat guard (design only, not built); temperature stays 0.2 by default.
- Descriptive only: per-task runs/spans, timeouts, first ok edit, edit_missing_param, cmd_error_shell, agent clock sum, patch bytes, sign test, gates.

## 3. What I did
Kernel aniket0202/gemma-31b-timing v6 (repo b4d9f59, pushed 05:34:58Z, COMPLETE 06:21Z), bundle dist/31b-v008.zip sha256 e1513aac...cfe9
(= v006 + configs/sampling.yaml root temperature 0.2 -> 0.6 only; code_analyzer 0.2 unchanged). I diffed the kernel's bundle dir against the
unzipped dist zip. They are identical apart from MANIFEST.md (pack leaves it out of the zip). The kernel header shows agent.yaml sha256 de80dff5... (same as v007), 4x L4, cap 4.0,
40 calls / 50 turns, conc 1. Same 8 ids, k=1. Post-processing: timing_summary --gate-mode stock-path --gate-vllm-seconds 600, trace_tool_errors,
thinking_bound, eval/plan005_armF_compare.py (REVIEWED CLEAN at 0c3c777, no integrity problems). Quota 14.49 h -> 16.02 h (+1.53 GPU-h).

## 4. Results (n=8 tasks, k=1; paired vs arm D = 31b-v006-p5d, temperature 0.2, same cap 4.0)
| metric | arm D (T 0.2) | arm F (T 0.6) | file |
|---|---|---|---|
| gates a/b/d/e (V) | PASS | PASS (a 8/8; b 171.8 <= 277 s; d vLLM 388 s; e 6 non-empty) | results/kaggle_timing_31b_v008.json |
| V add-on (summary + root usage, 8/8) | yes | yes; 1 thinking block in 1 task (17 chars), thinking_budget 0 | results/thinking_bound_31b_v008.json |
| non-empty diffs | 5/8 (Wilson 0.31-0.86) | 6/8 (Wilson 0.41-0.93) | results/plan005_armF_vs_D.json |
| discordant D-empty-only / F-empty-only | 1 / 0 | | same; exact sign p2 = 1.0 |
| **tasks with identical run >= 5 (gated)** | 2 (18, 20) | **3 (22, 10, 8)** | same |
| timeouts | 2 | 0 | same |
| first ok edit < 240 s agent clock | 5 | 6 | same |
| agent clock sum | 924.9 s | 671.7 s | same |
| edit_missing_param | 0 | 0 | results/trace_tool_errors_31b_v008.json |
| cmd_error_shell | 22 | 0 | same |
| legacy projection (diagnostic) | | FAIL 718 min; cap worst case 530 min | results/kaggle_timing_31b_v008.json |
**Verdict: NO-EFFECT.** HARM is not met (F empty 2/8, F-empty-only 0). LOOP-REDUCED fails its first condition: 3 tasks have a run >= 5.

Loops by id (longest run of byte-identical consecutive calls, D -> F): rich_3063 18 -> 22 (run_command both arms; span 34.7 -> 45.8 s),
rich_3454 20 -> 2, rich_3535 1 -> 10 (run_command, 14.4 s), fastapi_14851 3 -> 8 (read_file, 14.8 s). So loops vanished in one task and appeared
in two others. That pattern looks like run-to-run noise, not a temperature effect, and it matches the "honest limits" line of the addendum.
Patch bytes D -> F: rich_3063 0->339, rich_3067 655->654, rich_3454 657->657, rich_3535 465->465, rich_3930 0->0, rich_3953 684->649,
fastapi_14258 508->551, fastapi_14851 0->0. The non-empty count is not a pass rate (verification was skipped).

Honest limits: n=8/k=1 is a mechanism screen. The descriptive gains (no timeouts, no shell errors, 27% less agent clock) come from one sample per
task and were not gated. Temperature can change fix quality in ways this screen can't see. The 1 thinking block with thinking_budget 0 is
noted: 17 chars, 1 task.

## 5. Options
- **A (pre-registered path).** Accept NO-EFFECT. Temperature stays 0.2. Next loop lever = generic repeat guard (prompt/skill: "if your last
  call was identical and failed, change approach"), as a CPU design note only. The 31B GPU arm remains dec 061 iii exact-repeat loops. Cost 0.
- **B (deviation).** Also carry T 0.6 into plan 007 as a paired quality arm, based on the descriptive signals. That needs your explicit
  override of the pre-registered consequence, and it costs plan-007 quota (k>=2 on 33 dev).
- **C.** Re-run arm D unchanged (T 0.2) to measure loop recurrence noise. Cost about 1.5 GPU-h. Plan 007 at k>=2 measures this anyway.

## 6. Recommendation
**A.** No GPU request. Order for Nov 7 is unchanged: the dec 055 31b-v002 submit at 00:00Z comes FIRST. Then the Nov 8 slot proposal (due 12:00Z) and
the plan 007 pre-reg (due 18:00Z). If you want T 0.6 kept alive, I'd suggest a single optional plan-007 arm rather than B as a primary arm.
