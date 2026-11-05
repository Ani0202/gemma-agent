Fix the BLOCKING findings of two Codex reviews on this branch (codex/kernel-gate-finfix, HEAD e02666f, which stacks
codex/kernel-setup-fix5 -> codex/kernel-probes 63127c8 -> codex/kernel-probes-gate 92a74c7 -> e02666f). Read both reviews first:
/home/ubuntu/work/gemma/ops/codex/review-20261105T231036.md (probes) and /home/ubuntu/work/gemma/ops/codex/review-20261105T231320.md (gate).
Files: eval/kaggle/agent_timing.py, eval/kaggle/timing_summary.py, eval/tests/test_kernel_probes.py, eval/tests/test_agent_timing.py, docs/ATTRIBUTION.md.

1. P1 stock_setup_probe OVERALL deadline (probes review BLOCKING 1). Add a module constant P1_DEADLINE_SECONDS = 180 covering the WHOLE probe
   (venv creation, wheel copies, all execs, cleanup). Enforce it with a wall-clock deadline: each exec gets min(120, remaining) as its timeout, and
   after the deadline no further step starts. Cleanup still runs but is itself bounded (e.g. 30 s); on any overrun the row gets error='deadline'
   and total_s is the measured time. The probe must never raise. Budget: the pre-task should_stop check must reserve P1_DEADLINE_SECONDS + 30
   in addition to the existing per-task reservation when P1 is enabled, AND re-check remaining budget after P1 finishes and before the measured
   task starts (if insufficient: record the existing _stopped record and stop, exactly as should_stop does today). P1 time stays OUT of the task's
   measured Phase-1/totals (unchanged), but it must count toward the kernel elapsed/budget. Tests: a fake slow P1 hits the deadline -> error
   'deadline', never raises, bounded duration (use a tiny deadline via monkeypatch); a budget scenario like the reviewer's example (elapsed 5200,
   task 463, budget 6000, P1 360) stops BEFORE starting the task.
2. G1 evidence flag (probes review BLOCKING 2). In timing_summary probes.stock_setup: n_expected = header task_ids; all_le_30s is True ONLY if every
   expected task id has a stock_setup with finite, nonnegative total_s, no error, and total_s <= 30, with matching ids. Report n_missing and
   missing_ids. Regression test: two-task journal, one row lacks stock_setup -> all_le_30s False; also error row -> False.
3. Signed differences (gate review BLOCKING 2). numbers() keeps rejecting non-finite/non-numeric values everywhere, and raw measurements
   (wall seconds, phase1, setup, agent clock, finalization_seconds) must still be >= -1e-3 (clamp values in [-1e-3, 0) to 0.0 for raw
   measurements; < -1e-3 still raises). DERIVED differences (phase1_minus_image_seconds, stockpath_phase1_seconds) are signed: finite only, no
   sign check, reported as-is. Regression tests in BOTH gate modes ('total' and 'stock-path'): phase1=29.999999, image=10, setup.py=20 produces a
   tiny negative residual and the summary completes with a gate result; finalization_seconds=-0.000001 completes (clamped to 0).
4. Gate (b) formula (gate review BLOCKING 1): do NOT change the formula (it is a Director decision). Add to the summary's gate dict a field
   b_note = 'conservative: stock-path residual still includes workspace_editable and base_tar_extraction emulation steps (skipped by the stock
   path); biases (b) toward FAIL by their duration' and report per task the summed duration of those two steps as
   stockpath_retained_emulation_seconds (from setup_calls steps; null if missing). Test with a synthetic row.
5. Legacy decision field (fix5c review NON-BLOCKING 3, ops/codex/review-20261105T230800.md): rename the top-level summary key 'decision' to
   'legacy_projection_decision' (keep the value), keep decision_note, update tests/consumers (grep the repo eval/ for '"decision"' / ['decision']).
6. Attribution (fix5c review NON-BLOCKING 4): add docs/ATTRIBUTION.md entries for the five vendored wheels referenced by eval/kaggle/timing_push.sh
   (name, version, source URL = PyPI project page, license as stated in each wheel's METADATA; read the METADATA from the vendored wheel files).
Acceptance: python -m pytest eval/tests/test_agent_timing.py eval/tests/test_kernel_probes.py eval/tests/test_setup_check.py -q all pass
(offline); report counts. Re-summarize runs/e4b-v001-timing-v5/timing.jsonl is NOT possible in your sandbox if runs/ is absent; skip it and say so.
Do not change the default gate mode or any threshold. No other behaviour changes.
