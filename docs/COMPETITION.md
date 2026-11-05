# Competition facts (researched Nov 4, 2026; the Builder verifies each in Phase 0)

The sources were the Kaggle overview, data and discussion pages, the official starter notebook
(Ryan Holbrook), third-party summaries, and public competitor repos. Items tagged **[verify]** are
uncertain or the sources conflict. Correct this file when official pages say otherwise, and log
each correction in `ops/journal.md`.

## Links
- Main track: https://www.kaggle.com/competitions/gemma-4-developer-agent (slug
  `gemma-4-developer-agent`).
- Paper track: https://www.kaggle.com/competitions/gemma-4-developer-agent-paper. It closes
  Nov 12, and we're skipping it.
- Starter notebook: https://www.kaggle.com/code/ryanholbrook/getting-started-gemma-4-developer-agent.

## Dates (23:59 UTC)
- Entry and team-merge deadline: **Nov 25**. Aniket must accept the rules before then; he's
  doing it Nov 4.
- Final submission deadline: **Dec 2**. You select two finals.
- One submission per day, **and only one pending at a time** (staff, thread 747519). Queues of
  30–40 h+ are reported, so expect ~1 scored submission per 1.5–2 days; the last reliable new score
  comes from a submission made about Nov 27–28. (Resolved 2026-11-05, dec 013.)

## Prizes
- Main: $37k / $18k / $10k, by private leaderboard rank. Ties go to the earlier submission.
- Small-model bonus: $10k for the highest-ranking submission based on E2B or E4B. It must be one of
  the two selected finals, and it stays eligible for the main prizes too. A daily Kaggle notebook
  publishes small-model standings.
- The public LB uses about 50% of the roughly 120 hidden tasks; the private LB uses the rest.

## What you submit
- `submission.zip`, ≤ 3 GiB, with `agent.yaml` at the root. It's a declarative Google ADK Agent
  Config with `configs/`, `prompts/`, `sub_agents/` (via `agent_tool`), `skills/<name>/SKILL.md`
  (plus sandboxed `scripts/` and `resources/`), `adapters/<name>/` (PEFT LoRA safetensors), and
  `eval_config.yaml` for per-task limits.
- Allowed models: `gemma-4-31b-it-qat-w4a16-ct`, `gemma-4-12b-it-qat-w4a16-ct`,
  `gemma-4-e4b-it-qat-w4a16-ct`, `gemma-4-e2b-it-qat-w4a16-ct`. All agents in a bundle use the
  same model. **[verify]** that 12B, E4B and E2B are currently accepted by the validator (some
  repos say "31B only", and the bundled model list was reportedly stale).
- Prompts may contain only `{problem_description}`; any other `{word}` crashes the bundle.
- There's no arbitrary Python entrypoint and no internet at scoring time.
- Submission method: upload the zip, or submit a notebook version whose output is
  `/kaggle/working/submission.zip`. **[verify]** which method the CLI supports.

## Scoring runtime
- vLLM serves the chosen model on Kaggle L4x4 (4×L4, 96 GB) with `max_model_len` 32768 in the
  starter. A LoRA config can shrink the KV cache; check this.
- Phase 1, container A:
  - The repo sits at `/workspace` at `base_commit`.
  - The agent has these tools: `run_command`, `read_file` (≤ 150 lines / 10k chars), `edit_file`,
    `write_file`, `submit_patch`, `get_status`, `get_code_neighbors`, `search_similar_code`,
    `get_code_subgraph`, plus the skill helpers `run_skill_script` and `load_skill_resource`.
  - Command output is capped at about 5k chars.
  - The sandbox has 2 vCPU and 4 GiB, offline, with wheels at `/wheels`.
  - If `submit_patch` is never called, a non-empty source diff is still graded.
  - `submit_patch` and `get_status` reportedly don't count against call limits. **[verify]**
- Phase 2, container B: a fresh checkout, the agent's patch applied, and tests and config reset
  (`tests/`, `conftest.py`, `pytest.ini`, `setup.cfg`, `pyproject.toml`). Then the hidden
  `test_patch` is applied and `python3 -m pytest` must exit 0.
- **12 hours total**, including sandbox setup and vLLM startup, with tasks run sequentially.
  Going over reportedly errors the whole submission. No official ruling on the overrun
  outcome (see RULES_FINDINGS.md); we assume worst case. The default 60 min per task would blow the budget; about 5–6
  minutes per task fits.
- **[verify]** whether the private LB uses multiple runs to reduce variance (there's an open
  discussion thread).

## Data (`/kaggle/input/...`, about 22 GB, Apache-2.0)
- `tasks.jsonl` has 129 public tasks: fastapi 67, rich 48, requests 13, httpx 1. Each has
  `problem_statement`, `hints`, `patch`, `test_patch`, `base_commit` and `created_at`.
- `snapshots/<id>.tgz` holds the repos with forward history removed.
- `graphs/` (NetworkX JSON) and `embeddings/` (256-d `.npz`) back the graph tools.
  `search_similar_code` resolves symbol names, not free text.
- `wheels/` has 124 offline wheels. **[verify]** the architecture.
- `docker/` holds the sandbox Dockerfiles and the `imp` shim (Python 3.13).
- `sample_submission/` and `HARNESS_README.md` cover the swegemma, adk-submission and
  adk-eval-core libraries plus the local CLI (`swegemma eval ...`).
- **[verify]** the hidden set's composition. One source says private repos; the data page says
  the same generation and verification methods. Plan for generalization either way.

## Known traps (from public discussion and repos)
- About 27 fastapi tasks can't pass in the provided sandbox because `inline_snapshot` and
  `dirty_equals` are missing. Exclude them by gold calibration.
- JSON-escaped tool output gets copied into `edit_file`, causing "old_string not found".
- `ContextWindowExceededError` can bypass the fallback diff capture and produce an empty patch.
- In `EventsCompactionConfig`, the `LlmEventSummarizer` reportedly drops all tool calls and tool
  responses.
- vLLM's default LoRA configuration reserves memory on each GPU, shrinking the KV cache and
  causing hangs.
- Gemma 4 can loop in thinking mode or emit malformed tool calls under long context.
- Sample-submission dummy adapters are shaped for 31B and break smaller models. 12B needs vLLM
  `hf-overrides`.

## Scores seen (public LB, noisy)
- Most public notebooks score around 0.18. One prompt-only configuration was reported at 0.24.
- The same files have scored from 0.12 to 0.22, which tells you how much noise there is.
- One team measured graph tools helping E2B: 72 passes with them versus 54 without, across 123
  tasks × 8 samples.

## Rules that matter
- **External data and models** are allowed during development if they're free to everyone or meet
  the "reasonableness standard". At runtime, only the chosen Gemma model.
- **Distillation** from Claude or GPT trajectories had no official ruling as of mid-October. We
  don't use it, on terms-of-service grounds.
- No private sharing outside the team, and no redistributing Competition Data. No hand-labelling,
  and one account per person.
- Winners must license their code under Apache-2.0 or an OSI license and provide reproducible code
  plus a write-up.

## Phase 0 verification update (2026-11-04)
See docs/RULES_FINDINGS.md. Still [verify] (official pages unreadable by tooling): 12h overrun ruling, private-LB multiple runs, pending-submission cap, E4B validator acceptance. Third-party sources agree on: 4 allowed models, 1 sub/day, notebook-output submission, hidden set likely private repos.

## Official-source update (2026-11-04; see docs/RULES_FINDINGS.md, decision 004-002-001)
- **No repo overlap:** none of the training repos appear in the hidden test set (staff, thread 747248); all hidden tasks validate 100% with the gold patch. This supersedes the "[verify] hidden set composition" note above: generalize to unseen repos.
- **Timeout:** no official ruling on overrun outcome; staff (thread 749597) only said setting unfinished tasks to 0 "could lead to inconsistent results" and they'd look for other ways. Third-party reports: overrun fails the submission. We assume worst case. See RULES_FINDINGS.md.
- **Timeline:** entry/merge deadline Nov 25; final deadline Dec 2 23:59 UTC.
- **Prizes:** main $37k/$18k/$10k; E2B/E4B bonus $10k; separate **Paper Submission Award $35k** (competition `gemma-4-developer-agent-paper`, deadline Nov 12 23:59 UTC; Aniket decides whether to enter, escalation E2).
- Private-LB multiple runs: unknown; plan for one run.

## Rules sweep update (2026-11-05; decision 013; details + confidence tags in docs/RULES_FINDINGS.md)
- **M1** 1 submission/day, 2 finals; final score = better of the two private scores (host, 752220) [official + host-forum].
- **M2** Pending-submission cap RESOLVED: one pending at a time (staff Dustin, 747519) [host-forum]; queues 30–40 h+ [participant].
- **M3** 12 h overrun: no official ruling; participant report (752017) of a timeout with no partial score after adding only a test re-run step, and local public-repo timing underestimating hidden-repo test cost [participant]. Worst case stays.
- **M4** Private-LB multiple runs: no answer (754295); plan for one run.
- **M5** Hosted LLM APIs: no answer (755542); no new third-party services for task data.
- **M6** Small-model bonus: E2B/E4B, must be a final (Prizes page, host 751104). E4B validator acceptance RESOLVED (E4B entries score); intermittent "incorrect format" reports OPEN (752128) [participant].
- **M7** LoRA: mixed participant reports (755677); validate on exact base first.
- **Reference:** official small-model standings notebook: https://www.kaggle.com/code/ryanholbrook/gemma-4-developer-agent-small-model-leaderboard
