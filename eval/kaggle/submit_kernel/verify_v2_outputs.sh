#!/usr/bin/env bash
# Poll both CPU submit kernels (v2) until COMPLETE, download v2 output, compare sha to dist zip.
set -u
cd /home/ubuntu/work/gemma
out=results/submit_kernel_v2_verify.txt; : > $out
for pair in "31b dist/31b-v009.zip" "e4b dist/e4b-v002h.zip"; do
  set -- $pair; k=aniket0202/gemma-submit-$1; z=$2
  for i in $(seq 1 40); do s=$(kaggle kernels status $k 2>&1 | tail -1); case "$s" in *COMPLETE*|*ERROR*|*CANCEL*) break;; esac; sleep 30; done
  d=$(mktemp -d); kaggle kernels output "$k/2" -p "$d" -q >/dev/null 2>&1
  got=$(sha256sum "$d/submission.zip" 2>/dev/null | cut -d' ' -f1); want=$(sha256sum "$z" | cut -d' ' -f1)
  v=MISMATCH; [ -n "$got" ] && [ "$got" = "$want" ] && v=BYTE_IDENTICAL
  echo "$(date -u +%FT%TZ) $k v2 status=[$s] output_sha=$got dist=$z sha=$want $v" | tee -a $out
  rm -rf "$d"
done
