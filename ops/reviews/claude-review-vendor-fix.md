# Claude subagent review of 9ec991f..1c13123 (vendored wheels + tool-source preflight), branch codex/kernel-setup-fix5

## Provenance (Builder)
- Reviewer: a fresh general-purpose Claude subagent, read-only.
- It was given the diff, the v4 failure facts, dec 027/028 and the repro result paths. It was not given the Builder's conclusion.
- Launched ~20:04Z on 2026-11-05 (after 1c13123, committed 20:03:27Z); output received ~20:08Z (file written 20:08:53Z).

## Raw subagent output (verbatim)

VERDICT: BLOCKING

1. BLOCKING: `check_tool_sources` will falsely abort the next Kaggle run with "Offline scorer tool sources missing: pip" (eval/kaggle/agent_timing.py:164-165).
   - The check requires `fallback_wheel(wheels, 'pip')`, which only accepts a pip wheel in the wheelhouse or in ensurepip's `_bundled` dir.
   - On Kaggle neither exists. In the v4 Kaggle run (runs/e4b-v001-timing/timing.jsonl), the `pip_bootstrap` source was `runtime-site-packages:/usr/local/lib/python3.12/dist-packages`. That is the `copy_runtime_package('pip')` fallback, which means `fallback_wheel` returned None for the same wheels dir.
   - The real `bootstrap_pip` (line ~491) accepts that runtime copy, so setup would have worked. The pre-check does not accept it, so main() raises after install() and before vLLM. Every task is lost.
   - Neither the tests nor the local repro catch this. `test_check_tool_sources` writes a `pip-26.0` wheel into the fake wheelhouse. Locally, the pyimg CPython has ensurepip bundled, and the repro never calls `check_tool_sources`.
   - Fix: mirror `bootstrap_pip`. Treat pip as available if `fallback_wheel(...)` is found, or if `importlib.metadata.distribution('pip')` exists and its file list is pure Python (the same conditions `copy_runtime_package` checks), without copying anything. Add a test with no pip wheel and no ensurepip bundle but a runtime pip.

2. NON-BLOCKING, but unverified and it could fail the run: typer's dependency annotated-doc is not offline-resolvable from the wheelhouse plus embedded wheels.
   - typer-0.26.7 requires `annotated-doc>=0.0.2`. It is not in data/raw/wheels and not vendored.
   - I ran `missing_tool_closure` with runtime lookup disabled, against the local wheelhouse plus the vendored wheels. It returns `['annotated-doc']`.
   - Locally it resolves only because the venv and pyimg contain annotated_doc 0.0.5. The vendored repro row shows source `site-packages`, and `test_vendored_closure_complete_against_local_wheelhouse` passes for the same reason, so the test hides the dependency.
   - On Kaggle it depends on whether the runtime has it. That is likely, because google-adk 2.13 needs fastapi>=0.133, which needs annotated-doc, but nobody has checked.
   - If it is absent, the closure pre-check aborts before vLLM. That fails fast, but the run still fails.
   - Fix: vendor the official annotated_doc wheel (pure Python, tiny), add it to SHA256SUMS, and make the closure test fail when it would rely on the runtime (or run it with runtime lookup disabled).

3. NON-BLOCKING: the pre-check is looser than the real code in places, so it can pass a run that later fails at `tool_deps` (agent_timing.py:106-146).
   - (a) For the runtime fallback it checks only the version. The real path also needs `copy_runtime_package != 'missing'`: a file list exists, no .so files, and top-level .py files present.
   - (b) Wheel choice ignores tags. The real path uses `compatible_wheels` with the sandbox tags, so a newer cp313-only wheel could be walked instead of the one actually installed.
   - (c) It does not expand the requirements of packages taken from the runtime copy.
   - None of these matters for the current closure (all pure py3-none-any), but reusing `compatible_wheels` and the `copy_runtime_package` predicate would make it exact.

4. NON-BLOCKING: `check_tool_sources` runs even when SETUP_FIX=0 (main, line ~1159). That path does not install tools, so the check can abort a run that doesn't need them. Gate it on `SETUP_FIX == '1'`.

5. NON-BLOCKING, fidelity nit: the embedded wheels are copied into the sandbox's /wheels (pytest_timeout, pathspec, shellingham, trove_classifiers). The scorer's /wheels holds only the public wheelhouse. `setup.py` and the hook's editable install both use `--no-deps -e`, so this has no effect today. Optionally copy tools to a separate dir such as /tmp/toolwheels.

Checks with no problems:
- Vendored wheels: `sha256sum -c` matches all 4 files. I could not check the hashes against PyPI offline. timing_push.sh checks each sha and that the pytest-timeout wheel is present. `extra_wheels()` checks the sha again and rejects names containing `/` or starting with `.`.
- Embedding: the AST replacement of `EXTRA_WHEELS` works. `test_push_embeds_vendored_wheel` does a dry run, and the dict repr compiles.
- `extra_wheels()` writes to WORK/extra_wheels (/kaggle/working is writable). It costs about 0.7 ms per call, so there is no timing effect.
- Source priority (wheelhouse, then embedded, then runtime) is correct. The embedded set has no pytest or other line-9 tool, so the selected tool versions are unchanged (pytest 9.1.1, typer 0.26.7, setuptools 83.0.0, etc.). `selected` and `base_cache_key` still use the wheelhouse only. pytest-timeout is still in BASE_SKIP, so the base tar is unchanged.
- The new `tool_install`/`tool_deps` work (about 1.5 s + 3.3 s locally) falls inside IMAGE_EMULATION_STEPS, so it is reported separately and does not distort agent time.
- No new PIP_* env vars, the Docker step order is unchanged, and setup_calls logs the pytest-timeout source path.
- Order in main(): install(), then check_hook_targets(), then check_tool_sources(), then vLLM. Confirmed.
- Repro: the vendored no-stub run completes the full sequence for both tasks with `missing_tool_deps == []`. The rich_3006 editable failure in `setup.py` is unchanged from r4local (it is not a regression).
- The 109 tests pass. They do not model the Kaggle conditions in findings 1 and 2: no pip wheel, no ensurepip bundle, and no annotated_doc in the runtime.

## Builder actions (not part of the review)
Fixed in 87001e4 (20:11:03Z): runtime pip accepted, exact closure walk, annotated-doc vendored, SETUP_FIX gating. Finding 5 (embedded wheels in sandbox /wheels) not changed: no effect with --no-deps -e. Re-review: ops/reviews/claude-rereview-vendor-fix.md.
