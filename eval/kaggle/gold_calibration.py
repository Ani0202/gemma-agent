"""Offline Phase 2 gold calibration; no agent or model inference is performed."""

import argparse
import shutil
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import inspect
import json
import logging
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

# Kaggle's system python autoloads a langsmith pytest plugin that the scorer docker image lacks; it breaks on repo-local requests.py shadowing.
os.environ['PYTEST_ADDOPTS'] = (os.environ.get('PYTEST_ADDOPTS', '') + ' -p no:langsmith_plugin').strip()
DATA_DIR = Path('/kaggle/input/competitions/gemma-4-developer-agent')
WORKING_DIR = Path('/kaggle/working')
WHEELHOUSE = Path('/kaggle/input/datasets/metric/gemma-4-developer-agent-wheelhouse')
CONCURRENCY = 2
ONLY_IDS = None  # all tasks (diag ids list removed after local repro, cycle 37)


def finished_results(text):
    """Parse a journal, ignoring only a torn final JSON line; last full row wins.

    Both successful verifications and errors are finished attempts. Malformed
    complete records fail loudly rather than silently removing tasks.
    """
    results = {}
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            if index == len(lines) - 1 and not line.endswith('\n'):
                break
            raise ValueError(f'Invalid results JSON at line {index + 1}') from None
        if (not isinstance(row, dict) or not isinstance(row.get('instance_id'), str)
                or not row['instance_id'] or not isinstance(row.get('repo'), str)
                or type(row.get('resolved')) is not bool
                or 'exit_code' not in row or 'error' not in row
                or (row['exit_code'] is not None and type(row['exit_code']) is not int)
                or (row['error'] is not None and not isinstance(row['error'], str))
                or type(row.get('duration_seconds')) not in (float, int)
                or not math.isfinite(row['duration_seconds']) or row['duration_seconds'] < 0):
            raise ValueError(f'Invalid result schema at line {index + 1}')
        results[row['instance_id']] = row
    return results


def pending_tasks(tasks, results):
    """Validate the current task inventory and return unfinished tasks in order."""
    inventory = {task['instance_id']: task['repo'] for task in tasks}
    if len(inventory) != len(tasks):
        raise ValueError('Duplicate task ids in tasks.jsonl')
    for task_id, row in results.items():
        if task_id not in inventory or inventory[task_id] != row['repo']:
            raise ValueError('Resume journal does not match task inventory')
    return [task for task in tasks if task['instance_id'] not in results]


def summarize(tasks, results):
    """Aggregate every input task, including failures and unfinished attempts."""
    pending = pending_tasks(tasks, results)
    if os.environ.get('GOLD_LIMIT'):  # smoke runs only: first task of each repo
        seen = set(); pending = [t for t in pending if not (t['repo'] in seen or seen.add(t['repo']))]
    repos = {}
    passing, failing = [], []
    for task in tasks:
        task_id = task['instance_id']
        counts = repos.setdefault(task['repo'], dict(total=0, finished=0, passed=0, failed=0, pending=0))
        counts['total'] += 1
        row = results.get(task_id)
        if row is None:
            counts['pending'] += 1
            continue
        counts['finished'] += 1
        if row['resolved']:
            counts['passed'] += 1
            passing.append(task_id)
        else:
            counts['failed'] += 1
            reason = row['error'] or f"verification unresolved (exit_code={row['exit_code']})"
            failing.append({'instance_id': task_id, 'reason': reason[:200]})
    passing.sort()
    return dict(total=len(tasks), finished=len(results), passed=len(passing),
                failed=len(failing), pending=len(pending), concurrency=CONCURRENCY,
                timing_note='Concurrent calibration durations are not scorer timing measurements.',
                per_repo=dict(sorted(repos.items())), passing_ids=passing,
                failing_ids=sorted(failing, key=lambda row: row['instance_id']),
                pending_ids=sorted(task['instance_id'] for task in pending))


def resume_journal(path):
    """Repair only an interrupted final append, preserving all complete records."""
    if not path.exists():
        return {}
    text = path.read_text(encoding='utf-8')
    results = finished_results(text)
    if text and not text.endswith('\n'):
        try:
            json.loads(text.splitlines()[-1])
        except json.JSONDecodeError:
            # Remove an incomplete tail before further appends. No completed row is lost.
            with path.open('r+b') as stream:
                stream.truncate(len(text[:text.rfind('\n') + 1].encode('utf-8')))
        else:
            with path.open('a', encoding='utf-8') as stream:
                stream.write('\n')
    return results


def load_inventory(data_dir):
    with (data_dir / 'tasks.jsonl').open(encoding='utf-8') as stream:
        tasks = [json.loads(line) for line in stream if line.strip()]
    pending_tasks(tasks, {})
    return tasks


def install_harness():
    """Use preinstalled packages or the same offline wheelhouse as the starter."""
    try:
        import swegemma  # noqa: F401
        return
    except ImportError:
        pass
    staged = Path('/tmp/wheelhouse')
    staged.mkdir(parents=True, exist_ok=True)
    for w in WHEELHOUSE.glob('*.whl'):
        # CPU image is Python 3.13; wheelhouse binaries are cp312, so take pure wheels only.
        if 'cutlass' in w.name.lower() or not w.name.endswith('-none-any.whl'):
            continue
        # Kaggle dataset upload strips '+' from local version tags (e.g. cu128).
        name = w.name.replace('cu128', '+cu128') if 'cu128' in w.name and '+' not in w.name else w.name
        target = staged / name
        if not target.exists():
            try:
                os.symlink(w, target)
            except OSError:
                shutil.copyfile(w, target)
    wheels = sorted(str(p) for p in staged.glob('*.whl'))
    if not wheels:
        raise RuntimeError('Harness unavailable; attach metric/gemma-4-developer-agent-wheelhouse')
    proc = subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--no-index', '--no-deps',
                           '--force-reinstall', '--disable-pip-version-check', *wheels],
                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if proc.returncode:
        # pip diagnostics only (no task data); keep the tail for debugging.
        raise RuntimeError('wheel install failed: ' + proc.stderr[-1500:].replace(str(WHEELHOUSE), '<wh>'))


def choose_sandbox():
    """Probe actual offline container startup, not merely existence of docker CLI."""
    name = f'gold-calibration-probe-{os.getpid()}'
    try:
        probe = subprocess.run(
            ['docker', 'run', '--pull=never', '--rm', '--name', name,
             '--network=none', '--memory=4g', '--cpus=2',
             '--entrypoint', 'python3', 'swebench-sandbox:latest', '-c', 'pass'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        if probe.returncode == 0:
            return 'docker'
    except (OSError, subprocess.TimeoutExpired):
        pass
    finally:
        try:
            subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            pass
    return 'subprocess'


def patch_subprocess_deps(data_dir):
    """Emulate the docker-only dependency setup for the subprocess sandbox (swegemma skips it).

    Contract (swegemma 0.2.11 container_setup): for docker, _ensure_container_site_packages
    unpacks every deduplicated (highest-version, py313-compatible) wheel from wheels_dir that is
    < 20 MB and not in skip_base_pkgs (pytest, pluggy, ... come from the image) straight into
    site-packages, no resolver; large wheels are added only if imported by the workspace; then
    sandbox/setup.py runs with --fast-path. We replicate exactly that inside the sandbox venv.
    The sandbox venv uses system_site_packages=True, so the HOST python must mirror the image
    (Dockerfile.public: pytest, pytest-timeout==2.1.0, typer, build backends; nothing else).
    """
    import tarfile
    import swegemma.harness.container_setup as cs
    import swegemma.harness.verification as vf
    import swegemma.harness.sample_verification  # load all known by-name bindings
    import swegemma.evaluate
    import swegemma.cli
    import swegemma.harness.agent_runner
    orig = cs.install_test_dependencies
    wheels_src = Path(data_dir) / 'wheels'
    if not wheels_src.is_dir():
        wheels_src = WHEELHOUSE
    setup_py = Path(data_dir) / 'sandbox' / 'setup.py'
    if not setup_py.exists():
        setup_py = next(iter(Path(data_dir).rglob('setup.py')), setup_py)  # competition sandbox/setup.py

    def install(docker, container_id, repo='', *, fast_path=True, config=None):
        if type(docker).__name__ not in {'SubprocessManager', 'SubprocessSandbox'}:
            return orig(docker, container_id, repo, fast_path=fast_path, config=config)
        venv_dir = docker.sandboxes[container_id]['venv']
        sp_dir = next(iter(sorted(venv_dir.glob('lib/python3*/site-packages'))))
        base_wheels, large_wheels, _m2p, _req = cs._inspect_wheels_dir(wheels_src)
        selected = list(base_wheels)
        if large_wheels:  # public wheels have none; fail loudly rather than silently diverge
            raise RuntimeError('large wheels present; workspace-import scan not emulated')
        tar_path = cs._build_unpacked_wheels_tar(selected, 'sp_base_local', '.swegemma_base_injected')
        with tarfile.open(tar_path) as tf:
            tf.extractall(sp_dir, filter='data')
        docker.copy_to(container_id, setup_py, '/tmp/setup.py')
        flag = '--fast-path' if fast_path else ''
        docker.exec(container_id, f'python3 /tmp/setup.py {flag} {repo}'.strip(), timeout=280)
        probe_log = os.environ.get('GOLD_PROBE_LOG')  # diagnostic: which copy of the repo package is imported
        if probe_log:
            pkg = {'Textualize/rich': 'rich', 'encode/httpx': 'httpx', 'fastapi/fastapi': 'fastapi',
                   'psf/requests': 'requests'}.get(repo, repo.split('/')[-1])
            out = docker.exec(container_id, f'cd /workspace && PYTHONSAFEPATH=1 PYTHONNOUSERSITE=1 python3 -s -c '
                              f'"import {pkg};print({pkg}.__file__)"', timeout=60)
            with open(probe_log, 'a') as fh:
                fh.write(json.dumps({'container': str(container_id), 'repo': repo, 'probe': str(out)[:500]}) + '\n')
    for name, module in list(sys.modules.items()):
        if (name == 'swegemma' or name.startswith('swegemma.')) and getattr(module, 'install_test_dependencies', None) is orig:
            module.install_test_dependencies = install
    return install


async def verify_gold(task, patch, data_dir, sandbox):
    """The only swegemma API adapter; see docs/GOLD_CALIBRATION.md assumptions.

    verify_task owns fresh sandbox staging, baseline setup, and test_patch.
    Bind explicit parameters from Evaluator resources, failing closed on an
    unknown required argument rather than guessing positional argument order.
    """
    from swegemma.config import EvalConfig
    from swegemma.evaluate import Evaluator
    from swegemma.harness.verification import verify_task

    with tempfile.TemporaryDirectory(prefix='gold-verify-', dir='/tmp') as scratch:
        config = EvalConfig(tasks_path=data_dir / 'tasks.jsonl',
                            snapshots_dir=data_dir / 'snapshots', wheels_dir=data_dir / 'wheels',
                            results_dir=Path(scratch), submission_dir=data_dir / 'sample_submission',
                            models={}, sandbox=sandbox, verification_timeout_seconds=300, verbose=False)
        evaluator = Evaluator(config)
        context = {name.lstrip('_'): value for name, value in vars(evaluator).items()}
        context.update(task=task, agent_patch=patch, config=config,
                       snapshots_dir=config.snapshots_dir, wheels_dir=config.wheels_dir,
                       timeout_seconds=300, verification_timeout_seconds=300)
        from swegemma.deduplication import resolve_task_snapshot_paths
        _paths = resolve_task_snapshot_paths(config.snapshots_dir, task.instance_id, task.repo)
        context.update(snapshot_path=_paths[0], base_snapshot_path=_paths[1], patch_path=_paths[2])
        parameters = inspect.signature(verify_task).parameters
        if not {'task', 'agent_patch'} <= parameters.keys():
            raise RuntimeError('Unsupported verify_task signature')
        kwargs = {name: context[name] for name, p in parameters.items()
                  if name in context and p.kind in (p.KEYWORD_ONLY, p.POSITIONAL_OR_KEYWORD)}
        try:
            inspect.signature(verify_task).bind(**kwargs)
        except TypeError as exc:
            sig = inspect.signature(verify_task)
            req = [n for n, p in sig.parameters.items() if p.default is p.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)]
            import swegemma.evaluate as _ev, swegemma.harness.verification as _vf, re as _re
            _src = (inspect.getsource(_ev) + '\n' + inspect.getsource(_vf)).splitlines()
            _hits = [l.strip() for l in _src if _re.search(r'snapshot', l)]
            _d1 = ' || '.join(_hits)[:3000]
            import swegemma.sandbox as _sb
            _d2 = ','.join(n for n in dir(_sb) if 'Manager' in n or 'Sandbox' in n)
            raise RuntimeError('bind failed; SRC=' + _d1 + '; SB=' + _d2 + '; sig=' + str(sig)[:300] + '; required=' + ','.join(req) + '; ctx=' + ','.join(sorted(context))[:300]) from None
        result = verify_task(**kwargs)
        return await result if inspect.isawaitable(result) else result


def worker(args):
    """No stdout/stderr from this process is exposed by the coordinator."""
    logging.disable(logging.CRITICAL)
    start = time.monotonic()
    raw = next(t for t in load_inventory(args.data_dir) if t['instance_id'] == args.worker)
    row = dict(instance_id=raw['instance_id'], repo=raw['repo'], resolved=False,
               exit_code=None, duration_seconds=0.0, error=None, sandbox=args.sandbox)
    try:
        if args.sandbox == 'subprocess':
            patch_subprocess_deps(args.data_dir)
        from swegemma.models import load_tasks
        task = next(t for t in load_tasks(args.data_dir / 'tasks.jsonl')
                    if t.instance_id == args.worker)
        patch = raw.get('patch')
        if os.environ.get('GOLD_NULL_PATCH'):  # control: no source change; tests should fail
            patch = ('diff --git a/NULL_CONTROL.txt b/NULL_CONTROL.txt\nnew file mode 100644\n'
                     '--- /dev/null\n+++ b/NULL_CONTROL.txt\n@@ -0,0 +1 @@\n+null\n')
        if not isinstance(patch, str) or not patch.strip():
            row['error'] = 'Missing or empty gold patch'
        else:
            result = asyncio.run(verify_gold(task, patch, args.data_dir, args.sandbox))
            # Assumed result is a mapping or TaskResult-like object, never a bare bool.
            get = result.get if isinstance(result, dict) else lambda k, d=None: getattr(result, k, d)
            resolved = get('resolved')
            exit_code = get('test_exit_code', get('exit_code'))
            if type(resolved) is not bool or (exit_code is not None and type(exit_code) is not int):
                # Shape diagnostics only: type and field names, never values.
                names = sorted(result) if isinstance(result, dict) else [n for n in dir(result) if not n.startswith('_')]
                row['shape'] = f'{type(result).__module__}.{type(result).__name__}: {",".join(map(str, names))[:400]}'
                raise TypeError('Unsupported verification result')
            row.update(resolved=resolved, exit_code=exit_code)
            if not resolved:
                # Harness exception/error text can embed patches or task source. Never copy it.
                row['error'] = ('Harness verification error' if get('error') else
                                f'Phase 2 unresolved (exit_code={exit_code}; includes JUnit validation)')
    except Exception as exc:
        row['error'] = f'Verification/setup exception ({type(exc).__name__})'
        if str(exc).startswith('bind failed'):
            row['shape'] = str(exc)[:3600]  # API signature text only, no task data
        import traceback
        # Location only (file:line:function), never messages or values.
        row['where'] = ' <- '.join(f'{Path(f.filename).name}:{f.lineno}:{f.name}'
                                   for f in reversed(traceback.extract_tb(exc.__traceback__)[-4:]))
    row['duration_seconds'] = round(time.monotonic() - start, 3)
    args.result.write_text(json.dumps(row) + '\n', encoding='utf-8')


def run_one(task, data_dir, sandbox):
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='gold-worker-', dir='/tmp') as scratch:
        output = Path(scratch) / 'result.json'
        command = [sys.executable, str(Path(__file__).resolve()), '--worker', task['instance_id'],
                   '--data-dir', str(data_dir), '--sandbox', sandbox, '--result', str(output)]
        try:
            proc = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  timeout=3600)
            if proc.returncode == 0 and output.exists():
                row = next(iter(finished_results(output.read_text(encoding='utf-8')).values()))
                if row['instance_id'] != task['instance_id'] or row['repo'] != task['repo']:
                    raise ValueError('Worker result identity mismatch')
                return row
            error = f'Worker exited ({proc.returncode})'
        except subprocess.TimeoutExpired:
            error = 'Worker timed out after 3600s (setup and verification)'
        except Exception as exc:
            error = f'Worker failure ({type(exc).__name__})'
    return dict(instance_id=task['instance_id'], repo=task['repo'], resolved=False,
                exit_code=None, duration_seconds=round(time.monotonic() - start, 3),
                error=error, sandbox=sandbox)


def main():
    # Kaggle-only cleanup belongs at execution time, never on library import.
    if Path('/kaggle/working').is_dir():
        subprocess.run([sys.executable, '-m', 'pip', 'uninstall', '-y', 'langsmith'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=DATA_DIR)
    parser.add_argument('--working-dir', type=Path, default=WORKING_DIR)
    parser.add_argument('--worker', help=argparse.SUPPRESS)
    parser.add_argument('--result', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--sandbox', choices=('docker', 'subprocess'), help=argparse.SUPPRESS)
    args = parser.parse_args()
    os.environ.update(PIP_NO_INDEX='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                      OTEL_SDK_DISABLED='true', LITELLM_TELEMETRY='False', TMPDIR='/tmp')
    if args.worker:
        worker(args)
        return
    tasks = load_inventory(args.data_dir)
    ids = ONLY_IDS or ([l.strip() for l in open(os.environ['GOLD_IDS_FILE']) if l.strip()]
                       if os.environ.get('GOLD_IDS_FILE') else None)
    if ids:
        tasks = [t for t in tasks if t['instance_id'] in set(ids)]
    args.working_dir.mkdir(parents=True, exist_ok=True)
    journal = args.working_dir / 'gold_results.jsonl'
    results = resume_journal(journal)
    pending = pending_tasks(tasks, results)
    if os.environ.get('GOLD_LIMIT'):  # smoke runs only: first task of each repo
        seen = set(); pending = [t for t in pending if not (t['repo'] in seen or seen.add(t['repo']))]
    if pending:
        install_harness()
        sandbox = choose_sandbox()
        print(f'Gold calibration: total={len(tasks)}, resumed={len(results)}, '
              f'sandbox={sandbox}, concurrency={CONCURRENCY}', flush=True)
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool, journal.open('a', encoding='utf-8') as stream:
            futures = [pool.submit(run_one, task, args.data_dir, sandbox) for task in pending]
            for future in as_completed(futures):
                row = future.result()
                stream.write(json.dumps(row, allow_nan=False) + '\n')
                stream.flush()
                os.fsync(stream.fileno())
                results[row['instance_id']] = row
                print(f"Finished {len(results)}/{len(tasks)}: {row['instance_id']} "
                      f"resolved={row['resolved']} exit_code={row['exit_code']} err={row.get('error')} where={row.get('where')} shape={row.get('shape')}", flush=True)
    summary = summarize(tasks, results)
    encoded = json.dumps(summary, indent=2, sort_keys=True) + '\n'
    output = args.working_dir / 'gold_summary.json'
    temporary = output.with_suffix('.tmp')
    temporary.write_text(encoded, encoding='utf-8')
    temporary.replace(output)
    print(encoded, flush=True)


if __name__ == '__main__':
    main()
