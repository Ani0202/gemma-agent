# STATE: snapshot 2026-11-07 06:31Z (cycle 177; dec 082 approve, Nov 8 proposal SENT early). Rewrite each cycle, ≤80 lines (dec 017). History: ops/journal.md.
## Best bundles (none validated; runtime budget still unverified, codex BLOCKING)
- v000 (repo a12f0b7, static OK): 31b dist/31b-v000.zip 4a23e14a...efae161; e4b dist/e4b-v000.zip cc647bfb...6940e2
- e4b-v002 (v001 + cap 1.0 + max_output_tokens 8192 x2): dist/e4b-v002.zip sha256=60c0074684ef4f9aa9cd8744d08fa29a37f3b94fc893541a8b96ceed54944dad
  SUBMITTED 2026-11-06T00:11:23Z ref 58039259; SCORED public 0.05 (COMPLETE; first final poll 05:11:49Z, T=5.007 h). results/lb_e4b_v002.json filled,
  budget row updated, Director FYI'd. No runtime fields from CLI. E4B validator acceptance VERIFIED. Next e4b submit: next UTC day at earliest. Guard v6 applied b9caae4 (dry checks rc=3 x2).
- 31b-v002 (v001-t4 + cap 3.5): dist/31b-v002.zip sha256=e56a05e5701fa16a8dbbabb304d98f63a465511cefbb28d65850ea5ce086ec88
  SUBMITTED 2026-11-07T00:06:31Z ref 58072907 (dec 055 ALL conds held: window open; e4b COMPLETE 0.05; T=5.007 h <= 6.0 PASS;
  config commit cefb420 SUBMIT_KERNEL=aniket0202/gemma-submit-31b, kernel v1; veto journaled pre-submit). results/lb_31b_v002.json (PENDING);
  waiter lb-31b-v002-wait-light -> results/lb_31b_v002.polls.csv. On final: fill json (status, score, completed window), budget row, Director FYI.
  Validation submit: expect weak LB, don't act alone; write-up notes FastAPI-hint caveat (dec 060). config.env SUBMIT_KERNEL now = 31b kernel:
  next e4b submit needs the reverse config commit first. Next submit slot: 2026-11-08 UTC (ledger blocks same-day).
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
- DEC 079: approve, nothing changes. On v002 final mail Director T (first final poll - 00:06:31Z), exact status, public score; fill json.
  ERROR/timeout -> mail AT ONCE before any slot. Nov 8 default if PENDING at 12:00Z = e4b-v002 repeat. Dec 038 files rechecked OK 00:13Z.
## Running jobs (06:30Z): memguard-light, lb-31b-v002-wait-light (PENDING 06:06Z), passrate-31b-v012-main-wait-light (kernel v5 pushed 06:27:20Z -> runs/31b-v012-p9a-main, sealed on download).
- CODEX S81: review 060833 BLOCKING 1 (base stray evidence missing could still ON-ADOPT) -> fixed 71185a3 (safety_checks(): both arms need
  available stray evidence, zero governing for arm 3 only; +5 tests incl. unrounded wall-p90 gate; 1624 pass). Re-review s81b ops/codex/review-20261107T061229.md CLEAN (no blocking) -> arm-3 metrics allowed. Report must list amended arm-2 counts separately (S81.3).
- DEC 081 (on 020, approve A w/ changes): (1) arm-3 SMOKE (v4) PASS results/plan009_arm3_smoke.json: thinking blocks [5,10]=15, timing PASS,
  0 H (d4cdf0f0 results/plan009_arm3_smoke_d4cdf0f0.json; a208a023 alongside 0 H), identity OK; both rows NO_PATCH/timeout (descriptive). Quota
  smoke +0.63 h (11.89 AFTER). identity --event main PASS 06:26:50Z. MAIN pushed v5 06:27:20Z: 31 ids eval/plans/009-main-ids.txt, ONE session,
  budget 30000 s, seed-max 803, TRANSPORT 203e542b (dry-run == smoke), quota BEFORE 11.89 h. On land: quota AFTER + budget row; classify main
  (PYTHONPATH=eval/kaggle python3 eval/plan007_pinned/classify_rows_d4cdf0f0.py TIMING --out ...; also a208a023); plan008_metrics.py arm3
  (dirs smoke,main; --identity-json --bundle v012 --transport DIR=203e542b.. --push-event DIR=smoke|main --smoke-json results/plan009_arm3_smoke.json
  [--base-verdict-json]); report with amended arm-2 stray counts listed separately (S81.3). Missing ids -> D73.7 rule.
  (2-4) Addendum S81 f9a9562 PRE-DATA; code eda02a4+71185a3; codex s81b 061229 CLEAN. Pre-data rows: arm1 gov 0/lit 0, arm2 gov 0/lit 1.
  (5) backlog: tool-level empty-patch lever plan (tolerant edit_file error + exploration budget signal) AFTER arm 3. (6) Nov 8 slot due 12:00Z.
- DEC 080/report 020: diagnosis results/plan008_arm2_diagnosis.md (stray row = deliberate deliverable; empties 7 never-edited, 3 malformed edit_file). Arm 2
  (report 019) 8/33 vs arm1 4/33, A-only 4/B-only 0 p=0.125, MECH1/2 FAIL -> NOT SHIP-ELIGIBLE; base = arm 1; 31B default draft stays v009. Files 4de6787.
  arm3 CLI: --identity-json --bundle --transport DIR=SHA --push-event DIR=EVENT (every dir) --smoke-json [--base-verdict-json]. Arm-3 bundle
  31b-v012-p9a dist/31b-v012.zip sha256=78a8fd30389ec3acf58b44bc8743d750b496041f5c8d2b35790f0d913130ede5 (v009+think 4096), load PASS (e5196a4).
- DEC 071 (gate approved w/ conditions): items 1-3 DONE 787b465. Plan 008 Addendum D71: wiring (a) YES same Context (gate alive),
  (b) scored = patch at submit call, else end-of-session workspace diff, (c) no name keying (keep name submit_patch), (d) gate counts:
  worst +3 calls/+7 turns. Smoke ids eval/plans/008-smoke-ids.txt (rule: first 2 non-timeout empty arm-1 rows) sha dcae5058...;
  smoke PASS = ALL of (i)-(v) per D71.2. Arm 2 = v010 iff smoke PASS else v011. FALLBACK 31b-v011-p8b dist/31b-v011.zip
  sha256=4f5b078a367e964ffb7d7426f4d42e13451d0c9dde79322c7fee5bd3a88f4938 (agent.yaml==v009, PROMPT-LEVEL), pack+load PASS.
- DEC 069 (rep 018, A w/ conditions): arm 1 VALID by POST-HOC ruling = plan 007 Addendum C (7ceb059). PRIMARY 4/33 FINAL
  (codex 132715 BLOCKING = missing descriptive lines -> fixed; re-review 133120 CLEAN). results/plan007_arm1_summary.json v2
  (script sha 349b1bda...): a 4/33 (W 4.8-27.3), c 4/26, d 4/27 (literal), d' 4/33, empty 12/33 (2 to/10 non), unscreened 3/25, ENV CONTROL caveat l.152 on every arm-1 citation.
- PLAN 008 / 31b-v010-p8 (dec 069 item 3 + DEC 070): pre-reg eval/plans/008.md (1169579). Feasibility: bundle callbacks silently dropped
  (no registry passed), so repeat guard = PROMPT-LEVEL (Option A text verbatim + edit 2-fail -> shorter anchor or /tmp script, NOT write_file);
  empty guard = dec 070 1(b) prompt rule + IN-BUNDLE agent_tool gate named submit_patch (shares Context; <=2 bounces). Both deviations
  accepted (dec 072). Ship rule: pass delta>=0 AND empty<=4/33 AND run>=5 tasks<=6/33 AND safety (submitted-without-test <= 23+3=26).
  Dec 070 item 5: arm-3 addendum must require smoke thinking blocks > 0.
- PLAN 007 PRE-REG eval/plans/007.md (e547980): arm 1 = 31b-v009-p7a1 (v006 + cap 3.5; dist/31b-v009.zip d38c55c7..., pack PASS),
  33 dev fixed order eval/plans/007-arm1-ids.txt, --with-verification --no-stock-probe, slug aniket0202/gemma-31b-passrate.
- DEC 061 (on report 014): approve-with-changes; (i) v002 ERROR/timeout -> CAP-BOUND binds; (ii) v004 CPU draft, no slot; (iii) done.
  Item 4: plan 007 pre-reg (33-dev pass rate; H1 env; thinking off vs on paired arm) DUE 2026-11-07T18:00Z (may use leftover quota pre-reset).
  Item 5: Nov 8 slot candidate + 1-para justification DUE 2026-11-07T12:00Z (e4b-v002 repeat / e4b-v003 if packed+reviewed+smoke / 31b-v002 repeat).
  Item 6: arm E/F results files schema-headed (plan005_armE_vs_D.json has _schema); dec 038 paper evidence by Nov 9 23:59Z.
- DEC 057: no new bundle carries a repo-named hint; v000-v002 (both tracks) carry the FastAPI hint -> reports must say so; LB may tilt FastAPI-ward. e4b-v003 = e4b-v002 + generic fixes minus that line (CPU draft).
  31b-v004 CPU DRAFT dist/31b-v004.zip 50537e1d... (v007 + quoting line), no slot (dec 061 ii); NB3 timeout empty patch unguaranteed (dec 056 item 6).
- GCP $0 (project gemma-agent-839566; only l4x1 spot + cpu8 usable, dec 003). Owner policy: Kaggle first (dec 001). Kaggle GPU week of 11-07: 11.89/30 h at 06:26Z (arm 2 + arm-3 smoke done; 18.11 h left; arm-3 main est ~11 h). Log: ops/budget/kaggle.md. Resets 2026-11-14T00:00Z.
## Live caveats (dec 078: no FYIs for routine clean reviews; dec 022 timing (cap+S)x125+30<=660; dec 032 item 8 pending; forum: Builder posts nothing, dec 035). Standing: kernel Dockerfile.public only, no PIP_*, setup_calls logged (dec 027); -light = waiters/asks/reviews (dec 024); LORO weak (dec 014). - DEC 038 (paper, due Nov 12; evidence by Nov 9 23:59Z): (1) DONE results/failure_taxonomy_e4b_v001_v5.json (timeout 4, ok 2, ctx-ovf 1, test-edit 1);
  (2) results/kaggle_timing_e4b_v001.NOTE.md DONE (still add decision_note to JSON at probes merge); (3) e4b-v002 LB score -> schema-headed
  results file (score, submit/complete ts, sha); (4) report 010 results files schema-headed. Paper cites only files. Never edit paper/.
- Director reminder 2026-11-06T23:02Z: GCP quota re-request line to Aniket (keep until a decision marks it done). Kaggle GPU kernels pin starter docker_image (py3.12, cp312). Hosted-LLM-API data Q OPEN; no new 3rd-party svc. One pending submission; no partial credit on timeout. Quota log before/after smoke+main (dec 063/064).
## Timing facts (results/kaggle_timing_e4b_v000_setup.json) setup ~210 s/task, outside max_time_minutes (clock starts after setup); flat across repos. vLLM startup 5.39 min; verification ~410 s (excluded from the 12 h). Agent clock p90 144 s at cap 5.
- 31b-v001-t4 = TIMING bundle (cap 4.0, out 8192x2) dist/31b-v001.zip 3c3a2646...0f6a, load check results/bundle_load_check_31b_v001.json. NOT a candidate.
- Timing kernel (plan 006 DONE, G1 held -> dec 055): stack main 2db5f51 per Addendum A (gate fix from 92a74c7, worktree
  gemma-wt/codex-kernel-probes-gate). Last FROZEN+noted classifier: a208a023 (0d49b1c); rev-5 d4cdf0f0 frozen pending Director note (report 016).
- FINALS RULE: no final with cap > H3 bound (31B 1.23, e4b 1.0) unless a same-or-higher cap, same model, has SCORED on the real scorer. Plan slots so each track is validated well before Nov 29.
- TOPICS (Director mail 01:47Z, owner req): docs/TOPICS.md saved; on any topic status change (used now | planned | adjacent, not used) update its line + repo ref in the same cycle as the journal entry.
- DEC 082 (approve, no reply): report 021 FIRST results table = pass rate + arm3-vs-arm1 TIMEOUT count + EMPTY count w/ paired discordants
  (not footnote). On land: quota AFTER + budget row FIRST, then classifiers/metrics per dec 081 i1; budget hit w/ missing ids -> D73.7, no top-up.
- Nov 8 proposal SENT 06:30Z ops/drafts/nov8-slot-proposal.md (PENDING/ERROR -> e4b-v002 repeat; SCORED>=0.10 -> 31b-v002 repeat). Awaiting SUBMIT decision.
## Next 3
1. On 31b-v002 final: fill results/lb_31b_v002.json + budget row + Director FYI (ERROR -> CAP-BOUND binds per dec 061 i); note which proposal row now applies.
2. On SUBMIT decision for Nov 8: (e4b) reverse SUBMIT_KERNEL config commit first, grep-journaled; never while 58072907 PENDING.
3. On arm-3 main land: quota/budget row, seal check, classifiers, arm3 metrics, report 021 (dec 082 item 1 table layout).
