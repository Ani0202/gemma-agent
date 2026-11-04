# STATE (2026-11-04, cycle 7 / Phase 0)
Best bundles: none validated. v000 packed + static PASS + codex-review static OK (repo SHA a12f0b7):
 31b dist/31b-v000.zip sha256=4a23e14a1aae077161cb137b5ff72afe91ee2acb1d1fdbaf2e322abb6efae161
 e4b dist/e4b-v000.zip sha256=cc647bfb28bc6d2db0e3ec816df084f23a91230786d8fea177e2d63d2a6940e2
Remaining codex BLOCKING: runtime budget/timing unverified (needs harness compile + concurrency-1 timing on L4x4/Kaggle). Manifests+ATTRIBUTION fixed this cycle.
Env: x86_64 VM, 106G free. GCP project gemma-agent-839566. Data: data/raw only; snapshots/graphs/wheels NOT downloaded.
Owner GPU policy (decision 001): Kaggle first; spot + cheapest; requests <=$10; allowance $0. GCP spend $0. Kaggle quota 0h.
Open: spot rates still null (on-demand ceilings recorded: l4x1 0.85, l4x2 2.00, l4x4 4.00, a100 5.03, cpu8 0.27 $/h); rules scout running -> docs/RULES_FINDINGS.md, PRIOR_ART.md. GCP cumulative spend $0.
Running jobs: none.
Next 3: (1) dl-data job finishes -> flatten data/raw/{snapshots,wheels}/ nested dirs; (2) gold calibration on this VM via bin/job (no docker; swegemma not installed; check pip wheels/subprocess sandbox), then splits; (3) Kaggle E4B smoke+timing per plan 001. GCP spend $0.
