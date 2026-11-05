#!/bin/bash
# Codex usage limit hit 19:28Z (resets ~23:04Z). Sleep until 23:08Z, then re-run the original review command.
# Usage: relaunch-after-limit.sh <original-job-name>
set -e
cd /home/ubuntu/work/gemma
target=$(date -u -d 'today 23:08' +%s); now=$(date -u +%s)
[ "$target" -gt "$now" ] && sleep $((target - now))
exec bash ops/jobs/"$1".cmd
