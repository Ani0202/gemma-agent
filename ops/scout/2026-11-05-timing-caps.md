# Scout: timing caps, 2026-11-05
Public pages only, read-only. Kaggle notebook and discussion pages returned only titles to the fetch tool,
so the official starter eval_config.yaml and the staff posts were NOT directly read.
Confidence tags: CONFIRMED (primary page text seen), REPORTED (secondhand), UNCLEAR.

## COMPLIANCE / TIMING flags
- Official rules text (CONFIRMED via search snippet of https://www.kaggle.com/competitions/gemma-4-developer-agent):
  "Your agent has a limit of 12 hours to submit patches for all tasks, inclusive of sandbox setup time,
  but excluding time for patch validation. You may, but are not required, to set per-task time limits in
  your submission's eval_config.yaml."
- Setup is charged to the shared 12 h pool. No per-task setup figure was found anywhere (see Q3).

## Q1. max_time_minutes values by source
- Official starter / sample_submission eval_config.yaml: UNCLEAR. Not retrieved.
  Starter notebook: https://www.kaggle.com/code/ryanholbrook/getting-started-gemma-4-developer-agent (body not readable).
  A third-party PR says official sample agent.yaml wraps sub_agents/code_analyzer.yaml (REPORTED, unverified).
- mangeshraut712/Hindai PR #32 https://github.com/mangeshraut712/Hindai/pull/32 : 4.5 min, 40 tool calls,
  60 turns, timeout_seconds 180. Previous value was 8 min, lowered because 8 x 120 = 16 h. (REPORTED)
- johnsonhk88 repo https://github.com/johnsonhk88/kaggle-Google-The-Gemma-4-Developer-Agent-Competition :
  8 min/task, 28 calls, 300 s command timeout. Says "Default 60 min/task would time out the submission."
  (REPORTED; the 60 min default claim is from this repo, not verified officially)
- Another repo search snippet (not opened): max_time_minutes 30, 75 calls, 200 turns, 300 s. (REPORTED, weak)
- reconscribe guide https://reconscribe.com/gemma-4-developer-agent-competition-2026/ : names the keys
  max_time_minutes and max_tool_calls, gives no value. Budget math 12 h / 120 = ~6 min/task. (REPORTED)
- Peoplerepabulic and lmassaron repos: no values on the pages.

## Q2. Evidence that capped bundles were actually scored
- No post found showing a leaderboard score tied to a specific cap (5 min or otherwise). UNCLEAR.
- Hindai PR #32: no Kaggle score, eval never run; 2026-09-28 upload failed "Notebook Threw Exception"
  (a packaging error, not a timeout). (REPORTED)
- reconscribe: "Participants report that going over the limit errors the whole submission, although the
  overview does not say this." Staff in early Oct 2026 said scoring unfinished tasks as 0 instead of failing
  the run was "being reconsidered" (guide's paraphrase, no staff URL). (REPORTED)
- Public leaderboard exists https://www.kaggle.com/competitions/gemma-4-developer-agent/leaderboard
  (CLIST mirror: https://clist.by/standings/google-the-gemma-4-developer-agent-competition-artificial-intelligence-coding-custom-metric-70662440/)
  but I could not read it. Public notebook titled "[0.10]: Gemma 4 Developer Agent Submission"
  https://www.kaggle.com/code/nihilisticneuralnet/0-10-gemma-4-developer-agent-submission
  suggests a scored ~0.10 submission; its config was unreadable. UNCLEAR.
- Suggested follow-up: have a human/browser read that notebook and the starter notebook.

## Q3. Per-task sandbox setup time
- No public number found. UNCLEAR.
- Rules text says setup is inside the 12 h total. Whether it also counts against the per-task cap: UNCLEAR.
- A guide notes a measured mean of ~5.4 min/task in one repo and warns 120 x (5.4 + setup) may exceed 12 h
  (REPORTED, repo not identified).

## Q4. What counts toward 12 h
- Rules: sandbox setup included; patch validation excluded (CONFIRMED, above).
- vLLM server start-up included: reconscribe says "Kaggle Staff confirmed" (REPORTED, staff post not found, undated).
- Skill scripts run in the competition container and "that time counts against the central budget" (REPORTED, same guide).
- Smaller variants (E2B/E4B) "scored on the same hardware with the same 12-hour limit" per staff, undated
  (REPORTED via reconscribe).
- Public and private tasks run in the same 12 h run (REPORTED, reconscribe).
- Verification/validation after patches: excluded per rules (CONFIRMED).
- Queue delays over 15 h reported early Oct 2026 (REPORTED, reconscribe).
