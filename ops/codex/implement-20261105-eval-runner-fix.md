Implemented the blocking and non-blocking findings in review-20261105T145013.md.
No commit, Kaggle push, cloud operation, holdout evaluation, or changes to bundles,
competition data, results, decisions, or installed harness source were made.

Changes:

- `eval/sandbox_env.py` owns package isolation, dependency binding patches,
  bubblewrap command wrapping, startup probes, command timeout accounting and
  gold artifact placement. Both local entrypoints call `setup_scorer_env`.
  All manager commands, including verification/setup, pass through the executor
  hook after installed swegemma path translation. Missing/failed bubblewrap is
  fatal unless explicitly allowed; opt-out mode is recorded as `none`.
- The startup probe first checks an empty masked inventory directory, image
  pytest imports and workspace write-through, then repeats inventory invisibility
  and runtime checks with the wheelhouse mounted. A mounted wheelhouse child
  necessarily makes the inventory directory nonempty on that second probe.
  Temporary inventory mountpoints are recreated after masking `/tmp`.
- Python prefix and wheel targets are mounted read-only. Symlinks cannot expand
  the permitted exposure to arbitrary directories; mutable venv configuration
  cannot select another base prefix. Gold host patch files and calibration
  sandbox roots stay under the supplied artifact directory.
- Graph/embedding paths are resolved against the data directory and passed to
  the supplied context. Installed graph tools read files in the host process;
  they do not require subprocess mounts.
- `eval/tool_timing.py` prepends an ADK plugin to the harness-created App. It
  measures monotonic before/after/error boundaries by function-call ID with
  per-task ContextVar state. Trace timestamp subtraction is removed. Rows include
  timing coverage, command timeout counts and token-only leak diagnostics.
- Resume identity includes runner SHA/dirty flag, inventory/split/bundle hashes,
  swegemma/adk_submission/google-adk/litellm and Python versions, sorted wheel
  listing hash, sandbox mode and effective EvalConfig. Mismatches report a diff.
  `--force-new-out` archives the existing journal/artifacts before starting fresh.
- All recognized EvalConfig keys are forwarded, with explicit runner runtime
  settings/CLI overrides taking precedence. Unknown keys warn. Git octal path
  quoting is decoded as UTF-8 bytes. Diagnostic failures preserve verdict rows
  with `diag_error`. Duplicate IDs are checked in raw JSONL before load_tasks.
- Kaggle staging embeds the shared environment source into its single Python
  artifact. Offline tests import that staged artifact without the repository on
  sys.path. GOLD_NULL_PATCH, GOLD_IDS_FILE and GOLD_PROBE_LOG have regression tests.

Installed reference inspected: swegemma 0.2.11, adk_submission 0.2.13,
google-adk 2.13.0, litellm 1.108.0, CPython 3.13.18.

Validation:

The requested harness interpreter reports `No module named pytest`; used the
requested image-interpreter fallback with the existing harness packages exposed:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
LITELLM_LOCAL_MODEL_COST_MAP=True \
PYTHONPATH=/home/ubuntu/gemma-local/venv/lib/python3.13/site-packages \
RUN_AGENT_EVAL_E2E=1 \
/home/ubuntu/gemma-local/pyimg/cpython-3.13-linux-x86_64-gnu/bin/python3 \
  -m pytest eval/tests -q -rs
```

Output: **399 passed, 3 skipped, 4 subtests passed in 24.42s**.
`git diff --check` and `bash -n eval/kaggle/push.sh` also passed.

The passing in-memory E2E drives the existing stub_openai HTTP handler through
streams, with real compilation, ADK tools, subprocess commands, patch capture,
pytest/JUnit verification and synthetic gold calibration. It also checks changed
SHA refusal, output archival and row preservation after classification failure.
Its subprocess thread dispatch runs inline because this execution sandbox blocks
asyncio worker-thread socket wakeups. The separate real ADK parallel-tool test
measures 0.05 s and 0.5 s tools individually and validates concurrent task contexts.
All E2E data and artifacts are synthetic and live under pytest temporary paths.

Skipped checks / sandbox limits:

1. Real bubblewrap: installed, but denied with
   `bwrap: loopback: Failed to create NETLINK_ROUTE socket: Operation not permitted`.
   Fake-executor probe/mount/failure tests passed. Builder must run the real test
   in an environment that permits bubblewrap.
2. HTTP E2E: localhost socket creation denied. The in-memory handler variant passed.
3. YAML aliases: the existing fallback-parser parameter deliberately disables
   PyYAML; that parameter cannot support aliases.

Open validation: real bubblewrap execution and socket-based E2E remain to be run
by Builder. No public gold clean-list recalibration was performed; synthetic gold
checks establish plumbing, not the continued validity of existing exclusions.
Kaggle execution itself was not launched; the staged single-file import was tested
offline. Subprocess calibration on a host without usable bubblewrap requires
`--allow-unsandboxed` or `GOLD_ALLOW_UNSANDBOXED=1`.
