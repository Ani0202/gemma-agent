# Plan 008 arm 2 (31b-v011-p8b): CPU diagnosis per dec 080 item 2
Written 2026-11-07 ~06:30Z. Sources: sealed traces only (runs/31b-v011-p8b-arm2/, SEAL.sha256 OK at 05:54Z); no new runs.
Inputs: results/plan008_arm2.json, results/plan008_arm2_summary.json (4de6787), per-row trace.json / result.json,
eval/run_agent_eval.py (stray classifier), bundles/31b/v009|v011/prompts/system.md, data/raw/tasks.jsonl (gold patch FILE HEADERS only).
Helper: eval/plan008_arm2_empty_diag.py (per-row edit/write/diff tally; run from repo root with the 10 ids comma-separated). No task text below.

## (a) Stray row fastapi_15661
- What: one new file `scripts/release.py` (35 lines) in the submitted patch. Only file in the patch.
- How: tool call 31 of 40 (elapsed 268 s), `run_command`: quoted heredoc to `/tmp/release.py`, then the shell line
  `mv /tmp/release.py scripts/release.py`. Call 33 repeated that. Call 34 ran it. Call 36 `git status` showed it untracked.
  Call 37 `git add scripts/release.py`. Call 40 `submit_patch`.
- Why it was in /workspace: **deliberately, as the fix, not as scratch.** The agent wrote the file in /tmp (following
  system.md:32-33) and moved it into the repo as its deliverable. The task's gold patch also creates exactly one new
  non-package .py file under `scripts/`, with a different name (gold hunk `@@ -0,0 ...`). The hidden test imports that
  module, and the result.json error is ModuleNotFoundError for it. So the agent made the right kind of change but used the
  wrong module name. This is not a scratch-file leak (lever 1).
- Same exposure in v009 / v012? Yes, and by design. The relevant lines are identical in v009 and v011:
  bundles/31b/v009/prompts/system.md:31 ("Put ALL scratch files ... in `/tmp`, never in `/workspace`"), :32-33 (heredoc
  to /tmp), :34 ("confirm only intended source files changed ... delete or revert any stray files"). v012 = v009 plus
  sampling.yaml only. Nothing in any prompt forbids creating a new source file the task needs, and nothing should.

## (b) Empty guard: the 10 non-timeout empty rows
Correction to the dec 080 premise: of the 10 non-timeout empties, **8** called submit_patch. The "9" in the summary
(`empty_with_submit_patch_called`) counts all 15 empties, including timeout row rich_3480.

| reason the patch was empty at submit or end | rows | ids | called submit_patch |
|---|---|---|---|
| never edited (0 edit_file/write_file calls, 0 workspace-writing shell commands) | 7 | rich_2943, rich_3938, fastapi_14851, rich_3470, rich_3930, fastapi_15800, rich_3052 | 7/7, at call 39-40 of 40 |
| edit_file failures only (every call failed: "mandatory input parameters are not present: old_string") | 3 | rich_3471 (6/6 failed), rich_3061 (20/20), rich_3718 (25/25) | 1/3 (3061 and 3718 ended at the 50-turn limit) |
| edits reverted | 0 | | |
| other | 0 | | |

- Never-edited rows: the first budget warning ("Finalize your edits and call submit_patch") came at call 30. **0 of 7 ran
  `git diff` or `git status` at any point**, so the guard's required check never ran. 5 of 7 were in repeat loops
  (mechanism2 true, max identical run 8-28).
- Edit-failure rows: all 51 failures were malformed tool calls with old_string missing (the known escaping trap). No edit
  ever landed, so there was no diff for a check to find.
- **Why the guard didn't change behavior (one line):** it is a conditional instruction that the model never executed. The
  never-edited rows reached submit only at the call limit, where the guard's own "budget cannot fit an edit" exemption
  applies, and the other 3 rows failed at the tool-call format layer, which a diff check can't fix.

## (c) Measurement or classifier defect affecting arm 3?
**YES. This triggers the STOP in dec 080 item 3.** The stray-files classifier (eval/run_agent_eval.py:180-182) counts every new
file that is not a .py under the package root. In 2 of the 33 dev tasks, the gold patch itself creates such files:
fastapi_15661 (1 file under scripts/) and fastapi_15800 (6 .py files under docs_src/). On those tasks a CORRECT fix would
set stray_files > 0 and veto arm 3's SAFETY (plan 009 l.92, "stray files 0 rows"). Arm 2's stray hit is a false positive
of the same kind: a wrong-name deliverable, not scratch.
Minor, not material: plan 009's wall-p90 check compares values rounded to 0.1 s (codex 20261107T055702 BLOCKING 1). That
matters only within 0.05 s of the limit.

## Item 4: codex review of eval/plan008_arm2_summary.py (ops/codex/review-20261107T055702.log), folded in
- BLOCKING 1: the agent-clock check used a rounded max. rich_3468 = 210.000899 s > 210 s cap (timeout kill granularity),
  so literally `met.agent_clock` = **false**, not true. BLOCKING 2: missing clock evidence would pass. Today's inputs are
  complete, so no count changes.
- NB 1: paired empty-patch discordants (plan 008 l.56): **arm-2-only 8 / arm-1-only 5**.
- Every number in dec 080's table (primary 8/33 vs 4/33, A-only 4 / B-only 0, p=0.125, MECH1 15, MECH2 16, stray rows 1)
  was confirmed by the reviewer's in-memory regeneration (exact match).

## Re-stated arm-2 verdict
**NOT SHIP-ELIGIBLE, unchanged.** GUARD FAILED on both mechanisms (empty 15/33 > 4; repeats 16/33 > 6). SAFETY, read
literally: stray 1 row (a classifier false positive, see (c)) plus agent clock 210.0009 s > 210 s (granularity). The
plan-009 base stays arm 1 (v009), so arm 3 stays 31b-v012-p9a either way.
