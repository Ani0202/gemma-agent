# STATE: snapshot 2026-11-06 07:31Z (cycle 130, Phase 0). Rewrite each cycle, ≤80 lines (dec 017). History: ops/journal.md.
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
## Re-grounding check (EVERY cycle, dec 021 item 1e + dec 025 item 2)
- Linger (dec 025): `loginctl show-user "$(id -un)" -p Linger --value` must be `yes`, else tell Director. After NEXT reboot once: `systemctl --user list-units --type=service --state=running` names only; report non-ours units, never touch (may be Etho).
- Watchdog must be running: `bin/job status memguard-light` (fix6 deployed 23:37Z; stop = bin/job kill); if dead: `bin/job start memguard-light -- bin/memguard` (dec 024: always -light). Heavy jobs one at a time (waiters/memguard/codex exempt). Check `tail ops/logs/memguard.log` for KILL lines. No heavy job unless memguard runs.
- DEC 060: v004 full-arm-B-prompt deviation ACCEPTED provisionally (report 014 covered a-c); quoting line UNSCREENED. Nov 7 31B
  submit write-up must note v002 LB = ONLY result carrying the FastAPI hint caveat. Repeat metric added to plan 007 (Addendum).
## Running jobs (07:31Z): memguard-light, submit-window-31b-light (fires 11-07T00:00:30Z), codex-plan007-rev5-fold,
  passrate-31b-v009-smoke-wait-light (smoke kernel gemma-31b-passrate v1, pushed 07:28:20Z, PRE-FOLD 078f4ea; downloads to
  runs/31b-v009-p7a1-smoke + SEAL.sha256), codex-review-blindgate-light (eval/plan007_blind_gate.py).
- DEC 065: smoke decoupled from the fold. On download: journal + kaggle.md the SEAL hashes FIRST; then ONLY blind gate output
  (python3 -I eval/plan007_blind_gate.py <timing.jsonl> eval/plan007_pinned/classify_rows_a208a023.py a208a023...4e6b 3).
  NO pass/fail/resolved/patch viewing until re-frozen classifier has a Director note. HOLD (vLLM up, 3 rows, 0 H) -> main ids 4..33
  (--seed-max ceil max total), KERNEL_BUDGET so week <= 29.5 h AND kernel ends by 23:30Z, else after reset. Fold diff touching
  agent_timing.py/kernel path -> main uses pre-fold 078f4ea too. Plan-007 header deviation note added. Report 016 names run commits.
- R5 REVIEW 071306 = NOT CLEAN: 19 BLOCKING fail-open + 2 false-H. Folding via codex-build plan007-rev5-fold (branch
  codex/plan007-rev5-fold). On finish: review diff, tests, merge, ONE re-freeze, REPORT 016 (residuals, arm-F exposure, run commits).
  Build fails/tests regress: don't iterate; report what landed.
- REV 5 CANDIDATE 9d0a8b4 (sha 21c3d46e, not frozen) = r4 fixes; superseded by the fold. Last FROZEN+noted: a208a023 (0d49b1c).
- DEC 063/064: classifier freezes need Director note; quota log before/after smoke+main; week <= 29.5 h; dec 055 first.
- DEC 062 (report 015 approved, A): T stays 0.2 everywhere; no T 0.6 arm in plan 007; repeat guard = design note only (DONE draft
  eval/plans/007-repeat-guard.md); item 4: plan-007 arm 1 may use expiring quota IF pre-reg reviewed + pushed by 11-06T15:30Z, else after reset.
- PLAN 007 PRE-REG eval/plans/007.md (e547980): arm 1 = 31b-v009-p7a1 (v006 + cap 3.5; dist/31b-v009.zip d38c55c7..., pack PASS),
  33 dev fixed order eval/plans/007-arm1-ids.txt, --with-verification --no-stock-probe, slug aniket0202/gemma-31b-passrate.
- Arm E CAP-BOUND (rep 014, v007 3a62f41f.., cap 1.23); arm D v006 b7b2eb3d.. PASS (rep 013). ARM F DONE NO-EFFECT (report 015, dec 062 accepted). results/plan005_armF_vs_D.json + *_31b_v008.json (schema-header check pending, dec 062 item 6).
- DEC 061 (on report 014): approve-with-changes. CAP-BOUND accepted; A + B approved. (i) dec 055 v002 submit at 11-07T00:00Z stays FIRST;
  if SCORED -> bring v004 cap choice w/ data (FINALS RULE allows cap<=3.5); if ERROR/timeout -> CAP-BOUND binds, anti-loop only 31B path.
  (ii) v004 stays CPU draft, no slot; fold codex NB2 pipefail fix at system.md:33 next time source touched, label UNSCREENED; no repack.
  (iii) next 31B GPU arm = exact-repeat loops.
  Item 4: plan 007 pre-reg (33-dev pass rate; H1 env; thinking off vs on paired arm) DUE 2026-11-07T18:00Z (may use leftover quota pre-reset).
  Item 5: Nov 8 slot candidate + 1-para justification DUE 2026-11-07T12:00Z (e4b-v002 repeat / e4b-v003 if packed+reviewed+smoke / 31b-v002 repeat).
  Item 6: arm E/F results files schema-headed (plan005_armE_vs_D.json has _schema); dec 038 paper evidence by Nov 9 23:59Z.
- 31b-v004 CPU DRAFT: dist/31b-v004.zip sha256=50537e1ddcf13f160fcaa9b2bfa145ac13ef91d99a2ce0b27d69f54ee125f7b3 (5f9b4ae) = v007 +
  1 quoting/no-repeat line. No slot (dec 061 ii). Review 043840: no BLOCKING; NB2 pipefail system.md:33 -> fold in next touch, UNSCREENED;
  NB3 timeout empty patch unguaranteed (dec 056 item 6).
- DEC 057: no new bundle/draft carries any repo-named hint; dec 055 v002 untouched. e4b-v003 = e4b-v002 + generic prompt fixes
  minus the FastAPI line (CPU draft). Reports MUST state v000-v002 (both tracks) carry the hint; LB scores may tilt FastAPI-ward.
## Quota / spend
- GCP $0 (project gemma-agent-839566; only l4x1 spot + cpu8 usable, dec 003). Owner policy: Kaggle first (dec 001). Kaggle GPU this week: 16.02/30 h per `kaggle quota` ~06:27Z after arm F (+1.53). Log: ops/budget/kaggle.md. Resets 2026-11-07T00:00Z.
## Live caveats
- Standing: kernel Dockerfile.public only, no PIP_*, setup_calls logged (dec 027); -light = waiters/asks/reviews (dec 024); LORO weak (dec 014). - DEC 038 (paper, due Nov 12; evidence by Nov 9 23:59Z): (1) DONE results/failure_taxonomy_e4b_v001_v5.json (timeout 4, ok 2, ctx-ovf 1, test-edit 1);
  (2) results/kaggle_timing_e4b_v001.NOTE.md DONE (still add decision_note to JSON at probes merge); (3) e4b-v002 LB score -> schema-headed
  results file (score, submit/complete ts, sha); (4) report 010 results files schema-headed. Paper cites only files. Never edit paper/.
- Director reminder 2026-11-06T23:02Z: GCP quota re-request line to Aniket (keep until a decision marks it done).
- Any Kaggle GPU kernel must pin the starter docker_image (py3.12, cp312 wheelhouse). Hosted-LLM-API data question OPEN; no new 3rd-party services. One pending Kaggle submission at a time; no partial credit on timeout (docs/RULES_FINDINGS.md).
## Timing facts (results/kaggle_timing_e4b_v000_setup.json) setup ~210 s/task, outside max_time_minutes (clock starts after setup); flat across repos. vLLM startup 5.39 min;
  verification ~410 s (excluded from the 12 h). Agent clock p90 144 s at cap 5.
## Open decisions / instructions in force
- Dec 022 interim timing rule (cap+S)x125+30<=660; item 4 (truncation-safe diff, hygiene, trimming) pending = dec 032 item 8. Forum (dec 035): Builder posts nothing.
## Dec 034 (report 009 ruled: option C with gated step-up) — in force
- 31b-v001-t4 (dec 036 item 2 name; dir bundles/31b/v001) = TIMING bundle (cap 4.0, max_output_tokens 8192 x2): dist/31b-v001.zip sha256=3c3a264652ab1d72ff6b9c5609c482c34a2ab7af37eb600689e5cfa0bf810f6a,
  pack PASS, load check results/bundle_load_check_31b_v001.json (8192/8192, 240 s). NOT a submission candidate.
- Timing kernel (plan 006 DONE, G1 held -> dec 055): stack main 2db5f51 per Addendum A (gate fix from 92a74c7, worktree
  gemma-wt/codex-kernel-probes-gate). Summary: timing_summary.py --gate-mode stock-path --gate-vllm-seconds 600. Slug/push: ops/budget/kaggle.md.
- Gates for that run: (a) 8/8 no harness error; (b) max(Phase-1 - emulation) <= 277 s; (d) vLLM <= 600 s; (e) >= 1 non-empty diff.
- FINALS RULE: no final with cap > H3 bound (31B 1.23, e4b 1.0) unless a same-or-higher cap, same model, has SCORED on the real scorer. Plan slots so each track is validated well before Nov 29.
- OPEN (dec 034 item 6 / dec 058 item 7): plan 007 must pre-register which env the local sandbox models (H1: scorer site-packages test deps).
## Next 3
1. Smoke done -> seal hashes -> blind gate -> (HOLD) push main ids 4..33 sized to quota/23:30Z; seal + journal; quota before/after.
2. Fold done -> review + tests + merge + ONE re-freeze -> report 016 NEEDS_DECISION. Dec 055 31b-v002 submit at 11-07T00:00Z FIRST.
3. Nov 8 slot proposal (due 11-07T12:00Z); dec 038 paper evidence by Nov 9.
