# Report 018: plan 007 arm 1 (31b-v009-p7a1, 33 dev, k=1) result + H-count validity ruling

## 1. Question for the Director
Under the literal pre-registered rule, arm 1 is **INVALID** (7 H rows ≥ 5 of 33). But all 7 are the same empty-patch
H-VERIFY shape as smoke rich_3063, the case dec 068 ruled a classifier false positive. Addendum B's exact-reasons clause
misses the 6 main rows only because they also carry the `known_diag:record_chain` flag, which the pre-reg calls
"a flag, not an error, never gating". Can arm 1 count as VALID, with 4/33 as the arm-1 baseline (option A)?

## 2. Pre-registration (eval/plans/007.md, e547980; Addenda B/B.1 ea9c064, both committed before the main download)
Arm 1 is a measurement only, with no ship decision. PRIMARY = stock resolved=True / 33, Wilson 95%. Arm 1 is INVALID iff
H rows ≥ 5 of 33. Report layout a-e plus an empty-patch headline (Addendum B). Governing classifier d4cdf0f0; a208a023 is counted alongside.

## 3. What I did
- MAIN kernel gemma-31b-passrate v2 (code 078f4ea; ids 4..33; seed-max 803; budget 21000 s) finished COMPLETE at 13:23Z.
  Outputs were downloaded and sealed: runs/31b-v009-p7a1-main/SEAL.sha256 sha256=cd3ed918…2a5e (194 entries, `sha256sum -c` OK);
  timing.jsonl 63d8688d…8909. All 30 ids ran, so there is no chunk 2.
- Blind gate under d4cdf0f0: vLLM up, 30/30 rows, parse OK, max total 855.5 s, **h_count 6 → mechanical_gate FAIL**.
- I classified with the pinned d4cdf0f0 and a208a023. The summary script is eval/plan007_arm1_summary.py (commit 29e140e,
  sha c127dd31…). It calls assert_paired on every row and checks the fixed id order. **Its codex review
  (codex-review-arm1summary-light) is still running, so treat these numbers as provisional until it comes back clean.**
- Header facts: kernel 078f4ea (dec 065 deviation: ran before the rev-5 re-freeze); classifier d4cdf0f0;
  agent_timing.py 0dc1c972…dc96. Caveat: env agreement with the local gold calibration is unmeasured in the kernel path.

## 4. Results (results/plan007_arm1_summary.json; class files results/plan007_arm1_{smoke,main}_{d4cdf0f0,a208a023}.json)
| line | n | k | rate | Wilson 95% |
|---|---|---|---|---|
| (a) PRIMARY, stock resolved, all rows | 33 | 4 | 12.1% | 4.8–27.3% |
| (a) rich | 27 | 4 | 14.8% | 5.9–32.5% |
| (a) fastapi | 6 | 0 | 0% | 0–39.0% |
| (c) sens. excl. all H | 26 | 4 | 15.4% | 6.2–33.5% |
| (d) sens. excl. H except H-VERIFY(empty-patch) [literal predicate: rich_3063 only] | 27 | 4 | 14.8% | 5.9–32.5% |
| HEADLINE empty-patch rate (verified_patch_bytes==0) | 33 | 12 | 36.4% | 22.2–53.4% |

- (b) d4cdf0f0: H-VERIFY 7 (rich_3063 smoke; fastapi_14258, rich_3521, fastapi_14851, rich_3675, rich_3518, rich_3052 main);
  agent PASS 4 / PYTEST_1 13 / PYTEST_2_5 4 / NO_PATCH 5; known_diag 27.
- (e) a208a023: 0 H; PASS 4 / PYTEST_1 12 / PYTEST_2_5 3 / NO_PATCH 11 (main only; smoke a208a023 is in the smoke file).
- Every H row has verified_patch_bytes 0, exit 1 or 2, resolved False, no errors, and patch_submitted True. Apart from the
  extra known_diag reason, each one matches the Addendum B predicate. None of them is a kernel defect.
- Empty patches: 12 rows, 2 timeouts and 10 non-timeouts. **7 of the 12 called submit_patch with an empty diff**; those are
  exactly the 7 H rows. 5 of those 7 had 0 edit_file calls (mostly read_file, 33–38 calls), and 2 had 2 or 11 edits.
  3 more rows (rich_3454, rich_2943, rich_3718) hit the 50-turn limit with 22–40 edit_file calls and no diff, which looks like
  the edit-failure loop. Per-row turns and tool mix are in the JSON.
- Secondary: timeouts 4; test-file edits 0; stray files 0; agent clock max 210.0 s (= cap 3.5, enforced); agent wall
  p50/p90 336/415 s; verification p50/p90 425/426 s; total p50/p90/max 735/797/856 s; llm_turns p50/p90 36/43.
- No paired comparison: there is no arm 2 yet. This is the baseline.
- Quota: Kaggle GPU 27.66/30 h used (+10.41 for main), 2.34 h left, resets 11-07T00:00Z (ops/budget/kaggle.md).

## 5. Options
- **A (recommended): VALID with a documented ruling.** Treat the 6 main rows as H-VERIFY(empty-patch) in substance: they
  differ only by the non-gating known_diag flag. Then H that matters = 0 and the primary is 4/33. No rerun, because these
  are agent outcomes and a rerun would give the same rows. Cost: one post-hoc reading of the predicate, which the report
  will state openly (literal verdict INVALID, ruled VALID).
- B: Literal INVALID. No baseline exists, and arm 2 has nothing to pair against unless arm 1 is rerun after the reset
  (about 12 h of quota). Because the classifier is frozen, the rerun would very likely flag the same shape again.
- C: VALID only for the descriptive lines (empty-patch rate, timing, tool mix). Withhold the primary as a baseline and
  pre-register a fixed arm before arm 2.

## 6. Recommendation
**A.** The larger signal is that **36% of rows end with an empty diff, and 7/33 actively submit an empty patch.** That makes
lever 1 (always yield a non-empty source diff) the next arm, ahead of thinking on/off. Proposal, to be pre-registered and
reviewed by codex before any GPU use: a bundle-level guard so that submit_patch on an empty diff returns an instruction to
edit first, plus the edit-failure loop fix (short anchors or write_file). These are bundle byte changes, so they form a new arm.
No GPU request today; 2.34 h are left this week. The dec 055 31b-v002 submit at 11-07T00:00Z is unaffected and stays first.
