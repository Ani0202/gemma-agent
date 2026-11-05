# Kaggle L4x4 quota log
The weekly quota resets Saturday 00:00 UTC. L4x4 counts at 2×.

| date | kernel | L4x4 hours | quota-hours used | purpose |
|---|---|---|---|---|
| 2026-11-05 | aniket0202/gemma-e4b-timing v1 (E4B v000, 8 dev ids, -t 12600s) | FAILED at 2 s (cp312 wheels on default py3.13 image); ~0.05 h incl. boot (est) | ~0.1 (est) | plan 001 timing |
| 2026-11-05 | aniket0202/gemma-e4b-timing v2 (docker_image pinned) | FAILED: got T4 x2 (accelerator 'NvidiaL4X4' unknown -> silent fallback); vLLM bf16 unsupported on T4 | 0.07 h total for week per `kaggle quota` (v1+v2) | plan 001 timing |
| 2026-11-05 | aniket0202/gemma-e4b-timing v3 (machine_shape NvidiaL4 = starter's; fail-fast 4xL4 guard; repo 178e273) | pending (est ≤1.6 h, hard ≤3.5 h) | pending | plan 001 timing |
