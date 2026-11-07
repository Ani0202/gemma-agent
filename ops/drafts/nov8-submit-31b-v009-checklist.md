# Nov 8+ submit checklist: 31b-v009 (dec 083 item 1). Run IN ORDER at submit time; any FAIL voids the authorization.
a. `kaggle competitions submissions` right before submitting: 58072907 FINAL COMPLETE with a public score (any value). ERROR/timeout -> VOID, CAP-BOUND binds, mail Director AT ONCE.
   (First, dec 079 item 2: fill results/lb_31b_v002.json, mail T / status / score.)
b. UTC date >= 2026-11-08, NO pending submission on Kaggle. Ledger: no submit today. Never stack.
c. Gate 2: codex review of dist/31b-v009.zip as a submission candidate, no BLOCKING (job review-31b-v009-submit-light).
   RESULT 06:36Z: review-20261107T063339 BLOCKING 1 (empty diff on timeout/cap) -> (c) FAILS unless Director waives (report 022). DO NOT SUBMIT without a decision on 022.
   DEC 084 item 1: BLOCKING item WAIVED for sha d38c55c7...130d -> (c) PASSES. Journal the waiver line together with the Gate-4 line (d) BEFORE submitting.
   STATUS: (c) PASS by waiver, dec 084 item 1 / dec 085.
d. Gate 4 journal line BEFORE submit: "cap 3.5; H1/H2 bound (210+7+30)/60*125+30 = 544.6 <= 660 (eval_config comment); H3 943.8 waived by (a) under the FINALS RULE: same model, same cap as scored 31b-v002; v002 root thinking 4096 vs v009 0 -> v009 no slower per turn."
e. SUBMIT_KERNEL=aniket0202/gemma-submit-31b (already; no config change). Kernel v2 output BYTE_IDENTICAL to dist/31b-v009.zip (results/submit_kernel_v2_verify.txt). Journal the kernel version.
   Command: bin/kaggle-submit dist/31b-v009.zip 31b "sha:d38c55c79103 31b-v009 cap3.5 hint-free (dec 083)" 2
f. After: results/lb_31b_v009.json (lb_submission_v1, copy lb_31b_v002.json layout) + -light waiter -> results/lb_31b_v009.polls.csv.
   Write-up: first hint-free 31B on the scorer; local 4/33 (ENV CONTROL caveat); v002 vs v009 public = one noisy sample each, do not act on the difference.
   Write-up MUST include (dec 085 item 2): "empty-patch rate 12/33 locally (ENV CONTROL caveat), same mechanism as v002".
