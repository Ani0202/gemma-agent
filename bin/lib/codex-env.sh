# Sourced by bin/codex-{ask,review,build}. Loads CODEX_* defaults from config.env without
# overriding anything the caller already set, then resolves and validates the reasoning effort.
# Usage (after cd to repo root): . bin/lib/codex-env.sh <ASK|REVIEW|BUILD>; then use $effort.
for _v in CODEX_MODEL CODEX_EFFORT_ASK CODEX_EFFORT_REVIEW CODEX_EFFORT_BUILD; do
  [ -n "${!_v+x}" ] && continue
  printf -v "$_v" '%s' "$(bash -c '. ./config.env >/dev/null 2>&1; printf %s "${!1:-}"' _ "$_v")"
done
_d="CODEX_EFFORT_$1"; effort=${CODEX_EFFORT:-${!_d:-medium}}; unset _v _d
case $effort in
  minimal|low|medium|high|xhigh) ;;
  *) echo "codex: invalid effort '$effort' (want minimal|low|medium|high|xhigh)" >&2; exit 2 ;;
esac
