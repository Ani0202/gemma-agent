# 022: Gate 2 for 31b-v009 has one BLOCKING finding (empty diff on timeout or cap). Nov 8 authorization (c) fails as it stands

## Question for the Director
Codex Gate-2 review `ops/codex/review-20261107T063339.md` names one BLOCKING finding for dist/31b-v009.zip. Every bundle can still yield an empty source diff on timeout or call/turn exhaustion. Dec 083 (c) needs "no BLOCKING", so the Nov 8 v009 authorization is VOID unless you explicitly waive the non-empty-diff requirement for this sha. Do you waive it (keeping v009 as the Nov 8 entry), or should I change the plan?

## Pre-registration
None. This is a gate result, not an experiment. Dec 083 item 1c set the decision rule before the review ran: any BLOCKING means no submit.

## What I did (HEAD after this cycle; review inputs at 64386d7)
- Gate 2 for 31b-v009 (job review-31b-v009-submit-light, done rc 0, 06:36:26Z). Scope as in dec 083 1c.
- Gate review for e4b-v002h (job review-e4b-v002h-light, done rc 0, 06:36:15Z): `ops/codex/review-20261107T063438.md`.
- Fixed the e4b-v002h MANIFEST grep claim (non-blocking; MANIFEST only, so the zip sha is unchanged at 938d618c and pack still PASSes).

## Results
| item | 31b-v009 (d38c55c7…) | e4b-v002h (938d618c…) |
|---|---|---|
| sha / member set / diff | PASS. Diff vs v002: sampling.yaml, eval_config comments, system.md; agent.yaml byte-identical | PASS. Exactly 1 deleted line vs e4b-v002 |
| pack | PASS (9,067 B) | PASS (6,375 B) |
| tests / scratch | PASS | PASS |
| timing arithmetic | PASS (544.6 ≤ 660; H3 943.8 waived via (a)) | PASS (unchanged from v002: 619.4 ≤ 660) |
| BLOCKING | **1: empty diff possible on timeout or cap** | 1: "authorization pending". This is a release gate, not an artifact defect |

Evidence behind the v009 blocker, all on this exact bundle and with the ENV CONTROL caveat (results/plan007_arm1_summary.json `headline_empty_patch`): 12/33 empty patches (36.4%, Wilson 22.2–53.4%). Of these, 2 were timeouts and 10 were not; 7 of those 10 called submit_patch on an empty diff. Codex also confirmed in memory that the installed harness returns an empty fallback patch for an unchanged workspace and accepts an empty submit_patch.

Context the review does not weigh:
- The property is shared by every bundle we have. That includes 31b-v002 (submitted, pending) and e4b-v002 (SCORED 0.05). Neither carries any mechanism that forces an edit. Arm 2's in-bundle submit gate (plan 008) did not fix it and is not ship-eligible (dec 080).
- An empty patch fails that one task. It does not fail the submission. The submission-level risk (timeout) is covered by (a) and Gate 4, not by this finding.
- The fix is the tool-level lever from dec 081 item 5 (tolerant edit_file error plus an exploration-budget signal). That lever is backlogged until after arm 3, which is running now (main pushed 06:27Z, est. ~11 h).

v009 non-blocking findings (I did not fix them, because changing the zip changes the sha and breaks the arm-1 link). They go into the next prompt revision:
1. system.md:35 suggests config edits are OK when config is the subject. Protected files such as pyproject.toml are stripped regardless.
2. system.md:11 recommends error-message keywords. The harness favours symbol names (keywords get only the lexical fallback).
3. MANIFEST "NOT a submission candidate": already updated at 06:35:33Z. The in-zip eval_config comment stays on purpose.

## Options
A. **Waive non-empty-diff for 31b-v009 sha d38c55c7 (Recommended).** Gate 2 then has no artifact defect and the rest of the dec 083 checklist runs unchanged at 00:00:30Z. Trade-off: we knowingly submit a ~36% empty-patch rate. v002 has the same rate, and the purpose is hint-free timing validation under the FINALS RULE.
B. **Void v009 for Nov 8 and use the slot for e4b-v002h.** This needs your authorization plus the reverse SUBMIT_KERNEL config commit (kernel v2 output already BYTE_IDENTICAL). e4b-v002h has the same empty-diff property, so its review would raise the same issue if scoped the same way. This mainly moves the E4B validation a day earlier.
C. **Hold both until a tool-level empty-diff fix exists.** Clean on paper, but it costs slots and validation time, and the fix needs plan, eval and GPU time after arm 3. No candidate would clear the bar for several days.

## Recommendation
A. Waive the non-empty-diff requirement for 31b-v009 sha256=d38c55c79103950d6d269a722bd0c9db9db22e1c0ec96be230f6c24a332d130d, with every other dec 083 condition unchanged. Under a waiver, the write-up would note "empty-patch rate 12/33 locally (ENV CONTROL caveat), same mechanism as v002". e4b-v002h: no artifact defect; awaiting your Nov 8/Nov 9 authorization per dec 083 item 2. Start the empty-diff tool-level plan right after the arm-3 report (dec 081 item 5).
