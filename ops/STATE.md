# STATE: snapshot 2026-11-05 22:58Z (cycle 98, Phase 0). Rewrite each cycle, ≤80 lines (dec 017).
History: ops/journal.md; pre-cycle-51 STATE: ops/history/STATE-archive.md. Builder on Opus (dec 010: local-first, two-strike).
## Best bundles (none validated; runtime budget still unverified, codex BLOCKING)
- 31b: dist/31b-v000.zip sha256=4a23e14a1aae077161cb137b5ff72afe91ee2acb1d1fdbaf2e322abb6efae161 (repo a12f0b7; static+codex static OK)
- e4b: dist/e4b-v000.zip sha256=cc647bfb28bc6d2db0e3ec816df084f23a91230786d8fea177e2d63d2a6940e2 (same)
- e4b-v001 (dec 022 item 3, cap 5 -> 1.4 only): dist/e4b-v001.zip sha256=f2ced9c97ee1447cb3a78c0ebf65f4ecaff90c84b18313645d5d043c62d277e9 (re-pack, comment fix only), codex-review clean (no BLOCKING); re-time HELD until item 2 concludes.
- e4b-v002 (dec 032 item 1: v001 + cap 1.0 + max_output_tokens 8192 at both occurrences): dist/e4b-v002.zip
  sha256=60c0074684ef4f9aa9cd8744d08fa29a37f3b94fc893541a8b96ceed54944dad, bin/pack PASS, load check OK
  (results/bundle_load_check_e4b_v002.json: 8192/8192, 60 s). SUBMIT conditions (dec 032 item 3): (i) done; (ii) v002 review
  (review-e4b-v002-light, 23:09Z) no BLOCKING; (iii) fix5c review clean or BLOCKING = summary/gate-only; (iv) diff = item 1 (yes).
  All hold -> send SUBMIT dist/e4b-v002.zip sha256=60c0...4dad track=e4b + both review links (dec 033: Director authorizes at once).
  Slot cutoff ~23:45Z else Nov 6. Cap derivation for the SUBMIT mail (dec 033 item 2): overrun F = 7 s (5 s floor execution.py:37
  + killpg), worst = 60+7+221.6 = 288.6 s -> 631 min <= 660; post-cap fallback git 60 s default timeout = unmeasured tail.
- No local pass-rate scores yet. eval-runner-fix MERGED to main 70c0d9f (codex review clean + N1 count-cap fix d13ceac; 421 pass, 3 skip).
  Test cmd: /home/ubuntu/gemma-local/venv/bin/python3 with pyimg cp3.13 site-packages appended to sys.path, pytest eval/tests.
## Eval data
- Splits v2 FROZEN: clean 48 (rich 39, fastapi 9), dev 33, holdout 15; holdout uses = 0. Hashes: eval/splits/MANIFEST.json.
- requests/httpx dropped (wheel shadowing = scorer property, dec 014). Gold v2 files in results/ (gold_calibration_*, gold_failure_causes).
## Re-grounding check (EVERY cycle, dec 021 item 1e + dec 025 item 2)
- Linger (dec 025): `loginctl show-user "$(id -un)" -p Linger --value` must be `yes`, else tell Director. After NEXT reboot once: `systemctl --user list-units --type=service --state=running` names only; report non-ours units, never touch (may be Etho).
- Watchdog must be running: `bin/job status memguard` (old name, pid 7933) until the memguard-fix deploy, then `memguard-light`; if dead: `bin/job start memguard-light -- bin/memguard` (dec 024: always -light). Check `tail ops/logs/memguard.log` for KILL lines. No heavy job unless memguard runs.
- bin/job hardening is applied (b1eedd7); keep heavy jobs to one at a time until the Director relaxes this (waiters/memguard/codex exempt).
## Running jobs (22:58Z): fix5c + v002 reviews sleeping to Codex-limit reset (~23:08Z), review-kernel-probes-light (waits for both; reviews 63127c8 with the OLD minus-image prompt; bin/job stop was denied by the permission classifier),
  review-memguard-fix6e-light (waits for probes), review-kernel-probes-gate-light (waits for probes; dec 036 delta), memguard 7933 (0 kills).
- KERNEL v5 (87001e4, 4xL4): GATE FAIL (a) 7/8 rich_3930 ctx overflow, (b) max TOTAL 305.6>296; two-strike STOP (no v6);
  dec 032 -> v002 (above). results/kaggle_timing_e4b_v001.json top-level "decision" = legacy projection, not the gate.
- fix5 branch codex/kernel-setup-fix5 @87001e4: merge after fix5c review clean, then host eval/tests on main. Item 6 docker-order
  MERGED 8c55985; main eval/tests 469p/3s/1f (stale test_memguard oom_score_adj; fixed by the fix6 merge).
- memguard-fix6 eedf84b+0f5de3d livetest GREEN. Review clean -> merge + full eval/tests + deploy (stop 7933, start memguard-light). BLOCKING -> short report.
- NOTE: codex-build branches from main HEAD; follow-ups: manual worktree on prev commit + sed prev build-*.sh + bin/job start.
## bin/job, memguard, owner patch (cycles 62-66)
- Linger=yes since ~18:05Z (dec 025): scope path (MemoryMax=5G) is normal; Codex works under it. Owner patch v2 (ops/patches/bin-job-fallback.diff): HOLD for Aniket (dec 026), 3 BLOCKING in ops/codex/review-20261105T180811.md; plan v3 = pidfd helper. NOT started.
- sandbox-limits round 3 9d610b5 (wait4 ru_maxrss peak; Codex 459 pass/4 skip). Host test job sandbox-limits3-hosttest; if green -> codex-review -> merge eval/ only.
## Dec 027 still in force (superseded parts closed by dec 028)
- FIDELITY: kernel reproduces Dockerfile.public only (pip + line-9 tools, offline); NO PIP_* prefixes; setup_calls logging mandatory.
- Item 6 / dec 022 item 4 scoped (ops/codex/ask-20261105T181222.md): harness fallback diff covers caps when submit_patch not called;
  empty submit loses everything; draft prompt bundles/drafts/item4-system.md; plan 005 (paired A/B at v002 cap, needs GPU: ask in report 005).
## Quota / spend
- GCP $0 (project gemma-agent-839566; only l4x1 spot + cpu8 usable, dec 003). Owner policy: Kaggle first (dec 001).
- Kaggle GPU this week: 5.18/30 h per `kaggle quota` 21:05Z. Plan 006 cap 4.0 ~2.4 quota-h (-> ~7.6). Log: ops/budget/kaggle.md. Resets Sat 00:00Z.
## Live caveats
- Job naming (dec 024): waiters, codex-ask and codex-review jobs end in -light; builds, test suites and evals never do.
- LORO with only 2 repos (rich, fastapi) is weak; report 002 must say so (dec 014 item 3).
- DEC 038 (paper, due Nov 12; evidence by Nov 9 23:59Z): (1) taxonomy results/failure_taxonomy_e4b_v001_v5.json (trace-analyst, once);
  (2) results/kaggle_timing_e4b_v001.NOTE.md DONE (still add decision_note to JSON at probes merge); (3) e4b-v002 LB score -> schema-headed
  results file (score, submit/complete ts, sha); (4) report 010 results files schema-headed. Paper cites only files. Never edit paper/.
- Director reminder due 2026-11-06T23:02Z: GCP quota re-request line to Aniket; keep until a decision marks it done.
- Any Kaggle GPU kernel must pin the starter docker_image (py3.12, cp312 wheelhouse). Hosted-LLM-API data question OPEN; no new 3rd-party services.
- One pending Kaggle submission at a time; no partial credit on timeout (docs/RULES_FINDINGS.md).
## Timing facts (results/kaggle_timing_e4b_v000_setup.json)
- Harness sandbox setup ~210 s/task, outside max_time_minutes (clock starts after setup); flat across repos. vLLM startup 5.39 min;
  verification ~410 s (excluded from the 12 h). Agent clock p90 144 s at cap 5.

## Open decisions / instructions in force
- Dec 022: interim timing rule (cap + S) x125 + 30 <= 660 (S now per dec 034 hypotheses). Item 4 (truncation-safe diff, patch hygiene, tool-output trimming) pending = dec 032 item 8.
- Dec 020 item 7 / dec 019 item 2: EV-1 (typing_inspection 0.4.5 eval-only, NOT yet implemented) + gold/null on 48 clean, on a cpu8 VM via bin/gpu (<=$3, <=3 h), after the sandbox-limits merge. Dec 019 items 3-4 (per-repo rates; collection-error note) to fold in.

## Dec 034 (report 009 ruled: option C with gated step-up) — in force
- 31b-v001-t4 (dec 036 item 2 name; dir bundles/31b/v001) = TIMING bundle (cap 4.0, max_output_tokens 8192 x2): dist/31b-v001.zip sha256=3c3a264652ab1d72ff6b9c5609c482c34a2ab7af37eb600689e5cfa0bf810f6a,
  pack PASS, load check results/bundle_load_check_31b_v001.json (8192/8192, 240 s). NOT a submission candidate.
- Kernel probes P1-P3: branch codex/kernel-probes 63127c8 (on fix5 87001e4). DEC 036: gate fix on branch codex/kernel-probes-gate
  92a74c7 (worktree gemma-wt/codex-kernel-probes-gate): --gate-mode stock-path, b = max(phase1 - image_emu - setup.py) <= cap*60+37,
  h1_composite reported (not gated); 118 tests pass; v5 rich_3067 = 89.52 s; whole v5 b max 92.3 <= 121 (PASS; overall FAIL on (a)).
  Push the -gate branch at cap 4.0, budget 6000 only after BOTH review-kernel-probes-light and review-kernel-probes-gate-light are clean
  (eval/plans/006.md "Dec 036 correction"). Summary cmd: timing_summary.py --gate-mode stock-path --gate-vllm-seconds 600.
  Kaggle slug/push command: same as v5 (ops/budget/kaggle.md); log quota.
  DEC 037: minus-image-only BLOCKING in the 63127c8 review = MOOT (say so in push note); gate prompt scoped OK; queue order holds.
- Gates for that run: (a) 8/8 no harness error; (b) max(Phase-1 - emulation) <= 277 s; (d) vLLM <= 600 s; (e) >= 1 non-empty diff.
- G1 = P2 no docker binary + no docker.sock AND P1 stock setup <= 30 s on all 8 AND gates pass -> request SUBMIT 31b-v002 (cap <= 3.5,
  byte-identical to v001-t4 except cap + comment, no re-time; dec 036 item 2) in report 010, citing h1_composite.
- FINALS RULE: no final with cap > H3 bound (31B 1.23, e4b 1.0) unless a same-or-higher cap, same model, has SCORED on the real scorer. Plan slots so each track is validated well before Nov 29.
- e4b-v002 submit: record submit time, completion time, any runtime field from the Kaggle API/CLI in ops/budget/kaggle.md (weak evidence; never act on it alone).
- Forum question (dec 035, E4 YES): Aniket posts report 009 s6 from his own account; Builder posts NOTHING. When an answer appears, summarize it (no task data) in the next report. Nothing waits on it; G1 governs.
- OPEN eval-design question (dec 034 item 6): under H1, test deps come from the scorer's own site-packages, not setup.py. Before local
  pass-rate evals start, pre-register which environment the local sandbox models and why. Don't act on it before then.
- Dec 032 item 5: decision_note is in timing_summary (probes branch); add the same note field to results/kaggle_timing_e4b_v001.json at merge.
## Next 3
1. 23:08Z fix5c + v002 reviews -> evaluate v002 SUBMIT conditions (ii)/(iii) -> SUBMIT mail to Director (slot cutoff ~23:45Z).
2. fix5c clean: merge fix5 branch; probes + probes-gate reviews clean -> push codex/kernel-probes-gate (cap 4.0) -> timing_summary --gate-mode stock-path -> report 010.
3. fix6e review -> merge + deploy memguard-light. Then dec 032 item 8 (= dec 022 item 4 empty-patch protection, codex-build).
