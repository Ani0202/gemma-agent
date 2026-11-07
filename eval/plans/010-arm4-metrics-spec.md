# Spec: `arm4` mode in eval/plan008_metrics.py (plan 010, Addendum A5). Written PRE-DATA 2026-11-07T11:33Z.
Source of requirements: eval/plans/010.md (rule + Addendum A) and codex review ops/codex/review-20261107T112835.md item 4.
Do NOT change behaviour of existing modes (arm2/arm3/arm3smoke/base); existing tests must keep passing.

## CLI
`python3 eval/plan008_metrics.py arm4 --arm4-dirs DIR[,DIR] --base-dirs DIR[,DIR] --identity-json P --bundle v014 \
  --transport DIR=SHA (each arm-4 dir) --push-event DIR=smoke|main (each arm-4 dir) --smoke-json P --base-json results/plan009_arm3_vs_arm1.json \
  --arm1-dirs DIR[,DIR] --out P` (mirror arm3 flag names/semantics wherever arm3 already has them; reuse arm3 helpers).

## Required behaviour
1. Inventory: exactly the 33 registered ids (eval/plans/007-arm1-ids.txt) per arm; pair by id; first attempt retained; duplicate-attempt
   evidence, timeouts and H rows kept. Any arm with an incomplete inventory -> exit nonzero, verdict null ("NO_DECISION"); never a reduced denominator.
2. BASE = arm 3 (runs/31b-v012-p9a-{smoke,main}), bound to its recorded evidence (base-json sha + classifier shas). Base is VALID even
   though its plan-009 verdict is ON-BETTER-VETOED: do NOT reuse the SHIP-ELIGIBLE base-selection requirement (metrics ~l.1186).
3. PRIMARY: ARM4-only / ARM3-only resolved discordants, D = ARM3-only - ARM4-only, exact two-sided sign test, arm-4 resolved/33 + Wilson 95%.
4. Timeouts: `timed_out OR agent_timeout_fired`; counts arm4/arm3/arm1; paired timeout discordants vs arm 3 and vs arm 1.
   Empties: `verified_patch_bytes == 0`; same reporting.
5. Limits ABSOLUTE: timeouts <= 16, empties <= 18 (NOT existing base+N helpers: they would allow 23 / 21, metrics ~l.1099/1153).
6. TIMING (unrounded): every row agent_clock_seconds <= 220, finalization_seconds <= 30. SAFETY: test-file edits 0; S81 governing stray 0
   (governing + literal reported symmetrically for both arms); total wall p90 <= 1.10 x arm-3 p90 (unrounded); submitted-without-test
   <= 10 with D73.5 applied to BOTH arms (~l.1023).
7. Preserve: bound/recomputed smoke evidence, per-push identity, kernel pairing (transport), literal H >= 5 of 33 -> INVALID, missing evidence -> fail.
8. Verdict table, INVALID evaluated FIRST: INVALID; D >= 3 -> 2048-WORSE; D <= 2 and (timeouts > 16 or empties > 18) -> 2048-NO-GAIN;
   D <= 2, limits pass, TIMING or SAFETY fail -> VETOED; else 2048-ADOPT. Exactly one branch.
9. DESCRIPTIVE (no effect on verdict): original plan-009 rule arm 4 vs arm 1 incl. its timeout/empty vetoes; root thinking blocks/chars per
   task; repeat metric; LLM/tool calls p50/p90; context-overflow row count computed from traces (do NOT hardcode "not available" as
   summarize_arm does ~l.1052; if truly undeterminable for a row, count it as unknown and list ids); per-repo breakdown.
10. Output JSON schema name plan008_metrics/v1, mode arm4, script_sha256, input file shas, definitions block.

## Acceptance tests (new file eval/tests/test_plan010_metrics.py, synthetic fixtures only, offline)
D=2 vs D=3; timeouts 16 vs 17; empties 18 vs 19; overlapping failures (limit + safety both fail -> NO-GAIN precedence);
INVALID precedence over every branch (H=5); missing evidence -> fail; incomplete inventory -> NO_DECISION nonzero exit;
unrounded boundaries (220.0001 fails, wall p90 exactly 1.10x passes); vetoed-but-valid arm-3 base accepted; D73.5 on both arms.
Run: the repo's existing test invocation for eval/tests (see eval/tests/test_plan009_metrics.py header) — full eval/tests suite must pass.
