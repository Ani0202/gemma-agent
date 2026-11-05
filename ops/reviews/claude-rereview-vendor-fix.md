# Claude subagent re-review of 87001e4 (branch codex/kernel-setup-fix5)

## Provenance (Builder)
- Reviewer: a fresh general-purpose Claude subagent, read-only.
- It was given the commit, the prior review file and the Kaggle facts (runtime pip, Python 3.12).
- Launched ~20:11Z on 2026-11-05 (after 87001e4, committed 20:11:03Z); output received ~20:13Z.

## Raw subagent output (verbatim)

VERDICT: NO BLOCKING

I reviewed commit 87001e4 on branch codex/kernel-setup-fix5 against ops/reviews/claude-review-vendor-fix.md. All 111 tests pass.

I also ran a separate simulation. It was the commit's preflight (`missing_tool_closure`) and the real setup closure (`close_tool_dependencies`) against /home/ubuntu/work/gemma/data/raw/wheels plus the vendored wheels, using Kaggle-like cp312 manylinux tags and Python 3.12 markers. Results:
- Preflight with runtime=False: `[]`.
- Preflight with runtime=True: `[]`.
- Setup closure: missing `[]`. It resolves 16 edges, all from wheels. annotated-doc, pathspec, shellingham and trove-classifiers come from the embedded wheels; everything else comes from the wheelhouse.

**Answers to your checks**

1. Finding 1 (false abort on pip) is fixed (agent_timing.py:159). The pip check now passes if `fallback_wheel(...)` finds a wheel or `runtime_copyable('pip')` finds a copyable runtime pip. These are exactly the two sources `bootstrap_pip` uses (lines 498-509), and both checks run in the same kernel process after install(). The new test `test_check_tool_sources_accepts_runtime_pip` covers both outcomes. The `runtime_copyable`/`copy_runtime_package` split (lines 303-333) preserves behaviour. It has the same predicates in the same order (distribution lookup, the pytest-timeout==2.1.0 pin, no .so/.pyd/.dll/.dylib, a non-empty file list, the same filtering, at least one .py outside dist-info). It returns the same filtered `files`, so the copy loop and the returned source string are unchanged.

2. `missing_tool_closure` mirrors `close_tool_dependencies`:
   - same sources and order: wheelhouse, then embedded wheels, then runtime copy
   - same `compatible_wheels` tag selection
   - same pytest-timeout root selection (tag-filtered, wheelhouse first)
   - same runtime predicate plus version check
   - expands the metadata of runtime-sourced packages
   - same marker evaluation with `extra=''`

   The sandbox venv is built from the kernel's own interpreter: subprocess.py:334/360 calls `venv.create(...)` in-process, which uses `sys._base_executable`. So the kernel's `sys_tags`/`default_environment` match the sandbox probe. The probe uses pip's vendored `packaging`, which could only differ for platform wheels, and the whole closure is py3-none-any. On Kaggle the venv starts without pip (no ensurepip), so setup's starting "installed" set is pip plus the line-9 tools, all of which come from wheels the preflight also sees.

   I found no way the preflight can pass a run that then fails at tool_deps on a missing dependency. Every package setup expands, the preflight also expands with the same candidate. The one gap: a dependency wheel whose pip install fails (rc != 0) is not modelled. That is acceptable.

3. annotated-doc is vendored correctly. `sha256sum -c` is OK for all 5 files. The RECORD in the wheel matches the RECORD of the installed annotated_doc-0.0.5 in the local venv file for file. timing_push.sh:78-83 re-checks every SHA256SUMS line, `extra_wheels()` re-checks at run time, and docs/ATTRIBUTION.md:10 lists it.

   The strict test (`runtime=False`) does prove the wheelhouse plus vendored wheels close the dependency tree with no runtime packages, but only for the local interpreter (3.13 tags and markers); my simulation above confirms the cp312 case. Caveat: this assumes the local wheelhouse copy is identical to the Kaggle `DATA/wheels` dataset.

4. SETUP_FIX gating is correct. `main()` sets the default at line 1122 before the check at line 1166, so the check runs exactly when `patch_subprocess_deps` takes the fixed path (default `'1'`). `setup_only_main` never called the preflight, so it is unaffected. In the push script, `test_push_embeds_vendored_wheel` (dry run) passes. I found no regressions in tests or the repro.

**Findings**

1. NON-BLOCKING, agent_timing.py:136-139. The preflight can be stricter than setup in a theoretical case. Setup accepts an already-installed version if it satisfies a later requirement edge (lines 371-373). The preflight always walks the highest compatible version for each edge. Scenario: edge 1 is `foo<2`, so foo 1.9 is installed; edge 2 is `foo` with no bound. Setup reuses 1.9, but the preflight walks foo 3.0, and if 3.0 has a dependency that no source provides, the preflight aborts a run setup would complete. This cannot happen with the current wheelhouse (strict cp312 result is `[]`). Fix if wanted: keep a `resolved[name] = version` map in the preflight and reuse it when it satisfies the requirement, as setup does.

2. NON-BLOCKING, agent_timing.py:150-157. The tool-name check in `check_tool_sources` ignores wheel tags, while setup's `validate_tools` uses the tag-filtered selection. It could pass a platform-only tool wheel that setup then rejects. All line-9 tools are pure Python, so there is no current impact. Fix: use `compatible_wheels(wheels, sys_tags)` for the name check.

3. NON-BLOCKING, eval/tests/test_agent_timing.py:984-1001. The strict closure test runs only with the local 3.13 tags and markers. Kaggle runs 3.12, which has different marker outcomes (for example `python_version<"3.13"` dependencies). Fix: also call it with explicit cp312 tags and a patched `default_environment`, as my simulation does.

4. NON-BLOCKING, carried over from the previous review's item 5 (fidelity nit). The embedded wheels, now including annotated_doc, are still copied into the sandbox's `/wheels`, which the scorer's `/wheels` does not contain. It has no effect today because setup.py and the editable install both use `--no-deps`. Optional fix: copy tool dependencies to `/tmp/toolwheels`.

5. NON-BLOCKING, test quality. `test_runtime_copyable_matches_copy_runtime_package` only checks that the two functions agree on missing versus not missing for `pytest`. It does not compare the copied file set. That is fine given the code is shared, but the test is weak.

No re-review is needed for the Kaggle run.

## Builder actions (not part of the review)
- No code change after 87001e4.
- The NB findings are logged for the Codex review and for after the run.
