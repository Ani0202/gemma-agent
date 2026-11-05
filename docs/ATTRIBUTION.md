# Attribution
Public code and ideas reused from competition participants (Apache-2.0 unless noted). Each entry
gives the source URL, what we reused, and the date.

- Official competition `sample_submission` (Kaggle Gemma 4 Developer Agent competition data, `data/raw/sample_submission`; competition-provided starter, local only, not redistributed). Reused: agent.yaml structure, sub-agent/skill layout, eval_config schema as base for bundles/31b/v000 and bundles/e4b/v000. 2026-11-04.

- Official public competition starter (`docs/starter_notebook.ipynb`) and `HARNESS_README.md` sections 4, 8, 9 (Kaggle Gemma 4 Developer Agent competition). Referenced for offline wheelhouse setup, `EvalConfig`/`Evaluator` construction, sandbox selection, and Phase 2 semantics in `eval/kaggle/gold_calibration.py`; no task data copied. 2026-11-04.

- `pytest-timeout` 2.1.0 (MIT, https://pypi.org/project/pytest-timeout/2.1.0/), official PyPI wheel `pytest_timeout-2.1.0-py3-none-any.whl` sha256 f6f50101443ce70ad325ceb4473c4255e9d74e3c7cd0ef827309dfa4c0d975c6, vendored at `eval/kaggle/vendor/` (branch codex/kernel-setup-fix5) and embedded in private Kaggle timing kernels only, to reproduce Dockerfile.public line 9 offline. Eval tooling only; not a submission artifact, not training data. 2026-11-05.
- Runtime dependencies of the line-9 tools, official PyPI wheels vendored alongside pytest-timeout (pinned in `eval/kaggle/vendor/SHA256SUMS`, hashes match PyPI's published digests; private timing kernels only): `pathspec` 1.1.1 (MPL-2.0), `shellingham` 1.5.4 (ISC), `trove-classifiers` 2026.9.21.13 (Apache-2.0), `annotated-doc` 0.0.5 (MIT). 2026-11-05.
Vendored official PyPI wheels embedded by `eval/kaggle/timing_push.sh` for offline setup
(`eval/kaggle/vendor/`, pinned by `SHA256SUMS`). Licenses below are transcribed from each
wheel's `.dist-info/METADATA` license expression, license field, or license classifier. 2026-11-05.

| Name | Version | Source | License stated in METADATA |
| --- | --- | --- | --- |
| annotated-doc | 0.0.5 | https://pypi.org/project/annotated-doc/ | MIT |
| pathspec | 1.1.1 | https://pypi.org/project/pathspec/ | Mozilla Public License 2.0 (MPL 2.0) |
| pytest-timeout | 2.1.0 | https://pypi.org/project/pytest-timeout/ | MIT |
| shellingham | 1.5.4 | https://pypi.org/project/shellingham/ | ISC License (ISCL) |
| trove-classifiers | 2026.9.21.13 | https://pypi.org/project/trove-classifiers/ | Apache Software License |
