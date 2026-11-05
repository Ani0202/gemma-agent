# STATE: snapshot 2026-11-05 ~16:55Z (cycle 59, Phase 0). Rewrite each cycle, ≤80 lines (dec 017).
Per-cycle history: ops/journal.md; pre-cycle-51 STATE verbatim: ops/history/STATE-archive.md.
Builder on Opus (dec 010: local-first, two-strike).

## Best bundles (none validated; runtime budget still unverified, codex BLOCKING)
- 31b: dist/31b-v000.zip sha256=4a23e14a1aae077161cb137b5ff72afe91ee2acb1d1fdbaf2e322abb6efae161 (repo a12f0b7; static+codex static OK)
- e4b: dist/e4b-v000.zip sha256=cc647bfb28bc6d2db0e3ec816df084f23a91230786d8fea177e2d63d2a6940e2 (same)
- No local pass-rate scores yet. eval-runner-fix MERGED to main 70c0d9f (codex review clean + N1 count-cap fix d13ceac; 421 pass, 3 skip).
  Test cmd: /home/ubuntu/gemma-local/venv/bin/python3 with pyimg cp3.13 site-packages appended to sys.path, pytest eval/tests.

## Eval data
- Splits v2 FROZEN: clean 48 (rich 39, fastapi 9), dev 33, holdout 15; holdout uses = 0. Hashes: eval/splits/MANIFEST.json.
- requests/httpx dropped (wheel shadowing = scorer property, dec 014). Gold v2 files in results/ (gold_calibration_*, gold_failure_causes).

## Running jobs
- e4b-timing-wait3: Kaggle aniket0202/gemma-e4b-timing v3 (E4B v000, 8 dev ids eval/plans/001-timing-ids.txt, py3.12 image, machine_shape NvidiaL4, repo 178e273) -> runs/e4b-timing
  (v2 failed: got T4 x2 because 'NvidiaL4X4' isn't a valid shape. If v3 aborts with WrongAccelerator, NvidiaL4 = L4 x1: find the right shape name and ask the Director.)
- gold-rerun-b5 (started 15:59Z): pre-registered B5 rerun in shared env -> runs/gold-local2 (all 77) then runs/gold-null2 (null patch, 52 ids).
  e4b-timing-wait3 was still RUNNING at 15:59Z (~40 min in, so no fast WrongAccelerator abort).
- gold-rerun-b5: gold phase DONE (43/129 vs 52; 9 fastapi lost, typing_inspection missing; report 002). Null phase -> runs/gold-null2 still running.
- gold-diag4-wait DONE: 3/77 on Kaggle (not scorer-faithful); line closed.

## Quota / spend
- GCP $0 (project gemma-agent-839566; only l4x1 spot + cpu8 usable, dec 003). Owner policy: Kaggle first (dec 001).
- Kaggle GPU this week: 0.07 h used (v1+v2 failed fast, per `kaggle quota`); v3 pending (est ≤3.2, max 7.0). Log: ops/budget/kaggle.md. Resets Sat 00:00Z.

## Live caveats
- LORO with only 2 repos (rich, fastapi) is weak; report 002 must say so (dec 014 item 3).
- Paper evidence due Nov 9 23:59Z (dec 007): schema-headed results/ files for gold calibration (done), Kaggle E4B timing (pending), failure taxonomy via trace-analyst once (pending). paper/ is the paper session's; don't edit.
- Director reminder due 2026-11-06T23:02Z: GCP quota re-request line to Aniket; keep until a decision marks it done.
- Any Kaggle GPU kernel must pin the starter docker_image (py3.12, cp312 wheelhouse).
- Hosted-LLM-API data question OPEN; no new third-party services.
- One pending Kaggle submission at a time; no partial credit on timeout (docs/RULES_FINDINGS.md).

## Dec 017 (context clears): in progress
- Done: CLAUDE.md top line; this STATE trim + archive.
- Router: swapped by Aniket 15:57Z (pid 2601754); VERIFIED router.log 'clear builder' 16:00:15Z before delivery. Done.
- Dec 018 policy: owner activity keeps precedence over the 2 h clear valve.

## On job finish
- e4b-timing-wait3: FIRST confirm from kernel log that the guard saw 4 L4 devices (dec 018). If it aborted as 1xL4, find the valid
  4xL4 shape string from the starter notebook or the Kaggle API and report it; don't retry blind. Log every push in kaggle.md. Then: python3 eval/kaggle/timing_summary.py runs/e4b-timing/timing.jsonl results/kaggle_timing_e4b_v000.json;
  test-run share post-hoc from raw traces (exec-boundary, not FIFO-per-name); check header mcp_import_ok; fill ops/budget/kaggle.md actual hours.
- gold-rerun-b5: compare pass set of runs/gold-local2 vs gold-local (52/77, results/gold_calibration_*) and null control vs results/gold_null_control.jsonl.
  Identical pass set + null control => splits v2 stand (journal it, write results file); any change => short report to Director.

## Open decision
- Report 002 (ops/reports/002-gold-rerun-b5-fastapi-env.md): splits v2 vs v3 after B5 showed that fastapi gold fails without
  typing_inspection (wheelhouse and Dockerfile.public both lack it). Recommended C: keep v2, add an eval-only typing_inspection,
  report a scorer-faithful sub-score, and do a scout check. No protocol change until decided.

## Next 3
1. When gold-null2 finishes: compare with results/gold_null_control.jsonl and send the Director an FYI addendum for report 002.
2. e4b-timing results -> results/ + plan-001 p90 rule.
3. After the dec on 002: first-submission candidate report (003) + LORO caveat.
