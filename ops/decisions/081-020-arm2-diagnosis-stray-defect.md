DECISION: approve-with-changes
SUBMIT: none
GPU_ALLOWANCE: none
ESCALATE: none
DIGEST: The diagnosis found a measurement flaw in one safety check. It gets fixed before any new data arrives, and the thinking-on experiment starts now.
---
I checked the diagnosis against the files. results/plan008_arm2_diagnosis.md (a) shows the stray row is a deliberate wrong-name deliverable, not scratch. (c) shows that the gold patches of 2/33 dev tasks (fastapi_15661, fastapi_15800) create files the classifier at eval/run_agent_eval.py:180-182 counts as stray, so a correct arm-3 fix would veto SAFETY. That is a real classifier defect, and the STOP was correct. Option A is approved, with the changes below.

1. Push arm 3 NOW: 31b-v012-p9a, dist/31b-v012.zip sha256=78a8fd30389ec3acf58b44bc8743d750b496041f5c8d2b35790f0d913130ede5, under eval/plans/009.md as written. That means the smoke rule with the INVALID-on-no-thinking condition, ONE main session, the D73.7 chunk rule, and quota logged before and after. The run does not depend on the classifier, so do not wait for steps 2-3.
2. Stray amendment (dated pre-data addendum to plan 009 at l.92; commit it BEFORE the first arm-3 main row is pulled back to this VM, and journal the commit SHA and time):
   (a) GOVERNING stray = new files in the patch that are not .py under the package root, EXCLUDING any new file whose parent directory equals the parent directory of a file the task's gold patch creates (`@@ -0,0`). Exact directory match only. No prefix or ancestor matching, no extension or name matching.
   (b) Always report the LITERAL stray count (the old rule) next to the governing one, per row, as DESCRIPTIVE, with file paths (paths only, no content).
   (c) Apply the rule identically to arm-3 rows and base (arm-1) rows. Recompute and state the arm-1 and arm-2 stray counts under the amended rule in the arm-3 report.
   (d) The gold-patch file headers feed only this dev metric. They never reach a bundle, a prompt or a training set. Note this in the addendum.
3. In the same addendum, fix the rounding granularity (codex 20261107T055702 BLOCKING 1). TIMING and wall-p90 comparisons use unrounded values. Round only for display.
4. Get the amended classifier and arm3 metrics change through codex-review (-light), with a unit test covering: one gold-dir file exempted; a file in a sibling or child dir NOT exempted; literal count unchanged. It must be CLEAN before you compute any arm-3 metric. If it isn't CLEAN by the time arm-3 data lands, hold the metrics, not the run.
5. Backlog (no spend this week): 7/10 non-timeout empties never edited and submitted at call 39-40/40, i.e. they ran out of calls while exploring. 3/10 are malformed edit_file calls missing old_string. The next empty-patch lever is tool-level (a tolerant or clearer edit_file error, plus an exploration budget signal), not prompt text. Bring it as a plan after arm 3.
6. Unchanged: the Nov 8 slot proposal is due 2026-11-07T12:00Z. The v002 final handling follows dec 079.

Reasoning: this is a measurement fix decided before any arm-3 data exists, applied symmetrically. That is what pre-registration permits, and it is better than ruling on a veto after the fact (Option B). Exact-directory matching keeps the exemption narrow, so a scratch file dropped elsewhere still counts, and reporting the literal count keeps the change auditable. Holding the GPU run (Option C) would waste window time for nothing, because metrics are computed after the data lands.
