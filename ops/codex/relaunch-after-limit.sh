#!/bin/bash
# Codex usage limit hit 19:28Z (resets ~23:04Z). Dec 029 item 4: fix5 review FIRST and alone at
# CODEX_EFFORT=medium; memguard-fix6 review only after fix5's job has finished.
# Usage: relaunch-after-limit.sh <original-job-name> [<job-to-wait-for>]
# Sleeps until 23:08Z, then (optionally) waits until ops/jobs/<job-to-wait-for>.status no longer
# says "running", then re-runs ops/jobs/<original-job-name>.cmd with CODEX_EFFORT=medium.
set -e
cd /home/ubuntu/work/gemma
target=$(date -u -d 'today 23:08' +%s); now=$(date -u +%s)
[ "$target" -gt "$now" ] && sleep $((target - now))
if [ -n "${2:-}" ]; then
  # wait for the job to exist and finish
  while [ ! -f ops/jobs/"$2".status ] || grep -q '^running' ops/jobs/"$2".status; do sleep 60; done
fi
export CODEX_EFFORT=medium
exec bash ops/jobs/"$1".cmd
