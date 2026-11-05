# STATE: snapshot 2026-11-05 18:05Z (cycle 65, Phase 0). Rewrite each cycle, ≤80 lines (dec 017).
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
- Until bin-job-fallback.diff is applied: `bin/job status` + `ls /run/user/1001/bus`. If the bus is gone and a job says running with a dead pid, mark it failed and relaunch it ONCE (logout killed the scope; NOT a 137/memory bug). Linger is OFF (Aniket's SSH login supplies the bus).
- `bin/job status memguard` must say running; if not: `bin/job start memguard -- bin/memguard`. Check `tail ops/logs/memguard.log` for KILL lines. No heavy job unless memguard runs.
- bin/job hardening is applied (b1eedd7); keep heavy jobs to one at a time until the Director relaxes this (waiters/memguard/codex exempt).

## Running jobs (17:55Z)
- memguard (pid 7933): running, 0 kills. codex-review ops/codex/review-20261105T175251.md: 6 BLOCKING (descendants not allowlist-checked; pid reuse; orphan/fork survivors; test validity; 2 on the applied bin/job kill path). Fix: codex-build memguard-fix (branch codex/memguard-fix). The bin/job findings (stale pgid, setsid escapes) go in a later owner patch. On restart, admission refuses the name "memguard" when MemAvailable < 5G: use memguard-light then (Director informed).
- codex-sandbox-limits DONE: 2c42c7a, 76 pass (bwrap live check blocked inside Codex); its ops/ edits must NOT be merged. codex-review job review-sandbox-limits.
- RELAUNCHED 17:52Z (the first attempts all failed because Codex's tool host crashes under the ulimit -v 5G fallback): review-memguard, codex-sandbox-limits (branch codex/sandbox-limits), ask-setup-210s. All three now run under the systemd scope (the user bus exists since 17:51Z).
- review-job-fallback: codex-review of ops/patches/bin-job-fallback.diff.
- scout DONE: ops/scout/2026-11-05-timing-caps.md. No public setup figure; the rules text puts setup inside the 12 h; unclear whether it counts against the per-task cap; public caps 4.5/8 min. Dec 023 item 3 DONE: RULES_FINDINGS C1-C3 (starter defaults to 60 min if the key is absent; sample_submission 1 min; "[0.10]" notebook 4.5 min). Weigh C3 as a mean, not a worst case, in report 004.

## Codex x bin/job (cycles 62-63)
- Dec 023 item 1a DONE: ops/patches/bin-job-fallback.diff (scope path only if Linger=yes; fallback ulimit -d). codex-review clean (ops/codex/review-20261105T175555.md); path mailed to the Director 18:04Z. Awaiting Aniket.
- bin/job hardening applied by Aniket (b1eedd7). Its ulimit -v 5G fallback (no user bus) crashes Codex (SIGTRAP). ulimit -d 5G works (A/B probe 17:52Z). Asked the Director to relay a one-line fix to Aniket. If a Codex job fails with 'code-mode host closed its stdout', check the [bin/job] cap line in the log.

## Dec 022 item 2: setup root cause (IN PROGRESS, cycle 65)
- 2a: results/kaggle_timing_e4b_v000_setup_breakdown.json. The ~208 s lies between the ensurepip warning and the first prompt (dependency setup), with no per-command timestamps. Verification ~410 s is about 2x.
- 2b (codex-ask ops/codex/ask-20261105T175253.md): ~80% "kernel artifact". No unconditional 210 s wait in the harness. Leading suspect: sandbox/setup.py:208-211, where the offline editable pip fails, then a fallback pip WITHOUT --no-index runs (PIP_* is stripped by sandbox env sanitization) and retries an unreachable index on Kaggle.
- My checks: Dockerfile.public:9 pre-installs the build backends. The kernel's injector does extract poetry_core/pdm_backend (skip set = pytest/pluggy/pip/setuptools/wheel only, container_setup.py:155). The Kaggle venv was created WITHOUT pip (ensurepip failed -> subprocess.py:357 fallback), so setup.py's pip calls used whatever pip system_site_packages gave. The wheelhouse is 27 MB (extraction is not 210 s). setup.py has only 3 subprocess calls (208, 211, 390 slow path), so pip is the only candidate inside setup.py.
- Plan 003 repro (scripts eval/repro/plan003_pipfb_v{1,2}.sh; v2 needs the v1 out dir for proj-*; output dir in the scratchpad, see ops/jobs/pipfb2-light.cmd): v1 invalid (pip ignores http untrusted hosts, 0.5 s); v2 (https unroutable index) RUNNING as job pipfb2-light, already >3 min on one fallback. Mechanism plausible; NOT proven that Kaggle hit it.
- Next: if pipfb2 shows hang ~100-200 s -> report 004 with option: a CPU-only Kaggle kernel (internet off, pinned image, no GPU quota) that runs the kernel install() path on 2 tasks and logs every setup subprocess (cmd, s, rc, stderr tail). That's the decisive, cheap proof. Fix candidate: pre-install the backends + pip into the sandbox venv, or pass --no-index to the fallback via a setup.py wrapper; never fail silently.

## OOM incident (dec 020/021)
- Root cause from runs/gold-null2: null-phase rows 22 rich_4006 (327 s), 38 rich_3480 (2683 s), 39 rich_3772 (2867 s) hit exit 124. The harness executor already uses start_new_session+killpg (adk_eval_core subprocess_sandbox.py:57), so the orphan theory is weaker; the leading suspect is unbounded memory in a null-patch rich test with no per-sandbox memory cap (none locally; the scorer has 4 GiB). Unproven: no RSS was logged. The codex-sandbox-limits fix covers both.
- bin/job hardening: APPLIED by Aniket (b1eedd7). The review-memguard rerun still covers it.
- No exit-137 events since the reboot.

## Quota / spend
- GCP $0 (project gemma-agent-839566; only l4x1 spot + cpu8 usable, dec 003). Owner policy: Kaggle first (dec 001).
- Kaggle GPU this week: 0.07 h used (v1+v2 failed fast, per `kaggle quota`); 3.48 quota-h used after v3 (~1.74 L4x4 h). Log: ops/budget/kaggle.md. Resets Sat 00:00Z.

## Live caveats
- Reminder to Aniket due 2026-11-09T15:00Z: Etho judging over -> enable linger (check ~/.config/systemd/user for auto-starting units first, then `sudo loginctl enable-linger ubuntu`). Dec 023 item 4: on the first cycle at or after then, bin/send aniket the dec-023 text, then mail the Director. Keep until a decision marks it done.
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
1. Merge codex/sandbox-limits (eval/ files only) after review-sandbox-limits; merge memguard-fix after its review, then restart memguard; mail the Director bin-job-fallback.diff after review-job-fallback.
2. Dec 022 item 2: finish plan 003 (pipfb2-light), then report 004 (setup root cause + options; weigh RULES_FINDINGS C3 as a mean).
3. EV-1 implementation, then the cpu8 gold+null run; then item 4 levers and report 004.
