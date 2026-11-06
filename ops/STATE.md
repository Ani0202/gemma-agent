# STATE: snapshot 2026-11-06 01:06Z (cycle 103, Phase 0). Rewrite each cycle, ≤80 lines (dec 017).
History: ops/journal.md (pre-c51: ops/history/STATE-archive.md). Builder on Opus (dec 010: local-first, two-strike).
## Best bundles (none validated; runtime budget still unverified, codex BLOCKING)
- v000 (repo a12f0b7, static OK): 31b dist/31b-v000.zip 4a23e14a...efae161; e4b dist/e4b-v000.zip cc647bfb...6940e2
- e4b-v002 (v001 + cap 1.0 + max_output_tokens 8192 x2): dist/e4b-v002.zip sha256=60c0074684ef4f9aa9cd8744d08fa29a37f3b94fc893541a8b96ceed54944dad
  SUBMITTED 2026-11-06T00:11:23Z ref 58039259 (kernel aniket0202/gemma-submit-e4b v1, auth dec 040); PENDING. Waiter lb-e4b-v002-wait-light
  -> results/lb_e4b_v002.polls.csv; on score fill results/lb_e4b_v002.json (score, completed_utc, runtime fields) + ops/budget/kaggle.md.
  Next e4b submit: earliest after this scores AND next UTC day (one pending at a time). Guard v6 applied b9caae4 (dry checks rc=3 x2).
- 31b-v002 (dec 052 item 3; v001-t4 + cap 3.5 only): dist/31b-v002.zip sha256=e56a05e5701fa16a8dbbabb304d98f63a465511cefbb28d65850ea5ce086ec88,
  pack PASS, load check 8192 x2 / 210 s. Submit kernel aniket0202/gemma-submit-31b v1 (CPU) COMPLETE, output sha e56a05e5 verified. Review CLEAN.
  DEC 055 = SUBMIT AUTHORIZED, CONDITIONAL. ALL must hold or it is void: (1) now >= 2026-11-07T00:00Z (waiter submit-window-31b-light);
  (2) `kaggle competitions submissions` shows e4b 58039259 FINAL; (3) T = (first poll showing e4b final, results/lb_e4b_v002.polls.csv) - 00:11:23Z;
  submit only if e4b SCORED and T <= 6.0 h. If 6<T<=8 h or e4b ERRORED (any cause): do NOT submit, mail Director T + exact status text +
  options B (31B cap<=1.23) / C (repeat e4b-v002). e4b still pending at 2026-11-07T18:00Z: mail Director, don't submit.
  (4) commit "config: SUBMIT_KERNEL=aniket0202/gemma-submit-31b for 31b-v002 (dec 054)", grep into journal, kernel v1.
  (5) journal T + veto (number, threshold, verdict) BEFORE bin/kaggle-submit; then results/lb_31b_v002.json (same schema as
  lb_e4b_v002.json) + waiter -light. Expect a weak LB score (validation submit); don't act on it alone.
- CHECKLIST (dec 041 item 6): every Phase-0 [verify] in docs/COMPETITION.md is verified or listed open. OPEN: l.37 E4B/12B/E2B validator
  acceptance (first e4b submit settles E4B); l.55 submit_patch/get_status vs call limits; l.63 private-LB multiple runs; l.72 wheels arch
  (x86 assumed, unrecorded); 12h overrun ruling. VERIFIED: l.42 submit method = kernel output (dec 041); l.76 superseded by l.112.
- No local pass-rate scores yet. eval-runner-fix MERGED to main 70c0d9f (codex review clean + N1 count-cap fix d13ceac; 421 pass, 3 skip).
  Test cmd: /home/ubuntu/gemma-local/venv/bin/python3 with pyimg cp3.13 site-packages appended to sys.path, pytest eval/tests.
## Eval data
- Splits v2 FROZEN: clean 48 (rich 39, fastapi 9), dev 33, holdout 15; holdout uses = 0. Hashes: eval/splits/MANIFEST.json.
- requests/httpx dropped (wheel shadowing = scorer property, dec 014). Gold v2 files in results/ (gold_calibration_*, gold_failure_causes).
## Re-grounding check (EVERY cycle, dec 021 item 1e + dec 025 item 2)
- Linger (dec 025): `loginctl show-user "$(id -un)" -p Linger --value` must be `yes`, else tell Director. After NEXT reboot once: `systemctl --user list-units --type=service --state=running` names only; report non-ours units, never touch (may be Etho).
- Watchdog must be running: `bin/job status memguard-light` (fix6 deployed 23:37Z; stop = bin/job kill); if dead: `bin/job start memguard-light -- bin/memguard` (dec 024: always -light). Heavy jobs one at a time (waiters/memguard/codex exempt). Check `tail ops/logs/memguard.log` for KILL lines. No heavy job unless memguard runs.
## Running jobs (01:06Z): lb-e4b-v002-wait-light, memguard-light, submit-window-31b-light (fires 11-07T00:00:30Z), review-plan005-fix-light.
- DEC 056 (approve-with-changes): ONE Kaggle L4x4 run of plan 005 arm B (~2.1 h quota, $0 GCP) once review has no unresolved BLOCKING.
  review-20261106T005952: BLOCKING 1 (decision rule not total) + 2 (FastAPI/docs_src line in prompt) FIXED in 7879aef: Addendum A
  dated correction (V/E/M predicates, INVALID branch, sign test 1- and 2-sided), prompt-text-only edits (+pipefail, env-only failure,
  config-only exception), RE-PACKED dist/31b-v003.zip sha256=e9e603ab7decd589f5ea040579a5facf9c88858986039690ae8053df3e1f4d2f
  (old 3fa08f76 superseded, never run). trace_tool_errors.py: per-response tool, FIFO pairing, 4th arg ids file (exit 2 if incomplete);
  arm A output unchanged. review-plan005-fix-light = narrow confirm of those fixes.
- ON CLEAN: push arm B exactly as plan 006 (same kernel, --gate-mode stock-path, ids eval/plans/004-gpu-retime-ids.txt, conc 1, cap 4.0,
  40 calls/50 turns, KERNEL_BUDGET 6000), log quota before/after in ops/budget/kaggle.md. Then trace_tool_errors.py <run> 31b-v003-p5t4
  results/trace_tool_errors_31b_v003.json eval/plans/004-gpu-retime-ids.txt + timing summary -> results/kaggle_timing_31b_v003.json;
  report per dec 056 item 4; PASS -> v004 = v002 + prompt only (dec 056 item 5); else pre-registered branch.
- Addendum B pre-registered 01:03Z (eval/plans/005.md): structural early-edit/submit-guard mechanism M1/M2/M3, choose one by dated
  line after CPU ADK feasibility codex-ask; needs a separate quota request.
- Dec 055 checklist at 2026-11-07T00:00Z has PRIORITY over arm-B analysis.
- KERNEL v5 (87001e4, 4xL4): GATE FAIL (a) 7/8 rich_3930 ctx overflow, (b) max TOTAL 305.6>296; two-strike STOP (no v6);
  dec 032 -> v002 (above). results/kaggle_timing_e4b_v001.json top-level "decision" = legacy projection, not the gate.
- DEC 027 FIDELITY: kernel = Dockerfile.public only (offline); NO PIP_* prefixes; setup_calls logging mandatory.
- Dec 022 item 4 = plan 005 (ops/codex/ask-20261105T181222.md; draft bundles/drafts/item4-system.md; empty submit loses all; needs GPU).
## Quota / spend
- GCP $0 (project gemma-agent-839566; only l4x1 spot + cpu8 usable, dec 003). Owner policy: Kaggle first (dec 001).
- Kaggle GPU this week: 7.28/30 h per `kaggle quota` 01:00Z (plan 006 used +2.10). Log: ops/budget/kaggle.md. Resets 2026-11-07T00:00Z.
## Live caveats
- Job naming (dec 024): waiters, codex-ask and codex-review jobs end in -light; builds, test suites and evals never do.
- LORO with only 2 repos (rich, fastapi) is weak; report 002 must say so (dec 014 item 3).
- DEC 038 (paper, due Nov 12; evidence by Nov 9 23:59Z): (1) DONE results/failure_taxonomy_e4b_v001_v5.json (timeout 4, ok 2, ctx-ovf 1, test-edit 1);
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
## Next 3
1. review-plan005-fix-light clean -> push arm B (Kaggle, plan-006 stack), log quota; analyze per dec 056 item 4 when done.
2. e4b waiter final -> fill results/lb_e4b_v002.json + budget log, compute T. At 2026-11-07T00:00Z: run the dec 055 checklist above (priority).
3. Addendum B ADK feasibility codex-ask (CPU); dec 038 paper evidence by Nov 9 23:59Z; plan 007; ops/patches cleanup (dec 045 item 4).
