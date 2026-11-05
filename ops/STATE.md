# STATE: snapshot 2026-11-05 18:12Z (cycle 66, Phase 0). Rewrite each cycle, ≤80 lines (dec 017).
Per-cycle history: ops/journal.md; pre-cycle-51 STATE verbatim: ops/history/STATE-archive.md.
Builder on Opus (dec 010: local-first, two-strike).

## Best bundles (none validated; runtime budget still unverified, codex BLOCKING)
- 31b: dist/31b-v000.zip sha256=4a23e14a1aae077161cb137b5ff72afe91ee2acb1d1fdbaf2e322abb6efae161 (repo a12f0b7; static+codex static OK)
- e4b: dist/e4b-v000.zip sha256=cc647bfb28bc6d2db0e3ec816df084f23a91230786d8fea177e2d63d2a6940e2 (same)
- e4b-v001 (dec 022 item 3, cap 5 -> 1.4 only): dist/e4b-v001.zip sha256=f2ced9c97ee1447cb3a78c0ebf65f4ecaff90c84b18313645d5d043c62d277e9 (re-pack, comment fix only), codex-review clean (no BLOCKING); re-time HELD until item 2 concludes.
- No local pass-rate scores yet. eval-runner-fix MERGED to main 70c0d9f (codex review clean + N1 count-cap fix d13ceac; 421 pass, 3 skip).
  Test cmd: /home/ubuntu/gemma-local/venv/bin/python3 with pyimg cp3.13 site-packages appended to sys.path, pytest eval/tests.

## Eval data
- Splits v2 FROZEN: clean 48 (rich 39, fastapi 9), dev 33, holdout 15; holdout uses = 0. Hashes: eval/splits/MANIFEST.json.
- requests/httpx dropped (wheel shadowing = scorer property, dec 014). Gold v2 files in results/ (gold_calibration_*, gold_failure_causes).

## Re-grounding check (EVERY cycle, dec 021 item 1e + dec 023 item 1b)
- Linger check (dec 025): `loginctl show-user "$(id -un)" -p Linger --value` must be `yes`; if not, tell the Director. After the NEXT reboot, once: `systemctl --user list-units --type=service --state=running`, names only; report non-ours units to the Director, never inspect or touch them (may be Etho).
- Watchdog must be running: `bin/job status memguard` (old name, pid 7933) until the memguard-fix deploy, then `memguard-light`; if dead: `bin/job start memguard-light -- bin/memguard` (dec 024: always -light). Check `tail ops/logs/memguard.log` for KILL lines. No heavy job unless memguard runs.
- bin/job hardening is applied (b1eedd7); keep heavy jobs to one at a time until the Director relaxes this (waiters/memguard/codex exempt).

## Running jobs (18:12Z)
- memguard (old name, pid 7933): running, 0 kills. Replaced by memguard-light at the memguard-fix deploy.
- review-job-patch2-light, review-memguard-fix-light, codex-sandbox-limits2, codex-kernel-setup-fix.
- Done this cycle: pipfb2-light (plan 003), scout (ops/scout/2026-11-05-timing-caps.md; RULES_FINDINGS C1-C3).

## bin/job, memguard, owner patch (cycles 62-66)
- Linger=yes since ~18:05Z (dec 025): the scope path (MemoryMax=5G) is normal; Codex works under it.
- Owner patch v2 = ONE diff (dec 024 item 3): ops/patches/bin-job-fallback.diff (linger-gated scope, ulimit -d fallback, 6-field status with boot_id+starttime, GEMMA_JOB_ID marker, stale-boot refusal, trusted-pgid check, setsid escapes killed+reported, scope stop only if active). Smoke test ops/patches/bin-job-killtest.sh: 4/4 pass. v1 review clean; v2 review job review-job-patch2-light. Then mail the Director the path.
- memguard-fix: branch codex/memguard-fix (53c87da + my ddf9746: status parse >=3 fields for the v2 patch). 22 pass/1 skip. Review job review-memguard-fix-light. Merge only with no BLOCKING; deploy as memguard-light, start the new one BEFORE stopping old pid 7933 (dec 024 item 4).

## Dec 022 item 2: CONCLUDED "artifact" -> report 004 (NEEDS_DECISION)
- Plan 003 repro: one hung-index fallback pip = 103.4 s; 2 calls = 206.8 s vs Kaggle 207.4-210.8; verification 4 calls = 413 vs 410-412. results/plan003_pip_fallback_repro.json. Why Kaggle's offline install failed is unproven.
- Kernel fix: codex-build kernel-setup-fix (branch codex/kernel-setup-fix; spec ops/codex/build-kernel-setup-fix.spec). Needs my review + codex-review before any Kaggle push.
- Report 004 recommends B: Kaggle CPU-only setup check (no GPU quota), then ONE GPU re-time of v000 at cap 5. Even with the fix, the ship cap is ~4.75 (cap 5 + 0.2 setup = 680 > 660).

## OOM incident (dec 020/021)
- Root cause from runs/gold-null2: null-phase rows 22 rich_4006 (327 s), 38 rich_3480 (2683 s), 39 rich_3772 (2867 s) hit exit 124. The harness executor already uses start_new_session+killpg (adk_eval_core subprocess_sandbox.py:57), so the orphan theory is weaker; the leading suspect is unbounded memory in a null-patch rich test with no per-sandbox memory cap (none locally; the scorer has 4 GiB). Unproven: no RSS was logged. The codex-sandbox-limits fix covers both.
- bin/job hardening: APPLIED by Aniket (b1eedd7). The review-memguard rerun still covers it.
- No exit-137 events since the reboot.

## Quota / spend
- GCP $0 (project gemma-agent-839566; only l4x1 spot + cpu8 usable, dec 003). Owner policy: Kaggle first (dec 001).
- Kaggle GPU this week: 0.07 h used (v1+v2 failed fast, per `kaggle quota`); 3.48 quota-h used after v3 (~1.74 L4x4 h). Log: ops/budget/kaggle.md. Resets Sat 00:00Z.

## Live caveats
- Job naming (dec 024): waiters, codex-ask and codex-review jobs end in -light; builds, test suites and evals never do.
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
1. Await dec on report 004. Review + merge kernel-setup-fix; on approval push the CPU setup check.
2. Act on reviews: review-job-patch2-light (then mail the Director), review-memguard-fix-light (merge, deploy memguard-light), codex-sandbox-limits2 (then re-review, merge eval/ only).
3. EV-1 + the cpu8 gold/null run (dec 019/020) after the sandbox-limits merge; then dec 022 item 4 levers (truncation-safe diff, patch hygiene, tool-output trimming).
