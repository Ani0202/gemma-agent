# STATE: snapshot 2026-11-05 17:51Z (cycle 61, Phase 0). Rewrite each cycle, ≤80 lines (dec 017).
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

## Re-grounding check (EVERY cycle, dec 021 item 1e)
- `bin/job status memguard` must say running; if not: `bin/job start memguard -- bin/memguard`. Check `tail ops/logs/memguard.log` for KILL lines. No heavy job unless memguard runs.
- Until bin-job-hardening.diff is applied by Aniket: at most ONE heavy job at a time on this VM (waiters/memguard/codex-ask/review exempt).

## Running jobs (17:51Z)
- memguard (pid 7933, started 17:48Z): running, 0 kills; verified it sets oom_score_adj=1000 on bin/job targets. Test eval/tests/test_memguard.py 2/2 pass (job memguard-test).
- review-memguard: codex-review of bin/memguard + ops/patches/bin-job-hardening.diff.
- codex-sandbox-limits: codex-build of dec 020 item 6 (per-task group, 4 GiB tree-RSS kill, orphan tracking, peak RSS per task, GOLD_CONCURRENCY), branch codex/sandbox-limits.
- ask-setup-210s: codex-ask on dec 022 items 2a/2b/2d (the 210 s setup: intrinsic or a kernel artifact).
- scout (subagent): dec 022 item 2c public caps/setup -> ops/scout/2026-11-05-timing-caps.md.
- Killed (dec 020 item 4): gold-rerun-b5, e4b-timing-wait3 (both already dead after the reboot).

## OOM incident (dec 020/021)
- Root cause from runs/gold-null2: null-phase rows 22 rich_4006 (327 s), 38 rich_3480 (2683 s), 39 rich_3772 (2867 s) hit exit 124. The harness executor already uses start_new_session+killpg (adk_eval_core subprocess_sandbox.py:57), so the orphan theory is weaker; the leading suspect is unbounded memory in a null-patch rich test with no per-sandbox memory cap (none locally; the scorer has 4 GiB). Unproven: no RSS was logged. The codex-sandbox-limits fix covers both.
- bin/job patch for Aniket: ops/patches/bin-job-hardening.diff (setsid pgid kill + survivor report, scope stop, oom_score_adj 1000, MemAvailable<5G refusal unless *-light). Smoke-tested on a scratch copy: group kill, no survivors. Awaiting codex-review, then to the Director.
- No exit-137 events since the reboot.

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

## Open decisions / instructions in force
- Dec 022 (report 003): interim timing rule = (cap + max measured setup) x125 + 30 <= 660. Item 2 setup root-cause IN PROGRESS (ask-setup-210s + scout). Item 3: v001 (cap 1.4) may be built/packed now, but the re-time can't be pushed until item 2 concludes; ONE Kaggle timing run. Item 4 (truncation-safe diff, patch hygiene, tool-output trimming) to start. Item 5: no 31B timing yet. Report 004 next.
- Dec 020 item 7 / dec 019 item 2: EV-1 (typing_inspection 0.4.5 eval-only, NOT yet implemented) + gold/null on 48 clean, on a cpu8 VM via bin/gpu (<=$3, <=3 h), after the sandbox-limits merge. Dec 019 items 3-4 (per-repo rates; collection-error note) to fold in.

## Next 3
1. Review/merge codex/sandbox-limits (own review + codex-review); act on review-memguard findings; send the patch path to the Director.
2. Dec 022 item 2: write results/kaggle_timing_e4b_v000_setup_breakdown.json + RULES_FINDINGS from ask-setup-210s/scout, then codex-ask the adversarial take (2d). Meanwhile build+pack e4b-v001 (cap 1.4).
3. EV-1 implementation, then the cpu8 gold+null run; then item 4 levers and report 004.
