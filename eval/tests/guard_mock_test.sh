#!/bin/bash
# Offline test of a bin/kaggle-submit candidate against a MOCK kaggle CLI (dec 045 item 1).
# Usage: eval/tests/guard_mock_test.sh <candidate-kaggle-submit> <real-bundle.zip>
# The real kaggle CLI is made UNREACHABLE: every guard run is under `env -i` with PATH=<mock>:/usr/bin:/bin
# (no venv bins) and KAGGLE_CONFIG_DIR=<empty dir>, in a throwaway repo whose config.env names a fake competition.
# A preflight aborts unless `command -v kaggle` inside that environment resolves to the mock.
set -euo pipefail
cand=$(realpath "$1"); real=$(realpath "$2")
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/repo/bin" "$T/repo/ops/decisions" "$T/repo/dist" "$T/mock" "$T/kcfg"
cp "$cand" "$T/repo/bin/kaggle-submit"; chmod +x "$T/repo/bin/kaggle-submit"
printf '#!/bin/sh\nexit 0\n' > "$T/repo/bin/notify"; chmod +x "$T/repo/bin/notify"
printf 'COMP=mock-competition-not-real\nSUBMIT_MODE=kernel\nSUBMIT_KERNEL=mockowner/mock-kernel\n' > "$T/repo/config.env"
cp "$real" "$T/repo/dist/z.zip"
cat > "$T/mock/kaggle" <<EOF
#!/bin/bash
echo "\$*" >> "$T/calls.log"
if [ "\$1" = kernels ]; then d=\$5; cp "\${OUTZIP:-$T/repo/dist/z.zip}" "\$d/submission.zip"; exit 0; fi
if [ "\$2" = submissions ]; then case "\${SUBS:-none}" in
  none) echo "No submissions found";;
  today) printf 'ref,fileName,date,description,status,publicScore,privateScore\n9,submission.zip,%s 01:00:00,x,COMPLETE,0.1,\n' "\$(date -u +%F)";;
  sha) printf 'ref,fileName,date,description,status,publicScore,privateScore\n9,submission.zip,2026-11-01 01:00:00,e4b sha:%s y,COMPLETE,0.1,\n' "\$SHA12";;
  old) printf 'ref,fileName,date,description,status,publicScore,privateScore\n9,submission.zip,2026-11-01 01:00:00,other,COMPLETE,0.1,\n';;
  junk) echo "<html>oops";; fail) exit 1;; esac; exit 0; fi
case "\${MODE:-ok}" in ok) echo "Submission ref: 123";; noref) echo "ERROR: submission rejected";;
  400) echo "400 Client Error: Bad Request" >&2; exit 1;; 408) echo "408 Client Error: Request Timeout" >&2; exit 1;;
  503) echo "HTTPError: 503 Server Error" >&2; exit 1;; killed) exit 137;; esac
EOF
chmod +x "$T/mock/kaggle"
G() { env -i HOME="$T" PATH="$T/mock:/usr/bin:/bin" KAGGLE_CONFIG_DIR="$T/kcfg" "$@"; }
[ "$(G bash -c 'command -v kaggle')" = "$T/mock/kaggle" ] || { echo "ABORT: kaggle does not resolve to the mock"; exit 2; }
cd "$T/repo"
sha=$(sha256sum dist/z.zip | cut -d' ' -f1); echo "SUBMIT: AUTHORIZE sha256=$sha track=e4b" > ops/decisions/z.md
fail=0
reset() { : > ops/submissions.jsonl; rm -f ops/submissions.pending; }
expect() {  # <name> <expected rc> <expected pending Y|N> <expected records> <kernel version> -- env...
  local name=$1 erc=$2 epend=$3 erec=$4 kv=$5; shift 6; reset
  set +e; out=$(G "$@" SHA12="${sha:0:12}" bin/kaggle-submit dist/z.zip e4b m "$kv" 2>&1); rc=$?; set -e
  pend=$([ -e ops/submissions.pending ] && echo Y || echo N); rec=$(wc -l < ops/submissions.jsonl)
  if [ "$rc" = "$erc" ] && [ "$pend" = "$epend" ] && [ "$rec" = "$erec" ]; then echo "PASS $name"; else
    echo "FAIL $name: rc=$rc pending=$pend records=$rec :: $(printf '%s' "$out" | tail -1)"; fail=1; fi
}
expect ok 0 N 1 1 -- MODE=ok
expect reject400 4 N 0 1 -- MODE=400
expect amb408 5 Y 0 1 -- MODE=408
expect amb503 5 Y 0 1 -- MODE=503
expect killed 5 Y 0 1 -- MODE=killed
expect noref 5 Y 0 1 -- MODE=noref
expect subs_today 3 N 0 1 -- SUBS=today
expect subs_sha 3 N 0 1 -- SUBS=sha
expect subs_junk 3 N 0 1 -- SUBS=junk
expect subs_fail 3 N 0 1 -- SUBS=fail
expect subs_old 0 N 1 1 -- SUBS=old
expect no_version 3 N 0 x -- MODE=ok
expect bad_output 3 N 0 1 -- OUTZIP=/etc/hostname
# pending blocks the next call
reset; echo '{}' > ops/submissions.pending; set +e; G bin/kaggle-submit dist/z.zip e4b m 1 >/dev/null 2>&1; rc=$?; set -e
[ $rc = 3 ] && echo "PASS pending_blocks" || { echo "FAIL pending_blocks rc=$rc"; fail=1; }
# single use
reset; G MODE=ok bin/kaggle-submit dist/z.zip e4b m 1 >/dev/null 2>&1; set +e; G MODE=ok bin/kaggle-submit dist/z.zip e4b m 1 >/dev/null 2>&1; rc=$?; set -e
[ $rc = 3 ] && echo "PASS single_use" || { echo "FAIL single_use rc=$rc"; fail=1; }
# unauthorized sha
reset; cp dist/z.zip dist/z2.zip; echo >> dist/z2.zip; set +e; G MODE=ok bin/kaggle-submit dist/z2.zip e4b m 1 >/dev/null 2>&1; rc=$?; set -e
[ $rc = 3 ] && echo "PASS unauthorized" || { echo "FAIL unauthorized rc=$rc"; fail=1; }
# malformed root members (byte-level NUL, dir mode, symlink)
python3 -I - <<'PY'
import stat, zipfile
def mk(n, name, mode):
    z = zipfile.ZipFile(f'dist/{n}.zip', 'w'); zi = zipfile.ZipInfo(name); zi.external_attr = mode << 16; z.writestr(zi, 'x'); z.close()
mk('dirmode', 'agent.yaml', stat.S_IFDIR | 0o755); mk('link', 'agent.yaml', stat.S_IFLNK | 0o777)
z = zipfile.ZipFile('dist/nul.zip', 'w'); z.writestr('agent.yaml_extra', 'x'); z.close()
b = open('dist/nul.zip', 'rb').read().replace(b'agent.yaml_extra', b'agent.yaml\x00extra'); open('dist/nul.zip', 'wb').write(b)
PY
for b in dirmode link nul; do
  s2=$(sha256sum dist/$b.zip | cut -d' ' -f1); echo "SUBMIT: AUTHORIZE sha256=$s2 track=e4b" > ops/decisions/$b.md; reset
  set +e; out=$(G MODE=ok bin/kaggle-submit dist/$b.zip e4b m 1 2>&1); rc=$?; set -e
  [ $rc = 3 ] && printf '%s' "$out" | grep -q 'agent.yaml' && echo "PASS zip_$b" || { echo "FAIL zip_$b rc=$rc"; fail=1; }
done
grep -qv '^competitions submit mock-competition-not-real\|^competitions submissions mock-competition-not-real\|^kernels output mockowner/mock-kernel/' "$T/calls.log" && { echo "FAIL unexpected mock calls"; fail=1; } || true
echo "mock calls: $(wc -l < "$T/calls.log")"; [ $fail = 0 ] && echo "ALL PASS" || { echo "SOME FAILED"; exit 1; }
