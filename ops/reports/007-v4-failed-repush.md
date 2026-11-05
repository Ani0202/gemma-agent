# Report 007: e4b-v001 re-time kernel v4 failed in setup (no measurement); fixed; request one re-push

## 1. Question for the Director
Kernel v4 recorded no timing: all 8 tasks failed in 2-4 s at the setup step that emulates `pytest-timeout==2.1.0` from Dockerfile.public line 9. The kernel is now fixed and verified locally without the stub that hid the bug. May I push the e4b-v001 re-time once more as kernel v5? Dec 028 item 2 / dec 029 authorized ONE run, and v4 produced no measurement.

## 2. Pre-registration
Unchanged from dec 028 item 4 (gate (a)-(e)) and dec 029/030. The same bundle (dist/e4b-v001.zip sha256 f2ced9c9…, from bundles/e4b/v001), the same 8 ids, concurrency 1, verification skipped, budget 3900 s, `-t` 5700 s (≤ 3.17 quota-h cap; expected ~2).

## 3. What I did
- **v4** (branch codex/kernel-setup-fix5 at 9ec991f, pushed 19:46Z, done 19:54Z):
  - vLLM startup was 319 s on 4x NVIDIA L4 (header confirms).
  - Every task then hit `Sandbox execution error: No offline pytest-timeout 2.1.0 source available` at `pytest_timeout_source`. The agent never ran: 0 LLM calls.
  - The fail-closed classification (ef72e7e) correctly labelled every row a harness failure.
  - Cost: 0.25 quota-h (week 3.48 → 3.73 per `kaggle quota`).
  - Raw output is in `runs/e4b-v001-timing/` (gitignored).
- **Root cause:**
  - Dockerfile.public line 9 pip-installs the tools online at image build time.
  - The offline Kaggle wheelhouse has no pytest-timeout 2.1.0, and neither does the Kaggle runtime.
  - The local acceptance run (`results/plan003_kernel_setup_acceptance*.json`) passed because `/home/ubuntu/gemma-local/imgrt-stub` was on PYTHONPATH and supplied pytest-timeout 2.1.0, pathspec, shellingham and trove-classifiers.
  - Neither Claude review nor the unit tests could see this.
- **Fix (three commits on codex/kernel-setup-fix5):**
  - **9d386bc:** vendors the official PyPI `pytest_timeout-2.1.0-py3-none-any.whl` and embeds it in the kernel (`EXTRA_WHEELS`), sha256-checked at push time and in the kernel. Adds a pre-vLLM tool-source check.
  - **1c13123:**
    - A local repro run without the stub showed that `pathspec`, `shellingham` and `trove-classifiers` (hatchling/typer runtime deps) were also missing. Their official PyPI wheels are now vendored, pinned in `eval/kaggle/vendor/SHA256SUMS`; the hashes match PyPI's published digests.
    - Dependency source order is now: wheelhouse, then the embedded wheels (pip-installed, like the image), then a runtime copy.
  - **87001e4** (after a fresh Claude review found a BLOCKING issue, `ops/reviews/claude-review-vendor-fix.md`, verbatim):
    - The new pip pre-check would have falsely aborted on Kaggle, where pip comes from a runtime copy. It now accepts exactly the sources `bootstrap_pip` accepts.
    - The closure walk now mirrors the real setup code: tag-filtered `compatible_wheels`, the same runtime-copy predicate, and expansion of runtime-sourced requirements.
    - Also vendors `annotated-doc` (a typer dep, absent from the wheelhouse; locally it was hidden by the venv).
    - The pre-check is gated on SETUP_FIX=1.
  - Attribution is logged in docs/ATTRIBUTION.md. These are public eval tooling, not training data and not part of the submission.
- **Verification:**
  - 111 unit tests pass.
  - The strict closure test, with no runtime fallback, is complete against the local wheelhouse copy, also under cp312 tags.
  - The staged kernel's `check_tool_sources` passes under the Kaggle pip condition (no pip wheel, no ensurepip).
  - The no-stub repro reproduces the v4 failure before the fix and runs the full Docker-order sequence after it, with all 4 non-wheelhouse deps taken from the embedded wheels.
  - Final Claude re-review of 87001e4: **NO BLOCKING** (ops/reviews/claude-rereview-vendor-fix.md, verbatim). Its simulation with cp312 tags and 3.12 markers found the setup closure and the preflight both resolve fully (16 edges, all from wheels). Its 5 NB items are theoretical, test-quality or the /wheels nit; none affect this run.
  - Codex fix5 review (23:08Z, medium, alone) now targets main...87001e4. Its prompt mentions no Claude findings (dec 030 item 2).

## 4. Results (setup only; no timing yet)
| run | env | tasks | outcome | file |
|---|---|---|---|---|
| kernel v4 (9ec991f) | Kaggle 4xL4 | 8 | 8/8 harness failure at pytest_timeout_source, 2-4 s each; vLLM 319 s | runs/e4b-v001-timing/timing.jsonl |
| no-stub repro, unvendored | local, offline (bwrap) | 2 x 2 modes | fix mode fails at pytest_timeout_source (reproduces v4) | results/plan003_kernel_setup_nostub_unvendored.json |
| no-stub repro, vendored (87001e4) | local, offline | 2 x 2 modes | fix mode: full sequence, missing_tool_deps []; image-emulation steps ~5.4 s/task; rich_3006 editable rc 1 + 5 Retrying (known non-fatal scorer behaviour, as in the with-stub run) | results/plan003_kernel_setup_nostub_vendored.json |

Note for report 005: the image-emulation steps (tool_install ~1.5 s, tool_deps ~3.3 s, pip_check ~0.16 s, bootstrap ~0.34 s) add about 5.4 s/task inside Phase-1. That is higher than the 2.5-4 s the first review estimated, and it is conservative, since the scorer image already contains these. Gate (b) has ~6.4 s/task headroom, so the Director may want to see `phase1_minus_image_seconds` too (it is reported but not gated).

## 5. Options
- **A. Re-push now as v5 from 87001e4** (only if the final re-review has no BLOCKING findings). About 2 quota-h expected, 3.17 cap; week ~5.9/30 at worst. Results land around 21:00Z, before the 23:08Z Codex review, so today's slot stays possible under dec 029/030.
- **B. Wait for the Codex review at 23:08Z, then push.** Safer if you want Codex to see the vendoring first. Results then arrive around 00:30Z, so this is the Nov 6 slot at the earliest.
- **C. Drop the image-emulation steps and assume the scorer image's tools.** Faster and closer to the scorer's per-task cost, but it departs from dec 027 fidelity (the tools would then come from the Kaggle runtime, untested). Not recommended.

## 6. Recommendation
**A. SUBMIT none; Kaggle re-push: kernel v5 from 87001e4, dist/e4b-v001.zip sha256=f2ced9c97ee1447cb3a78c0ebf65f4ecaff90c84b18313645d5d043c62d277e9, 8 ids, budget 3900 s, -t 5700 s (≤3.17 quota-h; week would be ≤6.9/30).** The measurement is reversible and cheap, and the Codex review still gates any reliance on it (dec 029 item 3). The Codex fix5 prompt will be updated to HEAD = the pushed SHA, still without Claude findings (dec 030 item 2).
