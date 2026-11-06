# STATE: snapshot 2026-11-06 05:27Z (cycle 113, Phase 0). Rewrite each cycle, ≤80 lines (dec 017).
History: ops/journal.md (pre-c51: ops/history/STATE-archive.md). Builder on Opus (dec 010: local-first, two-strike).
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
- No local pass-rate scores yet. eval-runner-fix MERGED 70c0d9f (421 pass, 3 skip). Test cmd: /home/ubuntu/gemma-local/venv/bin/python3 with pyimg cp3.13 site-packages appended to sys.path, pytest eval/tests.
## Eval data
- Splits v2 FROZEN: clean 48 (rich 39, fastapi 9), dev 33, holdout 15; holdout uses = 0. Hashes: eval/splits/MANIFEST.json.
- requests/httpx dropped (wheel shadowing = scorer property, dec 014). Gold v2 files in results/ (gold_calibration_*, gold_failure_causes).
## Re-grounding check (EVERY cycle, dec 021 item 1e + dec 025 item 2)
- Linger (dec 025): `loginctl show-user "$(id -un)" -p Linger --value` must be `yes`, else tell Director. After NEXT reboot once: `systemctl --user list-units --type=service --state=running` names only; report non-ours units, never touch (may be Etho).
- Watchdog must be running: `bin/job status memguard-light` (fix6 deployed 23:37Z; stop = bin/job kill); if dead: `bin/job start memguard-light -- bin/memguard` (dec 024: always -light). Heavy jobs one at a time (waiters/memguard/codex exempt). Check `tail ops/logs/memguard.log` for KILL lines. No heavy job unless memguard runs.
- DEC 060 (on c109 FYI): v004 full-arm-B-prompt deviation ACCEPTED provisionally. Arm-E report MUST: (a) list every byte diff v004 vs v002
  (prompt sections, thinking_budget, cap, quoting line) + which are screened; (b) describe minimal alt, DON'T pack unless asked; (c) label
  quoting line UNSCREENED (covered only by later paired v004-vs-v002). Item 2: dec 059 last line superseded; Nov 7 31B submit write-up
  must note v002 LB = ONLY result carrying the FastAPI hint caveat. Item 3: repeat metric added to plan 007 (Addendum). Priority unchanged.
## Running jobs (05:27Z): review-p5e-light (codex review of report 014 + eval/plan005_armE_compare.py, aa192f6), memguard-light,
  submit-window-31b-light (fires 11-07T00:00:30Z). Arm E DONE: verdict CAP-BOUND (V; empty 5/8 > 4; D-only/E-only non-empty 2/0, p2 0.5;
  timeouts 2->5, all timeouts empty). dec 056 item 6 = binding blocker for 31B final at cap<=1.23. results/plan005_armE_vs_D.json.
  New post-hoc finding: identical-tool-call loops (rich_3067 17x same failing edit_file in E despite no-repeat rule). Report 014 drafted,
  NOT yet sent: send `Decision needed` after review CLEAN (fix any BLOCKING first). Recommends A (wait v002 LB) + B (anti-loop arm F next week).
- DEC 059 (on report 013): B approved. ARM E = 31b-v007-p5e (bundles/31b/v007, dist/31b-v007.zip 3a62f41fa5417ee5b129e845296c5a8e44d496f1d22501d5b3a4b29667be3c6f,
  v006 + cap 1.23 only; light review-20261106T043550 no BLOCKING). Addendum E rule: not V -> INVALID; V & E empty<=4/8 & E-empty-only(vs D)<=2
  -> USABLE; else CAP-BOUND. Analysis DONE c113 (report 014).
- 31b-v004 CPU DRAFT (dec 059 item 1): dist/31b-v004.zip sha256=50537e1ddcf13f160fcaa9b2bfa145ac13ef91d99a2ce0b27d69f54ee125f7b3 (5f9b4ae) =
  v007 + 1 quoting/no-repeat line (v002 + thinking 0 + plan-005 prompt + cap 1.23). DEVIATION from literal item 1 (full arm-B prompt kept)
  -> argue in arm-E report, offer minimal alt. No slot until v002 LB exists; v004 vs repeat-v002 needs paired evidence. Correction sent:
  arms B-E have no FastAPI line (dec 057 caveat = v000-v002 only).
- codex-review v004 DONE (ops/codex/review-20261106T043840.md): BLOCKING none (not submission clearance). NB1 = dec 060 deviation (in report 014);
  NB2 system.md:33 `python3 ... | tail` lacks pipefail (inherited from arm B/E prompt) -> list in report 014 as unscreened candidate, v004 NOT repacked;
  NB3 timeout empty patch unguaranteed (dec 056 item 6). Cap 1.23 = zero margin under S assumptions. Full compiler validation blocked by sandbox.
- Arm D DONE (report 013, PASS). Push cmd (dec 058): eval/kaggle/timing_push.sh aniket0202/gemma-31b-timing <bundle> eval/plans/004-gpu-retime-ids.txt 6000.
- DEC 057 (FastAPI/docs_src hint): dec 055 UNCHANGED (don't touch 31b-v002/zip/kernel). Standing rule: no new bundle/draft carries any
  repo-named hint (31b-v004+, e4b-v003+, drafts). v004 diff vs v002 = prompts/system.md + MANIFEST only, and MUST remove the line.
  bundles/drafts/item4-system.md line REMOVED (c104). FINALS: no final with a repo-specific line -> e4b-v003 = e4b-v002 + generic
  prompt fixes minus the line, CPU draft folded into dec 056 item 5; slot request later. Next report MUST state: v000-v002 (both tracks)
  carry an inherited FastAPI/docs_src hint; their LB scores may be tilted toward FastAPI-like tasks (paper + finals evidence say so).
## Quota / spend
- GCP $0 (project gemma-agent-839566; only l4x1 spot + cpu8 usable, dec 003). Owner policy: Kaggle first (dec 001).
- Kaggle GPU this week: 14.49/30 h per `kaggle quota` 05:23Z after arm E (+1.40). Log: ops/budget/kaggle.md. Resets 2026-11-07T00:00Z.
## Live caveats
- Standing: kernel Dockerfile.public only, no PIP_*, setup_calls logged (dec 027); -light = waiters/asks/reviews (dec 024); LORO weak (dec 014).
- DEC 038 (paper, due Nov 12; evidence by Nov 9 23:59Z): (1) DONE results/failure_taxonomy_e4b_v001_v5.json (timeout 4, ok 2, ctx-ovf 1, test-edit 1);
  (2) results/kaggle_timing_e4b_v001.NOTE.md DONE (still add decision_note to JSON at probes merge); (3) e4b-v002 LB score -> schema-headed
  results file (score, submit/complete ts, sha); (4) report 010 results files schema-headed. Paper cites only files. Never edit paper/.
- Director reminder 2026-11-06T23:02Z: GCP quota re-request line to Aniket (keep until a decision marks it done).
- Any Kaggle GPU kernel must pin the starter docker_image (py3.12, cp312 wheelhouse). Hosted-LLM-API data question OPEN; no new 3rd-party services. One pending Kaggle submission at a time; no partial credit on timeout (docs/RULES_FINDINGS.md).
## Timing facts (results/kaggle_timing_e4b_v000_setup.json) setup ~210 s/task, outside max_time_minutes (clock starts after setup); flat across repos. vLLM startup 5.39 min;
  verification ~410 s (excluded from the 12 h). Agent clock p90 144 s at cap 5.
## Open decisions / instructions in force
- Dec 022: interim timing rule (cap + S) x125 + 30 <= 660 (S now per dec 034 hypotheses). Item 4 (truncation-safe diff, patch hygiene, tool-output trimming) pending = dec 032 item 8.
- Dec 020 item 7 / dec 019 item 2: EV-1 (typing_inspection 0.4.5 eval-only, NOT yet implemented) + gold/null on 48 clean, on a cpu8 VM via bin/gpu (<=$3, <=3 h), after the sandbox-limits merge. Dec 019 items 3-4 (per-repo rates; collection-error note) to fold in.

## Dec 034 (report 009 ruled: option C with gated step-up) — in force
- 31b-v001-t4 (dec 036 item 2 name; dir bundles/31b/v001) = TIMING bundle (cap 4.0, max_output_tokens 8192 x2): dist/31b-v001.zip sha256=3c3a264652ab1d72ff6b9c5609c482c34a2ab7af37eb600689e5cfa0bf810f6a,
  pack PASS, load check results/bundle_load_check_31b_v001.json (8192/8192, 240 s). NOT a submission candidate.
- Timing kernel (plan 006 DONE, G1 held -> dec 055): stack main 2db5f51 per Addendum A (gate fix from 92a74c7, worktree
  gemma-wt/codex-kernel-probes-gate). Summary: timing_summary.py --gate-mode stock-path --gate-vllm-seconds 600. Slug/push: ops/budget/kaggle.md.
- Gates for that run: (a) 8/8 no harness error; (b) max(Phase-1 - emulation) <= 277 s; (d) vLLM <= 600 s; (e) >= 1 non-empty diff.
- FINALS RULE: no final with cap > H3 bound (31B 1.23, e4b 1.0) unless a same-or-higher cap, same model, has SCORED on the real scorer. Plan slots so each track is validated well before Nov 29.
- Forum question (dec 035): Aniket posts report 009 s6; Builder posts NOTHING; summarize any answer (no task data) in next report.
- OPEN (dec 034 item 6 / dec 058 item 7): plan 007 must pre-register which env the local sandbox models (H1: scorer site-packages test deps).
## Next 3
1. review-p5e-light done -> fix BLOCKING (if any) -> NEEDS_DECISION report 014 + bin/send director.
2. Dec 055 at 2026-11-07T00:00Z FIRST: (2)(3) hold; re-check (2) live, do (4) commit, (5) journal T=5.007 h <= 6.0 PASS, then submit.
3. Pre-register arm F (anti-loop, generic) for after reset; Dec 038 paper evidence by Nov 9 23:59Z; plan 007 pre-reg.
