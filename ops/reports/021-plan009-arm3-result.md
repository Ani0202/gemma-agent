# Report 021: plan 009 arm 3 (31b-v012-p9a, root thinking 4096) result

## 1. Question for the Director
The pre-registered rule returns **ON-BETTER-VETOED**. Resolved went 4 -> **10/33** (ON-only 6, OFF-only 0, sign p = 0.031), but timeouts
(21 vs 4, limit base + 2 = 6) and empties (18 vs 12, limit base + 3 = 15) fail. Under the rule we keep OFF. Do you (a) keep the rule's
verdict and v009 for Nov 8, (b) also schedule v012 for its own scored submit (dec 087 item 3, Nov 10), or (c) swap Nov 8 to v012?

## 2. Pre-registration (eval/plans/009.md l.98-110, written before data; unchanged)
- ON-ADOPT: ON-only > OFF-only with p < 0.2, AND arm-3 timeouts <= base + 2, AND TIMING passes, AND every SAFETY metric met.
- **ON-BETTER-VETOED**: ON ahead with p < 0.2 but timeouts, TIMING or SAFETY fail -> keep OFF; report with timing data as a candidate
  cap/budget follow-up (no automatic further arm).
- SAFETY: test edits 0; stray 0 rows; total wall p90 <= 1.10 x base; empties <= base + 3; submitted-without-test <= base + 3.
- BASE = arm 1 (v009), because arm 2 was NOT SHIP-ELIGIBLE (dec 080). Label: smoke shows thinking ACTIVE, not that the 4096 budget is enforced.
- Power caveat (pre-stated): k=1, n=33; p < 0.05 needs 6 of 6 one way. **That is what we observed.**

## 3. What I did
gemma-31b-passrate v5 (main, 31 ids = arm-1 ids 3..33) pushed 06:27:20Z from 47243d1, ONE session, COMPLETE ~11:19Z (kernel t = 17467 s
of the 30000 s budget). Smoke v4 supplies the other 2 ids (results/plan009_arm3_smoke.json PASS). Outputs sealed on download
(runs/31b-v012-p9a-main/SEAL.sha256, 200 lines, sha256 c0d01bb4...a1d4, `sha256sum -c` OK). Quota 11.89 -> **21.59 h** (+9.70;
ops/budget/kaggle.md). Frozen classifiers: d4cdf0f0 (governing) and a208a023 agree (0 H rows, same classes):
results/plan009_arm3_main_{d4cdf0f0,a208a023}.json. Metrics: eval/plan008_metrics.py arm3 arm1 (codex s81b CLEAN pre-data) ->
**results/plan009_arm3_vs_arm1.json** (inventory 33/33 both arms, order matches, IDENTITY zip/agent_yaml/TRANSPORT 203e542b OK for smoke+main).

## 4. Results (n = 33 dev, k = 1, same ids/order/seed-max; ON = arm 3 v012, OFF = arm 1 v009)
| metric | arm 1 (OFF) | arm 3 (ON) | paired ON-only / OFF-only / both | rule | met |
|---|---|---|---|---|---|
| **resolved** | 4/33 = 12.1% (W 4.8-27.3) | **10/33 = 30.3% (W 17.4-47.3)** | **6 / 0**, sign p = 0.031 | ON > OFF, p < 0.2 | YES |
| **timeouts** | 4 | **21** | 17 / 0 / 4 | <= 6 | **NO** |
| **empty patch** | 12 | **18** | 14 / 8 / 4 | <= 15 | **NO** |
| TIMING (agent <= 220 s, final <= 30 s) | pass | pass, 0 violations | | all rows | yes |
| total wall p90 | 796.8 s | 844.7 s | | <= 876.5 | yes |
| test-file edits | 0 | 0 | | 0 | yes |
| stray files (governing) | 0 | 0 | | 0 | yes |
| submitted without test (D73.5) | 23 (plan 007 observed def.) | 7 | | <= 26 | yes |
| H rows (governing) | 7 (sensitivity 4/26) | 0 | | VALIDITY < 5 for arm 3 | VALID |
All numbers: results/plan009_arm3_vs_arm1.json (`primary`, `arms.*`, `decision_inputs`).

ON-only resolved: rich_3454, rich_2943, rich_3043 (resolved despite timeout), rich_2725, rich_3518 (an arm-1 H row), rich_3718.
Excluding the 7 arm-1 H rows doesn't change the direction (arm-1 sensitivity 4/26; arm 3 has 0 H).

Descriptive (same file, `arms.*.descriptive`):
- Thinking: 33/33 tasks have blocks, 628 blocks, 421,685 chars (arm 1: 0).
- Repeat loops (MECH 2, max run >= 5): **1/33** (max 8, 10 repeated) vs arm 1 **17/33** (max 38, 366 repeated).
- LLM calls p50/p90: 17 / 33.8 vs 36 / 42.8. Tool calls: 16 / 32.8 vs 35 / 41.8.
- Agent clock (timing.jsonl, both arms' smoke+main): mean 183.6 s, p50 210.0 vs mean 132.5 s, p50 128.4. The model makes half as
  many calls, but each is slower, so it runs into the 3.5-min cap on 21/33 tasks. 18 of the 21 timeouts end with an empty diff.
- Per repo: rich 10/27 vs 4/27; fastapi 0/6 vs 0/6. Unscreened 25: 8/25 vs 3/25.
- Stray, literal (S81.3, listed separately): arm 3 has 1 row (fastapi_15661 scripts/release.py, exempted: gold dir scripts). Arm 2's amended
  counts (report 019 base): governing 0, literal 1 (same id, exempted). Arm 1: 0 / 0.
- ENV drift flagged by the script: setup wall p50/p90 215/640 s vs 638/640 s; verification p50 0 vs 425 s (empty diffs skip
  verification). Docker/vLLM/ADK versions are unrecorded in both arms. The ENV CONTROL caveat (dec 069) still applies to every arm-1 citation.

Scorer-runtime evidence (descriptive, not a gate). v002 scored COMPLETE in <= 9.006 h at cap 3.5 (results/lb_31b_v002.json). Its parent,
v001-t4, timed out on **6/8** tasks at cap 4.0, with mean agent clock 218/240 s (results/kaggle_timing_31b_v001.json). So v002 very
likely ran near cap-bound too, and v012's 184/210 s mean is no more time-hungry per task. Thinking 1024 (v005): 3/8 timeouts, mean
200 s. Thinking 0 (v006): 2/8, mean 116 s (results/kaggle_timing_31b_v00{5,6}.json). Caveat: n = 8, different ids, cap 4.0.
That is inference, not a measurement of v012 on the scorer.

## 5. Options
- **(a) Rule as written:** keep OFF. Nov 8 = v009 (authorized). v012 is recorded as a cap/budget follow-up candidate. This costs nothing
  now, but v009 (4/33) is unlikely to be a final if v012's gain is real, so the Nov 8 slot buys little ship-relevant information.
- **(b) Keep v009 on Nov 8 and add a v012 scored submit on Nov 10** (first slot after e4b-v002h, per dec 087 item 3). v012 needs its own
  COMPLETE score anyway (checker: INELIGIBLE vs v002). That score directly tests what the veto metrics stand in for (runtime under the
  real scorer). Needs a Gate-2 review of v012 (CPU, I can start it now).
- **(c) Swap Nov 8 to v012.** This puts the leading candidate's runtime and score on the LB 2 days earlier and leaves slack before Nov 29.
  It needs a new authorization and a v012 Gate-2 review before 00:00Z. The risk is that v012 runs over 12 h and returns no score. The
  evidence above makes that unlikely but doesn't rule it out. Also, v009's waived empty-diff-on-timeout BLOCKING (dec 084) bites harder
  here: 18 empties are mostly timeouts.
- Follow-up arm (any option): thinking 1024-2048 at cap 3.5 to cut timeouts and keep the loop reduction. It needs >= ~10 h quota, and
  8.41 h remains this week, so the earliest is the week of Nov 14. Or the dec 081 item-5 tool-level empty-patch lever on top of v012.

## 6. Recommendation
**(b)**, or (c) if you accept the runtime risk for a 2-day gain. p = 0.031 on 6/0 is the strongest paired result we have, and
the vetoed metrics are proxies. The real scorer settles them for one slot. Requests: none now. If (b) or (c), I'll run the v012 Gate-2
codex review (review-31b-v012-submit-light) and draft its checklist. SUBMIT authorization stays yours:
`SUBMIT dist/31b-v012.zip sha256=78a8fd30389ec3acf58b44bc8743d750b496041f5c8d2b35790f0d913130ede5 track=31b` (for (b): Nov 10; for (c): Nov 8).
