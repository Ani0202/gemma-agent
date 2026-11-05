# Report 002: B5 gold rerun changes the pass set (fastapi loses typing_inspection)

## 1. Question for the Director
Under the B5 shared, scorer-faithful environment, 8 of the 9 clean fastapi tasks fail even with the gold patch. Should splits v2
stay frozen, with fastapi run under a documented eval-only env deviation, or should we re-freeze as v3 (clean 40, almost all rich)?

## 2. Pre-registration (STATE cycle 57, journal 15:59Z)
B5 rerun of gold calibration (all tasks) plus the null control, in the shared `setup_scorer_env`. Rule: an identical pass set and an
unchanged null control mean splits v2 stand. Any change triggers a short report to the Director.

## 3. What I did (repo 4b87b96 + this cycle)
- Job gold-rerun-b5 produced runs/gold-local2 (sandbox=bwrap, `_host_env.pth` removed). The null-control phase (runs/gold-null2)
  is still running (33/52 at the time of writing).
- Compared it with results/gold_calibration_per_task.jsonl, giving results/gold_rerun_b5_compare.json.
- Root cause: reran fastapi_14258 alone with an exec-logging hook (scratchpad only, no repo change). pytest exits 2 at collection:
  `import pydantic` raises `ModuleNotFoundError: typing_inspection`. The wheelhouse injects pydantic 2.13.4, which needs
  typing_inspection, but the wheelhouse has no typing_inspection wheel. It is also missing from the pip line in Dockerfile.public
  and from our pyimg mirror. sandbox/setup.py --fast-path doesn't add it either. The old 52/77 run got typing_inspection 0.4.5
  from our harness venv through the `_host_env.pth` leak that B5 removed.

## 4. Results
| set | n | old pass | new pass | old-only | new-only |
|---|---|---|---|---|---|
| all tasks | 129 | 52 | 43 | 9 (all fastapi) | 0 |
| rich / requests / httpx | – | unchanged | unchanged | 0 | 0 |
| clean v2 (48) | 48 | 48 | 40 | 8 | 0 |
| dev v2 (33) | 33 | 33 | 28 | 5 | 0 |
| holdout v2 (15) | 15 | 15 | 12 | 3 | 0 |
The one remaining clean fastapi pass is fastapi_15661. Source: results/gold_rerun_b5_compare.json. This is a deterministic gold
check (k=1), not sampled, so no CI applies. The Kaggle cross-check runs/gold-diag4 gives 3/77. The Kaggle env is not
scorer-faithful (it has typing_inspection, but fastapi fails on inline_snapshot), so I'm dropping that line of work as redundant.

Caveat: Dockerfile.public may not be the exact scorer image. If the real image has typing_inspection, the old pass set is right.
I can't verify this offline.

## 5. Options
A. **Re-freeze splits v3 (scorer-faithful):** clean 40 = rich 39 + fastapi 1. It's honest about what the scorer can resolve, but
   LORO becomes impossible, and dev turns into a single repo, which increases the risk of overfitting to rich.
B. **Keep splits v2 frozen. Add typing_inspection 0.4.5 to the eval sandbox only, as a logged, eval-only deviation.** Report a
   scorer-faithful sub-score (fastapi excluded) next to every result. This keeps two repos for generalization checks with no
   protocol churn. Downside: our fastapi numbers may overstate what the scorer gives us.
C. B, plus one scout pass (a dec-allowed daily use) on public discussion for "typing_inspection" or fastapi import failures. That
   would tell us whether the real scorer has this gap. If it does, switch to A for ship decisions.

## 6. Recommendation
**C.** It's cheap and keeps the second repo for generalization. Ship decisions would rely on the faithful sub-score until the
scorer question is settled. Pending your decision I'll proceed with no eval-protocol change. The null-control result follows by
FYI when gold-null2 finishes. No GPU or holdout requests.
