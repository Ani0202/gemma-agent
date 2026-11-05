# Gold calibration on Kaggle

This private CPU kernel verifies **every** published `tasks.jsonl` task using its
reference `patch` as `agent_patch`. It performs no agent inference and needs no
model input. Phase 2 owns fresh snapshot/wheel staging, baseline setup, protected
file resets, application of `test_patch`, pytest, and JUnit validation. A zero
pytest exit alone is insufficient: the harness's `resolved` verdict is retained.
No task text, patches, pytest output, or raw exception messages are printed.

From the repository root, with the Kaggle CLI already authenticated and the
competition rules accepted:

```bash
eval/kaggle/push.sh YOUR_USERNAME/gemma-gold-calibration
kaggle kernels status YOUR_USERNAME/gemma-gold-calibration
mkdir -p runs/gold-calibration
kaggle kernels output YOUR_USERNAME/gemma-gold-calibration -p runs/gold-calibration
```

The helper stages `gold_calibration.py` and generates the CLI-required filename
`kernel-metadata.json` from `gold_calibration_metadata.json` in `/tmp`. Its required
argument supplies the actual owner/slug; the checked-in username is an example.
It uploads a kernel, and never submits predictions to the competition. The
metadata requests CPU only, GPU/TPU disabled, internet off, the competition source
`gemma-4-developer-agent`, and the official starter's
`metric/gemma-4-developer-agent-wheelhouse` dataset. No local data is uploaded.
The push and remote run must be performed by the operator; neither was run here.

The script uses the competition mount at
`/kaggle/input/competitions/gemma-4-developer-agent` and installs missing harness
packages offline from the attached wheelhouse, without a package index. This
follows the starter's wheel installation pattern but excludes GPU cutlass wheels
and does not start vLLM. Availability/compatibility of all harness dependencies on
the CPU image still needs a remote smoke check.

It tries starting the local `swebench-sandbox:latest` Docker image with network off
and without pulling an image. If Docker, its daemon, or the image is unavailable,
it selects the harness's `sandbox='subprocess'` (the equivalent of CLI
`--sandbox subprocess`). The subprocess backend is also used by the starter.
Exactly two task workers may run concurrently; each uses a separate process and
fresh harness sandbox. All scratch files are under `/tmp`. Verification pytest
has the official 300-second limit; a worker has an additional 3600-second outer
limit including setup. Durations include setup and are **not** concurrency-1
scorer timing measurements.

`/kaggle/working/gold_results.jsonl` receives one fsynced record per completed
attempt: instance id, repo, resolved, test exit code (null if unavailable), wall
duration, short safe error, and sandbox backend. Both successes and failures are
finished ids and skipped on restart. An interrupted final JSON append is removed
before resuming; malformed complete records, duplicate task ids, and inventory
mismatches are rejected. Duplicate completed records use the last record.

At completion, `/kaggle/working/gold_summary.json` is written atomically and
printed. It includes totals, per-repo counts, passing ids, failing ids/reasons,
and pending ids. There is no task selection or silent exclusion of setup errors.
A killed session may have only the journal; rerun with it to regenerate the summary.

Kaggle kernel pushes start new working directories: they do **not** automatically
resume prior output. To resume across sessions, fetch the journal, attach it as a
private input, and copy it into `/kaggle/working/gold_results.jsonl` before starting
this script in an interactive session. Preserve the original `tasks.jsonl` and
harness versions. The same working directory resumes automatically. Do not run
two coordinators against the same journal. To retry failures, use a separate run
or explicitly prepare a journal excluding those rows; ordinary restarts preserve
all completed attempts.

## Harness API assumptions requiring a Kaggle smoke check

References: the competition's `HARNESS_README.md` sections 4, 8, 9 and
[`starter_notebook.ipynb`](starter_notebook.ipynb). The README was read from the
main checkout because `data/` is absent from this worktree. Neither reference
provides the complete `verify_task` Python signature, and harness wheels are not
available locally. The only harness call adapter is `verify_gold`:

- Assumes `swegemma.harness.verification.verify_task` accepts named `task` and
  `agent_patch` parameters and owns the entire fresh Phase 2 setup/cleanup.
- Constructs `EvalConfig`/`Evaluator` following the starter, with `models={}`
  because no Phase 1 or inference is run. Assumes construction needs no model.
- Binds explicit verification parameters from the evaluator's instance resources
  (including private attributes with their leading underscore removed), plus
  `config`, snapshot/wheel paths, and the 300-second timeout. Unknown required
  arguments fail rather than guessing a positional order. If the installed API
  differs, adjust this one function after inspecting its signature.
- Accepts a sync or async result, as a mapping or object with `resolved`,
  `test_exit_code` (or `exit_code`), and optional `error`. Resolution is never
  inferred from exit code alone. Unsupported signatures/results and setup errors
  become recorded task failures. Only exception class names are exposed, since
  arbitrary harness errors can contain task code or patch hunks.

Offline verification (no Kaggle credentials, network, or harness required):

```bash
python3 -m py_compile eval/kaggle/gold_calibration.py
python3 -m unittest discover -s eval/tests -p test_gold_calibration.py -v
bash -n eval/kaggle/push.sh
```

## Reconciliation with public thread 751487 (dec 011, 2026-11-05)
Thread 751487 (Zbigniew Kirchner, Apache-2.0 notebooks) reports gold 127/129 in a "scorer-like" env. Its method
section says: "a clean venv, pytest, the competition wheels, **and the missing test packages**" (author's own
wheels dataset) and "a few old public tasks need period-correct versions (e.g. Pygments for 7 rich tasks)".
The author also states they do not know whether submissions use Docker or subprocess.
So the 127 env **adds packages absent from the official wheelhouse and pins older per-task versions**.
The official harness (swegemma 0.2.11, source-read): `_deduplicate_wheels` (packaging.version max) and
`sandbox/setup.py deduplicate_wheels` (semver max) both select the HIGHEST version per package; no resolver,
no per-task requirements pinning (fast-path only writes workspace_paths.pth + pytest config). Official
wheelhouse facts: 56 starlette versions, max 1.6.0 (removes Router on_startup); no pytest-httpbin/httpbin,
inline_snapshot or dirty_equals wheels; Pygments max 2.21.0.
Conclusion: explanation (b) (different wheel set) — not an emulation bug in our env. Exclusions for these
causes are tagged `scorer_fail=assumed` (code-verified against published harness, not run-verified in the
real scorer; the hidden scorer image could differ). Known residual emulation difference: docker path runs
`pip install --no-deps -e /workspace`; subprocess path relies on workspace_paths.pth (gold passers unaffected).

## v2 freeze (2026-11-05, dec 014): null control + wheel shadowing
- Null-patch control (runs/gold-null -> results/gold_null_control.jsonl): 4/52 gold-passers pass with NO source
  change (fastapi_14873, requests_7309/7315/7427). Excluded, cause `null_pass`.
- Import probe (results/gold_import_probe.jsonl): requests and httpx import from the sandbox site-packages; rich and fastapi
  import from /workspace.
- Root cause (source read + manual repro, scratch venv): swegemma `container_setup._build_unpacked_wheels_tar`
  (container_setup.py:266) drops every `*/RECORD` when unpacking wheels into site-packages. sandbox/setup.py then runs
  `pip install --no-index --no-deps -e /workspace`, which tries to uninstall the existing wheel copy and fails with
  `uninstall-no-record-file`; the online fallback fails offline. `workspace_paths.pth` entries come after site-packages,
  so a **src-layout** package (src/httpx, src/requests) resolves to the wheel copy. Flat-layout packages (rich/, fastapi/)
  win via cwd=/workspace at sys.path[0]. This is the official docker path's behaviour, not an emulation bug, so
  dec 014 rule 2b applies: requests/httpx are **unmeasurable locally** and dropped from dev/holdout.
- Clean set v2: 48 (rich 39, fastapi 9); dev 33 / holdout 15. Hashes in eval/splits/MANIFEST.json.
- Implication for agents (generic, not repo-specific): in any src-layout repo whose package is also in the wheelhouse,
  the agent's own test runs exercise the wheel, not its edits. Candidate prompt/skill check: confirm `pkg.__file__` is
  under /workspace before trusting a repro.
