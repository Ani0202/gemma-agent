Implemented in [agent_timing.py](/home/ubuntu/work/gemma-wt/codex-kernel-setup-fix/eval/kaggle/agent_timing.py): sandbox-compatible wheel selection, offline pip bootstrap and scorer tools, explicit PIP_* prefixes, and bounded per-task setup records. setup.py failures are recorded without stopping the run. Single-file staging and the starter image pin remain intact.

Test output: **437 passed, 4 skipped, 1 failed**. The unrelated memguard test observes `oom_score_adj=1000` where it expects `0`.

Open issues: the local wheelhouse lacks pip and pytest-timeout wheels. Added an [offline acceptance script](/home/ubuntu/work/gemma-wt/codex-kernel-setup-fix/eval/repro/plan003_kernel_setup.py) and [validation result](/home/ubuntu/work/gemma-wt/codex-kernel-setup-fix/results/plan003_kernel_setup_acceptance.json).

Sandbox prevented: bubblewrap network namespace creation failed with `Operation not permitted`. Neither task started, so per-step setup durations and the <30-second acceptance remain unverified. No protected paths were modified; no commit was run.
