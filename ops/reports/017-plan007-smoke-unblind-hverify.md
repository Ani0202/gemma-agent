# 017: plan-007 smoke unblinded; 1 H-VERIFY that comes from a classifier assumption, not a kernel defect

## 1. Question for the Director
Under the governing d4cdf0f0 classifier, smoke row rich_3063 is **H-VERIFY** (`verify:contradictory_failure_evidence`). The patch was empty and the stock verifier returned exit_code 1. Plan 007 l.89 assumed an empty patch would give exit_code null or -1. There's no kernel defect to fix, and dec 067 rules out a rev 6. Please confirm option A: no rerun, the row counts as FAIL in the primary (stock resolved=False), and it's footnoted. Not urgent: main runs until about 14:10Z.

## 2. Pre-registration
Unchanged from eval/plans/007.md (Smoke/chunks/reruns + Metrics). Decision rule: an H row reruns only after a documented defect fix (journal, commit, codex review). There are no reruns for AGENT outcomes. The primary numerator is stock resolved=True for every row, H rows included.

## 3. What I did (main 046e96e + this commit; kernel commit 078f4ea)
- Smoke (gemma-31b-passrate v1) downloaded 08:06:15Z and sealed: SEAL.sha256 85fb5648...674f68, sha256sum -c OK, timing.jsonl 76bd2483...c4bd7.
  Quota after smoke: 17.25 h (+1.23).
- Blind gate under a208a023: **HOLD** (vLLM up, 3/3 rows, parse ok, 0 H; walls 172.2 / 802.9 / 707.7 s, seed_max 803).
- **Main pushed 08:08:22Z**: gemma-31b-passrate v2, ids 4..33 (eval/plans/007-main-ids.txt sha ce249018...df73), --seed-max 803,
  KERNEL_BUDGET 21000 s, pushed from a detached worktree at 078f4ea. The bundle and ids are byte-identical to HEAD. Expected week total ~29.2 h (<= 29.5).
  The push came well before the 16:55Z deadline. The waiter passrate-31b-v009-main-wait-light seals the outputs.
- Unblinded 08:08:43Z (after the main push, per dec 067 item 3): classified under d4cdf0f0 (governing) and a208a023 (transparency).

## 4. Results (n=3 smoke rows, k=1; these are the first 3 arm-1 rows)
| row | stock resolved | d4cdf0f0 (governing) | a208a023 |
|---|---|---|---|
| rich_3063 | False | **H-VERIFY** contradictory_failure_evidence | NO_PATCH |
| rich_3953 | False | PYTEST_1 (known_diag record_chain) | PYTEST_1 (known_diag) |
| fastapi_14372 | False | PYTEST_2_5 (known_diag record_chain) | PYTEST_2_5 (known_diag) |

Primary so far: 0/3 resolved (Wilson 95% CI 0-56%). That's too few rows to read anything into. Files: results/plan007_arm1_smoke_d4cdf0f0.json,
results/plan007_arm1_smoke_a208a023.json (both carry the input sha 76bd2483...).
rich_3063 evidence (timing.jsonl): patch_submitted true, verified_patch_bytes 0, empty_patch true, exit_code 1, no result_error,
no patch-apply message, verification 24.3 s, agent clock 128 s of 210 s, timeout not fired, llm_turns 40, 39 tool calls (36 run_command).
The verifier applied the test patch to an unpatched tree and pytest failed, so it exited 1. That's legitimate and consistent with resolved=False.
The defect is the rev-5 rule `verified_patch_bytes == 0 and exit_code not in (None, -1) -> H-VERIFY` (classify_rows.py:239, plan l.89).
**Expect the same H-VERIFY for every empty-patch row in main**, which inflates the H count and shrinks the sensitivity-line n.

## 5. Options
- **A (recommended):** no rerun, since a rerun can't change anything and there's no defect to fix. The primary is unaffected. In the report I'd list such rows
  as "H-VERIFY(empty-patch, exit 1)", give the sensitivity line twice (excluding all H, and excluding H other than this
  sub-case), and show the a208a023 counts alongside. The classifier stays frozen. Cost: one footnote.
- B: a rev 6 that treats empty-patch + exit 1 as NO_PATCH. This contradicts dec 064/067 (no rev 6), and it's a post-hoc edit after unblinding.
- C: rerun the H rows anyway. That burns quota on a deterministic outcome and doesn't change the primary.

## 6. Recommendation
A. No requests. Dec 055 31b-v002 submit at 2026-11-07T00:00Z is still first.
