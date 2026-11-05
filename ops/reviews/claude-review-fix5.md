# Claude subagent review: main...codex/kernel-setup-fix5 (aa116cb), dec 029 item 1

## Provenance (Builder)
- Reviewer: a fresh general-purpose Claude subagent, read-only. It was given the code, dec 027/028 and the fix5 spec, not the Builder's conclusion.
- Launched ~19:33Z on 2026-11-05; output received ~19:38Z (before ef72e7e at 19:41:47Z).
- Corrections (dec 030 item 3):
  - The earlier version of this file was lightly copy-edited (ASCII arrows, "nothing was installed").
  - It was replaced by the raw subagent output, verbatim, in the section below.
  - The Builder's actions are in a separate section at the end.

## Raw subagent output (verbatim)

VERDICT: BLOCKING

Reviewed `main...codex/kernel-setup-fix5` (aa116cb) against the installed swegemma 0.2.11 source (`agent_runner.py`, `evaluate.py`, `verification.py`, `sandbox/base.py`, `sandbox/subprocess.py`), dec 027/028, `build-kernel-setup-fix5.spec` and `data/raw/docker/docker/Dockerfile.public`. The unit tests did not run: there is no `pytest` in `/home/ubuntu/gemma-local/venv`, and I installed nothing. All five changed Python files compile, and `bash -n timing_push.sh` passes. I did not do a dry run.

The data flow works end to end: kernel `timing.jsonl` -> `timing_summary.py --output results/kaggle_timing_e4b_v001.json`, and every item dec 028 asks for is recorded. The fidelity rules are met. The blocking problems are all in the gate (a) logic. As written, gate (a) will almost certainly report FAIL for a correct run of v001, and it can report PASS for a run that crashed partway.

## Findings

1. **BLOCKING: agent timeouts are labelled 'Harness task failure'.** `eval/kaggle/agent_timing.py:727-728`, used at `:808`.
   - `harness_error()` returns 'Harness task failure' whenever `result.error` or `agent_error` is non-empty.
   - In swegemma, `agent_error` is set for normal agent outcomes: `'Agent exceeded session timeout (1.4 min)'` (agent_runner.py:1027-1029), the turns-budget message, and `'Agent completed execution without calling submit_patch.'` (:1083, :1101).
   - `skip_verification` copies that string into `TaskResult.error` (agent_timing.py:699-701). The early-return path in evaluate.py:338-346 does the same.
   - Scenario: v001's cap is 84 s, so the E4B agent will hit the timeout on most or all tasks. Every such row gets `error='Harness task failure'`, and gate (a) FAILs (`timing_summary.py:80-88`). The pre-registered submission gate gives a false NO on a valid run. The row also loses the actual category.
   - The spec (item 1) says to flag only real harness/agent-runner errors. No test covers a timeout or no-submit `agent_error`; the test at `test_agent_timing.py:558-559` only checks `''` and 'Sandbox execution error'.
   - Fix: treat it as a harness error only for `Evaluation exception`, `Cleanup exception`, `ContainerSetupError`, a missing snapshot, or an `agent_error` that starts with `'Sandbox execution error'`. Record the rest as `agent_outcome` ∈ {timeout, turns, no_submit} in the row and the summary. Add tests.

2. **BLOCKING: gate (a) also fails any task with `setup_failed`, and on Kaggle that flag will be set for non-fatal setup results.** `timing_summary.py:80-82`.
   - `setup_failed` gets set by:
     - setup.py's own `-e` subprocess returning rc≠0 (`agent_timing.py:515-519`);
     - `workspace_editable` returning rc≠0 (`:485-486`).
   - Neither is fatal in the scorer. Docker runs `pip install ... -e /workspace 2>/dev/null || true`, and setup.py carries on after its editable attempt fails. That is the competition-harness behaviour dec 028 says the scorer shares.
   - Local evidence: `results/plan003_kernel_setup_acceptance_r4local.json` has rich_3006 with fix 1: `editable_rc 1`, Retrying 5, `setup_failed True`. Six of the 8 ids in `004-gpu-retime-ids.txt` are rich tasks, so gate (a) FAILs.
   - Fatal setup failures already raise, and agent_runner turns them into 'Sandbox execution error', so they surface through `error` anyway.
   - Fix: base (a) on `error` only. Report `editable_failed` / `setup_failed` counts as diagnostics outside the gate.

3. **BLOCKING: the expected task count comes from the rows written, not the planned task list.** `timing_summary.py:86-88`.
   - Gate (a) compares `complete == len(tasks)`, so if the kernel stops early (crash, `should_stop`, session timeout) after 5 of 8 tasks, it reports 5/5 PASS.
   - The overall `gate.status` can then be PASS with `missing_task_ids` non-empty and `stopped` set, although dec 028 (a) requires "all 8 tasks complete".
   - The spec said to use the number of rows, but the decision text takes precedence.
   - Fix: `n_expected = len(header['task_ids'])`. Gate (a) requires `complete == n_expected`, no `missing_task_ids`, no `_stopped`, and `done_present`.

4. **NON-BLOCKING (direction is conservative but material at this margin): Phase-1 includes image-emulation work the scorer never pays.**
   - Inside the timed sandbox window the kernel runs `venv_fidelity`, `pip_bootstrap`, `interpreter_probe`, `tool_install`, `tool_deps` and `pip_check` (`agent_timing.py:392-479`), plus four `record_distributions` probes that sit outside `setup_step` timing (`:388, :487, :494, :520`).
   - The scorer image already has those tools installed (Dockerfile.public line 9).
   - Local measurements put this at about 2.5-4 s per task (tool_install 1.5-2.9 s, bootstrap 0.35 s, deps 0.32 s, check 0.18 s, probes). The headroom at the 296 s gate is about 6.4 s per task, so this alone could cause a false FAIL on gate (b).
   - Fix: add `image_emulation_seconds` (the sum of those steps plus timed probes) and `phase1_wall_minus_image_seconds` to the row and summary. Report both and let the Director pick which one gates.

5. **NON-BLOCKING: the subprocess sandbox has no CPU or memory limit, so some steps will run faster than on the scorer.** The scorer gives each task 2 vCPU / 4 GiB. Here, setup.py's pip, the post-cap `git add -N` / `git diff`, and the agent's tests run unconstrained on the Kaggle VM. This underestimate is inherent to subprocess mode. Note it in report 005 as an unmeasured risk to the margin.

6. **NON-BLOCKING: the 4xL4 guard runs only after the full wheelhouse install.** `agent_timing.py:1026` comes after `install()` at `:1010`, which force-reinstalls vllm and torch (several minutes). Fix: run a cheap `nvidia-smi -L` check (count ≥4, all L4) at the top of `main()` before `install()`.

7. **NON-BLOCKING: the results file carries no provenance.** `timing_summary.py:94-134` drops the header's `git_sha`, `bundle_sha256`, `agent_yaml_sha256`, `gpu_names`/`gpu_count`, `caps`, `created_utc` and `verification_skipped`. Also, the kernel tars `bundles/e4b/v001` (which includes `MANIFEST.md`), not `dist/e4b-v001.zip`, so nothing ties the run to sha256 f2ced9c9…. Fix: copy the header provenance into the summary, and check that `agent_yaml_sha256` matches `agent.yaml` inside the zip.

8. **NON-BLOCKING: `fallback_count` adds two different units.** `timing_summary.py:17-28, 118` adds Retrying lines to index-fallback invocations, so one fallback with 5 retries counts as 6. Dec 028 asks for a "fallback count". Fix: report `fallback_invocations` and `retrying_lines_total` separately.

9. **NON-BLOCKING: the Phase-1 fallback can record 0.0.** `agent_timing.py:711-712`: if `_run_agent_sandbox` never ran, `phase1_wall_seconds` falls back to `agent_seconds` = 0.0 and still counts as measured in the (b)/(c) mean. Gate (a) would fail in that case, which hides the effect today, but it becomes a real distortion once (a) is fixed. Fix: use null when the wrappers didn't fire and `run_seconds == 0`, or require `phase1_source == 'sandbox_wrappers'` for (b)/(c).

10. **NON-BLOCKING: a diagnostic probe can change harness behaviour.** `agent_timing.py:168-172`: `record_distributions` raises on probe rc≠0 or a JSON parse error, and it is called outside `setup_step`. An unexpected probe failure would abort `install_test_dependencies`, turning into 'Sandbox execution error' with no agent run. Make it non-fatal: record the error and continue.

11. **NON-BLOCKING: the hook targets are checked only after vLLM starts.** `getattr(ar, 'sandbox_*')` and `ar.asyncio` are resolved in `evaluate()` (`:758-759`). If the latest wheelhouse ships a different swegemma, the kernel fails after about 10 minutes of vLLM startup. Fix: add a `hasattr` preflight right after `install()`.

12. **Informational:**
    - No code writes `results/kaggle_timing_e4b_v001.json` itself; the operator has to pass `--output results/kaggle_timing_e4b_v001.json`.
    - The run CLI is `bash eval/kaggle/timing_push.sh [--dry-run] [--with-verification] USER/SLUG bundles/e4b/v001 eval/plans/004-gpu-retime-ids.txt [BUDGET=10800]`, which sets kernel `-t` to 12600.
    - The proxy timeout, the sandbox wrappers and the verify stub all forward arguments, return values and exceptions unchanged. They are installed on module globals that agent_runner resolves at call time, and the originals are restored in `finally`. I found no behaviour change apart from the intended verification skip.

## Checklist

| Item | Status | Evidence |
|---|---|---|
| (i) Only Dockerfile.public setup (pip + line-9 tools, offline) | PASS | `agent_timing.py:85-86` SCORER_TOOLS = Dockerfile.public line 9; all pip calls use `--no-index` (`:72-73, :449, :463, :482`) |
| (i) No PIP_* env prefixes | PASS | env dict `:40-45` has no PIP_*; no PIP_ anywhere in timing_push.sh or the kernel (only in the unrelated `gold_calibration.py:329`) |
| (i) Docker step order | PASS | harness wheels → snapshot → git exclude; then `workspace_editable` (`:481`) before `base_tar_extraction` (`:493`) before `setup.py` (`:502`). Image tools are emulated per task (see finding 4) |
| (i) Starter docker_image pinned | PASS | `timing_push.sh:96` |
| (i) Internet OFF | PASS | `timing_push.sh:91` `enable_internet=False` |
| (i) Fail-fast 4xL4 guard | PASS (late) | `agent_timing.py:1026-1027`; runs after `install()` (finding 6) |
| (ii) setup_calls with duration, rc, Retrying | PASS | `agent_timing.py:175-200`, `:511-513`; summary `timing_summary.py:69-70` |
| (ii) Agent-clock seconds | PASS | `:639-657`, `:715` |
| (ii) Timeout fired | PASS | `:655-657` (`expired()` or TimeoutError) |
| (ii) Post-cap finalization seconds | PASS | `:717` (stop end − timeout exit), `finalization_exec` `:671-674` |
| (ii) Total Phase-1 wall, sandbox start→stop | PASS | `:670`, `:688`, `:710` |
| (ii) vLLM startup once | PASS | `:898-900`, `:1036-1038`; summary `:36-41` |
| (ii) Schema-headed results file, end-to-end flow | PASS (via `--output`) | `timing_summary.py:94-134`, `:150` |
| Gate (a) 8/8 no harness error | **FAIL** | findings 1, 2, 3 |
| Gate (b) max Phase-1 ≤ 296 | PASS (296 passes; all rows required) | `timing_summary.py:89` |
| Gate (c) mean ≤ 270 | PASS | `:90` |
| Gate (d) vLLM ≤ 600 s | PASS | `:91` |
| Gate (e) ≥ 1 non-empty source diff | PASS | `:67, :75, :92` (raw patch minus test and stray files) |

## Builder actions (not part of the review)
- No push on aa116cb.
- Minimal fix: ef72e7e (findings 1-3, plus 4 as an ungated diagnostic and 6-11), then guards 9ec991f.
- Re-reviewed: ops/reviews/claude-rereview-fix5.md.
