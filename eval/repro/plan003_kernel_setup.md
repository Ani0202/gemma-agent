Run the offline setup acceptance outside the Codex sandbox:

```sh
PYTHONPATH=/home/ubuntu/gemma-local/imgrt-stub \
  /home/ubuntu/gemma-local/venv/bin/python eval/repro/plan003_kernel_setup.py \
  --output results/plan003_kernel_setup_acceptance_r4local.json
```

The runner requires `bwrap --unshare-net`. It runs both modes sequentially on
`rich_3006` and `fastapi_14986`, without loading task text, an agent, or verification.
A bwrap failure produces `status: blocked` and no task rows. `--setup-fix 0` runs
only the control and produces `status: diagnostic`, never an acceptance pass.

The fixed mode installs only pip and Dockerfile.public line 9's Python tools and
their runtime dependency closure before attempting the workspace editable install.
`workspace_editable` uses the Docker hook's pip flags through `python3 -m pip` so
that the sandbox interpreter is used even when bootstrap pip has no console script.
It captures the actual return code and stderr that Docker's `|| true` and redirect
hide, and continues to injection and competition setup even if that attempt fails.
The subsequent steps are `base_tar_extraction` and `setup.py`. The latter invokes
the unmodified competition setup script through an output observer. No pip retry,
timeout, or index environment overrides are added.

Each of those three steps includes `distributions`, queried using
`importlib.metadata.distribution` in the sandbox interpreter after the step. For
the task package it reports location, metadata directory, version, and
`record_exists`. The control reports this state after injection and competition
setup; its early harness hook remains the original SubprocessManager no-op.
`editable_rc` is the first editable call inside competition setup,
`editable_final_rc` is its last call, and `workspace_editable_rc` is the earlier
Docker-equivalent attempt. `editable_failed` and `setup_failed` are true if any
observed editable attempt failed, even if a subsequent fallback succeeded. The
CPU summary consumes the failure flags and rejects any `missing_tool_deps`.

Both modes use a base-tar key derived from sorted selected wheel filenames and
sizes plus the installed harness version. Every build or reuse logs the key,
selected wheels, and tar member count. A marker-only or empty tar with selected
wheels fails loudly. Old `sp_base_local` caches cannot be reused by this path.

Journal stdout/stderr are capped at 2048 UTF-8 bytes per stream. Full output lives
in per-mode per-task JSONL artifacts linked by `setup_output_artifact`; only the
task ID appears in the filename. The acceptance JSON and console output include
editable rc, total retry count, setup seconds, and per-step distribution state.
These observations distinguish a RECORD-less injected distribution from metadata
left by the image tool install or earlier workspace editable attempt; they do not
assert that Kaggle exhibits the same failure or timing.
