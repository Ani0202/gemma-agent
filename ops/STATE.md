# STATE: snapshot 2026-11-05 ~17:52Z (cycle 60, Phase 0). Rewrite each cycle, ≤80 lines (dec 017).
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
- NONE. VM OOM-stalled ~16:45Z, rebooted 17:30Z. gold-rerun-b5 (null phase died at 39/52) and e4b-timing-wait3 marked failed 255.
- Owner (mail 17:37Z): no local job until the Director decides on the OOM incident; don't rerun gold-rerun-b5. bin/job now caps jobs at 5G (exit 137).
- e4b-timing v3 COMPLETE: 4x L4 confirmed, output in runs/e4b-timing. Gate FAIL -> report 003.

## Quota / spend
- GCP $0 (project gemma-agent-839566; only l4x1 spot + cpu8 usable, dec 003). Owner policy: Kaggle first (dec 001).
- Kaggle GPU this week: 0.07 h used (v1+v2 failed fast, per `kaggle quota`); 3.48 quota-h used after v3 (~1.74 L4x4 h). Log: ops/budget/kaggle.md. Resets Sat 00:00Z.

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

## Timing facts (results/kaggle_timing_e4b_v000_setup.json)
- Harness sandbox setup ~210 s/task, outside max_time_minutes (the budget clock starts after setup); flat across repos.
- vLLM startup 5.39 min; verification ~410 s (excluded from the 12 h). Agent clock p90 144 s at cap 5.
- Corrected rule proposed: (cap + max setup) x125 + 30 <= 660 -> cap <= 1.51 min.

## Open decisions
- Report 003 (NEEDS_DECISION): corrected timing formula + e4b-v001 (cap 1.4) + Kaggle re-time without verification; OOM local-job policy (proposed prlimit --as=4GiB per sandbox).
- Dec 019 (approved B): EV-1 typing_inspection eval-only + gold/null on 48 clean under EV-1. Blocked on the OOM policy. Items 3-4 (per-repo rates; collection-error note in the taxonomy/levers) still to fold in.

## Next 3
1. On the 003 decision: build e4b-v001 (cap only), pack, codex-review, Kaggle re-time (8 fresh dev ids, no verification).
2. Add a prlimit 4 GiB wrapper to the local sandbox runner, then the EV-1 gold+null job (dec 019 item 2) under bin/job.
3. codex-ask: is the ~210 s base-tar setup a cache miss in our kernel or intrinsic? Then a first-submission report.
