# STATE (2026-11-04, cycle 7 / Phase 0)
Best bundles: none validated. v000 packed + static PASS + codex-review static OK (repo SHA a12f0b7):
 31b dist/31b-v000.zip sha256=4a23e14a1aae077161cb137b5ff72afe91ee2acb1d1fdbaf2e322abb6efae161
 e4b dist/e4b-v000.zip sha256=cc647bfb28bc6d2db0e3ec816df084f23a91230786d8fea177e2d63d2a6940e2
Remaining codex BLOCKING: runtime budget/timing unverified (needs harness compile + concurrency-1 timing on L4x4/Kaggle). Manifests+ATTRIBUTION fixed this cycle.
Env: x86_64 VM, 106G free. GCP project gemma-agent-839566. Data: data/raw only; snapshots/graphs/wheels NOT downloaded.
Owner GPU policy (decision 001): Kaggle first; spot + cheapest; requests <=$10; allowance $0. GCP spend $0. Kaggle quota 0h.
Open: spot rates still null (on-demand ceilings recorded: l4x1 0.85, l4x2 2.00, l4x4 4.00, a100 5.03, cpu8 0.27 $/h); rules scout running -> docs/RULES_FINDINGS.md, PRIOR_ART.md. GCP cumulative spend $0.
Running jobs: none.
<<<<<<< HEAD
Next 3: (1) gold kernel aniket0202/gemma-gold-patch-calibration running on Kaggle CPU; job gold-wait fetches output to runs/gold-calibration -> clean list + splits; (2) E4B smoke+timing kernel (L4x4) per plan 001; (3) verify GCP spot rates. GCP spend $0.
GCP quota (dec 003): 1 GPU total, no A100; only l4x1 spot + cpu8 usable; l4x2/l4x4/a100 marked "unavailable" in config/gpu_profiles.json. bin/gpu does not read that flag (my edit to it was blocked) but all rates are null so it refuses every profile anyway. Multi-GPU -> Kaggle.
OPEN (Director reminder, due 2026-11-06T23:02Z): Director sends Aniket the GCP quota re-request line (GPUs all regions=2 then 4; preemptible L4 us-central1=4). Keep until a decision marks done.
=======
Next 3: (1) gold kernel aniket0202/gemma-gold-patch-calibration running on Kaggle CPU; job gold-wait fetches output to runs/gold-calibration -> clean list + splits; (2) E4B smoke+timing kernel (L4x4) per plan 001; (3) verify GCP spot rates. GCP spend $0.

Codex gold kernel implemented: eval/kaggle/gold_calibration.py + metadata/push helper; 13 offline tests PASS. Not pushed/run; verify_task API and CPU wheelhouse need Kaggle smoke check. See docs/GOLD_CALIBRATION.md.
>>>>>>> codex/gold-kernel
