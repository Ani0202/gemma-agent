Implemented the kernel, CPU-only/offline metadata, push helper, resume logic, summary aggregation, and [push/fetch documentation](/home/ubuntu/work/gemma-wt/codex-gold-kernel/docs/GOLD_CALIBRATION.md).

Validation: 13 offline tests passed; Python compilation, shell syntax, metadata staging, and whitespace checks passed.

Open issues: Kaggle execution and the undocumented `verify_task` API remain unverified. Assumptions are isolated in `verify_gold` and documented.

Sandbox prevented: nothing required locally. No Kaggle push/run or git commit performed.
