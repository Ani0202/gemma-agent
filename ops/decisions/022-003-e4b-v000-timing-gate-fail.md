DECISION: approve-with-changes
SUBMIT: none
GPU_ALLOWANCE: none
ESCALATE: none
DIGEST: First 4xL4 timing run done: fixed per-task setup overhead found, larger than expected; investigating before tightening time caps.
---
I spot-checked results/kaggle_timing_e4b_v000_setup.json. Setup is 208.1-212.0 s on all 8 tasks, vLLM startup is 5.39 min, and the max cap is 1.51 min. These match the report.

1. TIMING RULE (approved as the interim conservative rule, replacing cap*125+30 for every bundle on both tracks): worst case = (cap_minutes + max observed setup_minutes) x 125 + 30 <= 660, with verification excluded. Use the max setup measured on real 4xL4 for that track and model, never an assumed value. This rule binds the Submission Gate from now on.
2. ROOT-CAUSE THE SETUP FIRST (option B; one cycle, no quota, no GPU). Setup flat at 208-212 s (+/- 2 s) across repos looks like a fixed wait (a timeout, a retry/backoff loop, offline pip or index retries, a readiness poll), not real work, which would vary. Do these:
   a. From the existing runs/e4b-timing logs, build a timestamped breakdown of those ~210 s per task: which step starts and ends where. Write it to results/kaggle_timing_e4b_v000_setup_breakdown.json.
   b. Code-read swegemma container_setup and sandbox/setup.py: is the wheels tar or site-packages staging cached across tasks within one run? If so, why did our 8 tasks each pay the cost? Check whether our kernel drives the harness the way the scorer does: one process for all tasks, or one per task.
   c. External sanity check, public info only: what max_time_minutes do the competition starter and the public notebooks use? Do bundles with that cap get scored, or do they time out? If public 5-min-cap bundles score on the LB, then the scorer can't be paying 210 s per task with 125 tasks. Record what you find in docs/RULES_FINDINGS.md.
   d. Get an adversarial take: codex-ask on the a-c evidence: "intrinsic to the scorer, or an artifact of our kernel?"
3. THEN, by outcome:
   - Artifact of our kernel (fixable on our side): fix the kernel and re-time v000 at cap 5 on 8 fresh dev ids, with verification skipped. Use the real setup figure from that run.
   - Intrinsic or unresolved: build e4b-v001 = v000 with only max_time_minutes changed 5 -> 1.4. Pack it, put it through codex-review, and Kaggle re-time it on 8 fresh dev ids, with verification skipped. That run must also report how many truncated runs still produced a non-empty source diff.
   Either way the run must fit the weekly plan (<=10 L4x4 h). Log it in ops/budget/kaggle.md, and run only ONE Kaggle timing run for this question.
   You may build and pack v001 now in parallel with item 2, because it's cheap. Don't push the re-time until item 2 has concluded.
4. TRUNCATION-SAFE DIFF (lever 1, start now, CPU only): make sure that when the agent hits the cap, the current workspace diff is still collected. Add patch hygiene in the bundle: a diff touching only config files like .pre-commit-config.yaml counts as "no source change", so keep working; guard whole-file rewrites (the 190 KB diff) with edit-not-rewrite guidance. Also cut prompt tokens per turn (tool-output trimming). At 7-36 tok/s, with 45k-278k prompt tokens per task, this is the main quality lever under a short cap.
5. 31B: no 31B timing run until item 2 concludes. If setup is intrinsic, the 31B cap will be similar to E4B's (~1.4 min) and per-turn cost is higher. In that case, put a short 31B-vs-E4B quality-under-cap note in the next report, because it may change how we split effort between tracks.
6. OOM LOCAL-JOB POLICY: decisions 020 and 021 already answer this; follow them. `prlimit --as=4GiB` alone is NOT enough. It limits virtual memory per process, not the process tree, and the orphans that survive a timeout are the suspected leak. Required: one process group per task, kill the whole group on timeout, assert no survivors, log peak RSS per task, and bin/memguard running (dec 021). prlimit is only a backstop. The EV-1 gold+null run (dec 019 item 2) goes on the cpu8 VM under the $3 from dec 020, not on this VM.
7. Next report (004): item 2's findings, the re-time result, and the first-submission candidate. Note the 1/8 resolved and the fastapi exit-2 (EV-1 class) failures as caveats.

Reasoning: the 1.4-min cap would cut 5 of the 8 observed runs short and probably gut quality on both tracks. Its basis is a suspiciously constant 210 s that may be a fixed wait or an artifact of our kernel, and that would also cripple 31B. One cheap root-cause cycle can either rescue ~3.5 min/task of agent time or confirm the conservative cap; quota is spent either way. Meanwhile the interim formula keeps every future gate safe: a timeout scores zero, so the cliff takes priority over quality.
