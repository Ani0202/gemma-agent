# STATE (2026-11-04, cycle 2 / Phase 0)
Best bundles: none validated. v000 packed+PASS (bin/pack): dist/31b-v000.zip sha256=4a23e14a1aae077161cb137b5ff72afe91ee2acb1d1fdbaf2e322abb6efae161 ; dist/e4b-v000.zip sha256=cc647bfb28bc6d2db0e3ec816df084f23a91230786d8fea177e2d63d2a6940e2. Sub-agent includes inlined (.. is blocked). Awaiting codex-review.
Env: x86_64 VM, 106G free, 11G RAM. GCP project gemma-agent-839566, zone us-central1-a.
Data: data/raw has HARNESS_README, tasks.jsonl, docker/, sample_submission/, sandbox/setup.py. Snapshots(129)/graphs(59)/embeddings(127)/wheels(124) NOT downloaded (decide location).
Note: sample eval_config caps are tiny (1 min, 10 calls) - not a usable baseline.
Running jobs: codex-pack (bin/pack + tests, branch codex/pack).
GPU spend $0. Kaggle quota 0h.
Open: gpu_profiles.json rates null; COMPLIANCE.md not started; rules pages unread (scout/WebFetch); is the public-best 31B config known? (need PRIOR_ART).
Next 3: (1) review+merge codex/pack, run pack on both bundles, codex-review, report 001 (SUBMIT 31B v000); (2) rules/discussion read -> COMPETITION.md, COMPLIANCE.md; PRIOR_ART; (3) gpu profiles + $5 cpu8 request; gold calibration.

OWNER GPU POLICY (decision 001): Kaggle first; spot + cheapest profile; requests <=$10 with rate x hours estimate; allowance $0. Cumulative GCP spend: $0 (milestones 50/100/130). bin/gpu already SPOT; rates in config/gpu_profiles.json still null.
Next: after review -> report 001 (baseline SUBMIT 31B v000 maybe), rules reading, fill spot rates, check gold calibration on CPU/Kaggle.

[cycle 4] codex-review done: prompts fixed (/tmp rule, submit last) -> bundles v000 edited, zips in dist/ are STALE until re-pack. Running: codex-build pack-harden. Next: merge pack-harden, re-pack + re-review, report 001.
Codex pack-hardening handoff (2026-11-04T22:28Z):
- Implemented review BLOCKING 1–2 and non-blocking 1,3 in bin/pack; docs/PACK.md defines static validation guarantees.
- Offline pack tests: 341 passed, 1 expected fallback-alias skip; both unchanged v000 bundles PASS (6057 shipped bytes each).
- No zip rebuilt, evaluation run, GPU/cloud spend or submission. Existing zip hashes above remain unchanged.
- Next: Builder review of bin/pack, eval/tests/test_pack.py and docs/PACK.md; wrapper commits; harness compilation/runtime checks remain separate.
- Source review/README read from main checkout because this worktree has an empty review file and no data/raw directory.

[cycle 5] pack-harden merged (a12f0b7), v000 zips re-packed (shas above, current). Next: final codex-review of re-packed bundles, report 001, rules/COMPLIANCE reading.

[cycle 6] Running: review-v000 (codex-review of re-packed bundles). GCP cumulative spend $0. Spot rates NOT filled: web search gave no verified spot numbers (on-demand g2-standard-48 ~ $4.00/h unverified); need cloud pricing page fetch/gcloud SKU lookup. Next: read review -> fix -> report 001; rules reading; rates.
