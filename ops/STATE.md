# STATE (2026-11-05, cycle 23 / Phase 0)
Best bundles: none validated. v000 packed + static PASS + codex static OK (repo SHA a12f0b7):
 31b dist/31b-v000.zip sha256=4a23e14a1aae077161cb137b5ff72afe91ee2acb1d1fdbaf2e322abb6efae161
 e4b dist/e4b-v000.zip sha256=cc647bfb28bc6d2db0e3ec816df084f23a91230786d8fea177e2d63d2a6940e2
Remaining codex BLOCKING: runtime budget/timing unverified (needs concurrency-1 timing on L4x4/Kaggle).
Env: x86_64 VM. GCP project gemma-agent-839566, spend $0. Kaggle quota used 0h. Owner GPU policy (dec 001): Kaggle first.
GCP quota (dec 003): only l4x1 spot + cpu8 usable; multi-GPU -> Kaggle.
Rules (dec 004-002-001): docs/RULES_FINDINGS.md rewritten from official sources; no repo overlap with hidden set; LORO mandatory for ship decisions; no partial credit on timeout.
Gold v3 finished but ALL 129 rows = adapter TypeError ('Unsupported verification result'; ~45s/task, verify_task ran, my result-shape assumption wrong). No clean list yet. Fix: worker now records result type/field names (no values) in row['shape']. Smoke v1 (cycle 22): still TypeError, no 'shape' field => error raised elsewhere (likely EvalConfig/verify_task call). Cycle 23: worker now records 'where' (file:line:func, no values); smoke v3 pushed. Running: gold-smoke-wait2 -> runs/gold-smoke2 (kernel aniket0202/gemma-gold-smoke, 1 task/repo via GOLD_LIMIT, ~4 tasks) -> runs/gold-smoke; then fix adapter to real shape and rerun full gold kernel (~50 min CPU, no GPU quota).
Open: (1) E2 resolved (dec 005): paper session owns paper/, do not edit; keep results/ files self-describing (schema + header line). (2) Director reminder due 2026-11-06T23:02Z: GCP quota re-request line to Aniket; keep until decision marks done. (3) Hosted-LLM-API data question OPEN; no new third-party services.
Next 3: (1) read smoke shape, fix adapter, rerun full gold; gold output -> clean list + splits; (2) E4B smoke+timing kernel (L4x4) per plan 001; (3) report 002 with baseline SUBMIT.
Paper evidence (dec 007, due Nov 9 23:59Z, no extra compute): commit schema-headed results/ files for (a) gold calibration per-task outcomes+exclusion causes, (b) timing per task from Kaggle E4B smoke (31B if run), (c) failure taxonomy via trace-analyst once. Not yet produced; flag here if any won't exist by Nov 9.
