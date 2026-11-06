# Report 016: plan-007 classifier rev-5 re-freeze (d4cdf0f0) + blind-gate fold

## 1. Question for the Director
Please give the Director note that approves the rev-5 re-freeze `eval/kaggle/classify_rows.py`
sha256=d4cdf0f012659c685789add3b8e5687362ba01673344bdc1f1bad97f81d8ae5e (code commit bb0131f), so it can classify the
smoke and main rows offline. Also please confirm that the main run (ids 4..33) uses the smoke's kernel commit 078f4ea.

## 2. Pre-registration
From dec 064 item 3 and dec 066: fold every item in the exhaustive rev-5 review (codex 20261106T071306: 19 BLOCKING + 2 false-H)
into ONE re-freeze. There is no rev-6 review; residuals go to the Director along with the arm-F exposure. The decision rule is that
the freeze is usable only if every listed reproduction yields H (or the stated non-H for the false-H/legit shapes), the full
eval/tests suite passes, and the arm-F rows don't change. Blind gate (dec 066 item 1): ONE codex pass. Fold only the BLOCKING items
that leak pass/fail/resolved/patch or miscount H/mechanics, run its tests, and use it.

## 3. What I did
- Rev-5 fold: codex-build branch `codex/plan007-rev5-fold` (bb0131f), merged as 19a6de0. Rules + `test_rev5_*` tests for items 1-19 and false-H 1-2.
  Pinned copy: `eval/plan007_pinned/classify_rows_d4cdf0f0.py`. The plan-007 freeze line has been added (eval/plans/007.md, "RE-FROZEN rev 5").
- **Process defect:** the codex worktree could not see the review file (its copy was empty there), so codex's tests are its own
  constructions, not the review's exact rows. To cover that gap, I re-ran the review's exact `B | overrides` reproducers (and 9
  legitimate non-H shapes) against the merged classifier: `eval/plan007_rev5_repro.py` -> `results/plan007_rev5_repro.txt`.
- Blind gate (`eval/plan007_blind_gate.py`): folded all 4 BLOCKING items from review 20261106T072941:
  (1) EXPECTED_ROWS is now required and must be ≥1; (2) instance_ids are regex-validated, and an invalid id prints `?` and the gate
  FAILs; (3) any exception -> a bare `mechanical_gate FAIL` with no traceback, and non-finite or missing totals FAIL;
  (4) stdout is limited to the whitelist (vllm_up, rows, rows_parse, wall, max_total/seed_max_ceil, h_count, gate), with no
  sha/dup/exception counts or parse diagnostics. Exit codes: 0 HOLD, 3 FAIL, 2 usage/sha. New tests: `eval/tests/test_plan007_blind_gate.py`.

## 4. Results
| Check | n | Result | File |
|---|---|---|---|
| Review 071306 BLOCKING reproducers (direct classify) | 16 (1-14, 4b, 19) | 16/16 H | results/plan007_rev5_repro.txt |
| Review CLI reproducers (15a, 15b, 16, 17, 18) | 5 | 4 rc=1 reject, 18 -> H-ROW (kernel_void) | results/plan007_rev5_repro.txt |
| False-H 1-2 (setup.py / workspace_editable not-run) | 2 | 2/2 non-H (EXIT0_UNRESOLVED) | results/plan007_rev5_repro.txt |
| Legit shapes (PASS, EXIT0_UNRESOLVED, 124, NO_PATCH null/-1, PATCH_APPLY null/-1, JUnit exit 0, agent-end) | 9 | 9/9 non-H | results/plan007_rev5_repro.txt |
| Legit completed prefix without `_done`; full run with `_done` | 2 | rc 0, PASS, 0 H | (ad-hoc check; same shapes as test_rev5_17) |
| eval/tests full suite | 1156 | 1156 passed / 4 skipped | (run 07:35Z) |
| Arm-F exposure (31b-v008 timing, 8 rows) | 8 | 8 H-ROW (all r1 schema guard), known_diag 7, 0 H-SETUP, kernel_void false; unchanged vs a208a023 | results/plan007_classifier_armF_check.json |
| Blind gate tests | 21 | 21 passed | eval/tests/test_plan007_blind_gate.py |
| Blind gate on arm F (sanity, expected 8) | 8 | rows 8, h_count 8, FAIL (matches review) | ad-hoc run |

This is not a pass-rate experiment, so there are no Wilson CIs or discordant pairs.

## Residuals (no rev-6, per dec 064 item 3)
1. CLOSED this cycle: the review's exact rows are now in pytest (eval/tests/test_plan007_rev5_repro.py runs the repro script and
   asserts 32/32 OK). Full suite: 1178 passed / 4 skipped (07:37Z), which includes the 21 blind-gate tests.
2. Blind gate NON-BLOCKING: the pinned classifiers import `agent_timing.AGENT_OUTCOMES` from HEAD. agent_timing.py was last
   changed in 63f6866 and hasn't changed since the a208a023 freeze, so it doesn't drift today, but it isn't hash-pinned.
3. Kernel path: `git diff 078f4ea HEAD -- eval/kaggle bin` touches only classify_rows.py, which the kernel doesn't import.
   Under dec 065, the main run is NOT forced onto the pre-fold commit, but using 078f4ea keeps smoke and main on identical code.

## 5. Options
A. Approve the d4cdf0f0 freeze. Smoke/main blind gate stays on a208a023 (dec 065). After the main run, rows are classified under
   d4cdf0f0 for the report, and a208a023 counts are reported alongside. Main uses kernel commit 078f4ea.
B. Reject and keep a208a023 for everything. Rev-5's 19 fail-open paths would stay open in the final classification.

## 6. Recommendation
**A**: approve the d4cdf0f0 freeze (the repro rows are already in pytest). Main ids 4..33 run on 078f4ea once
the smoke blind gate HOLDs. They'll be sized to week ≤29.5 h and to end by 23:30Z, with the dec 055 submit at 00:00Z first.
No SUBMIT, GPU or HOLDOUT requests.
