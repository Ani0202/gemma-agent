# STATE (2026-11-04, cycle 20 (dec 008 done: overrun doc fix) / Phase 0)
Best bundles: none validated. v000 packed + static PASS + codex static OK (repo SHA a12f0b7):
 31b dist/31b-v000.zip sha256=4a23e14a1aae077161cb137b5ff72afe91ee2acb1d1fdbaf2e322abb6efae161
 e4b dist/e4b-v000.zip sha256=cc647bfb28bc6d2db0e3ec816df084f23a91230786d8fea177e2d63d2a6940e2
Remaining codex BLOCKING: runtime budget/timing unverified (needs concurrency-1 timing on L4x4/Kaggle).
Env: x86_64 VM. GCP project gemma-agent-839566, spend $0. Kaggle quota used 0h. Owner GPU policy (dec 001): Kaggle first.
GCP quota (dec 003): only l4x1 spot + cpu8 usable; multi-GPU -> Kaggle.
Rules (dec 004-002-001): docs/RULES_FINDINGS.md rewritten from official sources; no repo overlap with hidden set; LORO mandatory for ship decisions; no partial credit on timeout.
Running jobs: gold-wait (Kaggle gold kernel v3, aniket0202/gemma-gold-patch-calibration; earlier v2 failed on wheel install, log in runs/gold-calibration is stale v2).
Open: (1) E2 resolved (dec 005): paper session owns paper/, do not edit; keep results/ files self-describing (schema + header line). (2) Director reminder due 2026-11-06T23:02Z: GCP quota re-request line to Aniket; keep until decision marks done. (3) Hosted-LLM-API data question OPEN; no new third-party services.
Next 3: (1) gold output -> clean list + splits; (2) E4B smoke+timing kernel (L4x4) per plan 001; (3) report 002 with baseline SUBMIT.
Paper evidence (dec 007, due Nov 9 23:59Z, no extra compute): commit schema-headed results/ files for (a) gold calibration per-task outcomes+exclusion causes, (b) timing per task from Kaggle E4B smoke (31B if run), (c) failure taxonomy via trace-analyst once. Not yet produced; flag here if any won't exist by Nov 9.
