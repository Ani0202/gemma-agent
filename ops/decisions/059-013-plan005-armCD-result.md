DECISION: approve-with-changes
SUBMIT: none
GPU_ALLOWANCE: none
ESCALATE: none
DIGEST: A free Kaggle screen showed the 31B agent works with thinking switched off and runs ~40% faster; approved one more free screen at the short time cap. Nov 7 31B submission plan unchanged.
---
Option B approved, with a tighter Addendum E rule and two cheap checks.

1. Design direction: approved as a direction, not as a ship decision. Thinking off (thinking_budget 0) goes into the 31b-v004 CPU draft: v004 = v002 + thinking_budget 0 + the /tmp fix + hint-line removal (dec 056 item 6 / dec 057), with the cap set by the finals rule (≤1.23 unless 31b-v002 scores on the real scorer at 3.5, in which case bring the cap choice back to me with data). Pack it and codex-review it. No slot request until the v002 LB result exists, and v004 competes against repeating v002 on paired evidence. A PASS on empty-diff counts at n=8/k=1 is not quality evidence.
2. Arm E: one Kaggle L4x4 run (~1.2 h of quota, which expires at 2026-11-07T00:00Z anyway; $0 GCP). Bundle 31b-v007 = 31b-v006 with only the cap changed to 1.23, byte diff vs v006 limited to eval_config.yaml + MANIFEST. Same plan-006 stack: same 8 ids, 40 calls/50 turns, conc 1, KERNEL_BUDGET 6000 s, --gate-mode stock-path. Codex-review it (a light review is fine for a cap-only diff). Push by 21:00Z or drop it with no further decision. Log quota before and after.
3. Pre-register Addendum E BEFORE packing, with this rule instead of the proposed "D + 2", which would call 5/8 empty "usable":
   - not V -> INVALID.
   - V and E empty ≤ 4/8 and E-empty-only (vs D) ≤ 2 -> USABLE.
   - otherwise -> CAP-BOUND.
   Descriptive only (not gated): timeouts, the number of tasks whose first successful edit lands before the cap, and the per-id patch bytes D -> E. If CAP-BOUND, write one line saying that dec 056 item 6 (a timeout must never yield an empty diff) becomes the binding blocker for any 31B final at cap ≤1.23.
4. Two cheap CPU checks to put in the arm E report: (a) whether the 4 same-byte patches in C vs D are byte-identical (sha of each diff); (b) a breakdown of the 22 new cmd_error_shell errors in D by cause (quoting/heredoc, missing binary, syntax, other), counts only, no task text. If one generic cause dominates, fold a fix into the v004 draft.
5. Priority is unchanged: the dec 055 checklist at 2026-11-07T00:00Z comes before arm E and its analysis. A running arm E kernel doesn't block the submit.
6. e4b: noted that thinking off is a candidate e4b lever, and it may also address the e4b context-overflow failure (kernel v5, 7/8). Don't screen it this week. Include it as an arm when you bring the next e4b design after the e4b-v002 LB result.
7. Next week the main request is still plan 007 (33-dev pass rate, dec 058 item 7). It should include thinking-off vs thinking-on as a paired arm if the quota allows, because that is the quality question these screens can't answer.

Reasoning: I spot-checked results/plan005_armD_vs_C.json (empty C 3 / D 3, discordant 1/1, Md 8 tasks, verdict PASS, max root completion 2105 -> 545) and results/trace_tool_errors_31b_v00{5,6}.json (empty 3/3, cmd_error_shell 0 -> 22, edit_missing_param 7 -> 0). All match report 013, and the pre-registered rules were applied as written. Arm E is the most relevant measurement for a 31B final under the H3 cap, and it uses quota that is lost at the reset. I tightened the rule because the proposed threshold would have called 5/8 empty diffs usable. The rise in shell errors is a real cost of thinking off and needs a cause before v004 ships. Known limits: n=8/k=1, empty-diff counts are not pass rates, and arms B-E all carry the inherited prompt (dec 057 caveat).
