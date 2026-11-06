#!/bin/bash
# Poll a Kaggle submission ref until it leaves PENDING/RUNNING; log polls (UTC, status, scores) for results/lb_*.json.
# Usage: ops/tools/lb_wait.sh <ref> <logfile>
cd /home/ubuntu/work/gemma; source config.env
ref=$1; log=$2
while true; do
  row=$(kaggle competitions submissions "$COMP" -v 2>&1 | awk -F, -v r="$ref" '$1==r')
  echo "$(date -u +%FT%TZ),$row" >> "$log"
  case "$row" in *PENDING*|*RUNNING*|"") sleep 1800;; *) break;; esac
done
