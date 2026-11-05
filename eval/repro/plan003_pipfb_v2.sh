#!/usr/bin/env bash
# Plan 003 repro v2: HTTPS index (pip ignores plain-http untrusted hosts). Reuses the venvs/projects from pipfb.sh (without backends: recreate).
set -u
O=$1; cd $O
PY=$(ls /home/ubuntu/gemma-local/pyimg/cpython-3.13*/bin/python3.13 | head -1)
for be in poetry pdm; do
  rm -rf venv2-$be; $PY -m venv venv2-$be; P=venv2-$be/bin/python
  for mode in hang dns; do
    url=https://10.255.255.1/simple; [ $mode = dns ] && url=https://pypi.invalid/simple
    s=$(date +%s.%N); env PIP_INDEX_URL=$url $P -m pip install --no-deps -e proj-$be > log-$be-$mode.txt 2>&1; rc=$?
    echo "$be fallback-$mode: $(python3 -c "print(round($(date +%s.%N)-$s,1))") s rc=$rc retries=$(grep -c 'Retrying' log-$be-$mode.txt)"
  done
done
