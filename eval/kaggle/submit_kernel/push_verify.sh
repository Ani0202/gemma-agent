#!/usr/bin/env bash
# Stage + push a CPU submit kernel for <zip>, wait for COMPLETE, verify the new version's output is byte-identical.
# Usage: eval/kaggle/submit_kernel/push_verify.sh <zip> <owner/slug> <out_txt>   (no submission is made)
set -u
cd "$(dirname "$0")/../../.." || exit 1
z=$1; k=$2; out=$3
st=$(mktemp -d /tmp/submitk.XXXXXX)
python3 -I eval/kaggle/submit_kernel/stage.py "$z" "$k" "$st" || exit 1
push=$(kaggle kernels push -p "$st" 2>&1); echo "$push"
ver=$(echo "$push" | grep -oE 'version [0-9]+' | grep -oE '[0-9]+' | tail -1)
[ -n "$ver" ] || { echo "$(date -u +%FT%TZ) $k push: no version parsed: $push" | tee -a "$out"; exit 1; }
sleep 20
for i in $(seq 1 60); do s=$(kaggle kernels status "$k" 2>&1 | tail -1); case "$s" in *COMPLETE*|*ERROR*|*CANCEL*) break;; esac; sleep 30; done
d=$(mktemp -d /tmp/submitk-out.XXXXXX); kaggle kernels output "$k/$ver" -p "$d" -q >/dev/null 2>&1
got=$(sha256sum "$d/submission.zip" 2>/dev/null | cut -d' ' -f1); want=$(sha256sum "$z" | cut -d' ' -f1)
v=MISMATCH; [ -n "$got" ] && [ "$got" = "$want" ] && v=BYTE_IDENTICAL
echo "$(date -u +%FT%TZ) $k v$ver status=[$s] output_sha=$got dist=$z sha=$want $v" | tee -a "$out"
rm -rf "$d" "$st"
