# Claude subagent review: main...codex/kernel-setup-fix5 (aa116cb), dec 029 item 1
Reviewer: fresh general-purpose subagent, read-only, given the code + dec 027/028 + spec (not the Builder's conclusion).
Date: 2026-11-05 ~19:45Z. Saved verbatim by the Builder.

VERDICT: BLOCKING

Reviewed `main...codex/kernel-setup-fix5` (aa116cb) against the installed swegemma 0.2.11 source (`agent_runner.py`, `evaluate.py`, `verification.py`, `sandbox/base.py`, `sandbox/subprocess.py`), dec 027/028, `build-kernel-setup-fix5.spec` and `data/raw/docker/docker/Dockerfile.public`. The unit tests did not run: there is no `pytest` in `/home/ubuntu/gemma-local/venv`, and nothing was installed. All five changed Python files compile, and `bash -n timing_push.sh` passes. No dry run was done.

The data flow works end to end: kernel `timing.jsonl` -> `timing_summary.py --output results/kaggle_timing_e4b_v001.json`, and every item dec 028 asks for is recorded. The fidelity rules are met. The blocking problems are all in the gate (a) logic. As written, gate (a) will almost certainly report FAIL for a correct run of v001, and it can report PASS for a run that crashed partway.

## Findings

1. **BLOCKING: agent timeouts are labelled 'Harness task failure'.** `eval/kaggle/agent_timing.py:727-728`, used at `:808`.
   - `harness_error()` returns 'Harness task failure' whenever `result.error` or `agent_error` is non-empty.
   - In swegemma, `agent_error` is set for normal agent outcomes: `'Agent exceeded session timeout (1.4 min)'` (agent_runner.py:1027-1029), the turns-budget message, and `'Agent completed execution without calling submit_patch.'` (:1083, :1101).
   - `skip_verification` copies that string into `TaskResult.error` (agent_timing.py:699-701). The early-return path in evaluate.py:338-346 does the same.
   - Scenario: v001's cap is 84 s, so the E4B agent will hit the timeout on most or all tasks. Every such row gets `error='Harness task failure'`, and gate (a) FAILs (`timing_summary.py:80-88`). The pre-registered submission gate gives a false NO on a valid run. The row also loses the actual category.
   - The spec (item 1) says to flag only real harness/agent-runner errors. No test covers a timeout or no-submit `agent_error`; the test at `test_agent_timing.py:558-559` only checks `''` and 'Sandbox execution error'.
   - Fix: treat it as a harness error only for `Evaluation exception`, `Cleanup exception`, `ContainerSetupError`, a missing snapshot, or an `agent_error` that starts with `'Sandbox execution error'`. Record the rest as `agent_outcome` in {timeout, turns, no_submit} in the row and the summary. Add tests.

2. **BLOCKING: gate (a) also fails any task with `setup_failed`, and on Kaggle that flag will be set for non-fatal setup results.** `timing_summary.py:80-82`.
   - `setup_failed` gets set by setup.py's own `-e` subprocess returning rc!=0 (`agent_timing.py:515-519`) and by `workspace_editable` returning rc!=0 (`:485-486`).
   - Neither is fatal in the scorer. Docker runs `pip install ... -e /workspace 2>/dev/null || true`, and setup.py carries on after its editable attempt fails. That is the competition-harness behaviour dec 028 says the scorer shares.
   - Local evidence: `results/plan003_kernel_setup_acceptance_r4local.json` has rich_3006 with fix 1: `editable_rc 1`, Retrying 5, `setup_failed True`. Six of the 8 ids in `004-gpu-retime-ids.txt` are rich tasks, so gate (a) FAILs.
   - Fatal setup failures already raise, and agent_runner turns them into 'Sandbox execution error', so they surface through `error` anyway.
   - Fix: base (a) on `error` only. Report `editable_failed` / `setup_failed` counts as diagnostics outside the gate.

3. **BLOCKING: the expected task count comes from the rows written, not the planned task list.** `timing_summary.py:86-88`.
   - Gate (a) compares `complete == len(tasks)`, so if the kernel stops early (crash, `should_stop`, session timeout) after 5 of 8 tasks, it reports 5/5 PASS.
   - The overall `gate.status` can then be PASS with `missing_task_ids` non-empty and `stopped` set, although dec 028 (a) requires "all 8 tasks complete".
   - The spec said to use the number of rows, but the decision text takes precedence.
   - Fix: `n_expected = len(header['task_ids'])`. Gate (a) requires `complete == n_expected`, no `missing_task_ids`, no `_stopped`, and `done_present`.

4. **NON-BLOCKING (conservative direction, but material at this margin): Phase-1 includes image-emulation work the scorer never pays.** Inside the timed sandbox window the kernel runs `venv_fidelity`, `pip_bootstrap`, `interpreter_probe`, `tool_install`, `tool_deps` and `pip_check` (`agent_timing.py:392-479`), plus four `record_distributions` probes outside `setup_step` timing (`:388, :487, :494, :520`). The scorer image already has those tools (Dockerfile.public line 9). Local measurements: ~2.5-4 s/task (tool_install 1.5-2.9 s, bootstrap 0.35 s, deps 0.32 s, check 0.18 s, probes). Headroom at the 296 s gate is ~6.4 s/task, so this alone could cause a false FAIL on gate (b). Fix: add `image_emulation_seconds` and `phase1_wall_minus_image_seconds` to row and summary; report both and let the Director pick which gates.

5. **NON-BLOCKING: the subprocess sandbox has no CPU or memory limit**, so setup.py's pip, the post-cap `git add -N` / `git diff`, and the agent's tests run faster than under the scorer's 2 vCPU / 4 GiB. Inherent to subprocess mode; note in report 005 as an unmeasured risk to the margin.

6. **NON-BLOCKING: the 4xL4 guard runs only after the full wheelhouse install.** `agent_timing.py:1026` comes after `install()` at `:1010` (force-reinstalls vllm/torch, several minutes). Fix: cheap `nvidia-smi -L` check at the top of `main()` before `install()`.

7. **NON-BLOCKING: the results file carries no provenance.** `timing_summary.py:94-134` drops the header's `git_sha`, `bundle_sha256`, `agent_yaml_sha256`, `gpu_names`/`gpu_count`, `caps`, `created_utc`, `verification_skipped`. The kernel tars `bundles/e4b/v001` (incl. `MANIFEST.md`), not `dist/e4b-v001.zip`. Fix: copy header provenance into the summary; check `agent_yaml_sha256` matches the zip's `agent.yaml`.

8. **NON-BLOCKING: `fallback_count` adds two different units** (`timing_summary.py:17-28, 118`): Retrying lines + index-fallback invocations. Fix: report `fallback_invocations` and `retrying_lines_total` separately.

9. **NON-BLOCKING: the Phase-1 fallback can record 0.0** (`agent_timing.py:711-712`): if `_run_agent_sandbox` never ran, `phase1_wall_seconds` falls back to `agent_seconds` = 0.0 and counts in the (b)/(c) mean. Fix: require `phase1_source == 'sandbox_wrappers'` for (b)/(c).

10. **NON-BLOCKING: a diagnostic probe can change harness behaviour** (`agent_timing.py:168-172`): `record_distributions` raises on probe rc!=0 or JSON error, outside `setup_step`, which would abort `install_test_dependencies`. Make it non-fatal.

11. **NON-BLOCKING: hook targets are checked only after vLLM starts** (`:758-759`). If the wheelhouse ships a different swegemma, the kernel fails after ~10 min of vLLM startup. Fix: `hasattr` preflight right after `install()`.

12. **Informational:** nothing writes `results/kaggle_timing_e4b_v001.json` by default (operator passes `--output`). CLI: `bash eval/kaggle/timing_push.sh [--dry-run] [--with-verification] USER/SLUG bundles/e4b/v001 eval/plans/004-gpu-retime-ids.txt [BUDGET=10800]` (kernel `-t` = budget + 1800). The timeout proxy, sandbox wrappers and verify stub forward args/returns/exceptions unchanged, are installed on module globals resolved at call time, and are restored in `finally`; no behaviour change found apart from the intended verification skip.

## Checklist

| Item | Status | Evidence |
|---|---|---|
| (i) Only Dockerfile.public setup (pip + line-9 tools, offline) | PASS | `agent_timing.py:85-86`; all pip calls `--no-index` (`:72-73, :449, :463, :482`) |
| (i) No PIP_* env prefixes | PASS | env dict `:40-45`; none in timing_push.sh or the kernel |
| (i) Docker step order | PASS | harness wheels -> snapshot -> git exclude; `workspace_editable` (`:481`) before `base_tar_extraction` (`:493`) before `setup.py` (`:502`) |
| (i) Starter docker_image pinned | PASS | `timing_push.sh:96` |
| (i) Internet OFF | PASS | `timing_push.sh:91` |
| (i) Fail-fast 4xL4 guard | PASS (late) | `agent_timing.py:1026-1027` (finding 6) |
| (ii) setup_calls with duration, rc, Retrying | PASS | `:175-200`, `:511-513`; summary `:69-70` |
| (ii) Agent-clock seconds | PASS | `:639-657`, `:715` |
| (ii) Timeout fired | PASS | `:655-657` |
| (ii) Post-cap finalization seconds | PASS | `:717`, `:671-674` |
| (ii) Total Phase-1 wall, sandbox start->stop | PASS | `:670`, `:688`, `:710` |
| (ii) vLLM startup once | PASS | `:898-900`, `:1036-1038`; summary `:36-41` |
| (ii) Schema-headed results file, end-to-end | PASS (via `--output`) | `timing_summary.py:94-134`, `:150` |
| Gate (a) | **FAIL** | findings 1, 2, 3 |
| Gate (b) max Phase-1 <= 296 | PASS | `timing_summary.py:89` |
| Gate (c) mean <= 270 | PASS | `:90` |
| Gate (d) vLLM <= 600 s | PASS | `:91` |
| Gate (e) >= 1 non-empty source diff | PASS | `:67, :75, :92` |
