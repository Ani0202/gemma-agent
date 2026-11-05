#!/usr/bin/env bash
# Smoke test for the proposed bin/job kill-path fixes. Runs the patched copy in a fresh scratch tree only.
# Usage: killtest.sh <patched-job-script>
set -u
D=$(mktemp -d /tmp/claude-1001/-home-ubuntu-work-gemma/bd3846a9-90cd-442d-9edb-69dd8ad0c778/scratchpad/jobpatch/kt.XXXX)
mkdir -p "$D/tools"; install -m 755 "$1" "$D/tools/jobx"; cd "$D" || exit 1
J=tools/jobx
alive() { kill -0 "$1" 2>/dev/null && echo yes || echo NO; }

echo "== T1 setsid escape (expect both sleeps killed, no survivors)"
$J start t1-light -- bash -c 'setsid sleep 3011 & echo $! > esc.pid; sleep 3012'
sleep 1; cat ops/jobs/t1-light.status
E=$(cat esc.pid); echo "escaped pid $E pgid $(ps -o pgid= -p "$E" | tr -d ' ') (job pgid $(awk '{print $4}' ops/jobs/t1-light.status))"
$J kill t1-light; sleep 0.5; echo "escaped alive after kill: $(alive "$E")"

echo "== T2 stale boot id (expect nothing signalled)"
$J start t2-light -- sleep 3013; sleep 1
read -r st p d g b t < ops/jobs/t2-light.status
echo "running $p $d $g deadbeef-0000 $t" > ops/jobs/t2-light.status
$J kill t2-light; echo "t2 wrapper alive: $(alive "$p")"
echo "running $p $d $g $b $t" > ops/jobs/t2-light.status; $J kill t2-light >/dev/null; echo "after real kill: $(alive "$p")"

echo "== T3 reused pgid, new 6-field record (expect unrelated group untouched)"
setsid sleep 3014 & U=$!; sleep 0.5
echo "running 999999 2026 $U $(cat /proc/sys/kernel/random/boot_id) 12345" > ops/jobs/t3-light.status
$J kill t3-light; echo "unrelated $U alive: $(alive "$U")"; kill "$U"

echo "== T4 reused pgid, legacy 4-field record, wrapper gone (expect untouched)"
setsid sleep 3015 & U=$!; sleep 0.5
echo "running 999998 2026 $U" > ops/jobs/t4-light.status
$J kill t4-light; echo "unrelated $U alive: $(alive "$U")"; kill "$U"
