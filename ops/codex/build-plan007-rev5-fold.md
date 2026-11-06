Implemented in [classify_rows.py](/home/ubuntu/work/gemma-wt/codex-plan007-rev5-fold/eval/kaggle/classify_rows.py), with regressions in [test_classify_rows.py](/home/ubuntu/work/gemma-wt/codex-plan007-rev5-fold/eval/tests/test_classify_rows.py).

All test names below begin with `test_rev5_`.

| Item | Rule implemented | Test suffix |
|---|---|---|
| 1 | Success with result error → H-VERIFY | `01_resolved_result_error` |
| 2 | Conflicting message categories → H-ROW | `02_conflicting_messages` |
| 3 | JUnit failures require integer exit 0 | `03_junit_requires_exit_zero` |
| 4 | Apply failure requires patch and compatible exit | `04_apply_requires_patch_and_failure_exit` |
| 5 | No patch requires null/-1 exit | `05_no_patch_exit` |
| 6 | Required keys distinguish missing from null | `06_missing_vs_null` |
| 7 | Require setup keys and subprocess rc | `07_missing_step_key`, `07_missing_subprocess_rc` |
| 8 | Validate step names, subprocess placement, argv | `08_step_and_argv` |
| 9 | Validate identity directly and through CLI | `09_identity_direct_and_cli` |
| 10 | Not-run requires all four conditions | `10_not_run_requires_empty_evidence` |
| 11 | Diagnostics require executed nonzero integer rc | `11_diagnostic_requires_executed_rc` |
| 12 | Match markers within each stream | `12_marker_per_stream` |
| 13 | Require exact offline command shape | `13_exact_offline_command` |
| 14 | Consume immediate matching fallback exemption | `14_fallback_immediate_same_identity_consumed` |
| 15 | Reject unrecognized CLI records | `15_cli_rejects_unrecognized_records` |
| 16 | Reject duplicate JSON keys | `16_duplicate_json_keys` |
| 17 | Enforce ordered prefix and completion count | `17_journal_accounting`, `17_completed_prefix_without_done` |
| 18 | Void kernels force every row to H-ROW | `18_kernel_void` |
| 19 | Numeric overflow fails closed | `19_numeric_overflow` |
| False-H 1 | Preserve setup.py not-run | `false_h_01_setup_py_not_run` |
| False-H 2 | Preserve workspace not-run | `false_h_02_workspace_not_run` |

Preserved the requested legitimate outcome tests. Metadata recognition includes the producer’s actual `_vllm` and `_stopped` forms.

Offline test output: **1,155 passed, 5 skipped, 4 subtests passed** using pyimg Python with harness `PYTHONPATH`.

Regenerated the arm-F artifact through the existing CLI: **8 H-ROW, 7 known diagnostics, 0 H-SETUP**, unchanged. Only SHA and kernel-void reporting fields changed.

Classifier SHA-256:
```text
d4cdf0f012659c685789add3b8e5687362ba01673344bdc1f1bad97f81d8ae5e
```

**RESIDUAL / open issues:** The supplied review file is empty, so its exact B row and overrides could not be recovered. All numbered requirements in your message were implemented and tested.

Sandbox prevented: nothing. No commit was run.
