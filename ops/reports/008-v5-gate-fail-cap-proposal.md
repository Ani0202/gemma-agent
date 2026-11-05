# Report 008: e4b-v001 re-time (kernel v5) measured cleanly but FAILED gate (a) and (b); two-strike STOP; cap proposal for v002

## 1. Question for the Director
Kernel v5 ran to completion and the measurement is valid, but e4b-v001 fails the pre-registered gate: (a) 7/8, because one task hit a context overflow, and (b) max total Phase-1 was 305.6 s against a 296 s limit. Per dec 031 item 2 I have stopped: there is no v6 and no SUBMIT request for v001. May I build e4b-v002 (cap 1.0 min, `max_output_tokens` 16384 → 8192) and request SUBMIT from this measurement without another re-time (option A)?

## 2. Pre-registration (unchanged, written before results)
Dec 028 item 4 gate (a)-(e). Dec 031 item 3: (b) and (c) bind on TOTAL Phase-1 including image emulation; `phase1_minus_image` is reported but is not a gate. If the gate fails on the total, propose a lower cap computed from the total (dec 028 item 4 / dec 030 item 5).

## 3. What I did
- Kernel v5 was pushed 20:16Z from a clean worktree at exactly 87001e4 (dec 031 item 1) and finished ~21:00Z. The waiter downloaded the output to `runs/e4b-v001-timing-v5/` (gitignored).
- I ran `eval/kaggle/timing_summary.py` from 87001e4, writing `results/kaggle_timing_e4b_v001.json`.
- Provenance OK:
  - header git_sha is 87001e4593a6…;
  - agent_yaml_sha256 427db5ca… equals `unzip -p dist/e4b-v001.zip agent.yaml | sha256sum`;
  - hardware was 4x NVIDIA L4, concurrency 1, caps max_time_minutes 1.4.
  - The header's `bundle_sha256` (e82cf07b…) is the kernel's hash of its embedded payload, not the dist zip hash. The agent.yaml match is the binding check.
- Quota: `kaggle quota` shows 5.18 h used of 30 this week (v5 used ≈1.45 h). Resets Sat 00:00Z.
- Reliance caveat (dec 031 item 4): the Codex fix5c review (main...87001e4, 23:08Z) has not run yet. These numbers are provisional until it is clean.

## 4. Results (`results/kaggle_timing_e4b_v001.json`, n=8 tasks, 1 sample each, concurrency 1)
| task | setup s | agent s | timeout fired | finalize+teardown s | TOTAL Phase-1 s | minus image s | diff |
|---|---|---|---|---|---|---|---|
| rich_3063 | 16.6 | 72.9 | no | 0.28 | 93.0 | 80.6 | yes |
| rich_3067 | 215.9 | 84.0 | yes | 0.29 | 303.2 | 291.7 | **empty** |
| rich_3454 | 215.7 | 41.9 | no | 0.29 | 260.7 | 249.3 | yes |
| rich_3535 | 215.8 | 84.0 | yes | 0.29 | 302.7 | 291.2 | yes (fallback) |
| rich_3930 | 215.4 | 69.1 | no | 0.30 | 287.1 | 275.7 | yes (fallback); **HARNESS ERROR** |
| rich_3953 | 215.6 | 84.0 | yes | 0.30 | 302.7 | 291.2 | yes (fallback) |
| fastapi_14258 | 215.1 | 85.3 | yes | 0.52 | **305.6** | 294.2 | yes (fallback) |
| fastapi_14851 | 215.1 | 56.9 | no | 0.44 | 278.5 | 267.2 | yes |

| gate | value | threshold | status |
|---|---|---|---|
| (a) all complete, no harness error | 7/8 | 8 | **FAIL** |
| (b) max TOTAL Phase-1 | 305.6 s | ≤ 296 | **FAIL** (without image emulation: 294.2, not a gate per dec 031 item 3) |
| (c) mean TOTAL Phase-1 | 266.7 s | ≤ 270 | PASS (margin 3.3 s) |
| (d) vLLM startup | 352.5 s | ≤ 600 | PASS |
| (e) ≥1 non-empty source diff | 7 | ≥ 1 | PASS |

The setup failures I report here as prominently as the passes:
- **(a) failure cause:** rich_3930 got vLLM 400 "maximum context length is 32768 tokens… requested 16384 output tokens and your prompt contains at least 16385 input tokens".
  - The bundle requests `max_output_tokens: 16384` (`configs/sampling.yaml:3`, `sub_agents/code_analyzer.yaml:21`). Any prompt over 16384 tokens therefore errors, and that happened at 69 s.
  - This is bundle behaviour, not a kernel artefact, so the scorer would hit it too. The fallback diff still produced a non-empty patch.
- **Setup, 7/8 tasks:** setup is ~202 s inside the `setup.py` step (rc 0, 0 Retrying lines). rich_3063, the first task, took 1.5 s there. This matches report 004 (harness property). So S ≈ 216 s total sandbox setup, not ~10 s.
- **Patch hygiene:** 1 empty patch (rich_3067), 1 task with test files edited (stripped by the scorer), 0 stray files.
- **Records hygiene:** the summary's top-level `"decision": "PASS"` is the legacy cap-arithmetic projection field. It is NOT the gate (`gate.status` = FAIL). I have not changed the file's values. Before the file is cited (paper or reports), it needs a note field naming this, as in dec 031 item 5; that is a small timing_summary change that will go through review.

### Cap derivation from TOTAL (dec 028 items 4-5)
- Worst composite = cap + max agent overrun past the cap (1.32 s, fastapi_14258) + max non-agent overhead (Phase-1 minus agent, 221.6 s, fastapi_14851). The overhead includes setup, image emulation, finalization and teardown.
- Projection = composite/60 × 125 + 30.

| cap (min) | worst s/task | projected min | margin to 302.4 s ceiling | gate (b) ≤296 |
|---|---|---|---|---|
| 1.4 (v001) | 306.9 | 669.4 | −4.5 | fail |
| 1.3 | 300.9 | 656.9 | 1.5 | fail |
| 1.2 | 294.9 | 644.4 | 7.5 | pass by 1.1 s |
| **1.0** | **282.9** | **619.4** | **19.5** | pass |

- **Dec 028 item 5 (v002 cap-4.0 path):** S is ~216 s, not ~10 s, so that path stays closed. At cap 4.0: (4.0 + 216/60 + 0.01) × 125 + 30 = 980 min, which is over 660.
- **Why 1.0 rather than 1.2:** the 202 s setup is an 8-task observed max, and an overrun loses the whole submission. At 1.0 the 19.5 s/task margin covers about a 9% worse setup tail.

## 5. Options
- **A (recommended).** Build e4b-v002 = v001 + `max_time_minutes 1.0` + `max_output_tokens 8192` (both places). Pack, codex-review the bundle, then submit on this measurement without a re-time, once the Codex fix5c review is clean. Timing is unaffected because the cap only shrinks the agent clock and the overhead was measured. The token change removes the observed overflow, and 8192 output tokens is far above anything 60 s at E4B speed produces.
  - Pro: a first LB score on Nov 6, and no quota spent.
  - Con: v002 itself is untimed. The overflow fix is untested on Kaggle.
- **B.** Same build, plus one Kaggle re-time of v002 on the same 8 ids (≈1.5 quota-h; week would be ~6.7/30) before SUBMIT.
  - Pro: a direct gate measurement on the shipped bundle.
  - Con: costs a day and quota.
- **C.** Cap 1.2 instead of 1.0.
  - Pro: more agent time.
  - Con: only 1.1 s headroom on gate (b) and 7.5 s to the ceiling, which I judge too thin given the cliff.

## 6. Recommendation
Option A. Request: approve building e4b-v002 (cap 1.0, max_output_tokens 8192). After the bundle review and the Codex fix5c review, I'll send `SUBMIT dist/e4b-v002.zip sha256=<hex> track=e4b` in a short follow-up. No GPU spend is requested. Under the two-strike rule, no v6 push of v001.
