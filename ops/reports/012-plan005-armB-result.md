# Report 012: plan 005 arm B result (MECHANISM-ONLY) and two follow-up screens (Kaggle L4x4 request)
Builder, 2026-11-06T02:22Z, repo parent 5e6a87e (commit that adds this report).

## 1. Question for the Director
Arm B fixed the tool errors it targeted but not the empty diffs (4/8, same as arm A). May I spend about 2.1 h of Kaggle L4x4 quota
on arm C (thinking_budget 4096 -> 1024, one config line) before the 2026-11-07T00:00Z reset, after review-p5c-light is clean? And may I
also run Addendum B (M2 edit-checkpoint skill, ~2.1 h) if it is built and reviewed before the reset?

## 2. Pre-registration
eval/plans/005.md Addendum A + correction 01:04Z (before the arm-B run). V = gates a/b/d/e pass and trace_tool_errors.py exits 0.
E = B empty <= 2/8 and B-empty-only <= 1. M = write_outside_ws <= 2 and edit_missing_param <= 9. V+E+M = PASS; V+M without E =
MECHANISM-ONLY (report, no ship, trace-analyst); V without M = FAIL. Addendum B (01:03Z) and Addendum C (02:19Z, new) are pre-registered
before any of their runs; the M2 choice line is dated 02:19Z, after Codex feasibility. (Stamps typed as 02:35Z/02:40Z in the plan
were wrong; a correction line gives the git commit times.)

## 3. What I did
- Arm B = aniket0202/gemma-31b-timing v2, bundle 31b-v003-p5t4 (dist/31b-v003.zip e9e603ab). The downloaded bundle dir equals
  bundles/31b/v003 (diff -rq clean). The kernel header reports git_sha 7e6bba3; `git diff 2db5f51 7e6bba3 -- eval/kaggle` is empty,
  so this is the same stack as arm A. Quota 7.28 -> 9.42 h (+2.14), see ops/budget/kaggle.md.
- Ran eval/trace_tool_errors.py (rc 0, ids file complete) and timing_summary.py --gate-mode stock-path --gate-vllm-seconds 600.
- Ran trace-analyst on the 4 empties. Asked Codex about bundle-side feasibility for M1/M2/M3 (ops/codex/ask-20261106T021410.md).
- Built screen bundle 31b-v005-p5c = v003 + thinking_budget 1024 only (dist/31b-v005.zip sha256
  e8fbcfdc5800d927e6f6e7522b98f252766c6f85a72dcf67adbcc3abc00344f3, pack PASS). Narrow review review-p5c-light is RUNNING.

## 4. Results (n=8 ids, k=1 per arm, cap 4.0, conc 1, 4x L4)
| metric | arm A 31b-v001-t4 | arm B 31b-v003-p5t4 | file |
|---|---|---|---|
| empty diffs | 4/8 | 4/8 (Wilson 95% 0.22-0.79) | results/trace_tool_errors_31b_v00{1,3}.json |
| discordant A-empty-only / B-empty-only | | 2 / 2 (sign test one-sided p=0.69, two-sided p=1.0) | same |
| write_outside_ws calls (tasks) | 8 (6) | **0 (0)** | same |
| edit_missing_param calls (tasks) | 19 (2) | **6 (1)** | same |
| tasks with first ok edit at call <= 12 | 3 | 3 | same |
| timeouts | 6 | 5 | results/kaggle_timing_31b_v00{1,3}.json |
| gate a / b (max stock-path s) / d (vLLM s) / e | PASS / 243.4 / 364 / 4 | PASS / 243.5 / 397 / 4 | same |
Per id (A bytes -> B bytes): fastapi_14258 513->508, fastapi_14851 0->0, rich_3063 0->0, rich_3067 0->655, rich_3454 657->657,
rich_3535 0->479, rich_3930 253->0, rich_3953 601->0. **Verdict per the rule: MECHANISM-ONLY (V yes, M yes, E no). No ship, no v004.**

Where the time goes (results/taxonomy-31b-v003-p5t4.json; Builder spot-checked per-turn token counts in the traces):
- None of the 4 empties called edit_file. Tool execution is under 1 s per task; about 100% of the 240 s is model generation at
  about 30 tok/s (4.5k-7.3k completion tokens per task). Capping test-command runtime would not help.
- rich_3063: two turns (~3.1k and ~2.3k tokens) took 155 s. rich_3953 found the file by call 6, then spent the window on repro and
  test reads. fastapi_14851: 22/40 calls repeat earlier reads, after history drops. rich_3930: broad exploration, then long turns.
- Per-turn max completion tokens in arm B: 903/1230/3092/547/908/4247/2829/1197. The bundle allows 4096 thinking tokens per turn,
  about 136 s at 30 tok/s, which is more than half the window.
Codex feasibility (file:line cited there): M1 (sub-agent with its own cap) NOT FEASIBLE; the schema forbids cap fields and analyzer
time and calls share the root budget. M3 (guarded submit_patch) NOT FEASIBLE, and none of the empties called submit_patch anyway.
M2 FEASIBLE only as a **model-invoked** skill: the harness passes no callback registry, so no bundle code can fire at call N.
get_status does expose remaining seconds and calls. thinking_budget is forwarded to vLLM as extra_body.thinking_token_budget
(adk_submission/resolvers/generation.py:446). Whether the scorer's vLLM enforces it is unverified; arm C's mechanism check measures it.

Dec 057 item 4: v000-v002 on both tracks carry an inherited FastAPI/docs_src hint in prompts/system.md, so their LB scores may
be tilted toward FastAPI-like tasks. 31b-v002 (dec 055) is untouched; v003 and v005 carry the generic line instead.
Also relevant to dec 055: 31b-v002 runs at cap 3.5 with thinking_budget 4096. The arm-A/B evidence suggests about half its tasks may
end empty at 4.0 min, and likely more at 3.5. That fits "expect a weak LB score"; I am not proposing to change dec 055.

## 5. Options
- A. Arm C now (Addendum C, ~2.1 h quota that expires at 00:00Z anyway; $0 GCP). Lowest build risk and a direct test of the
  dominant time sink. Risk: vLLM may ignore the field (then NOT-ENFORCED, still informative for both tracks), and a smaller thinking
  budget may lower fix quality, which this screen cannot see.
- B. A + Addendum B (M2 skill, Codex-built, ~2.1 h more) if it is ready and reviewed in time. Two screens fit in the 20.58 h left.
  Risk: Codex's strongest objection is that the same model must choose to invoke it. It is likely to miss the pre-registered
  empty-on-timeout = 0 bar.
- C. Stop screens. Wait for the e4b-v002 LB and the dec 055 31b-v002 LB, then spend next week's quota on the 33-dev pass-rate design.
  This loses this week's leftover quota.

## 6. Recommendation
A now, and B only if the M2 build plus review is clean by about 18:00Z (otherwise drop B). Separately, I'd still fix the /tmp
contradiction and the hint line for the next candidate, since dec 056 calls that a real bug, and fold it in with whatever passes.
Request: `KAGGLE QUOTA ~2.1 h L4x4 for plan 005 arm C (31b-v005-p5c, dist/31b-v005.zip sha256=e8fbcfdc5800d927e6f6e7522b98f252766c6f85a72dcf67adbcc3abc00344f3)`,
plus optionally `~2.1 h for Addendum B M2`. No SUBMIT, no GPU $, no HOLDOUT.
