#!/usr/bin/env bash
# Stage a self-contained private GPU timing or CPU setup kernel. --dry-run never invokes Kaggle.
set -euo pipefail
dry_run=false
skip_verification=1
while [[ ${1:-} == --dry-run || ${1:-} == --with-verification ]]; do
  case $1 in
    --dry-run) dry_run=true ;;
    --with-verification) skip_verification=0 ;;
  esac
  shift
done
setup_only=0
setup_fix=1
if [[ ${1:-} == --setup-only ]]; then
  setup_only=1
  setup_fix=${2:?SETUP_FIX required}
  [[ $setup_fix == 0 || $setup_fix == 1 ]] || { echo 'SETUP_FIX must be 0 or 1' >&2; exit 2; }
  shift 2
  [[ $# -ge 2 && $# -le 3 ]] || { echo 'Usage: timing_push.sh [--dry-run] [--with-verification] --setup-only SETUP_FIX USER/SLUG IDS_FILE [BUDGET_SECONDS]' >&2; exit 2; }
  set -- "$1" - "$2" "${3:-1800}"
fi
if [[ $# -lt 3 || $# -gt 4 || ! $1 =~ ^[A-Za-z0-9_-]+/[A-Za-z0-9_-]+$ ]]; then
  echo "Usage: $0 [--dry-run] [--with-verification] KAGGLE_USER/SLUG BUNDLE_DIR IDS_FILE [BUDGET_SECONDS]" >&2
  exit 2
fi
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
stage_dir=$(mktemp -d /tmp/timing-kernel-push.XXXXXX)
# Dry runs retain the generated artifact for inspection.
if ! $dry_run; then trap 'rm -rf -- "$stage_dir"' EXIT; fi
budget=${4:-10800}
python3 - "$script_dir" "$stage_dir" "$1" "$2" "$3" "$budget" "$setup_only" "$setup_fix" "$skip_verification" <<'PY'
import ast
import base64
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile

source, stage = map(Path, sys.argv[1:3])
kernel_id, bundle_arg, ids_arg, budget_arg, setup_only_arg, setup_fix_arg, skip_verification_arg = sys.argv[3:]
setup_only = setup_only_arg == "1"
bundle, ids_file = Path(bundle_arg).resolve(), Path(ids_arg)
budget = int(budget_arg)
if budget <= 0:
    raise ValueError('Budget must be positive')
ids = [s.strip() for s in ids_file.read_text().splitlines() if s.strip() and not s.lstrip().startswith('#')]
if not ids or len(ids) != len(set(ids)) or any(not re.fullmatch(r'[A-Za-z0-9_.-]+', s) for s in ids):
    raise ValueError('Nonempty unique safe task IDs required')
# PyYAML is not required on the push host. agent.yaml uses a scalar model declaration.
buf = io.BytesIO()
model = None
if not setup_only:
    models = set()
    for path in [bundle / 'agent.yaml', *sorted((bundle / 'sub_agents').rglob('*.yaml')), *sorted((bundle / 'sub_agents').rglob('*.yml'))]:
        for line in path.read_text().splitlines():
            match = re.fullmatch(r'\s*model:\s*[\'"]?(gemma-4-(?:31b|12b|e4b|e2b)-it-qat-w4a16-ct)[\'"]?\s*(?:#.*)?', line)
            if match:
                models.add(match[1])
    if len(models) != 1:
        raise ValueError('Expected one allowed scalar model declaration')
    model = models.pop()
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb', mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode='w') as tf:
            for path in sorted(bundle.rglob('*')):
                if path.is_symlink() or not (path.is_file() or path.is_dir()):
                    raise ValueError('Bundle contains symlink or special file')
                tf.add(path, arcname=path.relative_to(bundle).as_posix(), recursive=False)
# Official PyPI wheels the scorer image pip-installs online (Dockerfile.public line 9 and runtime deps)
# but the offline wheelhouse lacks; pinned by vendor/SHA256SUMS, provenance in docs/ATTRIBUTION.md.
extra_wheels = {}
for line in (source / 'vendor' / 'SHA256SUMS').read_text().splitlines():
    digest, name = line.split()
    data = (source / 'vendor' / name).read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Vendored wheel sha256 mismatch: ' + name)
    extra_wheels[name] = [digest, base64.b64encode(data).decode()]
if 'pytest_timeout-2.1.0-py3-none-any.whl' not in extra_wheels:
    raise ValueError('Vendored pytest-timeout 2.1.0 wheel missing')
constants = dict(BUNDLE_B64=base64.b64encode(buf.getvalue()).decode(), TASK_IDS=ids, EXTRA_WHEELS=extra_wheels,
                 GIT_SHA=subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip(),
                 KERNEL_BUDGET_SECONDS=budget, SETUP_ONLY=setup_only, SETUP_FIX=int(setup_fix_arg),
                 SKIP_VERIFICATION=skip_verification_arg == "1")
text = (source / 'agent_timing.py').read_text()
lines = text.splitlines(keepends=True)
for node in reversed(ast.parse(text).body):
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id in constants:
        key = node.targets[0].id
        lines[node.lineno-1:node.end_lineno] = [f'{key} = {constants.pop(key)!r}\n']
if constants:
    raise ValueError('Missing template constants')
generated = ''.join(lines)
compile(generated, 'agent_timing.py', 'exec')
(stage / 'agent_timing.py').write_text(generated)
# No network per task constraint. Assumption: Kaggle model_sources accepts versioned model handles.
metadata = dict(id=kernel_id, title=kernel_id.split('/')[1], code_file='agent_timing.py', language='python',
                kernel_type='script', is_private=True, enable_gpu=not setup_only, enable_internet=False,
                dataset_sources=['metric/gemma-4-developer-agent-wheelhouse'],
                competition_sources=['gemma-4-developer-agent'], model_sources=[] if setup_only else [f'google/gemma-4/Other/{model}/2'], kernel_sources=[],
                # Pin the starter notebook's image (Python 3.12; wheelhouse binaries are cp312).
                # Source: kaggle kernels pull ryanholbrook/getting-started-gemma-4-developer-agent -m (2026-11-05).
                docker_image='gcr.io/kaggle-private-byod/python@sha256:37c64f7dd9c54116ecd1bcc88817c5469b88387388fade02bfa8bf3fc647d461')
(stage / 'kernel-metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
print(json.dumps(metadata, indent=2))
print(f'Generated script: {len(generated.encode())} bytes; stage: {stage}')
print('CPU setup check; no model; starter image pinned' if setup_only else
      'Metadata assumption (offline): model_sources uses google/gemma-4/Other/<model>/2 (starter casing); docker_image pinned to starter')
PY
if $dry_run; then
  echo "Dry run: no push. Staged: $stage_dir"
elif [[ $setup_only == 1 ]]; then
  kaggle kernels push -p "$stage_dir" -t "$((budget + 1800))"
else
  # 'NvidiaL4' is the starter notebook's machine_shape; unknown names (e.g. NvidiaL4X4) silently fall back to T4 x2.
  kaggle kernels push -p "$stage_dir" --accelerator NvidiaL4 -t "$((budget + 1800))"
  shape_dir=$(mktemp -d /tmp/timing-kernel-shape.XXXXXX)
  kaggle kernels pull "$1" -p "$shape_dir" -m >/dev/null
  shape=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["machine_shape"])' "$shape_dir/kernel-metadata.json")
  rm -rf -- "$shape_dir"
  echo "Server machine_shape: $shape"
  if [[ $shape != NvidiaL4 ]]; then echo "WARNING: accelerator is $shape, not NvidiaL4; kernel will abort at the GPU check" >&2; fi
fi
