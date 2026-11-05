#!/bin/bash
# fix5c review BLOCKING 1 (ops/codex/review-20261105T230800.md): delta review of the gate (a) finalization fix.
# Runs AFTER the queued probes / probes-gate / fix6e reviews (Codex capacity).
set -e
cd /home/ubuntu/work/gemma
for j in review-kernel-probes-light review-kernel-probes-gate-light review-memguard-fix6e-light; do
  while [ ! -f ops/jobs/$j.status ] || grep -q '^running' ops/jobs/$j.status; do sleep 60; done
done
export CODEX_EFFORT=medium
exec bin/codex-review 'Light delta review. Branch codex/kernel-gate-finfix (worktree /home/ubuntu/work/gemma-wt/kernel-gate-finfix), diff codex/kernel-probes-gate...codex/kernel-gate-finfix (one commit e02666f). It addresses BLOCKING 1 of ops/codex/review-20261105T230800.md: gate (a) in eval/kaggle/timing_summary.py must not count a task complete when a post-timeout finalization sandbox_exec (row finalization_exec, recorded by agent_timing.py observe_sandbox ~l.763-785) raised or returned rc != 0; rc None without an exception fails closed. Check: (1) the fix closes the reported reproduction (8 rows with finalization_exec rc=124 -> gate FAIL) and cannot be bypassed by any finalization_exec shape agent_timing.py can write; (2) no false FAIL for rows without finalization_exec (no timeout) or with all rc 0 (v5 journal runs/e4b-v001-timing-v5/timing.jsonl stays a=7/8); (3) the new tests in eval/tests/test_agent_timing.py exercise it; (4) nothing else in the diff changes gate semantics. Mark each finding BLOCKING or NON-BLOCKING. Only review this delta. Do not edit files.'
