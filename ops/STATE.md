# STATE: snapshot 2026-11-05 ~15:25Z (cycle 52, Phase 0). Rewrite each cycle, ≤80 lines (dec 017).
Per-cycle history: ops/journal.md; pre-cycle-51 STATE verbatim: ops/history/STATE-archive.md.
Builder on Opus (dec 010: local-first, two-strike).

## Best bundles (none validated; runtime budget still unverified, codex BLOCKING)
- 31b: dist/31b-v000.zip sha256=4a23e14a1aae077161cb137b5ff72afe91ee2acb1d1fdbaf2e322abb6efae161 (repo a12f0b7; static+codex static OK)
- e4b: dist/e4b-v000.zip sha256=cc647bfb28bc6d2db0e3ec816df084f23a91230786d8fea177e2d63d2a6940e2 (same)
- No local pass-rate scores yet (eval runner numbers unreliable until eval-runner-fix is merged).

## Eval data
- Splits v2 FROZEN: clean 48 (rich 39, fastapi 9), dev 33, holdout 15; holdout uses = 0. Hashes: eval/splits/MANIFEST.json.
- requests/httpx dropped (wheel shadowing = scorer property, dec 014). Gold v2 files in results/ (gold_calibration_*, gold_failure_causes).

## Running jobs
- e4b-timing-wait3: Kaggle aniket0202/gemma-e4b-timing v3 (E4B v000, 8 dev ids eval/plans/001-timing-ids.txt, py3.12 image, machine_shape NvidiaL4, repo 178e273) -> runs/e4b-timing
  (v2 failed: got T4 x2 because 'NvidiaL4X4' isn't a valid shape. If v3 aborts with WrongAccelerator, NvidiaL4 = L4 x1: find the right shape name and ask the Director.)
- codex-eval-runner-fix: B1–B5 + N1–N3 from review ops/codex/review-20261105T145013.md (spec ops/codex/build-eval-runner-fix.spec)
- gold-diag4-wait: Kaggle cross-check only, redundant

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
- Router: review done; BLOCKING fixed in bin/.router.new (clear gated on tmux success). Swap DENIED by the permission system
  for the Builder; escalated to Director. Someone with permission runs: mv bin/.router.new bin/router &&
  tmux respawn-window -k -c ~/work/gemma -t gemma:router bin/router; then check ops/logs/router.log for the next delivery.

## On job finish
- e4b-timing-wait3: python3 eval/kaggle/timing_summary.py runs/e4b-timing/timing.jsonl results/kaggle_timing_e4b_v000.json;
  test-run share post-hoc from raw traces (exec-boundary, not FIFO-per-name); check header mcp_import_ok; fill ops/budget/kaggle.md actual hours.
- codex-eval-runner-fix: review diff, real-bwrap tests + stub E2E, confirm N2 (verification_timeout_seconds forwarded), codex-review, merge.
  Then rerun gold-local + gold-null in shared env (B5). Pre-registered: identical pass set + null control => splits v2 stand; any change => short report.

## Next 3
1. Router swap: waiting on Director/owner (permission denied to Builder).
2. e4b-timing results -> results/ + plan-001 p90 rule (parallel with 3).
3. eval-runner-fix review/merge -> gold rerun -> report 002 (first-submission candidate + LORO caveat).
