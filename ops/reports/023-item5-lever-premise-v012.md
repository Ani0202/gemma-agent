# Report 023: dec 081 item 5 / dec 089 item 6 tool-level empty-patch lever: premise does not hold on v012

## 1. Question for the Director
On v012 (arm 3), every empty patch (18/33) is classed as a timeout with zero edits. No row lost its patch to a malformed `edit_file`. One empty row (41 calls) also used up its call budget about 18 s before the timeout, so call exhaustion overlaps there. Even counting it, 1/33 is under the decision rule's threshold of 3. Should I shelve the tool-level lever for the v012 lineage and let plan 010 (thinking 2048) address the time sink? Or do you still want a plan 011 arm?

## 2. Pre-registration
This is descriptive only, with no arm and no GPU. The question was written before tallying: do the arm-2 empty mechanisms (7 call-exhaustion never-edited, 3 malformed `edit_file`) recur on v012? Decision rule, fixed before tallying: if fewer than 3 of 33 v012 rows are non-timeout empties attributable to edit failure or call exhaustion, a tool-level lever has too few target rows to beat ±3 noise on 33. In that case I propose shelving it rather than spending an arm.

## 3. What I did
- Read the harness code. `edit_file`, `get_status` and the budget warning are fixed harness code that a bundle cannot change. The harness attaches an automatic `budget_warning` once 10 or fewer **calls** remain (`swegemma/tools/base.py:47-63`). There is **no automatic time warning**, but the agent can query one: `get_status` (`swegemma/tools/execution.py:119`) reports remaining time, elapsed agent time and remaining calls. The one tool path a bundle controls is a skill script: `run_skill_script` runs `python3` in the sandbox work dir (`adk_eval_core/sandbox/base.py:164+`), so a tolerant-edit helper is technically possible. Using it would still need prompt text, so the bundle would need its own score (dec 087).
- Wrote `eval/plan011_empty_diag.py`, which tallies counts only and prints no task text. I ran it on the sealed arm-3 rows. No new runs.

## 4. Results (arm 3 = 31b-v012-p9a, 33 dev ids, 1 sample per task)
| class | main (31) | smoke (2) | total 33 |
|---|---|---|---|
| resolved | 10 | 0 | 10 |
| empty, timeout, 0 edits | 16 | 2 | **18** |
| empty, non-timeout (never edited or edit failed) | 0 | 0 | **0** |
| patch, timeout | 2 | 0 | 2 |
| patch, wrong | 3 | 0 | 3 |
| malformed `edit_file` calls (rows) | 9 (1 row, resolved) | 0 | 9 (1) |

Files: `results/plan011_diag_arm3_main.json`, `results/plan011_diag_arm3_smoke.json`. Classifier inputs: `results/plan009_arm3_{main,smoke}_d4cdf0f0.json`. The 18 empty-timeout rows (main + smoke) used a median of 15.5 tool calls (range 5–41). In 7 of them the agent made 10 or fewer calls in the whole 210 s, which points to the clock running out during model generation rather than calls running out. Overlap: 1 row (41 calls, `get_status` at call 41 showed 40 used / 0 remaining / ~18 s left) had already used up its calls before the timeout. The classifier's precedence still labels it `empty_timeout`, but it counts as call exhaustion too; with it, the rule's tally is 1 < 3. That is the thinking-4096 time sink plan 010 targets. Script review: `ops/codex/review-20261107T121430.md`. Its three BLOCKING items were all about report text: (1) median/≤10 counts used main-only data, now fixed to all 18; (2) call-exhaustion overlap, now acknowledged; (3) `get_status` time signal, now described. The table counts were independently reproduced. Non-blocking issues (whitespace-vs-zero-byte empty predicate, the `empty_edit_failed` label not checking response success, and inventory validation) have zero effect on these rows. They are recorded for any reuse, which will use the exact-byte predicate and inventory checks.

## 5. Options
- **A. Shelve the item-5 lever for the v012 lineage.** Re-check with the same script on plan-010 arm-4 rows: if non-timeout empties reach 3 or more there, bring a plan 011 then. Cost 0. Risk: none on current data.
- **B. Build a plan 011 arm anyway:** a skill `safe_edit` helper plus prompt text telling the agent to edit by mid-budget. It has 0 malformed-edit target rows and 1 call-exhaustion overlap row on v012 under the mechanisms named in dec 081, and only the "edit earlier" part would touch the 18 timeouts. That part is prompt text, which dec 081 said this lever should not be. It would need its own score and would use about 9.7 h of Kaggle quota.
- **C. Fold a time signal into plan 010's successor as a knob-only change,** e.g. analyzer thinking ≤2048. That stays finals-eligible under dec 087 (b). Decide after the arm-4 data.

## 6. Recommendation
A, with C kept as the follow-up after arm-4 data (week of 11-14). No requests: no SUBMIT, no GPU, no HOLDOUT.
