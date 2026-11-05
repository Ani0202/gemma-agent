# Report 004: the ~210 s per-task setup is (very likely) an artifact of our timing kernel

## 1. Question for the Director
Dec 022 item 2 is concluded as "artifact of our kernel". Do we take the artifact branch of item 3: fix the kernel, verify setup on a Kaggle **CPU** session (no GPU quota), then ONE GPU re-time of v000 at cap 5?

## 2. Pre-registration
eval/plans/003.md (written 18:03Z, before any repro result). Hypothesis: the offline editable install in sandbox/setup.py:208 fails in our subprocess sandbox, and the fallback at :211 (index-backed, PIP_* stripped) waits on an unreachable index. Decision rule: if (1) the offline call fails fast, AND (2) the fallback against a hanging index takes >= 90 s, AND (3) the offline call succeeds fast once the backend is present, then "artifact" is supported. Then fix the kernel and re-time v000 at cap 5 (dec 022 item 3).

## 3. What I did (git 0b09985 + this commit)
- 2a: per-task breakdown from the Kaggle log -> results/kaggle_timing_e4b_v000_setup_breakdown.json. The whole ~208 s sits between the "ensurepip unavailable" warning and the first prompt, i.e. dependency setup. No per-command timestamps exist.
- 2b: codex-ask code read (ops/codex/ask-20261105T175253.md): no unconditional 210 s wait anywhere in the harness. setup.py makes only 3 subprocess calls (:208, :211, :390 slow path), and verification runs dependency setup twice (it takes ~410 s, 2x). The scorer image (Dockerfile.public:9) pre-installs pip and all the build backends; our kernel's venv was created WITHOUT pip.
- 2c: public caps -> docs/RULES_FINDINGS.md C1-C3 (the starter defaults to 60 min when the key is absent; sample_submission uses 1 min; the "[0.10]" notebook uses 4.5 min, which bounds only the MEAN setup+agent time, < ~5.9 min).
- 2d: Codex's adversarial take is included in 2b: ~80% artifact. Its strongest counter-argument is that constant input can mean constant real work. The wheelhouse is 27 MB, so extracting it is not 210 s.
- Plan 003 local repro: eval/repro/plan003_pipfb_v{1,2}.sh. v1 was invalid (pip ignores plain-http untrusted indexes) and is reported here, not hidden.

## 4. Results (results/plan003_pip_fallback_repro.json; Kaggle data results/kaggle_timing_e4b_v000_setup_breakdown.json)
| case (fresh py3.13 venv, no backend) | poetry-core | pdm-backend |
|---|---|---|
| (1) offline --no-index --no-build-isolation | 0.3 s, rc 2 (fails) | 0.3 s, rc 2 |
| (2) fallback, https index that hangs | **103.4 s**, rc 1, 5 retries | **103.3 s**, rc 1, 5 retries |
| (2') fallback, index DNS fails | 8.0 s, rc 1 | 8.0 s, rc 1 |
| (3) offline after backend installed | 0.6 s, rc 0 | 0.4 s, rc 0 |

| Kaggle quantity (n=8 tasks, 1 sample each) | measured | repro prediction |
|---|---|---|
| setup (warning -> first prompt) | 207.4-210.8 s | 2 hung calls = 206.8 s |
| verification wall (2 setups) | 410.1-411.9 s | 4 hung calls = 413.4 s |

The decision rule is met on all three conditions. Caveats: (a) Kaggle's setup.py output was never captured, so WHY its offline install failed is unproven. Our injector does extract poetry_core/pdm_backend; the leading candidate is that the pip came from the system site-packages, combined with an ABI or path issue (Codex also flags cp313 wheels selected for a py3.12 run). (b) "2 hung calls per setup" is inferred from the timing match, not observed. No paired pass-rate comparison applies (this is a timing question).

Implication: if the fix holds, setup drops to ~seconds and the interim rule gives a max cap of (660-30)/125 - setup ≈ **4.85 min** (setup 10 s). cap 5 itself still fails the gate: (5+0.2)x125+30 = 680. A re-time at cap 5 measures agent time; the ship cap would be ~4.75. 31B (dec 022 item 5): the ~1.4-min squeeze would not apply, so there's no track-split change yet.

## 5. Options
A. **Artifact branch as written** (dec 022 item 3a): merge the kernel fix (codex-build kernel-setup-fix, running; spec ops/codex/build-kernel-setup-fix.spec: pip + Dockerfile.public tool set offline in the sandbox venv, PIP_NO_INDEX prefix, per-step setup_calls logged, bwrap --unshare-net local acceptance), then ONE GPU re-time of v000 at cap 5 on 8 fresh dev ids, verification skipped (~1.7 L4x4 h). Risk: if the fix is incomplete on Kaggle, we burn the one run.
B. **A, plus a CPU-only Kaggle check first** (recommended): push the fixed kernel as a CPU session, internet off, pinned image, setup only, no model, on the same 8 + 8 fresh ids. It costs no GPU quota and ~20 min wall. It captures the real setup.py output. Gate: per-task setup <= 30 s and editable install rc 0 on all tasks. Only then the GPU re-time (A). If setup is still >= 60 s, fall back to C with real evidence.
C. **Treat as unresolved**: re-time v001 (cap 1.4). Safe, but it probably guts quality on both tracks, and the evidence now argues against it.

## 6. Recommendation
B. Requests: approve a Kaggle CPU-only setup-verification session (no GPU quota), then the single dec 022 GPU timing run of v000 at cap 5 after the CPU gate passes. No submission, no holdout use, no GCP spend.
