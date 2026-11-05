DECISION: approve-with-changes
SUBMIT: none
GPU_ALLOWANCE: none
ESCALATE: none
DIGEST: Setup delay traced to the competition's own harness; one Kaggle timing run of the safe small-model bundle approved, first submission to follow if it passes.
---
I spot-checked results/plan003_kernel_setup_acceptance_r4local.json and it matches the table: setup.py 8.85 / 8.59 / 8.77 / 0.59 s, Retrying 5/5/5/0, fastapi Docker-order rc 0. Option A is approved, and the CPU 2a session (option B) is dropped because the GPU re-time logs setup_calls on Kaggle directly. The dec 027 item 2a STOP condition is met: the artifact branch is closed, 2b is moot, and no v000 cap-5 re-time. Dec 027 item 5 applies, so the one GPU timing run is e4b-v001.

My adversarial check is ops/codex/ask-<latest> (codex-ask, medium, 19:2xZ). Its key finding: our bound (1.4 + 212/60) x 125 + 30 = 646.7 leaves only ~6.4 s/task of headroom. Post-cap finalization (git add -N / git diff, up to 2 x 60 s command timeouts in swegemma/harness/agent_runner.py:1045-1118) runs OUTSIDE the 84 s asyncio.timeout. And 212 s is an 8-task observed max, not an upper bound. So the re-time has to measure the COMPLETE Phase-1 wall time per task, not the agent clock.

1. Prerequisite: codex-review the merge diff of the round-4 agent_timing.py (branch codex/kernel-setup-fix c4c9528) into the timing kernel. Merge only with no BLOCKING. The fidelity rule of dec 027 item 1 still binds: no PIP_* prefixes, Docker order, starter docker_image pinned, internet OFF.
2. Then push ONE Kaggle L4x4 timing run of dist/e4b-v001.zip (sha256 f2ced9c97ee1447cb3a78c0ebf65f4ecaff90c84b18313645d5d043c62d277e9) on eval/plans/004-gpu-retime-ids.txt (8 ids), concurrency 1, verification skipped, fail-fast 4xL4 guard on. Log it in ops/budget/kaggle.md. This is within the weekly plan (~3 quota-h; week total would be ~6.5 of ~30).
3. The kernel must record, per task: setup_calls (each step's duration, rc, Retrying count), agent-clock seconds, whether the 84 s timeout fired, post-cap finalization seconds (fallback diff + teardown), and the TOTAL Phase-1 wall seconds from sandbox start to sandbox stop. Also record vLLM startup once. Write it to a schema-headed results/kaggle_timing_e4b_v001.json.
4. SUBMISSION GATE for e4b-v001 (pre-registered here, before the run). ALL must hold:
   (a) all 8 tasks complete with no harness error;
   (b) max per-task TOTAL Phase-1 wall <= 296 s (this reproduces the 646.7 projection; the absolute ceiling is (660-30)/125 = 302.4 s);
   (c) mean per-task TOTAL Phase-1 wall <= 270 s;
   (d) vLLM startup <= 10 min;
   (e) at least 1 non-empty source diff among the 8 (the bundle produces patches at cap 1.4).
   If all pass, send a SHORT report 005 at once (table: per-task setup / agent / finalization / total, the gate lines, and the measured S and fallback count). Name it NEEDS_DECISION and request SUBMIT for today's slot if before ~23:00Z, otherwise tomorrow's. I'll authorize promptly. Do NOT run kaggle-submit until the AUTHORIZE line exists.
   If (b) or (c) fails: no submission. Report the numbers and propose a lower cap (e.g. 1.0) using max total wall, not the agent cap.
5. What the re-time also decides: if measured S on Kaggle L4x4 is ~10 s (fast fallback failure, not a ~103 s hang), the cap-4.0 path (e4b-v002) re-opens under the dec 027 item 4 rule (both conditions), but only with the finalization overhead added to the formula: (cap + S + F_max) x 125 + 30 <= 660 and the stress variant (cap + F_max + 0.875 + 0.75 S). Put that derivation in report 005. Don't build v002 until I've seen it.
6. In parallel, CPU only: fix eval/sandbox_env.py to the Docker order and cache key (Codex finding 2) via codex-build, then the full eval/tests on main. Finish the memguard-fix5 merge/deploy per STATE. Keep one heavy job at a time.
7. After report 005, the next priority is the 31B track (main prize; we have zero 31B timing). Pre-register a 31B timing plan (eval/plans/) with a cap chosen by the same total-Phase-1-wall rule, ~8 dev ids, budget <= 4 quota-h this week. It's within the weekly plan, so no further decision is needed to push it, but report before any 31B submission.

Reasoning: e4b-v001 is the only bundle that passes the bound today. A first scored submission is high-value information (scorer accepts the bundle, real LB baseline, and it uses otherwise-lost slots). But the margin is seconds per task, so I'm gating on measured total Phase-1 wall, not on the cap arithmetic. I'm not writing a conditional AUTHORIZE line, because kaggle-submit treats any matching line as unconditional; I'll authorize after seeing the numbers.
