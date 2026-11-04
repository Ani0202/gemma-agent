#!/usr/bin/env bash
# Upload a private CPU calibration kernel; this is not a competition submission.
set -euo pipefail
if [[ $# != 1 || ! $1 =~ ^[A-Za-z0-9_-]+/[A-Za-z0-9_-]+$ ]]; then
  echo "Usage: $0 KAGGLE_USERNAME/KERNEL_SLUG" >&2
  exit 2
fi
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
stage_dir=$(mktemp -d /tmp/gold-kernel-push.XXXXXX)
trap 'rm -rf -- "$stage_dir"' EXIT
cp -- "$script_dir/gold_calibration.py" "$stage_dir/gold_calibration.py"
python3 - "$script_dir/gold_calibration_metadata.json" "$stage_dir/kernel-metadata.json" "$1" <<'PY'
import json
import sys
from pathlib import Path
metadata = json.loads(Path(sys.argv[1]).read_text())
metadata['id'] = sys.argv[3]
Path(sys.argv[2]).write_text(json.dumps(metadata, indent=2) + '\n')
PY
kaggle kernels push -p "$stage_dir"
