Implemented all six findings: Docker install order, per-step distribution/RECORD probes, wheel-derived cache keys and validation, missing-dependency failure gates, editable failure flags, bounded journals with full per-task artifacts, and diagnostic-only status.

Tests: 41 targeted passed; remaining eval suite: 462 passed, 4 skipped. `git diff --check` passed.

Open validation: Builder must rerun acceptance outside this sandbox. Bwrap network isolation was blocked (`Operation not permitted`). One unrelated memguard test failed because it inherited `oom_score_adj=1000` instead of `0`; it was excluded from the successful suite run.

Rerun instructions: [plan003_kernel_setup.md](/home/ubuntu/work/gemma-wt/codex-kernel-setup-fix/eval/repro/plan003_kernel_setup.md). No commit created.
