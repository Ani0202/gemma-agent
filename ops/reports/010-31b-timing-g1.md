# Report 010: plan 006 (31B timing at cap 4.0) result; G1 holds -> SUBMIT 31b-v002
2026-11-06T01:05Z, Builder. Run: kernel aniket0202/gemma-31b-timing v1 (repo main 2db5f51, bundle 31b-v001-t4).
Results file: results/kaggle_timing_31b_v001.json (schema kaggle_timing_summary_v1, `--gate-mode stock-path --gate-vllm-seconds 600`).

## 1. Question for the Director
G1 holds (all three legs). Do you authorize submitting 31b-v002 (cap 3.5) after e4b ref 58039259 is final, as dec 053
anticipated? I also propose a pre-registered veto on that submission, based on e4b's elapsed scoring time (section 5, A).

## 2. Pre-registration (copied from eval/plans/006.md, dec 034 item 2 + dec 036; written before any 31B data)
- Gates: (a) 8/8 complete, no harness error; (b) max(stockpath_phase1) <= 4.0 x 60 + 37 = 277 s; (d) vLLM startup <= 600 s;
  (e) >= 1 non-empty source diff; (c) not gated.
- G1 = P2 docker_which null AND docker_sock false; P1 stock setup <= 30 s on all 8 (all_le_30s); gates PASS.
  All three -> request SUBMIT 31b-v002 (cap <= 3.5, byte-identical to v001-t4 except cap + comment, no re-time). Lead with h1_composite.

## 3. What I did
Waited for the kernel (COMPLETE 00:51Z, ~63 min runtime). Downloaded the outputs to runs/31b-v001-t4-timing and ran
eval/kaggle/timing_summary.py (main 2db5f51, reviewed) in stock-path mode. No code changes. Kaggle GPU this week is now
**7.28 / 30 h** per `kaggle quota` (+2.10 h for this run, below the ~2.6 h estimate). It resets 2026-11-07T00:00Z.

## 4. Results (n = 8 dev-timing ids, eval/plans/004-gpu-retime-ids.txt, 1 sample each, concurrency 1, 4x NVIDIA L4, verification skipped)
| item | value | threshold | verdict |
|---|---|---|---|
| **h1_composite max** (agent clock + finalization + P1 stock setup) | **245.6 s** (mean 221.4) | reported, not gated | -> ~3.6 min/task at cap 3.5 |
| (a) complete, no harness error | 8/8 | 8 | PASS |
| (b) max stockpath_phase1 | 243.4 s | 277 s | PASS |
| (d) vLLM startup (31B) | 364.5 s | 600 s | PASS |
| (e) non-empty source diff | 4/8 (Wilson 95% 22-78%) | >= 1 | PASS |
| P2 platform probe | docker_which null, docker_sock false; DNS pypi.org timeout (10 s) | — | G1 leg PASS |
| P1 stock subprocess setup | max 5.33 s, all 8 <= 30 s (1.9-5.3 s) | 30 s | G1 leg PASS |
| P3 decode, per task | 27.2-33.5 completion tok/s (gap-based); 10-41 LLM calls; 1.3-5.4 calls/min | — | scorer conditions |
All values are from results/kaggle_timing_31b_v001.json (gate, probes.*, h1_composite_seconds, tasks[]).

**Failures, as prominently as wins:**
- **6/8 hit the 4.0-min timeout** (agent_outcome timeout). Only 2 called submit (rich_3454 at 133 s, fastapi_14258 at 172 s).
- **4/8 ended with an empty source diff** (rich_3063, rich_3067, rich_3535, fastapi_14851). All four timed out before
  any edit landed. The other 2 timeouts produced a diff only through the fallback patch (rich_3930, rich_3953).
  At cap 3.5 I expect at least as many empty diffs. No pass rate exists (verification skipped, by design).
- Emulation diagnostics (not gated, same as e4b v5): setup_failed / editable_failed / fallback 7/8. This is the known
  ~202 s networked setup.py pip fallback in our Dockerfile.public emulation (setup_py_emulation max 202.2 s). It is subtracted by
  stock-path (b).
- There were 0 test-file edits and 0 stray files. The old legacy projection field still says FAIL (956 min); that is the
  dec 032 item 5 total-wall projection, which includes the emulated 202 s, and it is not the gate.

**Runtime projection for 31b-v002 (cap 3.5), worst case at 125 tasks:**
- H1 (subprocess backend, setup.py skipped; supported by P2 + P1): per task <= 210 + 5.3 + 0.24 + ~0.2 s ≈ 3.6 min.
  125 x 3.6 = 450 min, + vLLM 6.1 min, + 30 min margin ≈ **486 min, under the 660-min limit (174 min of headroom)**.
- H2 (setup.py runs and hits the ~202 s network blackhole): ≈ 7.0 min/task -> ~880 min, **which overruns 12 h**. That would fail the
  submission (one slot lost, no partial credit). P2 shows that a Kaggle notebook (where E4 places the scorer) has no Docker, which
  is the main argument against H2. The residual risk is that the scorer uses Docker on a non-notebook host (report 009 E5).

## 5. Options
- **A (recommended). SUBMIT 31b-v002 after e4b ref 58039259 is final, with a veto.** Pre-registered now, before the e4b score
  arrives: let T = e4b complete_utc - 00:11:23Z. Under H1, e4b-v002 (cap 1.0) needs ≈ 125 x ~1.1 min + startup ≈ 2.5 h; under H2
  it needs ≈ 9.5-10 h. **If T > 8 h, or e4b fails on time, do NOT submit 31b-v002.** In that case report back with the cap-1.23
  fallback (B). If T <= 8 h, submit as authorized. This uses T only as a veto, never as a go signal on its own (dec 034
  "weak evidence"), since queueing can only make T larger. Trade-offs: it gives the first real-scorer validation of a cap above
  the H3 bound, which is what the FINALS RULE needs before Nov 29. The LB score will be weak (about half empty diffs), but the
  bundle has the same model and prompts as later 31B quality bundles. Risk: if H2 holds and the veto misses (T short for other
  reasons), we lose one slot.
- **B. 31B at cap <= 1.23 (H3-safe).** This fits in every world. But at cap 4.0 half the tasks made no edit, so at 1.23 almost all
  diffs would be empty. It would measure almost nothing about quality and would not validate any cap we would ship.
- **C. Repeat e4b-v002 for LB variance.** This costs no build work and tells us about run-to-run noise. It gives no 31B
  information and delays 31B validation by a day.

## 6. Recommendation
**A.** `SUBMIT dist/31b-v002.zip sha256=e56a05e5701fa16a8dbbabb304d98f63a465511cefbb28d65850ea5ce086ec88 track=31b`,
conditional on: e4b ref 58039259 final (server list checked first); veto T > 8 h; dec 054 SUBMIT_KERNEL config commit
(-> gemma-submit-31b v1) before the submit; no change to v002 or the kernel since review-20261106T001642 (clean).
Next (pre-approved, CPU): with plan 006 done, the dec 050 heavy-job hold lifts, so I start plan 005 (dec 022 item 4: truncation-safe
diff, i.e. the 4 empty-diff timeouts above) and plan 007. Neither changes v002.
