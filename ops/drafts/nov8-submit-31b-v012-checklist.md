# Nov 8 submit checklist: 31b-v012 (dec 089 item 2). Run IN ORDER at submit time; any FAIL voids the authorization -> FALLBACK item 4 (v009 under dec 083, ops/drafts/nov8-submit-31b-v009-checklist.md) + mail Director.
Bundle: dist/31b-v012.zip sha256=78a8fd30389ec3acf58b44bc8743d750b496041f5c8d2b35790f0d913130ede5 track=31b (bundles/31b/v012).
DEADLINE: conditions (b)-(e) met by 2026-11-07T23:45Z, else item 4 fallback.
a. 58072907 (31b-v002) FINAL COMPLETE, public 0.15. STATUS: MET (results/lb_31b_v002.json). Re-run `kaggle competitions submissions` right before submitting:
   UTC date >= 2026-11-08, NO pending submission, ledger has no submit today, never stack.
b. Gate 2: job review-31b-v012-submit-light (codex review 20261107T112341). NO BLOCKING except a finding equivalent to the v009
   "empty diff on timeout/cap" BLOCKING (review 063339), which dec 089 item 2b waives for sha 78a8fd30 only. Any OTHER BLOCKING -> NO v012 submit, item 4, mail Director.
   STATUS: PENDING.
c. Gate 1/4: bin/pack bundles/31b/v012 PASS (2026-11-07T11:26Z, 9070 B; unzip == source minus MANIFEST). sha recorded in bundles/31b/v012/MANIFEST.md (yes).
   Timing bound: cap 3.5 -> 3.5x125+30 = 467.5 <= 660 (dec 089); H1/H2 (210+7+30)/60*125+30 = 544.6 <= 660 (eval_config comment).
   Gate-4 journal line BEFORE submit: "Gate 4 31b-v012: cap 3.5; 3.5x125+30=467.5<=660; H1/H2 544.6<=660; H3 waived by dec 086 (v002 COMPLETE at cap 3.5, thinking 4096 main+analyzer = v012 config, T=9.006 h); Gate-2 empty-diff waiver dec 089 2b."
   STATUS: pack PASS; journal line due at submit time.
d. Submit kernel aniket0202/gemma-submit-31b NEW version with v012 output BYTE_IDENTICAL (job submit-kernel-v012-verify-light -> results/submit_kernel_v012_verify.txt).
   SUBMIT_KERNEL stays 31b (no config change). v2 (= v009) stays available for the fallback (guard takes an explicit version).
   STATUS: MET 2026-11-07T11:27:11Z: kernel v3 output BYTE_IDENTICAL (results/submit_kernel_v012_verify.txt). Journal kernel v3 at submit.
   Command: bin/kaggle-submit dist/31b-v012.zip 31b "31b-v012 cap3.5 think4096 (dec 089)" 3   (guard prefixes sha:<12>)
e. Window waiter: submit-window-nov8-v012-light (restarted 11:26:57Z with the v012 sha; old submit-window-nov8-light killed). Guard NOT edited.
f. After: results/lb_31b_v012.json (lb_submission_v1, copy lb_31b_v002.json layout) + -light waiter -> results/lb_31b_v012.polls.csv.
   Write-up MUST say: plan 009 arm 3 verdict ON-BETTER-VETOED (10/33 vs 4/33, 6/0 p=.031); 21/33 local timeouts, 18/33 empty diffs (ENV CONTROL caveat);
   carries the dec 089 empty-diff-on-timeout waiver; submitted to measure scorer runtime at thinking 4096 main+analyzer, cap 3.5.
   If ERROR or timeout: VOID, mail Director AT ONCE; v012 NOT finals-eligible at thinking 4096.
   On COMPLETE: run eval/finals_eligibility.py v009 vs v012 (dec 089 item 3; expect ELIGIBLE: thinking main 0 <= 4096 only).
g. On a v012 submit the dec 083 v009 authorization LAPSES (dec 089 item 3). e4b-v002h stays Nov 9 (dec 089 item 5; reverse SUBMIT_KERNEL commit + kernel recheck first).
