"""Offline setup acceptance using one rich and one fastapi frozen dev snapshot.

Builder command OUTSIDE the Codex sandbox (runs BOTH SETUP_FIX=0 and =1):
  /home/ubuntu/gemma-local/venv/bin/python eval/repro/plan003_kernel_setup.py

Optional --setup-fix 0|1 selects a single mode. Defaults use the main checkout's
public data/wheelhouse; override with --data-dir and --wheels-dir. Output defaults
to results/plan003_kernel_setup_acceptance.json, including per-step durations and
bounded pip errors; full output is stored in per-task artifacts. bwrap --unshare-net is mandatory; no PIP_* overrides,
venv monkeypatching, model, agent, verification, downloads, or holdout access.
"""
import argparse
from contextvars import ContextVar
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path('/home/ubuntu/work/gemma/data/raw'))
    parser.add_argument('--wheels-dir', type=Path)
    parser.add_argument('--output', type=Path, default=Path('results/plan003_kernel_setup_acceptance.json'))
    parser.add_argument('--setup-fix', choices=('0', '1'))
    parser.add_argument('--inside-bwrap', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    identity = dict(_schema='plan003_kernel_setup_acceptance_v1',
                    script='eval/repro/plan003_kernel_setup.py',
                    local_data_dir=str(args.data_dir.resolve()),
                    task_ids=['rich_3006', 'fastapi_14986'],
                    setup_fix_modes=[int(args.setup_fix)] if args.setup_fix else [0, 1])
    if not args.inside_bwrap:
        command = ['bwrap', '--dev-bind', '/', '/', '--unshare-net', sys.executable,
                   str(Path(__file__).resolve()), *sys.argv[1:], '--inside-bwrap']
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode and 'bwrap:' in result.stderr:
            args.output.write_text(json.dumps(dict(**identity, status='blocked', rc=result.returncode,
                stderr=result.stderr[-2048:], rows=[]), indent=2) + '\n')
        print(result.stdout, end='')
        print(result.stderr, end='', file=sys.stderr)
        return result.returncode
    os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
    spec = importlib.util.spec_from_file_location('timing', Path(__file__).parents[1] / 'kaggle/agent_timing.py')
    timing = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(timing)
    timing.WORK = args.output.parent / (args.output.stem + '_artifacts')
    state = ContextVar('acceptance')
    rows = []
    with tempfile.TemporaryDirectory(prefix='kernel-setup-') as temp:
        root = Path(temp)
        wheels = (args.wheels_dir or args.data_dir / 'wheels').resolve()
        (root / 'wheels').symlink_to(wheels)
        (root / 'sandbox').symlink_to((args.data_dir / 'sandbox').resolve())
        (root / 'snapshots').symlink_to((args.data_dir / 'snapshots').resolve())
        for mode in [args.setup_fix] if args.setup_fix else ['0', '1']:
            os.environ['SETUP_FIX'] = mode
            for iid, repo in [('rich_3006', 'Textualize/rich'), ('fastapi_14986', 'fastapi/fastapi')]:
                row = timing.setup_task(root, wheels, iid, repo, state)
                rows.append(row)
                print(json.dumps(dict(instance_id=iid, setup_fix=int(mode),
                    steps={c['step']: c['duration_s'] for c in row['setup_calls']},
                    editable_rc=row['editable_rc'], workspace_editable_rc=row.get('workspace_editable_rc'),
                    retrying_lines=row['retrying_lines'], setup_s_total=row['setup_s_total'],
                    distributions={c['step']: c['distributions'] for c in row['setup_calls']
                                   if 'distributions' in c})), flush=True)
    # The unfixed mode is diagnostic; only fixed rows must pass the setup gate.
    fixed = [r for r in rows if r['setup_fix'] == 1]
    passed = bool(fixed) and all(not r['setup_failed'] and not r.get('editable_failed') and
                 not r.get('missing_tool_deps') and r['editable_rc'] == 0 and
                 r['retrying_lines'] == 0 and r['setup_s_total'] <= 30 for r in fixed)
    args.output.write_text(json.dumps(dict(**identity, status=('passed' if passed else 'failed') if fixed else 'diagnostic', rows=rows), indent=2) + '\n')
    return int(bool(fixed) and not passed)


if __name__ == '__main__':
    raise SystemExit(main())
