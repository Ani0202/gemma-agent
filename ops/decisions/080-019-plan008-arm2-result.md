DECISION: approve-with-changes
SUBMIT: none
GPU_ALLOWANCE: none
ESCALATE: none
DIGEST: The second guard experiment did not hit its targets and won't be adopted. A short CPU-only diagnosis comes next, then the thinking-on experiment.
---
I checked the numbers against the files. results/plan008_arm2_summary.json gives primary 8/33 vs 4/33, A-only 4 / B-only 0, p=0.125, and stray_files_rows=1 (met.stray=false). results/plan008_arm2.json totals give mechanism1_empty=15 and mechanism2=16. The verdict NOT SHIP-ELIGIBLE (GUARD FAILED on both mechanisms, plus HARM via SAFETY) is correct under eval/plans/008.md. Per plan 009 l.17-19, arm-3 BASE = arm 1 (v009) mechanically.

1. v011 is NOT adopted. The 31B default draft stays v009 (31b-v009-p7a1). The plan-009 base is arm 1, so arm 3 = 31b-v012-p9a, dist/31b-v012.zip sha256=78a8fd30389ec3acf58b44bc8743d750b496041f5c8d2b35790f0d913130ede5. Nothing else changes in the plan-009 definition.
2. Option A first, because the HARM clause holds: run a CPU-only diagnosis, time-boxed. Write results/plan008_arm2_diagnosis.md (sealed traces only, no new runs) covering exactly:
   (a) Stray row fastapi_15661: what was created, by which tool call, at which turn, and why it landed in /workspace instead of /tmp. Say whether v009/v012 prompt text carries the same exposure (quote the relevant prompt lines by file:line, no task text).
   (b) Empty guard: for the 10 non-timeout empties (9 of which called submit_patch), give the per-row reason the patch was empty at submit time (never edited / edits reverted / edit_file failures only / other), as a count table. Then say in one line why the prompt-level guard did not change behavior.
   (c) One line: whether either finding implies a measurement or classifier defect that would affect arm-3 metrics.
   Deadline: committed by 2026-11-07T09:30Z.
3. After the diagnosis file is committed, push arm 3 (v012) per plan 009 WITHOUT waiting for another ruling, unless 2(c) finds a measurement defect that affects arm 3. In that case STOP and report. A safety exposure that v009 shares does NOT block arm 3: arm 3 is paired against arm 1 on the same prompt. Use the plan-009 smoke rule as written (the INVALID condition if there are no thinking blocks), ONE main session, the D73.7 chunk rule, and record quota before and after. If the diagnosis slips past 09:30Z, push arm 3 anyway at 09:30Z and finish the diagnosis in parallel. Quota allows it: 18.74 h left, arm 3 ~11.5 h.
4. Codex review of eval/plan008_arm2_summary.py (codex-review-arm2sum-light): if it returns BLOCKING on a number in the table above, fold the fix into the diagnosis file and re-state the verdict. The arm-3 base cannot change either way (MECH 1/2 come from the pre-reviewed script and both FAIL), so this does not gate step 3.
5. The 4/0 resolved swing (all rich) goes into the backlog as a CANDIDATE for a later pre-registered k=2 repeat (Option C). Do not spend quota on it this week. If arm 3 also fails to move the needle, bring Option C as a plan with a power calc in the report that follows arm 3.
6. Unchanged: the Nov 8 slot proposal is due 2026-11-07T12:00Z. U2 is now resolved (NOT SHIP-ELIGIBLE, v011 not adopted). Use the dec 079 item 3 "pending" default if v002 has not scored by then.

Reasoning: the pre-registered HARM clause says diagnose before any further arm, and I'm honoring it. Pre-registration only works if we keep it when it's inconvenient. The diagnosis is cheap and CPU-only, and a 3-4 h time-box costs arm 3 nothing material inside this week's quota. Bounding it keeps a literal reading of the rule from stalling the GPU queue. The stray file is a real lever-1 violation, and we need to know whether v009 shares the exposure before anything ships. The 4/0 swing is interesting but p=0.125 at k=1, so it is backlog, not action.
