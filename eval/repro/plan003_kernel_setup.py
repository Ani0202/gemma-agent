"""Offline acceptance for the timing injector, using two frozen dev snapshots.

Run with the harness interpreter and its pytest/image packages available:
  python eval/repro/plan003_kernel_setup.py --data-dir /path/to/data/raw \
      --wheels-dir /path/to/complete/wheelhouse --output /tmp/setup-acceptance.json
The wheelhouse must include pip and pytest-timeout==2.1.0 as well as public wheels.
No downloads, task text, gold patches, tests, or holdout inventory are used.
"""
import argparse
from contextvars import ContextVar
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--wheels-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--inside-bwrap', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.inside_bwrap:
        command = ['bwrap', '--dev-bind', '/', '/', '--unshare-net', sys.executable,
                   str(Path(__file__).resolve()), *sys.argv[1:], '--inside-bwrap']
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            # Bubblewrap startup can fail before the child creates an artifact.
            if not args.output.exists():
                args.output.write_text(json.dumps(dict(status='blocked', rc=result.returncode,
                    stderr=result.stderr[-2048:], rows=[]), indent=2) + '\n')
        print(result.stdout, end='')
        print(result.stderr, end='', file=sys.stderr)
        return result.returncode
    spec = importlib.util.spec_from_file_location('timing', Path(__file__).parents[1] / 'kaggle/agent_timing.py')
    timing = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(timing)
    from swegemma.sandbox import SubprocessManager
    import swegemma.sandbox.subprocess as sb
    from swegemma.harness.container_setup import extract_snapshot
    state = ContextVar('acceptance')
    rows = []
    failure = None
    try:
        with tempfile.TemporaryDirectory(prefix='kernel-setup-') as temp:
            root = Path(temp)
            (root / 'wheels').symlink_to(args.wheels_dir.resolve())
            (root / 'sandbox').symlink_to((args.data_dir / 'sandbox').resolve())
            install = timing.patch_subprocess_deps(root, state)
            for iid, repo in [('rich_3006', 'Textualize/rich'), ('fastapi_14986', 'fastapi/fastapi')]:
                current = dict(instance_id=iid, started=time.perf_counter(), setup_calls=[], setup_failed=False)
                rows.append(current)
                state.set(current)
                manager = SubprocessManager(system_site_packages=False, base_dir=root)
                # Reproduce Kaggle's no-pip venv without invoking failing ensurepip twice.
                create = sb.venv.create
                def without_pip(*a, **kw):
                    kw['with_pip'] = False
                    return create(*a, **kw)
                try:
                    with patch.object(sb.venv, 'create', without_pip):
                        sid = timing.setup_step(current, 'venv', manager.start)
                    extract_snapshot(manager, sid, args.data_dir / 'snapshots' / (iid + '.tgz'))
                    sp = next(manager.sandboxes[sid]['venv'].glob('lib/python*/site-packages'))
                    log = root / (iid + '-pip.jsonl')
                    # setup.py discards pip's output. Observe subprocess results in the child
                    # to assert the FIRST editable attempt succeeds and scan ALL output for retries.
                    observer = '''import subprocess, json
_original_run = subprocess.run
def _run(*a, **kw):
    result = _original_run(*a, **kw)
    command = a[0] if a else kw.get('args', [])
    if isinstance(command, list) and 'pip' in command and '-e' in command:
        text = str(result.stdout) + str(result.stderr)
        with open(LOG, 'a') as stream:
            stream.write(json.dumps(dict(rc=result.returncode, retry='Retrying' in text)) + '\\n')
    return result
subprocess.run = _run
'''.replace('LOG', repr(str(log)))
                    (sp / 'sitecustomize.py').write_text(observer)
                    install_started = time.perf_counter()
                    install(manager, sid, repo)
                    duration = time.perf_counter()-install_started + current['setup_calls'][0]['duration_s']
                    calls = [json.loads(line) for line in log.read_text().splitlines()]
                    assert len(calls) == 1 and calls[0] == dict(rc=0, retry=False), calls
                    assert not current['setup_failed'], current['setup_calls']
                    assert current['setup_calls'][-1]['rc'] == 0
                    current['total_setup_s'] = duration
                    assert duration < 30, duration
                finally:
                    manager.cleanup_all()
    except Exception as exc:
        failure = type(exc).__name__ + ': ' + str(exc)[:2048]
    finally:
        for row in rows:
            row.pop('started', None)
        args.output.write_text(json.dumps(dict(status='failed' if failure else 'passed',
            error=failure, rows=rows), indent=2) + '\n')
    return int(failure is not None)


if __name__ == '__main__':
    raise SystemExit(main())
