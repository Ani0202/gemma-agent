DECISION: approve-with-changes
SUBMIT: none
GPU_ALLOWANCE: none
ESCALATE: none
DIGEST: none
---
Option A approved: no rerun, no rev 6, classifier d4cdf0f0 stays frozen and governing. I checked the file: timing.jsonl sha 76bd2483… matches, and rich_3063 has resolved=False, exit_code=1, verified_patch_bytes=0, empty_patch=True, result_error=None. The H-VERIFY comes from the `patch_bytes == 0 and code not in (None, -1)` clause (classify_rows.py ~l.239). That rule is a false-positive assumption, not a kernel defect. The primary is unchanged: stock resolved=False counts as FAIL.

1. Pre-register the sub-case NOW, before the main outputs download. Append an addendum to eval/plans/007.md, then commit and journal it with a UTC time earlier than the main download time. The addendum defines "H-VERIFY(empty-patch)" exactly: d4cdf0f0 h == H-VERIFY with reasons == ['verify:contradictory_failure_evidence'] only, verified_patch_bytes == 0, exit_code an int not in (0, -1), resolved is False, result_error/agent_error_text null or empty, and no patch-apply or verify-failure message. Any H row that doesn't match this definition exactly stays under the plan's existing H-row rule (reruns only after a documented defect fix). Write the definition as a small pure function plus a test. It lives in the report script, NOT in classify_rows.py.
2. Report layout for plan-007 arm 1: (a) the primary, stock resolved=True over all rows, with Wilson CI and a per-repo breakdown; (b) governing d4cdf0f0 class counts as-is; (c) sensitivity line 1, excluding all H rows; (d) sensitivity line 2, excluding H rows other than H-VERIFY(empty-patch); (e) a208a023 counts alongside. Footnote the l.89 assumption once.
3. Report the empty-patch rate prominently as its own headline metric: the count and share of rows with verified_patch_bytes == 0, with Wilson CI, split into timeout and non-timeout cases. rich_3063 submitted an empty patch after 40 turns with 82 s of agent clock still unused. That's a lever-1 failure (always yield a non-empty source diff), and it's likely the cheapest next fix. For each empty-patch row in main, list the turn count and tool-call mix, but don't analyse beyond that until the main report.
4. Nothing about main or chunk 2 changes. Priorities are unchanged: the dec 055 31b-v002 submit at 2026-11-07T00:00Z comes first; the Nov 8 slot proposal is due 2026-11-07T12:00Z; dec 038 evidence is due by Nov 9 23:59Z.

Reasoning: a rerun is deterministic and changes nothing, and rev 6 is ruled out. The only real risk is that a post-unblinding reinterpretation gets fitted to main's results. Item 1 closes that by fixing the sub-case definition before main is seen. Empty patches are both a classifier artefact and a real agent failure mode, so they get measured, not buried.
