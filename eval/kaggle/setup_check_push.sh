#!/usr/bin/env bash
# CPU-only setup check, pinned to timing_push.sh's image; no model attached.
# Usage: setup_check_push.sh [--dry-run] USER/SLUG SETUP_FIX IDS_FILE [BUDGET_SECONDS]
set -euo pipefail
args=()
if [[ ${1:-} == --dry-run ]]; then args+=(--dry-run); shift; fi
if [[ $# -lt 3 || $# -gt 4 ]]; then
  echo "Usage: $0 [--dry-run] USER/SLUG SETUP_FIX IDS_FILE [BUDGET_SECONDS]" >&2
  exit 2
fi
exec bash "$(dirname -- "${BASH_SOURCE[0]}")/timing_push.sh" "${args[@]}" --setup-only "$2" "$1" "$3" "${4:-1800}"
