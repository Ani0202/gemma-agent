Run a local bundle with the image-mirror interpreter base:

```sh
/home/ubuntu/gemma-local/venv/bin/python eval/run_agent_eval.py \
  --bundle bundles/e4b/v000 --data-dir data/raw --split eval/splits/dev.txt \
  --run-name baseline-local --concurrency 1 --endpoint http://localhost:8000/v1
```

The runner uses swegemma 0.2.11 programmatically with the subprocess sandbox. Caps
come from the bundle's `eval_config.yaml`, with CLI overrides taking precedence.
It checks two clean tasks with gold patches before inference. `--selfcheck-ids a,b`
chooses the two checks; `--skip-selfcheck` explicitly bypasses them. Only IDs in the
frozen dev split are accepted. `--ids a,b` limits the agent run, not the default
self-check selection. Concurrent durations are throughput measurements, not scorer
timing measurements.

Commands in both agent and verification sandboxes require bubblewrap. Startup
checks inventory hiding, image pytest imports, and workspace write-through, then
checks the full runtime mounts. The only read-only exposures under hidden paths
are the image Python prefix and wheel assets. Graph tools execute in the host
process; their graph and embedding paths resolve under `--data-dir` when relative.
`--allow-unsandboxed` explicitly permits a failed/missing-bubblewrap probe and
records `sandbox: "none"` in the header and every row. Such runs have no filesystem
gold isolation.

`results/<run-name>.jsonl` contains a metadata header and sanitized task metrics.
Completed attempts, including failures, are skipped on resume. Changing the bundle,
caps, split, model registry, data directory, endpoint or concurrency requires a new
name or `--force-new`, which **replaces the results journal**. Raw traces, logs,
pre-stripping agent diffs, and harness outputs remain in `runs/<run-name>/`.
`patch_bytes` and file classifications describe the agent diff before protected-file
stripping; `output.json` includes the diff actually passed to verification.

`--out /path` places both the journal and raw artifact subdirectory under that
directory. Gold self-check patch files and sandbox roots also stay under the
artifact directory. Without `--out`, the existing `results/` and `runs/` layout is
preserved. `--force-new-out` archives the existing journal and artifact directory
with a timestamp before starting fresh. Resume compares runner SHA/dirty flag,
inventory and split hashes, bundle hash, installed package/Python versions,
wheel listing hash, sandbox mode and effective configuration, and reports the
changed fields on mismatch.

Every recognized `EvalConfig` evaluation key is forwarded, with CLI runtime
paths, model registry, subprocess backend, concurrency and cap overrides taking
precedence. Unknown keys produce warnings. The header records the effective
configuration. `tool_seconds` uses ADK execution callbacks keyed by function-call
ID and monotonic time; `tool_calls_timed` and `tool_seconds_unmatched` report
coverage. Parallel or nested tools can have overlapping execution durations.
`cmd_timeouts` counts command timeouts, including those the agent recovers from;
`timed_out` retains its session/verification meaning. Leak diagnostics record only
matched sensitive tokens, and diagnostic failures preserve the row with
`diag_error`.

Gold calibration's local subprocess path uses the same environment setup. Its
Kaggle push script embeds `eval/sandbox_env.py` in the staged single-file kernel.
On a host without usable bubblewrap, calibration requires `--allow-unsandboxed`
or `GOLD_ALLOW_UNSANDBOXED=1`. `GOLD_NULL_PATCH`, `GOLD_IDS_FILE` and `GOLD_PROBE_LOG`
remain available. The Docker calibration path is unchanged.

The offline stub accepts a JSON array of assistant messages, including OpenAI
`tool_calls`, or full completion responses. Responses are consumed in order;
exhaustion returns HTTP 409. It supports non-streaming chat completions and models:

```sh
python eval/stub_openai.py --script /tmp/responses.json --port 8000
```

No packages need installing for tests. If the harness venv lacks pytest, use the
image interpreter and expose the existing harness packages:

```sh
export PYTHONPATH=/home/ubuntu/gemma-local/venv/lib/python3.13/site-packages
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export LITELLM_LOCAL_MODEL_COST_MAP=True
/home/ubuntu/gemma-local/pyimg/cpython-3.13-linux-x86_64-gnu/bin/python3 -m pytest eval/tests -q
RUN_AGENT_EVAL_E2E=1 /home/ubuntu/gemma-local/pyimg/cpython-3.13-linux-x86_64-gnu/bin/python3 -m pytest eval/tests -q -rs
```

The integration tests use synthetic snapshots and a temporary bundle, without
competition data or a GPU. The HTTP variant needs localhost socket permission;
the in-memory variant drives the same stub handler without sockets and verifies
patch capture, gold calibration, resume rejection and diagnostic row persistence.
The real bubblewrap probe skips only if bubblewrap is missing or denied by the
execution sandbox. `--allow-foreign-python` is a unit-test escape hatch.
