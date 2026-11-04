# Report 001: v000 baseline status and runtime gate
## Question for the Director
v000 bundles are statically valid and codex-reviewed; the only blocker is runtime/timing. May I (a) run a Kaggle L4x4 timing/smoke check of E4B and 31B v000 using the free quota (no GCP), and (b) is anyone able to read the Kaggle Rules tab/threads in a browser (our tooling cannot)?
## Pre-registration
Hypothesis: v000 caps satisfy cap_minutes*125+30 <= 660 and a non-empty diff is produced on smoke tasks. Decision rule: if measured per-task wall time at concurrency 1 times 125 + startup exceeds 660 min, lower caps before any submission.
## What I did
pack-harden merged, v000 re-packed (repo SHA a12f0b7): 31b sha256=4a23e14a1aae077161cb137b5ff72afe91ee2acb1d1fdbaf2e322abb6efae161, e4b sha256=cc647bfb28bc6d2db0e3ec816df084f23a91230786d8fea177e2d63d2a6940e2. Static pack PASS, codex-review static OK (ops/codex/review-20261104T223524.md). Rules scouted from secondary sources only (docs/RULES_FINDINGS.md). Spot rates not found; on-demand ceilings recorded (config/gpu_profiles.json).
## Results
No eval results yet (no runtime numbers exist; nothing to table). Gold calibration, splits not done: snapshots/graphs/wheels not downloaded.
## Options
1. Kaggle-only: notebook pulls the competition data, runs gold calibration on CPU plus E4B/31B smoke+timing on L4x4 (~chunked, within weekly quota; current logged quota 0h, I need the Director to confirm Aniket's Kaggle access/quota). Cost $0.
2. Small GCP cpu8 spot calibration (<$10): needs verified spot rate first; only if Kaggle CPU can't.
3. Do nothing until rules confirmed: loses time.
## Recommendation
Option 1. No SUBMIT request yet (runtime unverified, per Hard rules). GPU +$0. Need: Kaggle notebook/CLI access confirmed, and a human read of the rules tab.
