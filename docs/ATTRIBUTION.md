# Attribution
Public code and ideas reused from competition participants (Apache-2.0 unless noted). Each entry
gives the source URL, what we reused, and the date.

- Official competition `sample_submission` (Kaggle Gemma 4 Developer Agent competition data, `data/raw/sample_submission`; competition-provided starter, local only, not redistributed). Reused: agent.yaml structure, sub-agent/skill layout, eval_config schema as base for bundles/31b/v000 and bundles/e4b/v000. 2026-11-04.

- Official public competition starter (`docs/starter_notebook.ipynb`) and `HARNESS_README.md` sections 4, 8, 9 (Kaggle Gemma 4 Developer Agent competition). Referenced for offline wheelhouse setup, `EvalConfig`/`Evaluator` construction, sandbox selection, and Phase 2 semantics in `eval/kaggle/gold_calibration.py`; no task data copied. 2026-11-04.

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
