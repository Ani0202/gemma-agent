Implemented B1–B5 and N1–N3: shared isolation setup, graph paths, execution timing, resume fingerprints, config forwarding, and durable diagnostics.

Tests: **399 passed, 3 skipped, 4 subtests passed** using the requested fallback interpreter. Synthetic stub E2E captured a patch and passed verification.

Sandbox prevented real bubblewrap and localhost HTTP tests. The third skip is the existing YAML fallback alias case. Builder still needs to run those integration checks and recalibrate gold exclusions. No commit made.

[Implementation report](/home/ubuntu/work/gemma-wt/codex-eval-runner-fix/ops/codex/implement-20261105-eval-runner-fix.md)
