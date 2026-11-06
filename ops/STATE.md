# STATE: snapshot 2026-11-06 14:32Z (cycle 151, Phase 0). Rewrite each cycle, ≤80 lines (dec 017). History: ops/journal.md.
## Best bundles (none validated; runtime budget still unverified, codex BLOCKING)
- v000 (repo a12f0b7, static OK): 31b dist/31b-v000.zip 4a23e14a...efae161; e4b dist/e4b-v000.zip cc647bfb...6940e2
- e4b-v002 (v001 + cap 1.0 + max_output_tokens 8192 x2): dist/e4b-v002.zip sha256=60c0074684ef4f9aa9cd8744d08fa29a37f3b94fc893541a8b96ceed54944dad
  SUBMITTED 2026-11-06T00:11:23Z ref 58039259; SCORED public 0.05 (COMPLETE; first final poll 05:11:49Z, T=5.007 h). results/lb_e4b_v002.json filled,
  budget row updated, Director FYI'd. No runtime fields from CLI. E4B validator acceptance VERIFIED. Next e4b submit: next UTC day at earliest. Guard v6 applied b9caae4 (dry checks rc=3 x2).
- 31b-v002 (dec 052 item 3; v001-t4 + cap 3.5 only): dist/31b-v002.zip sha256=e56a05e5701fa16a8dbbabb304d98f63a465511cefbb28d65850ea5ce086ec88,
  pack PASS, load check 8192 x2 / 210 s. Submit kernel aniket0202/gemma-submit-31b v1 (CPU) COMPLETE, output sha e56a05e5 verified. Review CLEAN.
  DEC 055 = SUBMIT AUTHORIZED, CONDITIONAL. ALL must hold or it is void: (1) now >= 2026-11-07T00:00Z (waiter submit-window-31b-light);
  (2) [HOLDS: COMPLETE 0.05] e4b 58039259 FINAL; (3) [HOLDS: T=5.007 h, SCORED] T = (first poll showing e4b final, results/lb_e4b_v002.polls.csv) - 00:11:23Z;
  submit only if e4b SCORED and T <= 6.0 h. If 6<T<=8 h or e4b ERRORED (any cause): do NOT submit, mail Director T + exact status text +
  options B (31B cap<=1.23) / C (repeat e4b-v002). e4b still pending at 2026-11-07T18:00Z: mail Director, don't submit.
  (4) commit "config: SUBMIT_KERNEL=aniket0202/gemma-submit-31b for 31b-v002 (dec 054)", grep into journal, kernel v1.
  (5) journal T + veto (number, threshold, verdict) BEFORE bin/kaggle-submit; then results/lb_31b_v002.json (same schema as
  lb_e4b_v002.json) + waiter -light. Expect a weak LB score (validation submit); don't act on it alone.
- CHECKLIST (dec 041 item 6): every Phase-0 [verify] in docs/COMPETITION.md is verified or listed open. OPEN: l.37 12B/E2B validator
  acceptance (E4B VERIFIED by 58039259 scoring); l.55 submit_patch/get_status vs call limits; l.63 private-LB multiple runs; l.72 wheels arch
  (x86 assumed, unrecorded); 12h overrun ruling. VERIFIED: l.42 submit method = kernel output (dec 041); l.76 superseded by l.112.
## Eval data
- Splits v2 FROZEN: clean 48 (rich 39, fastapi 9), dev 33, holdout 15; holdout uses = 0. Hashes: eval/splits/MANIFEST.json.
- requests/httpx dropped (wheel shadowing = scorer property, dec 014). Gold v2 files in results/ (gold_calibration_*, gold_failure_causes).
- RE-GROUND EVERY CYCLE (dec 021/025). Linger: `loginctl show-user "$(id -un)" -p Linger --value` must be `yes`, else tell Director. After NEXT reboot once: `systemctl --user list-units --type=service --state=running` names only; report non-ours units, never touch (may be Etho).
- Watchdog must be running: `bin/job status memguard-light` (fix6 deployed 23:37Z; stop = bin/job kill); if dead: `bin/job start memguard-light -- bin/memguard` (dec 024: always -light). Heavy jobs one at a time (waiters/memguard/codex exempt). Check `tail ops/logs/memguard.log` for KILL lines. No heavy job unless memguard runs.
- DEC 060: v004 full-arm-B-prompt deviation ACCEPTED provisionally (report 014 covered a-c); quoting line UNSCREENED. Nov 7 31B
  submit write-up must note v002 LB = ONLY result carrying the FastAPI hint caveat. Repeat metric added to plan 007 (Addendum).
## Running jobs (14:32Z): memguard-light, submit-window-31b-light (fires 11-07T00:00:30Z).
- CYCLE 151: targeted re-review 142723 NOT CLEAN (residual B3: unpaired gate-authored inner submit_patch resp -> boundary None) -> D73.6 TRIGGERED:
  ARM 2 = v011 (dist/31b-v011.zip 4f5b078a...4938), NO smoke, no more v010 rounds; Director FYI'd. B3 moot for v011 (builtin submit_patch);
  fix B3 (+regression test, targeted review) before any gate arm uses metrics.
- DEC 076: D73.6 stands; single-run-dir exit 3 kept; arm 2 = ONE session; D73.7 chunk rule c93967b (pre-data, NO build unless chunk 2 needed).
- DEC 075 (ack FYI): MANIFEST v010 l.1 fixed -> b0785a30, fc24fcc3/c7a86295 VOID (MANIFEST excluded from zip, sha unchanged). Review CLEAN -> NO decision request, proceed + 1-line FYI; decision only if arms/ids/thresholds/rule change.
- DEC 074 APPROVE D73: D73.5 (submit_unverifiable counts AGAINST arm 2; metrics arm2 mode must implement - d73 build only REPORTS it, add after merge)
  + D73.6 (combined review = LAST full round; BLOCKING -> fix + 1 targeted re-review; not CLEAN after that or by 11-07T06:00Z -> arm 2 = v011, no smoke) written to 008.md.
- DEC 073 APPROVE (D72 accepted as governing pre-data defs; metrics asserts mech2 17/empty 12 fail -> STOP+report, never adjust; arm-1 safety base committed BEFORE arm-2 rows; new gate-changing BLOCKING -> new sha + D72.x line + 1-line FYI; re-verify /tmp if reuse_containers ever set).
- DEC 072: gate = harness-equal eligibility + observable reasons + failure-safe counter + SUBMIT FAILED (1a3b831); fc24fcc3 VOID (D73). Plan 008 D72 = pinned metric defs.
- DEC 071 (gate approved w/ conditions): items 1-3 DONE 787b465. Plan 008 Addendum D71: wiring (a) YES same Context (gate alive),
  (b) scored = patch at submit call, else end-of-session workspace diff, (c) no name keying (keep name submit_patch), (d) gate counts:
  worst +3 calls/+7 turns. Smoke ids eval/plans/008-smoke-ids.txt (rule: first 2 non-timeout empty arm-1 rows) sha dcae5058...;
  smoke PASS = ALL of (i)-(v) per D71.2. Arm 2 = v010 iff smoke PASS else v011. FALLBACK 31b-v011-p8b dist/31b-v011.zip
  sha256=4f5b078a367e964ffb7d7426f4d42e13451d0c9dde79322c7fee5bd3a88f4938 (agent.yaml==v009, PROMPT-LEVEL), pack+load PASS.
- DEC 069 (rep 018, A w/ conditions): arm 1 VALID by POST-HOC ruling = plan 007 Addendum C (7ceb059). PRIMARY 4/33 FINAL
  (codex 132715 BLOCKING = missing descriptive lines -> fixed; re-review 133120 CLEAN). results/plan007_arm1_summary.json v2
  (script sha 349b1bda...): a 4/33 (W 4.8-27.3), c 4/26, d 4/27 (literal), d' 4/33, empty 12/33 (2 to/10 non), unscreened 3/25,
  thinking blocks 0, dec060 identical runs: 17/33 tasks max run >=5, max 38, 366 repeated; 11/12 empty rows have run >=5.
  ENV CONTROL caveat l.152 on every arm-1 citation. Chunk 2 not needed (main covered all 30) -> journal before arm 2.
- PLAN 008 / 31b-v010-p8 (dec 069 item 3 + DEC 070): pre-reg eval/plans/008.md (1169579). Feasibility: bundle callbacks silently dropped
  (no registry passed), so repeat guard = PROMPT-LEVEL (Option A text verbatim + edit 2-fail -> shorter anchor or /tmp script, NOT write_file);
  empty guard = dec 070 1(b) prompt rule + IN-BUNDLE agent_tool gate named submit_patch (shares Context; <=2 bounces). Both deviations
  accepted (dec 072). Ship rule: pass delta>=0 AND empty<=4/33 AND run>=5 tasks<=6/33 AND safety (submitted-without-test <= 23+3=26).
  Dec 070 item 5: arm-3 addendum must require smoke thinking blocks > 0.
- PLAN 007 PRE-REG eval/plans/007.md (e547980): arm 1 = 31b-v009-p7a1 (v006 + cap 3.5; dist/31b-v009.zip d38c55c7..., pack PASS),
  33 dev fixed order eval/plans/007-arm1-ids.txt, --with-verification --no-stock-probe, slug aniket0202/gemma-31b-passrate.
- DEC 061 (on report 014): approve-with-changes. CAP-BOUND accepted; A + B approved. (i) dec 055 v002 submit at 11-07T00:00Z stays FIRST;
  if SCORED -> bring v004 cap choice w/ data (FINALS RULE allows cap<=3.5); if ERROR/timeout -> CAP-BOUND binds, anti-loop only 31B path.
  (ii) v004 stays CPU draft, no slot; fold codex NB2 pipefail fix at system.md:33 next time source touched, label UNSCREENED; no repack.
  (iii) next 31B GPU arm = exact-repeat loops.
  Item 4: plan 007 pre-reg (33-dev pass rate; H1 env; thinking off vs on paired arm) DUE 2026-11-07T18:00Z (may use leftover quota pre-reset).
  Item 5: Nov 8 slot candidate + 1-para justification DUE 2026-11-07T12:00Z (e4b-v002 repeat / e4b-v003 if packed+reviewed+smoke / 31b-v002 repeat).
  Item 6: arm E/F results files schema-headed (plan005_armE_vs_D.json has _schema); dec 038 paper evidence by Nov 9 23:59Z.
- 31b-v004 CPU DRAFT dist/31b-v004.zip 50537e1d... (v007 + quoting line), no slot (dec 061 ii); NB3 timeout empty patch unguaranteed (dec 056 item 6).
- DEC 057: no new bundle carries a repo-named hint; v000-v002 (both tracks) carry the FastAPI hint -> reports must say so; LB may tilt FastAPI-ward. e4b-v003 = e4b-v002 + generic fixes minus that line (CPU draft).
- GCP $0 (project gemma-agent-839566; only l4x1 spot + cpu8 usable, dec 003). Owner policy: Kaggle first (dec 001). Kaggle GPU this week: 27.66/30 h per `kaggle quota` 13:26Z after main (+10.41); 2.34 h left. Log: ops/budget/kaggle.md. Resets 2026-11-07T00:00Z.
## Live caveats (dec 022 timing (cap+S)x125+30<=660; dec 032 item 8 pending; forum: Builder posts nothing, dec 035)
- Standing: kernel Dockerfile.public only, no PIP_*, setup_calls logged (dec 027); -light = waiters/asks/reviews (dec 024); LORO weak (dec 014). - DEC 038 (paper, due Nov 12; evidence by Nov 9 23:59Z): (1) DONE results/failure_taxonomy_e4b_v001_v5.json (timeout 4, ok 2, ctx-ovf 1, test-edit 1);
  (2) results/kaggle_timing_e4b_v001.NOTE.md DONE (still add decision_note to JSON at probes merge); (3) e4b-v002 LB score -> schema-headed
  results file (score, submit/complete ts, sha); (4) report 010 results files schema-headed. Paper cites only files. Never edit paper/.
- Director reminder 2026-11-06T23:02Z: GCP quota re-request line to Aniket (keep until a decision marks it done). Kaggle GPU kernels pin starter docker_image (py3.12, cp312). Hosted-LLM-API data Q OPEN; no new 3rd-party svc. One pending submission; no partial credit on timeout. Quota log before/after smoke+main (dec 063/064).
## Timing facts (results/kaggle_timing_e4b_v000_setup.json) setup ~210 s/task, outside max_time_minutes (clock starts after setup); flat across repos. vLLM startup 5.39 min; verification ~410 s (excluded from the 12 h). Agent clock p90 144 s at cap 5.
## Dec 034 (option C, gated step-up) in force
- 31b-v001-t4 (dec 036 item 2 name; dir bundles/31b/v001) = TIMING bundle (cap 4.0, max_output_tokens 8192 x2): dist/31b-v001.zip sha256=3c3a264652ab1d72ff6b9c5609c482c34a2ab7af37eb600689e5cfa0bf810f6a,
  pack PASS, load check results/bundle_load_check_31b_v001.json (8192/8192, 240 s). NOT a submission candidate.
- Timing kernel (plan 006 DONE, G1 held -> dec 055): stack main 2db5f51 per Addendum A (gate fix from 92a74c7, worktree
  gemma-wt/codex-kernel-probes-gate). Last FROZEN+noted classifier: a208a023 (0d49b1c); rev-5 d4cdf0f0 frozen pending Director note (report 016).
- FINALS RULE: no final with cap > H3 bound (31B 1.23, e4b 1.0) unless a same-or-higher cap, same model, has SCORED on the real scorer. Plan slots so each track is validated well before Nov 29.
- OPEN (dec 034 item 6 / dec 058 item 7): plan 007 must pre-register which env the local sandbox models (H1: scorer site-packages test deps).
## Next 3
1. Dec 055 31b-v002 submit 11-07T00:00Z FIRST (checklist in Best bundles); kaggle quota log after reset.
2. Then arm-2 v011 full 33-id run, ONE session (D73.7), post-reset quota; verify kernel/runner config points at v011 sha first.
3. Nov 8 slot proposal (due 11-07T12:00Z); arm-3 thinking addendum (dec 070 item 5) due 11-07T18:00Z; dec 038 paper evidence by Nov 9.
