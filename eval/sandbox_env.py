"""Shared local scorer environment; no installed harness source is modified.

The executor hook is after swegemma's path translation, and covers exec_async,
run_command, setup, and verification as well as agent commands.
"""
from contextvars import ContextVar
import base64
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import time

from eval import proctree

command_metrics = ContextVar('command_metrics', default=None)
gold_artifact_dir = ContextVar('gold_artifact_dir', default=None)

BWRAP_TEMPLATE = [
    'bwrap', '--die-with-parent', '--unshare-net', '--unshare-pid',
    '--ro-bind', '/', '/', '--dev', '/dev', '--proc', '/proc',
    '--tmpfs', '<each hidden path>', '--tmpfs', '/tmp',
    '--dir', '<each hidden path under /tmp, if any>',
    '--bind', '<sandbox_root>', '<sandbox_root>',
    '--ro-bind', '<each ro path>', '<same>',
    '--chdir', '<workspace>', '/bin/bash', '-c', '<translated_cmd>',
]


def bwrap_argv(command, workspace, hidden_paths, ro_paths):
    workspace = Path(workspace).resolve()
    root = workspace.parent
    argv = BWRAP_TEMPLATE[:11]
    # Mask parents first so nested masks don't get covered by their parents.
    for path in sorted({str(Path(p).absolute()) for p in hidden_paths},
                       key=lambda p: (len(Path(p).parts), p)):
        argv += ['--tmpfs', path]
    argv += ['--tmpfs', '/tmp']
    # A final /tmp mask removes nested hidden mountpoints. Recreate their empty
    # directories so temporary inventories can be probed with ls as well.
    for path in sorted({str(Path(p).absolute()) for p in hidden_paths}):
        if path != '/tmp' and Path(path).is_relative_to('/tmp'):
            argv += ['--dir', path]
    argv += ['--bind', str(root), str(root)]
    # Bind each asset at its resolved path and, when reached through a symlink
    # (uv's cpython-3.13 -> cpython-3.13.18 alias under a masked $HOME), at the
    # unresolved path too, so venv interpreter symlinks don't dangle in the sandbox.
    binds = set()
    for p in ro_paths:
        src = str(Path(p).resolve())
        binds |= {(src, src), (src, str(Path(p).absolute()))}
    for path, dest in sorted(binds, key=lambda b: (len(Path(b[1]).parts), b)):
        # Only explicit runtime assets may be re-exposed, never inventory/artifacts.
        if ({'tasks.jsonl', 'splits', 'runs', 'results'} & (set(Path(path).parts) | set(Path(dest).parts))
                or (Path(path).is_dir() and (Path(path) / 'tasks.jsonl').exists())):
            raise ValueError('Forbidden read-only exposure')
        argv += ['--ro-bind', path, dest]
    argv += ['--chdir', str(workspace), *command]
    return argv


def runtime_ro_paths(workspace, ro_paths):
    root = Path(workspace).resolve().parent
    cfg = (root / 'venv/pyvenv.cfg').read_text()
    home = next(line.split('=', 1)[1].strip() for line in cfg.splitlines()
                if line.startswith('home ='))
    prefix = Path(home).resolve().parent
    if prefix != Path(sys.base_prefix).resolve():
        raise ValueError('Sandbox python prefix differs from the scorer interpreter')
    # Keep the unresolved alias too; bwrap_argv binds the resolved target there.
    paths = {prefix, Path(home).absolute().parent, *(Path(p).resolve() for p in ro_paths)}
    def wheel_target(path):
        target = path.resolve()
        # Agent-created symlinks must not turn an arbitrary directory into a
        # new read-only exposure. Only wheel files or trusted wheelhouse subdirs
        # can be reached through symlinks; a file mount cannot expose siblings.
        if not (target.is_file() and target.suffix == '.whl') and not any(
                target.is_relative_to(Path(p).resolve()) for p in ro_paths):
            raise ValueError('Untrusted wheel symlink target')
        paths.add(target)

    wheels = root / 'wheels'
    if wheels.is_symlink():
        wheel_target(wheels)
    for path in wheels.rglob('*'):
        if path.is_symlink():
            wheel_target(path)
    return paths


def execute_limited(command, cwd, env, timeout=300, *, shell=None,
                    max_output_chars=10 * 1024 * 1024):
    """Installed executor contract, with host process-tree limits and cleanup."""
    from adk_eval_core.errors import EvalCoreError
    from adk_eval_core.sandbox.base import ExecutionResult

    start = time.perf_counter()
    try:
        # Fresh interpreters give threaded GOLD_CONCURRENCY workers separate
        # subreaper/adoption domains, without forking a multithreaded process.
        worker = subprocess.run(
            [sys.executable, '-c', proctree.supervisor_source() + '\nsupervisor_main()\n'],
            input=json.dumps(dict(command=command, cwd=str(cwd), env=dict(env),
                                 timeout=timeout, shell=shell,
                                 max_output_chars=max_output_chars)),
            capture_output=True, text=True)
        if worker.returncode:
            raise RuntimeError('Sandbox supervisor failed: ' + worker.stderr)
        result = json.loads(worker.stdout)
        observed = result.pop('metrics')
        metrics = command_metrics.get()
        if metrics is not None:
            metrics['peak_rss_bytes'] = max(metrics.get('peak_rss_bytes', 0),
                                            observed.get('peak_rss_bytes', 0))
            for key in ('mem_kills', 'orphan_kills'):
                metrics[key] = metrics.get(key, 0) + observed.get(key, 0)
        result['duration_seconds'] = round(time.perf_counter() - start, 3)
        return ExecutionResult(**result)
    except (RuntimeError, OSError, ValueError, EvalCoreError) as exc:
        return ExecutionResult(status='error', stdout='', stderr=str(exc), exit_code=-1,
                               duration_seconds=round(time.perf_counter() - start, 3))


def apply_isolation(hidden_paths, ro_paths):
    """Wrap the module executor, retaining the installed manager's translation/env.

    Empty hidden_paths disables bwrap (explicit opt-out), but retains timeout
    accounting. Repeated setup replaces this hook rather than stacking it.
    """
    import swegemma.sandbox.subprocess as sb
    hidden_paths, ro_paths = tuple(hidden_paths), tuple(ro_paths)
    original = getattr(sb.execute_subprocess_command, '_unwrapped', sb.execute_subprocess_command)

    def execute(command, cwd, env, **kwargs):
        if ro_paths:
            command = [*command[:2], re.sub(r'(?<![\w.-])/wheels(?![\w.-])',
                                           str(Path(ro_paths[0]).resolve()), command[2])]
        if hidden_paths:
            if not isinstance(command, list) or command[:2] != ['/bin/bash', '-c']:
                raise RuntimeError('Unsupported harness subprocess command')
            # The harness's fallback wheel search doesn't include custom data dirs.
            command = bwrap_argv(command, cwd, hidden_paths, runtime_ro_paths(cwd, ro_paths))
        result = execute_limited(command=command, cwd=cwd, env=env, **kwargs)
        metrics = command_metrics.get()
        if metrics is not None and (result.status == 'timeout' or result.exit_code == 124):
            metrics['cmd_timeouts'] = metrics.get('cmd_timeouts', 0) + 1
        return result

    execute._unwrapped = original
    sb.execute_subprocess_command = execute
    return BWRAP_TEMPLATE.copy()


def probe_isolation(manager, inventory_path, data_dir, *, empty_data=True):
    """Fail closed on visibility, image imports, or broken workspace write-through."""
    sid = manager.start()
    try:
        # Encode host paths to bypass swegemma's /tmp path translation in probes
        # whose inventory is itself under /tmp. A failed ls must fail the probe.
        encoded = lambda p: shlex.quote(base64.b64encode(str(p).encode()).decode())
        empty_check = 'contents=$(ls -A "$data") && test -z "$contents" && ' if empty_data else ''
        cmd = (f'inventory=$(printf %s {encoded(inventory_path)} | base64 -d); '
               f'data=$(printf %s {encoded(data_dir)} | base64 -d); '
               'test ! -e "$inventory" && ' + empty_check +
               "python3 -c 'import pytest' && "
               'echo probe > /workspace/x && echo probe > /tmp/y')
        result = manager.exec(sid, cmd, timeout=60)
        workspace = manager.sandboxes[sid]['workspace']
        if result.exit_code != 0 or not (workspace / 'x').is_file():
            raise RuntimeError('bubblewrap startup probe failed: ' + result.stderr[:500])
    finally:
        manager.cleanup_all()


def isolate_gold_tempfiles():
    """Route verification's temporary patch serialization to the caller's out dir."""
    import tempfile
    import swegemma.harness.verification as vf
    if getattr(vf.tempfile, '_gold_redirect', False):
        return

    class Tempfiles:
        _gold_redirect = True

        def __getattr__(self, name):
            return getattr(tempfile, name)

        def NamedTemporaryFile(self, *args, **kwargs):
            if gold_artifact_dir.get() is not None:
                kwargs['dir'] = gold_artifact_dir.get()
            return tempfile.NamedTemporaryFile(*args, **kwargs)

    vf.tempfile = Tempfiles()


def setup_scorer_env(data_dir, *, out_dir=None, repo_root=None, allow_unsandboxed=False):
    """Common subprocess scorer setup for evaluation and gold calibration."""
    from swegemma.sandbox import SubprocessManager
    from swegemma.harness.container_setup import resolve_wheels_dir
    from types import SimpleNamespace
    data_dir = Path(data_dir).resolve()
    repo_root = Path(repo_root or Path(__file__).resolve().parents[1]).resolve()
    out_dir = Path(out_dir or data_dir.parent / 'gold-output').resolve()
    isolate_host_packages()
    patched = patch_subprocess_deps(data_dir)
    isolate_gold_tempfiles()
    hidden = [Path.home(), repo_root, data_dir, out_dir, Path('/home/ubuntu/work/gemma-wt')]
    wheels = resolve_wheels_dir(SimpleNamespace(wheels_dir=data_dir / 'wheels',
                                              tasks_path=data_dir / 'tasks.jsonl',
                                              snapshots_dir=data_dir / 'snapshots'))
    ro = [wheels.resolve()] if wheels else []
    try:
        if not shutil.which('bwrap'):
            raise RuntimeError('bubblewrap is not installed')
        # First check the empty inventory mask before mounting its wheelhouse
        # child. Then repeat with the complete runtime mounts: wheels may be
        # visible under data_dir, but the inventory must remain inaccessible.
        template = apply_isolation(hidden, [])
        probe_isolation(SubprocessManager(), data_dir / 'tasks.jsonl', data_dir)
        apply_isolation(hidden, ro)
        probe_isolation(SubprocessManager(), data_dir / 'tasks.jsonl', data_dir, empty_data=False)
        mode = 'bwrap'
    except Exception:
        # Never leave an unusable boundary or silently downgrade its protection.
        apply_isolation([], ro)
        if not allow_unsandboxed:
            raise
        mode, template = 'none', None
        import logging
        logging.warning('bubblewrap unavailable/probe failed; explicitly allowed unsandboxed run',
                        exc_info=True)
    return dict(sandbox=mode, bwrap_argv_template=template, patched=patched,
                wheels_dir=wheels)


def isolate_host_packages():
    """Keep pyimg system packages; remove swegemma's extra harness-venv .pth leak."""
    from swegemma.sandbox import SubprocessManager
    original = SubprocessManager.start
    if getattr(original, '_image_only', False):
        return

    def start(self):
        base = getattr(self, 'base_dir', None)
        if gold_artifact_dir.get() is not None:
            self.base_dir = Path(gold_artifact_dir.get())
        try:
            sid = original(self)
        finally:
            self.base_dir = base
        for pth in self.sandboxes[sid]['venv'].glob('lib/python*/site-packages/_host_env.pth'):
            pth.unlink()
        return sid
    start._image_only = True
    SubprocessManager.start = start


def setup_script_path(data_dir):
    """The dependency setup script the subprocess installer copies and executes."""
    setup_py = Path(data_dir) / 'sandbox' / 'setup.py'
    if not setup_py.exists():
        setup_py = next(iter(sorted(Path(data_dir).rglob('setup.py'))), setup_py)  # competition sandbox/setup.py
    return setup_py


def setup_script_identity(data_dir):
    """Resolved path + content hash of the setup script (part of resume identity)."""
    import hashlib
    path = setup_script_path(data_dir)
    return dict(path=str(path.resolve()),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None)


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
    orig = getattr(cs.install_test_dependencies, '_scorer_original', cs.install_test_dependencies)
    previous = cs.install_test_dependencies
    wheels_src = Path(data_dir) / 'wheels'
    if not wheels_src.is_dir():
        wheels_src = Path('/kaggle/input/datasets/metric/gemma-4-developer-agent-wheelhouse')
    setup_py = setup_script_path(data_dir)

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
    install._scorer_original = orig
    for name, module in list(sys.modules.items()):
        if ((name == 'swegemma' or name.startswith('swegemma.'))
                and getattr(module, 'install_test_dependencies', None) in (orig, previous)):
            module.install_test_dependencies = install
    return install

