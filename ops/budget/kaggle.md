# Kaggle L4x4 quota log
The weekly quota resets Saturday 00:00 UTC. L4x4 counts at 2×.

| date | kernel | L4x4 hours | quota-hours used | purpose |
|---|---|---|---|---|
| 2026-11-05 | aniket0202/gemma-e4b-timing v1 (E4B v000, 8 dev ids, -t 12600s) | FAILED at 2 s (cp312 wheels on default py3.13 image); ~0.05 h incl. boot (est) | ~0.1 (est) | plan 001 timing |
| 2026-11-05 | aniket0202/gemma-e4b-timing v2 (docker_image pinned) | FAILED: got T4 x2 (accelerator 'NvidiaL4X4' unknown -> silent fallback); vLLM bf16 unsupported on T4 | 0.07 h total for week per `kaggle quota` (v1+v2) | plan 001 timing |
| 2026-11-05 | aniket0202/gemma-e4b-timing v3 (machine_shape NvidiaL4 = starter's; fail-fast 4xL4 guard; repo 178e273) | COMPLETE 15:20-~17:03Z, 4x NVIDIA L4 confirmed (~1.7 h) | week total 3.48 h per `kaggle quota` 17:45Z (incl. v1+v2) | plan 001 timing; gate FAIL (report 003) |
| 2026-11-05 | aniket0202/gemma-e4b-timing v4 (E4B v001 cap 1.4, bundles/e4b/v001 == dist/e4b-v001.zip f2ced9c9 + MANIFEST.md; 8 ids eval/plans/004-gpu-retime-ids.txt; conc 1; verification skipped; budget 3900 s, -t 5700 s; branch codex/kernel-setup-fix5 aa116cb + Builder gate fix ef72e7e + guards 9ec991f) | pushed 19:46Z, FAILED 19:54Z in setup (8/8 harness failure at pytest_timeout_source; no offline pytest-timeout 2.1.0); vLLM 319 s | week 3.73 h after (+0.25) | dec 028 item 2 / dec 029 re-time; not relied on until Codex fix5 review clean |
| 2026-11-05 | aniket0202/gemma-e4b-timing v5 (E4B v001 re-time re-push, dec 031; clean worktree at 87001e4, vendored wheels verified vs SHA256SUMS; same bundle f2ced9c9, same 8 ids, conc 1, verification skipped, budget 3900 s, -t 5700 s) | pushed 20:16Z, RUNNING | week before 3.73 h; cap +3.17 | dec 028 item 2 / dec 031; two-strike: no v6 without a decision |
