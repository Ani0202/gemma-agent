# Claude subagent re-review of the Builder gate fix ef72e7e (branch codex/kernel-setup-fix5), dec 029 item 2

## Provenance (Builder)
- Reviewer: a fresh general-purpose Claude subagent, read-only. It was given the diff aa116cb..ef72e7e, the first review and dec 028.
- Launched ~19:42Z on 2026-11-05 (after ef72e7e, committed 19:41:47Z); output received ~19:45Z.
- Corrections (dec 030 item 3):
  - The earlier header said "~20:10Z". That was wrong: the file was first written ~19:46Z, just before the push.
  - The earlier body was a Builder summary. It has been replaced by the raw subagent output, verbatim, below.

## Raw subagent output (verbatim)

VERDICT: NO BLOCKING

I reviewed `git diff aa116cb ef72e7e` against the swegemma 0.2.11 source in `/home/ubuntu/gemma-local/venv`, `ops/reviews/claude-review-fix5.md` and dec 028 items 3 and 4.
- The test command you gave passes: 102 tests, `test_agent_timing.py` + `test_setup_check.py`.
- I also ran `check_hook_targets()` against the installed 0.2.11. It passes and finds every attribute.
- I edited nothing.

**Fix check for findings 1-3: all fixed.**

- **Finding 1 (fail-closed classification):** fixed. I checked every `agent_error` assignment in `agent_runner.py`:
  - 791/948 and 1033 (turns budget or "maximum allowed LLM turns"), 870/928/1028 (session timeout), 936 (tool-call budget) and 1081/1095 (no submit_patch) all match the `AGENT_OUTCOMES` regexes. They are anchored with `re.match` and `\b` holds before " (" and ".".
  - 1043 and 1109 (`Sandbox execution error: …`) match nothing, so they count as a harness failure. A prefix match can't mask them.
  - `ContainerSetupError` and a failing `sandbox_start` (line 493, outside the try) propagate out of `evaluate_task`. 0.2.11 has no catch there, so they become `Evaluation exception (...)`.
  - A missing snapshot returns `error='Snapshot file not found…'`, which is unrecognised, so it fails.
  - In `evaluate()` (`agent_timing.py:829-882`), every non-normal path leaves `error` non-None: the exception branch, the cleanup override, the trace-parse branch (`(error or '') + ' trace parse'`) and the row-build fallback (literal error string; `phase` has no `error` key, so there is no duplicate-kwarg crash).
  - `harness_error` checks both `result.error` and `agent_error`, so a normal outcome can't hide a different unknown error. A test covers this.
- **Finding 2:** fixed. `setup_failed` and `editable_failed` are now diagnostics only (`timing_summary.py:97`). Real fatal setup failures still surface as `Sandbox execution error`, so they still fail.
- **Finding 3:** fixed. `n_expected = len(header['task_ids'])`, and gate (a) also requires no missing ids, no `_stopped` and `_done` present.
  - Note that `main()` writes `_done` in `finally` even after a crash. The crash case is therefore caught by `_stopped`, which `except BaseException` always appends.
  - SIGKILL or a Kaggle session kill leaves no `_done`, so it fails too.
  - A valid run (8 rows, all timeouts, some `setup_failed=True`, wrapper-sourced Phase-1) gives PASS. `test_gate_a_passes_with_timeouts_and_nonfatal_setup_failures` tests exactly this.
  - The ids file has 8 non-comment ids.

**Findings**

1. NON-BLOCKING, `agent_timing.py:733-736`. The outcome regexes are copied from 0.2.11. If the Kaggle wheelhouse ships a swegemma with different wording, every timeout row becomes 'Harness task failure' and gate (a) gives a false FAIL. It can't give a false PASS, because classification fails closed. The cause would show as `agent_outcome_counts={'None': 8}`, and the raw text is in `runs/<iid>/result.json`.
   - Fix (optional): `check_hook_targets` could also grep `inspect.getsource(ar)` for the four message prefixes and log a warning.

2. NON-BLOCKING, `agent_timing.py:946-956`. `check_hook_targets` does not cover what `patch_subprocess_deps` needs: `container_setup.install_test_dependencies`, `_inspect_wheels_dir`, `_LARGE_WHEEL_THRESHOLD_BYTES`, `SubprocessManager.sandboxes`. If the wheelhouse version lacks one, the run still dies after about 10 minutes of vLLM startup.
   - Fix: add `(cs, ('install_test_dependencies', '_inspect_wheels_dir', '_LARGE_WHEEL_THRESHOLD_BYTES'))`.
   - The placement is correct: after `install()` and before `start_server`.
   - Importing `swegemma.evaluate`/`agent_runner` early adds no timed work. vLLM startup is timed inside `start_server`, and the same modules are imported again later.
   - If `mcp` is missing, the run aborts before vLLM instead of failing after it. That has the same outcome, only sooner.

3. NON-BLOCKING, `agent_timing.py:936-943`. `gpu_preflight` is correct for `GPU 0: NVIDIA L4 (UUID: GPU-…)` × 4. It skips when nvidia-smi is missing or times out. It raises when nvidia-smi exits non-zero with empty or one-line output, which is correct because there are no usable GPUs. A substring check would let L40S through, but the torch check remains authoritative. No regression.

4. NON-BLOCKING, `agent_timing.py:152-177`. `record_distributions` is now non-fatal, and the harness path is unchanged.
   - Its four probes (a few `python3 -c` starts per task) still run inside the Phase-1 window and are not counted in `image_emulation_seconds`. That diagnostic therefore understates image-emulation time slightly, in the conservative direction.
   - It's acceptable as long as report 005 says so.
   - The step names in `IMAGE_EMULATION_STEPS` match the `setup_step` names actually used.

5. NON-BLOCKING, `timing_summary.py:89-90, 160`. The reported `phase1_seconds` distribution still includes values from the `run_agent_sandbox` fallback, possibly 0.0. Gates (b) and (c) are protected by `all_phase1`, so this affects reporting only.
   - Fix: compute the distribution over `wrapped(r)` rows only.

6. NON-BLOCKING, `timing_summary.py`. The summary never asserts that `n_expected == 8`. A shorter ids file would pass gate (a) with fewer tasks.
   - Fix: add an `--expected-n` argument (default 8) and check it in (a).
   - `verification_skipped` (per row) is not in the provenance or tasks output, and nothing checks `agent_yaml_sha256` against `dist/e4b-v001.zip`. Both were part of review finding 7; the operator should verify them by hand.

7. NON-BLOCKING, pre-existing, `agent_timing.py:884-887`. The raw artifact writes (`evaluator.trace.to_dict(...)`, `result.model_dump`) are unguarded and run after the row is appended. If one raises, the kernel crashes and the remaining tasks are lost. Gate (a) fails closed in that case, but measurements are lost.
   - Fix: wrap them in try/except and record `artifact_error`.

8. NON-BLOCKING, `agent_timing.py:747-750`. With `--with-verification` (not the gate run), `verify_task` sets `error = junit_error or agent_error` for unresolved tasks. Ordinary test failures would then be labelled 'Harness task failure'. This doesn't affect the dec 028 run, which skips verification.

9. NON-BLOCKING, tests.
   - The new tests do test the classifier, the gate-(a) PASS and FAIL cases, the separate fallback units, the non-fatal probe and the preflight.
   - Missing: an `evaluate()`-level test where `_run_agent_sandbox` returns `(patch, 'Agent exceeded session timeout (1.4 min)', None)` and the row is expected to show `error is None, agent_outcome == 'timeout'`.
   - Missing: a no-patch timeout through the early-return path.
   - Missing: a `check_hook_targets` test against the real swegemma, if it's importable.
   - The existing `test_skip_verification_result_and_task_row` covers the runner, setup and cleanup exception branches, which all give non-None errors.

10. Informational. Gates (a)-(e) are not fully protected from a vLLM that hangs without erroring: every task would end as a timeout, which counts as normal. Gate (e) catches a total failure. A partial failure would most likely surface as `Sandbox execution error`.
    - Optional: show `llm_turns == 0` / `completion_tokens` per task in the summary as a sanity check.

Files reviewed:
- `/home/ubuntu/work/gemma-wt/codex-kernel-setup-fix5/eval/kaggle/agent_timing.py`
- `/home/ubuntu/work/gemma-wt/codex-kernel-setup-fix5/eval/kaggle/timing_summary.py`
- `/home/ubuntu/work/gemma-wt/codex-kernel-setup-fix5/eval/tests/test_agent_timing.py`
- `/home/ubuntu/gemma-local/venv/lib/python3.13/site-packages/swegemma/harness/agent_runner.py`
- `/home/ubuntu/gemma-local/venv/lib/python3.13/site-packages/swegemma/evaluate.py`

## Builder actions (not part of the review)
- Fixed in 9ec991f:
  - NB 2: container_setup attributes added to `check_hook_targets`.
  - NB 7: raw artifact writes guarded, with a `_artifact_error` journal record that the summary reports.
- Pushed kernel v4 from 9ec991f at 19:46Z.
- To do when summarizing:
  - NB 5 and NB 6: summary-side only; the journal can be re-summarized after any fix.
  - Check n_expected == 8, verification_skipped and agent_yaml_sha256 by hand.
- Report 005 notes: NB 4 and NB 10.
