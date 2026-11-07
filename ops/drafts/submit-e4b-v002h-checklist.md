# Submit checklist: e4b-v002h (dec 084 item 3). AUTHORIZED, CONDITIONAL. Run IN ORDER; any FAIL = do not submit that day.
Bundle dist/e4b-v002h.zip sha256=938d618ceaeb7602d86e49a9cf7d2b7ce7191e8936d9520bb7d005a6c5f04836 track=e4b.
Day = FIRST UTC day on which ALL hold:
a. `kaggle competitions submissions`: nothing PENDING, no other submission this UTC day (ledger too). Never stack.
b. EITHER 31b-v009 auth VOID (58072907 ERROR/timeout -> mail Director AT ONCE; then e4b-v002h may take the Nov 8 slot),
   OR 31b-v009 already submitted on an EARLIER UTC day and no longer pending. Otherwise 31B gets the earlier slot: wait.
c. Immediately before submit: reverse config commit
     sed -i 's#^SUBMIT_KERNEL=.*#SUBMIT_KERNEL=aniket0202/gemma-submit-e4b#' config.env; git commit -m "config: SUBMIT_KERNEL=aniket0202/gemma-submit-e4b for e4b-v002h (dec 084)"
   e4b kernel: v2 already pushed 06:34:57Z on 11-07 with output BYTE_IDENTICAL (results/submit_kernel_v2_verify.txt). Re-download its
   output and re-check the sha right before submitting (re-push only if the output is unavailable; then use the new version). Journal the kernel version.
d. Gate-4 journal line: "cap 1.0; (cap+S)x125+30 = 619.4 <= 660; same cap/model as scored e4b-v002 (T=5.007 h)".
e. Command: bin/kaggle-submit dist/e4b-v002h.zip e4b "sha:938d618ceaeb e4b-v002h cap1.0 hint-free (dec 084)" <kernel version>
f. After: results/lb_e4b_v002h.json (lb_submission_v1, layout as lb_e4b_v002.json) + -light waiter -> results/lb_e4b_v002h.polls.csv.
   Write-up: identical to e4b-v002 (public 0.05) except the hint line; score delta vs v002 = one noisy sample each, do not act on it.
   Then a config commit back to SUBMIT_KERNEL=aniket0202/gemma-submit-31b only when a 31B submit is next authorized.
