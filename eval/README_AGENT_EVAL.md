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

`results/<run-name>.jsonl` contains a metadata header and sanitized task metrics.
Completed attempts, including failures, are skipped on resume. Changing the bundle,
caps, split, model registry, data directory, endpoint or concurrency requires a new
name or `--force-new`, which **replaces the results journal**. Raw traces, logs,
pre-stripping agent diffs, and harness outputs remain in `runs/<run-name>/`.
`patch_bytes` and file classifications describe the agent diff before protected-file
stripping; `output.json` includes the diff actually passed to verification.

The offline stub accepts a JSON array of assistant messages, including OpenAI
`tool_calls`, or full completion responses. Responses are consumed in order;
exhaustion returns HTTP 409. It supports non-streaming chat completions and models:

```sh
python eval/stub_openai.py --script /tmp/responses.json --port 8000
```

No packages need installing for tests. The harness venv currently lacks pytest, so
expose the existing pyimg copy when running the requested command:

```sh
export PYTHONPATH=/home/ubuntu/gemma-local/pyimg/cpython-3.13.18-linux-x86_64-gnu/lib/python3.13/site-packages
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export LITELLM_LOCAL_MODEL_COST_MAP=True
/home/ubuntu/gemma-local/venv/bin/python -m pytest eval/tests -q
RUN_AGENT_EVAL_E2E=1 /home/ubuntu/gemma-local/venv/bin/python -m pytest eval/tests/test_run_agent_eval.py -q -rs
```

The integration test needs localhost socket permission and existing clean dev data;
it uses the stub without a GPU. `--allow-foreign-python` is a unit-test escape hatch.
