DECISION: approve-with-changes
SUBMIT: none
GPU_ALLOWANCE: none
ESCALATE: none
DIGEST: Small-model timing run measured cleanly but missed the safety margin; a tighter-capped version is approved for build, first submission to follow once reviews are clean.
---
I spot-checked results/kaggle_timing_e4b_v001.json. gate.status is FAIL: (a) 7/8, with rich_3930 'Harness task failure'; (b) 305.56 s against 296; (c) 266.70; (d) 352.5; (e) 7. The per-task rows match the report table. Provenance: git_sha is 87001e4 and the hardware is 4x NVIDIA L4. The two-strike stop was handled correctly. Option A is approved as below.

1. BUILD bundles/e4b/v002 = v001 with EXACTLY two changes: max_time_minutes 1.4 -> 1.0, and max_output_tokens 16384 -> 8192. First grep the whole bundle (agent.yaml, every sub_agent, every config) for 16384 / max_output_tokens / max_tokens and change EVERY occurrence. List them in MANIFEST.md. Nothing else changes: no prompt edits, no item-4 work in this bundle. The eval_config.yaml comment states the derivation: worst = 60 + 1.32 + 221.6 = 282.9 s/task -> 619.4 min <= 660 (dec 028 item 4 rule, on TOTAL Phase-1 including image emulation).
2. Pack with bin/pack and record the sha256 in MANIFEST. Run a local load check proving that the ADK config parses and the two new values are what the runtime reads (print the effective max_output_tokens per agent and the effective timeout). Then codex-review the v001 -> v002 diff (light).
3. SUBMIT request conditions (all must hold; this is pre-registered now):
   (i) bin/pack validation passes and the sha256 is in MANIFEST;
   (ii) the v002 bundle review has no BLOCKING;
   (iii) the Codex fix5c review (main...87001e4) is clean, or its BLOCKING items are classified "summary/gate-logic only" and none affects the measured setup/agent/finalization seconds (dec 029 item 3, dec 031 items 4 and 6);
   (iv) the diff to v001 is exactly the item-1 changes.
   When all hold, send a short follow-up: SUBMIT dist/e4b-v002.zip sha256=<hex> track=e4b, with links to both reviews. No re-time is needed. The cap only shrinks the agent clock, and the non-agent overhead was measured on the scorer hardware. This is a deliberate baseline/information submission (gate item 3 justified: there is no scored best yet). It is not a structural change, so gate item 5 does not apply.
4. Slot: the dec 030 item 4 cut-off is unchanged. If the request reaches me before ~23:45Z it goes in today's slot; otherwise Nov 6. No partial reports, and nothing gets rushed.
5. Records hygiene (dec 031 item 5 pattern): add the note field to results/kaggle_timing_e4b_v001.json naming the top-level "decision" as the legacy projection, not the gate. Don't change any values. Bundle it with the next reviewed timing_summary change.
6. CPU-only, short note in the next report: explain why rich_3063 (task 1) spent 1.5 s in setup.py while tasks 2-8 spent ~202 s with 0 Retrying lines. If it shows the 202 s is an emulation artifact rather than a scorer property, that would free ~3 min/task of cap on BOTH tracks, so it matters a lot. Use existing logs only; no new Kaggle run for this.
7. After the v002 SUBMIT request, the single most important next experiment is the 31B timing run (plan 006, dec 028 item 7, <= 4 quota-h, pre-approved). Set its cap by the same total-Phase-1 rule using S/F from this run. It will land around 1.0-1.2 min, so state it explicitly in the plan addendum before pushing. 31B vLLM startup must be measured and checked against (d) <= 10 min. If it's longer, the +30 constant needs revisiting in the report.
8. After that: dec 022 item 4 (empty-patch protection: rich_3067 shipped an empty diff; test-file edits) as the first quality lever, via codex-build.

Reasoning: we have zero scored submissions and the slots are burning. v002 strictly shrinks the measured v001 envelope. It has 19.5 s/task of margin to our 660-min line, and a ~26% margin to the real 12 h limit at 120 tasks. The token change removes the one observed harness error, and only removes it, so a re-time would cost a day and ~1.5 quota-h to confirm arithmetic. Cap 1.2 (option C) leaves 1.1 s of gate headroom on an 8-task max, which is too thin for a cliff. Before authorizing, I'll run the adversarial codex-ask promised in dec 027 item 7 on the submit-without-re-time logic.
