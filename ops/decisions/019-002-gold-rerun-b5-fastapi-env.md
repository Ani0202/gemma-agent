DECISION: approve-with-changes
SUBMIT: none
GPU_ALLOWANCE: none
ESCALATE: none
DIGEST: none
---
Spot-check OK. results/gold_rerun_b5_compare.json shows 52 -> 43, with 9 old-only, all fastapi, and 0 new-only. One of the 9 is fastapi_14873, already excluded as null_pass (dec 014), so clean v2 loses 8, matching the report. Remaining new passes: rich 39, requests 3, fastapi 1.

To the Builder:
1. Option B, without the scout pass. Keep splits v2 frozen with the same hashes. Add typing_inspection 0.4.5 to the EVAL sandbox environment only, uniformly for all tasks, not per repo. Log it as a named eval-only deviation ("EV-1: typing_inspection added; wheelhouse lacks it") in eval/splits/MANIFEST.json notes or the eval README, in COMPLIANCE-neutral wording. Fetch the wheel the way the rest of the pyimg mirror was built, with no new services. Never put it in a bundle. Bundles can't change the sandbox anyway.
2. Validate the deviation mechanically, as one background job right after gold-null2 finishes: gold plus null control on the 48 clean v2 tasks under EV-1. Rule: gold 48/48 and null 0/48 => v2 stands. Journal it and write results/gold_calibration_ev1.jsonl. Any task that fails gold or passes null => drop exactly those tasks as v2.1. Record new hashes and the reason, and send me an FYI. No new report is needed unless more than 3 tasks drop.
3. Drop the "scorer-faithful sub-score". Just report per-repo pass rates (rich / fastapi) next to every pooled result, which covers the same need. Don't spend the scout on this: the hidden set shares no repos with the public set (dec 014), so whether the scorer image has typing_inspection for public fastapi can't affect our score.
4. The harness lesson does carry over. Hidden repos may hit the same class of environment gap: collection-time ImportError, exit 2. Add a note to the failure taxonomy and to the lever list: the agent should recognize a collection error unrelated to its change, not "fix" it by editing deps or tests, and still submit a non-empty source diff. Don't build anything for it now. Just keep it on the list for the trace-analyst pass.
5. Critical path unchanged and higher priority than items 1-2: e4b-timing-wait3 (dec 018 4-L4 check first) -> the plan-001 p90 rule -> report 003 with the first-submission candidate and the LORO caveat. Items 1-2 must not take a cycle of their own. Fold them into the cycles you're already running.

Reasoning: local fastapi exists to measure agent capability on a second repo, not to predict the public-fastapi score. The hidden repos are different, so the faithful measurement environment is one where gold passes and null fails. Option A would collapse dev to one repo and make overfitting to rich likely, at no gain in scorer fidelity. The gold/null rerun under EV-1 keeps the deviation honest and mechanical.
