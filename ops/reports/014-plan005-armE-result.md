# Report 014: plan 005 arm E (31b-v007-p5e, thinking off, cap 1.23): CAP-BOUND

## 1. Question for the Director
Arm E returned the pre-registered verdict **CAP-BOUND**. So, as the rule says, dec 056 item 6 (a timeout must never yield an empty diff) is
now the binding blocker for any 31B final at cap <= 1.23. Do you agree that the 31B path is: (i) the dec 055 31b-v002 submit at 11-07T00:00Z
as the real unlock (if cap 3.5 SCORES, the FINALS RULE no longer binds us to 1.23); (ii) v004 stays a CPU draft, with no slot; (iii) the next 31B GPU arm
targets the identical-tool-call loops found below (option B)?

## 2. Pre-registration (eval/plans/005.md Addendum E, written ~04:35Z before packing and before any run)
- not V -> INVALID. V and E empty <= 4/8 and E-empty-only (vs D) <= 2 -> USABLE. Otherwise CAP-BOUND (+ the dec 056 item 6 line).
- Descriptive only: timeouts, first ok edit_file/write_file before 73.8 s agent clock, per-id patch bytes D->E, sign test, agent clock sum, tool errors, gates a/b/d/e.

## 3. What I did
Kernel aniket0202/gemma-31b-timing v5 (repo 8000c75), bundle = dist/31b-v007.zip sha256 3a62f41f...3c6f (= v006 + cap 4.0 -> 1.23 only).
The kernel's bundle dir was diffed against the unzipped dist zip: every file is identical. The only extra file is MANIFEST.md (pack leaves it out of the zip). It was
uploaded before the 04:42Z prose correction, so it says "incl. inherited FastAPI hint". That's wrong for v003+ and has no effect on behaviour.
Same 8 ids, conc 1, k=1, 40 calls/50 turns, KERNEL_BUDGET 6000 s. Analysis (main, this cycle's commit): timing_summary --gate-mode stock-path,
trace_tool_errors, thinking_bound, and new eval/plan005_armE_compare.py (agent-clock first-edit time counting edit_file AND write_file; longest
run of byte-identical consecutive tool calls). Quota: 13.09 h -> 14.49 h (+1.40 GPU-h; ops/budget/kaggle.md).

## 4. Results (n=8 tasks, k=1; paired vs arm D = 31b-v006, cap 4.0)
| metric | arm D (cap 4.0) | arm E (cap 1.23) | file |
|---|---|---|---|
| gates a/b/d/e (V) | PASS | PASS (b: 77.2 <= 110.8 s; d: vLLM 350 s; e: 3 non-empty) | results/kaggle_timing_31b_v007.json |
| V add-on (summary + root usage, 8/8) | yes | yes; 0 thinking blocks 8/8 | results/thinking_bound_31b_v007.json |
| non-empty diffs | 5/8 (Wilson 0.31-0.86) | 3/8 (Wilson 0.14-0.69) | results/plan005_armE_vs_D.json |
| discordant D-only / E-only non-empty | 2 / 0 | | same; exact sign p1 = 0.25, p2 = 0.50 |
| timeouts | 2 | 5 (every timeout -> empty diff) | same |
| first ok edit < 73.8 s agent clock | 3 | 3 | same |
| agent clock sum | 924.9 s | 499.3 s | same |
| edit_missing_param | 0 | 18 (17 in one task) | results/trace_tool_errors_31b_v007.json |
| cmd_error_shell | 22 | 2 | same |
**Verdict: CAP-BOUND** (E empty 5/8 > 4; E-empty-only 2 is within its limit). Not a strike: the verdict concerns the cap, not the prompt.
dec 056 item 6 is now the binding blocker for any 31B final at cap <= 1.23.

Per id, patch bytes D -> E: rich_3063 0->0, rich_3067 655->0, rich_3454 657->657, rich_3535 465->0, rich_3930 0->0, rich_3953 684->539,
fastapi_14258 508->508, fastapi_14851 0->0. The two E-only empties had their first D edit at 109 s (rich_3067) and 58 s (rich_3535).
The three surviving E diffs landed their first edit at 12-35 s.

**New finding: identical-tool-call loops (descriptive, post hoc, NOT pre-registered).** The longest run of byte-identical consecutive tool calls
per task is in results/plan005_armE_vs_D.json (`*_max_identical_call_run`; start/end/span agent-clock s in `*_max_identical_run_{start,end,span}_s`, span = first to last call of the run):
- E: rich_3067 = **17 identical failing edit_file calls, agent-clock 16.1-71.6 s (span 55.6 s)**, i.e. the rest of the window. This happened although the prompt says "if an edit fails twice
  with the same error, do NOT repeat it". rich_3063 = 16 identical run_command (span 32.4 s); fastapi_14851 = 8 identical read_file (span 14.8 s).
- D: rich_3454 = 20 identical run_command (span 44.9 s; this is the 21-repeat quoting_heredoc of dec 059 item 4b); rich_3063 = 18 identical run_command (span 34.7 s).
- So at thinking off, 2-3 of 8 tasks per arm lose ~15-56 s each to exact repeats (spans 14.8-55.6 s). Inside a 73.8 s window that's the main way time is lost.
  The prompt rule doesn't stop it (seen in E). The v004 quoting line targets only the shell-error variant.
Honest limits: n=8/k=1, and empty-diff counts aren't pass rates. The loop metric was defined after seeing the data. Cap 1.23 has zero margin under H3.

## 5. Dec 059 item 4 checks (done in c108, results/shell_error_causes_31b_v005_v006.json)
(a) The 4 C/D patches with equal byte counts are byte-identical (sha). (b) cmd_error_shell 22 = quoting_heredoc 22, in 1 task, 2 distinct commands, 21 identical repeats.
That was folded into v004 as the quoting/no-repeat line.

## 6. Dec 060 item 1: v004 vs v002 byte diff (dist/31b-v004.zip 50537e1d; diff -r bundles/31b/v002 bundles/31b/v004)
| # | change | file | screened? |
|---|---|---|---|
| 1 | thinking_budget 4096 -> 0 | configs/sampling.yaml | YES: arm D vs C (PASS, report 013) |
| 2 | max_time_minutes 3.5 -> 1.23 | eval_config.yaml (+ comment lines) | YES: arm E vs D = **CAP-BOUND** (this report) |
| 3 | early-edit line (first edit by ~call 12) | prompts/system.md s2 | arm B vs A (MECHANISM-ONLY, report 012) |
| 4 | short-anchor edit_file line | system.md s2 | arm B (same) |
| 5 | anchor-avoids-quotes / no-repeat-after-2-fails / /tmp-script fallback | system.md s2 | arm B (same); **E shows the no-repeat clause failing (rich_3067)** |
| 6 | never write_file on existing files | system.md s2 | arm B (same) |
| 7 | FastAPI docs_src line -> generic example-code line | system.md s2 | arm B (same); required by dec 057 |
| 8 | targeted pytest with `set -o pipefail; ... -x -q 2>&1 \| tail -30` | system.md s3 | arm B (same) |
| 9 | keep outputs small; grep-exit-1 / sitecustomize noise line | system.md s3 | arm B (same) |
| 10 | write_file/edit_file reject /tmp -> quoted-heredoc scripts | system.md s4 | arm B (same) |
| 11 | **quoting line ("same quoted-heredoc script for ANY code with quotes/backticks/$ ...; never re-run a shell error unchanged")** | system.md s4 | **UNSCREENED**: only a later paired v004-vs-v002 run would cover it |
| 12 | git status check also allowed after confirmed env-only failures | system.md s4 | arm B (same) |
| 13 | diff must touch a non-test SOURCE file (not config-only) | system.md s4 | arm B (same) |
| 14 | submit_patch ONCE, freezes patch, workspace auto-collected on timeout | system.md s4 | arm B (same) |
Arms B-E all carry 3-10 and 12-14 as one unit; no single line was screened alone. Codex NB2 (system.md:33 `python3 /tmp/repro.py 2>&1 | tail`
without pipefail, inherited from arm B) is an unscreened candidate fix. v004 is NOT repacked.
**Minimal alternative (described, not packed):** v002 + #1 + #2 + #7 only (thinking off, cap 1.23, dec 057 line swap). It drops the arm-B prompt block
and the quoting line. Against it: arm B's prompt cut write_outside_ws 8->0 and edit_missing_param 19->6 vs arm A (results/trace_tool_errors_31b_v001.json, _v003.json; MECHANISM-ONLY, empties 4->4), and the early-edit line is what
the 1.23 cap needs most. I still recommend the full v004 over the minimal alt, but neither should get a slot at cap 1.23 now (CAP-BOUND).

## 7. Options
- **A. Park the 31B 1.23 path.** Wait for the dec 055 31b-v002 submit (cap 3.5). If it SCORES inside 12 h, the FINALS RULE allows 31B finals at cap
  <= 3.5, and CAP-BOUND stops binding. Cost 0. Risk: if v002 errors/times out, 31B has no validated cap above 1.23.
- **B. (Recommended in addition to A) Anti-loop arm F next week** (after the 11-07 reset, ~1.4 GPU-h, same 8 ids, paired vs E or D at the
  cap A makes legal): a generic, non-repo-specific change aimed at exact repeats. Candidates: temperature 0.2 -> ~0.6 (greedy-ish
  decoding makes repeats likely), or a sub-agent/skill pattern. My understanding (not verified here): vLLM presence/frequency penalties count
  only the current output's tokens, so they likely won't break cross-turn repeats. Pre-register before running.
- **C. Pursue dec 056 item 6 directly** (timeout -> non-empty diff). A declarative bundle can't add harness code, so the only levers are prompt timing
  and the scorer's auto-collection of workspace edits. E's 5 timeouts had NO landed edit, so this is "edit earlier", not "collect better". It collapses into B.

## 8. Recommendation
A + B. No submission or GPU request this cycle (B fits the weekly Kaggle plan after the reset; I'll pre-register it as plan 005 Addendum F or
plan 008 and send it before running). Dec 055 checklist at 2026-11-07T00:00Z still comes first and is unaffected. Write-up note (dec 060 item 2):
the v002 LB score will be the only result carrying the FastAPI hint caveat.


Revision c114: codex review ops/codex/review-20261106T052532.md BLOCKING (repeat range 15-72 s -> spans 14.8-55.6 s) fixed; NB1 (8-id assert) and NB2 (run timestamps saved) fixed in eval/plan005_armE_compare.py; regenerated JSON, all other fields unchanged, verdict CAP-BOUND unchanged.
