DECISION: approve
SUBMIT: none
GPU_ALLOWANCE: none
ESCALATE: none
DIGEST: Shelved a planned tool-level fix after the data showed it had almost nothing to target; the time-budget experiment stays the main line.
---
Option A approved, and C stays as the follow-up. Spot-check: results/plan011_diag_arm3_main.json counts resolved 10 / empty_timeout 16 / patch_timeout 2 / patch_wrong 3 = 31, and results/plan011_diag_arm3_smoke.json has empty_timeout 2. Total: 18 empties, all timeouts, with no non-timeout empty class. This matches report 023.

1. SHELVE the dec 081 item-5 / dec 089 item-6 tool-level empty-patch lever (tolerant edit helper plus budget signal) for the v012 lineage. No plan 011 arm and no quota spent on it. Its target mechanisms (malformed edit_file, call exhaustion) total 1/33 on v012, below the pre-registered threshold of 3. Move the idea into ops/backlog-prompt.md with a pointer to report 023.
2. Before arm 4 runs, append a PRE-DATA addendum to eval/plans/010.md: after arm 4 lands, re-run eval/plan011_empty_diag.py on the arm-4 main and smoke rows, descriptively. Rule: if non-timeout empties attributable to edit failure or call exhaustion are >= 3/33 (overlap rows count, as in report 023), bring a plan 011 proposal. Otherwise the lever stays shelved. Before that reuse, fix the script's non-blocking items (exact-byte empty predicate, inventory validation, `empty_edit_failed` checking response success) and get a -light codex review CLEAN. Commit the addendum before any arm-4 data exists.
3. Option C (a further knob-only time cut, e.g. analyzer thinking <= 2048 or main lower) is NOT pre-registered yet. Propose it in the arm-4 report only if arm 4 still shows timeouts as the dominant empty mechanism. It must stay a dec 087 (b) knob-only diff against a COMPLETE bundle.
4. No change to priorities. (a) Tonight: the Nov 8 v012 submission per dec 089 and its checklist. The waiter fires 00:00:30Z. On ERROR or timeout: VOID, mail me at once. (b) Nov 9: e4b-v002h per dec 084/089 item 5 (reverse the SUBMIT_KERNEL commit and recheck the kernel first). (c) THE SINGLE MOST IMPORTANT NEXT EXPERIMENT is still plan 010 arm 4 (v014 = v012 + thinking 2048), smoke+main with the week-of-11-14 quota, paired against arm 3 on the same 33 ids.
5. Until then, keep CPU work light and pre-data only. Don't start new arms.

Reasoning: the pre-registered rule was set before tallying and it fails cleanly. All 18 empties are clock-outs with 0 edits, and 7 of them made <= 10 calls in 210 s, so the sink is generation time and not tool friction. Spending ~9.7 h of quota on a lever with ~1 target row couldn't separate from ±3 noise, and as a prompt/tool change it would also need its own scored slot. Plan 010 attacks the actual mechanism and stays finals-eligible without a slot. Shelving is free and reversible, and item 2's re-check lets the lever come back if arm 4 changes the empty mix.
