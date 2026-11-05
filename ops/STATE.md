# STATE: snapshot 2026-11-05 19:27Z (cycle 81, Phase 0). Rewrite each cycle, ≤80 lines (dec 017).
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

## Re-grounding check (EVERY cycle, dec 021 item 1e + dec 025 item 2)
- Linger check (dec 025): `loginctl show-user "$(id -un)" -p Linger --value` must be `yes`; if not, tell the Director. After the NEXT reboot, once: `systemctl --user list-units --type=service --state=running`, names only; report non-ours units to the Director, never inspect or touch them (may be Etho).
- Watchdog must be running: `bin/job status memguard` (old name, pid 7933) until the memguard-fix deploy, then `memguard-light`; if dead: `bin/job start memguard-light -- bin/memguard` (dec 024: always -light). Check `tail ops/logs/memguard.log` for KILL lines. No heavy job unless memguard runs.
- bin/job hardening is applied (b1eedd7); keep heavy jobs to one at a time until the Director relaxes this (waiters/memguard/codex exempt).

## Running jobs (19:27Z)
- memguard (old name, pid 7933): running, 0 kills. Replaced by memguard-light at the memguard-fix deploy.
- DEC 028 (report 005-prelim, option A APPROVED): 2a STOP met; artifact branch closed, 2b moot, no v000 re-time. CPU 2a dropped.
  Item 1-3: codex-kernel-setup-fix5 RUNNING (branch codex/kernel-setup-fix5 on round-4 c4c9528; spec ops/codex/build-kernel-setup-fix5.spec):
  SKIP_VERIFICATION, asyncio.timeout proxy (agent clock + fired), sandbox_start/stop/exec wrappers (finalization, teardown,
  TOTAL Phase-1 wall), vLLM startup in header, timing_summary gate lines. Then ONE codex-review of the merge diff (round 4 +
  fix5) -> no BLOCKING -> merge -> push e4b-v001 (bundles/e4b/v001, sha256 f2ced9c9...) on 004-gpu-retime-ids, -t ~3 quota-h.
  Gate (dec 028 item 4, pre-registered): (a) 8/8 no harness error (b) max Phase-1 <= 296 s (c) mean <= 270 s (d) vLLM <= 10 min
  (e) >= 1 non-empty source diff. Pass -> short report 005 NEEDS_DECISION, request SUBMIT (today if < ~23:00Z). NO kaggle-submit
  until an AUTHORIZE line exists. Fail (b)/(c) -> propose lower cap from max total wall. Report 005 also derives the v002 cap with
  F: (cap+S+F)x125+30<=660 and (cap+F+0.875+0.75S); don't build v002 before the Director sees it.
- Item 6: codex-sandbox-env-docker-order RUNNING (bin/codex-build from main; Docker order + wheel-set cache key + marker in
  eval/sandbox_env.py) -> review -> merge -> full eval/tests on main.
- codex-memguard-fix6 RUNNING (round 6; inode-identity detection + fail closed). Then host livetest + review; no BLOCKING -> merge +
  deploy (stop 7933, start memguard-light at once). If still BLOCKING: stop iterating, short report (old memguard works).
- Item 7: plan eval/plans/006.md pre-registered (31B timing, cap from e4b-v001 S/F, <= 4 quota-h, same 8 ids). After report 005.
- NOTE: bin/codex-build always branches from main HEAD; for follow-up rounds create the worktree on the previous commit manually,
  write the spec, sed the previous build-*.sh, and bin/job start codex-<name>.

## 2a (CLOSED by dec 028): cause = harness RECORD strip (container_setup.py:266) + task package in base set; history in journal/report 005-prelim.

## bin/job, memguard, owner patch (cycles 62-66)
- Linger=yes since ~18:05Z (dec 025): the scope path (MemoryMax=5G) is normal; Codex works under it.
- Owner patch v2 = ONE diff (dec 024 item 3; dec 026: HOLD for Aniket, low urgency, after the critical path; keep the RLIMIT_DATA comment): ops/patches/bin-job-fallback.diff. v2 review ops/codex/review-20261105T180811.md: 3 BLOCKING (grep regex marker -> use grep -F; PID reuse between scan and signal plus cached group_ok -> bind identities (pidfd); legacy 3/4-field records -> refuse destructive signalling without identity evidence). Plan v3: a small Python helper using pidfds (like memguard) called from bin/job kill. NOT started (low urgency).
- memguard-fix: round 2 adae3eb review ops/codex/review-20261105T182108.md: 2 BLOCKING (legacy history merge in setdefault; two guards target each other). Round 3 job codex-memguard-fix3 (spec ops/codex/build-memguard-fix3.spec): history merge + protect every memguard process/wrapper. DEPLOY CHANGED: no overlap. With no heavy jobs running, stop pid 7933, then start memguard-light at once. Then host livetest (ops/codex/memguard-fix-livetest.sh) + re-review; merge only with no BLOCKING.
- sandbox-limits round 3 9d610b5 (wait4 ru_maxrss peak; Codex 459 pass/4 skip). Host test job sandbox-limits3-hosttest; if green -> codex-review -> merge eval/ only.

## Dec 027 (report 004 approved, option B with fidelity changes): plan 004 pre-registered (eval/plans/004.md)
- FIDELITY: the timing kernel may only reproduce Dockerfile.public (pip + the line-9 tool set, offline). NO PIP_NO_INDEX/retry prefixes. setup_calls logging is mandatory.
- Build chain on branch codex/kernel-setup-fix: round 1 c57bd65 (437 pass; still has the PIP prefix; bwrap acceptance blocked in Codex's sandbox; local wheelhouse lacks pip/pytest-timeout wheels). Round 2 DONE b21e400 (444 pass/4 skip; Codex's bwrap blocked: NETLINK). Now running locally (job kernel-setup-accept): eval/repro/plan003_kernel_setup.py locally (both modes) + codex-review, then push CPU stage 2a.
- Kaggle CPU session (no GPU quota): 2a UNFIXED on rich_3006 + fastapi_14986 -> WHY. If the cause is the competition's own harness/wheel ABI, STOP and report. 2b FIXED on 16 ids (eval/plans/004-setup-check-ids.txt). Gate: setup <= 30 s, editable rc 0 16/16, 0 Retrying. -> results/kaggle_setup_cpu_check.json; log in ops/budget/kaggle.md.
- Only if 2b passes: ONE GPU re-time of v000 cap 5 on eval/plans/004-gpu-retime-ids.txt (not a ship candidate). If 2b fails: re-time v001 instead.
- Ship cap = both (i) (cap+S)x125+30 <= 660 and (ii) (cap + 0.875 + 0.75S)x125+30 <= 660 -> ~4.0 min at S~10 s -> e4b-v002 after the re-time.
- Report 005: the 2a cause, the CPU gate, the GPU re-time, and the first-submission bundle with its cap derivation (the Director will run a codex-ask adversarial check).
- Item 6 / dec 022 item 4: scoped (ops/codex/ask-20261105T181222.md). The harness's fallback diff already covers caps/overflow when submit_patch was NOT called; submit_patch freezes the patch (an empty submit loses everything). No bundle-level output trimming or compaction knob exists; the timing kernel compaction = starter cell 10 (faithful). Draft prompt bundles/drafts/item4-system.md; plan 005 pre-registered (paired A/B at the v002 cap, needs GPU: ask in report 005).
- Background (plan 003): hung-index fallback 103.4 s/call; 2 calls = 206.8 s vs Kaggle 207-211 s. results/plan003_pip_fallback_repro.json.

## OOM incident (dec 020/021)
- Root cause from runs/gold-null2: null-phase rows 22 rich_4006 (327 s), 38 rich_3480 (2683 s), 39 rich_3772 (2867 s) hit exit 124. The harness executor already uses start_new_session+killpg (adk_eval_core subprocess_sandbox.py:57), so the orphan theory is weaker; the leading suspect is unbounded memory in a null-patch rich test with no per-sandbox memory cap (none locally; the scorer has 4 GiB). Unproven: no RSS was logged. The codex-sandbox-limits fix covers both.
- bin/job hardening: APPLIED by Aniket (b1eedd7). The review-memguard rerun still covers it.

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

## Timing facts (results/kaggle_timing_e4b_v000_setup.json)
- Harness sandbox setup ~210 s/task, outside max_time_minutes (the budget clock starts after setup); flat across repos.
- vLLM startup 5.39 min; verification ~410 s (excluded from the 12 h). Agent clock p90 144 s at cap 5.
- Corrected rule proposed: (cap + max setup) x125 + 30 <= 660 -> cap <= 1.51 min.

## Open decisions / instructions in force
- Dec 022 (report 003): interim timing rule = (cap + max measured setup) x125 + 30 <= 660. Item 2 setup root-cause IN PROGRESS (ask-setup-210s + scout). Item 3: v001 (cap 1.4) may be built/packed now, but the re-time can't be pushed until item 2 concludes; ONE Kaggle timing run. Item 4 (truncation-safe diff, patch hygiene, tool-output trimming) to start. Item 5: no 31B timing yet. Report 004 next.
- Dec 020 item 7 / dec 019 item 2: EV-1 (typing_inspection 0.4.5 eval-only, NOT yet implemented) + gold/null on 48 clean, on a cpu8 VM via bin/gpu (<=$3, <=3 h), after the sandbox-limits merge. Dec 019 items 3-4 (per-repo rates; collection-error note) to fold in.

## Next 3
1. codex-kernel-setup-fix5 done -> codex-review merge diff (round 4 + fix5) -> no BLOCKING: merge, dry-run, push e4b-v001 L4x4 re-time.
2. Re-time result -> timing_summary gate -> report 005 (NEEDS_DECISION, SUBMIT request if pass).
3. sandbox-env-docker-order + memguard-fix6 reviews/merges; then 31b-v001 per plan 006.
