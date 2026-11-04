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
