"""Self-contained Kaggle timing script; starter notebook cells 2/8/10, swegemma 0.2.11.
Trace/patch classification copied from codex/eval-runner; no repository imports.
Build using timing_push.sh. Raw task artifacts stay in /kaggle/working/runs.
"""
import asyncio
import base64
from collections import Counter
import dataclasses
from datetime import datetime, timezone
import glob
import hashlib
import importlib
import io
import json
import logging
import os
from pathlib import Path
import re
import shutil
import shlex
import signal
import socket
import subprocess
import sys
import tarfile
import threading
import time

BUNDLE_B64 = ""  # embedded by timing_push.sh
TASK_IDS = []
# {wheel filename: [sha256, base64]}: public wheels the scorer image pip-installs online but the offline
# Kaggle wheelhouse lacks (pytest-timeout==2.1.0, Dockerfile.public line 9). Embedded by timing_push.sh.
EXTRA_WHEELS = {}
SETUP_ONLY = False
SKIP_VERIFICATION = True
SETUP_FIX = 1
GIT_SHA = ""
KERNEL_BUDGET_SECONDS = 3 * 3600
P1_DEADLINE_SECONDS = 180
STOCK_PROBE = True  # P1 (plan 006 addendum): time the stock subprocess setup per task
# Plan 007 (codex review 063014 item 4): should_stop reserves sandbox setup passes explicitly, and a
# prior chunk's (smoke) max per-task total seeds observed_max because each kernel restarts `totals`.
SETUP_PASS_SECONDS = 240  # per sandbox dependency-setup pass; 1 pass (agent) + 2 (Container B) with verification
OBSERVED_MAX_SEED_SECONDS = 0.0
DATA = Path('/kaggle/input/competitions/gemma-4-developer-agent')
WORK = Path('/kaggle/working')
BUNDLE = WORK / 'bundle'
WHEELHOUSE = Path('/kaggle/input/datasets/metric/gemma-4-developer-agent-wheelhouse')

def install():
    print('python', sys.version.split()[0], 'executable', sys.executable, flush=True)
    env = dict(TRANSFORMERS_NO_TF='1', TRANSFORMERS_NO_FLAX='1', TRANSFORMERS_OFFLINE='1',
               VLLM_NO_USAGE_STATS='1', VLLM_WORKER_MULTIPROC_METHOD='spawn',
               VLLM_ENGINE_READY_TIMEOUT_S='1200', VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS='1',
               NCCL_DEBUG='WARN', LITELLM_LOCAL_MODEL_COST_MAP='True', LITELLM_TELEMETRY='False',
               LITELLM_LOG='WARNING', PYTORCH_CUDA_ALLOC_CONF='expandable_segments:True',
               OTEL_SDK_DISABLED='true', OTEL_PYTHON_DISABLED='true')
    os.environ.update(env)
    for key in ('OPENAI_API_KEY', 'LOCAL_API_KEY'):
        os.environ.setdefault(key, 'EMPTY')
    for pattern in ('/usr/local/lib/python*/dist-packages/*cutlass*.pth',
                    '/usr/local/lib/python*/site-packages/*cutlass*.pth'):
        for pth in glob.glob(pattern):
            try:
                os.unlink(pth)
            except OSError:
                pass
    staged = Path('/tmp/wheelhouse')
    staged.mkdir(exist_ok=True)
    for w in WHEELHOUSE.glob('*.whl'):
        gpu_wheel = w.name.lower().startswith(('vllm-', 'torch-', 'triton-', 'nvidia_'))
        if 'cutlass' in w.name.lower() or (os.environ.get('SETUP_ONLY') == '1' and gpu_wheel):
            continue
        name = w.name.replace('cu128', '+cu128') if 'cu128' in w.name and '+' not in w.name else w.name
        target = staged / name
        if not target.exists():
            try:
                target.symlink_to(w)
            except OSError:
                shutil.copyfile(w, target)
    wheels = sorted(map(str, staged.glob('*.whl')))
    if not wheels:
        raise RuntimeError('No wheelhouse wheels')
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--no-deps',
                    '--no-index', '--force-reinstall', *wheels], check=True)
    importlib.invalidate_caches()
    os.environ['PYTEST_ADDOPTS'] = (os.environ.get('PYTEST_ADDOPTS', '') + ' -p no:langsmith_plugin').strip()
    result = subprocess.run([sys.executable, '-m', 'pip', 'uninstall', '-y', 'langsmith'], capture_output=True)
    print('langsmith uninstall rc=', result.returncode, flush=True)
    for name in ('LiteLLM', 'LiteLLM Router', 'LiteLLM Proxy', 'litellm', 'httpx', 'httpcore',
                 'openai', 'urllib3', 'opentelemetry', 'opentelemetry.context'):
        lg = logging.getLogger(name); lg.setLevel(logging.WARNING)
        if 'litellm' in name.lower():
            lg.propagate = False
            lg.handlers.clear()

def extra_wheels():
    """Write the embedded wheels (sha256-checked) to a kernel-local dir and return it."""
    target = WORK / 'extra_wheels'
    target.mkdir(parents=True, exist_ok=True)
    for name, (digest, payload) in EXTRA_WHEELS.items():
        data = base64.b64decode(payload)
        if hashlib.sha256(data).hexdigest() != digest or '/' in name or name.startswith('.'):
            raise RuntimeError('Embedded wheel failed verification: ' + name)
        (target / name).write_bytes(data)
    return target


def pytest_timeout_wheels(wheels):
    """Wheelhouse pytest-timeout 2.1.0 first, then the embedded official wheel."""
    return [*sorted(Path(wheels).glob('pytest_timeout-2.1.0-*.whl')),
            *sorted(extra_wheels().glob('pytest_timeout-2.1.0-*.whl'))]


def missing_tool_closure(wheels, tags=None, runtime=True):
    """Mirror the sandbox tool_deps walk: compatible_wheels (wheelhouse, then embedded), then runtime copy.

    tags default to the kernel interpreter's, which is the sandbox venv's interpreter on Kaggle.
    """
    from packaging.markers import default_environment
    from packaging.requirements import Requirement
    from packaging.tags import sys_tags
    from packaging.utils import canonicalize_name, parse_wheel_filename
    tags = [str(t) for t in sys_tags()] if tags is None else tags
    extra = extra_wheels()
    selected = compatible_wheels(wheels, tags)
    roots = [wheel_metadata(selected[canonicalize_name(n)]) for n in SCORER_TOOLS
             if n not in ('pip', 'pytest-timeout') and canonicalize_name(n) in selected]
    timeout = [p for p in pytest_timeout_wheels(wheels)
               if any(str(t) in tags for t in parse_wheel_filename(p.name)[3])]
    roots.extend(wheel_metadata(p) for p in timeout[:1])
    env, seen, missing, queue = dict(default_environment(), extra=''), set(), [], list(roots)
    while queue:
        metadata = queue.pop()
        key = (canonicalize_name(metadata['Name']), metadata['Version'])
        if key in seen:
            continue
        seen.add(key)
        for raw in metadata.get_all('Requires-Dist', []):
            req = Requirement(raw)
            if req.marker and not req.marker.evaluate(env):
                continue
            name = canonicalize_name(req.name)
            candidate = compatible_wheels(wheels, tags, req).get(name) or compatible_wheels(extra, tags, req).get(name)
            if candidate:
                queue.append(wheel_metadata(candidate))
                continue
            found = runtime_copyable(name) if runtime else None
            if found is not None and found[0].version in req.specifier:
                queue.append(found[0].metadata)
            elif name not in missing:
                missing.append(name)
    return missing


def check_tool_sources(wheels):
    """Before vLLM starts: every Dockerfile.public line-9 tool needs an offline wheel (or pip fallback)."""
    from packaging.utils import canonicalize_name, parse_wheel_filename
    names = set()
    for w in Path(wheels).glob('*.whl'):
        try:
            names.add(canonicalize_name(parse_wheel_filename(w.name)[0]))
        except Exception:
            continue
    missing = [n for n in SCORER_TOOLS if n not in ('pip', 'pytest-timeout') and canonicalize_name(n) not in names]
    if not pytest_timeout_wheels(wheels):
        missing.append('pytest-timeout==2.1.0')
    if fallback_wheel(wheels, 'pip') is None and runtime_copyable('pip') is None:  # same sources as bootstrap_pip
        missing.append('pip')
    missing.extend(missing_tool_closure(wheels))
    if missing:
        raise RuntimeError('Offline scorer tool sources missing: ' + ', '.join(missing))
    return sorted(names)


SCORER_TOOLS = ('pip', 'pdm-backend', 'setuptools', 'wheel', 'poetry-core',
                'hatchling', 'flit-core', 'editables', 'pytest', 'pytest-timeout', 'typer')
BASE_SKIP = {'pytest', 'pytest-timeout', 'pytest-asyncio', 'pytest-httpbin',
             'pytest-xdist', 'pluggy', 'pip', 'setuptools', 'wheel'}


def setup_command(repo, fast_path=True):
    return ('python3 /tmp/setup_observer.py /tmp/setup.py ' +
            ('--fast-path ' if fast_path else '') + shlex.quote(repo))


def compatible_wheels(wheels, tags, requirement=None):
    """Highest version per distribution, with sandbox PEP 425 tags (never host tags)."""
    from packaging.utils import canonicalize_name, parse_wheel_filename
    rank = {tag: i for i, tag in enumerate(tags)}
    selected = {}
    for path in sorted(Path(wheels).glob('*.whl')):
        name, version, build, wheel_tags = parse_wheel_filename(path.name)
        if requirement is not None and (name != canonicalize_name(requirement.name) or version not in requirement.specifier):
            continue
        matches = [rank[str(tag)] for tag in wheel_tags if str(tag) in rank]
        if not matches:
            continue
        score = (version, -min(matches), build)
        if name not in selected or score > selected[name][0]:
            selected[name] = (score, path)
    return {name: item[1] for name, item in selected.items()}


def setup_artifact(current, payload):
    """Full diagnostics live outside the journal, with only a task ID in the filename."""
    iid = current.get('instance_id')
    if iid is None or not (payload.get('stdout') or payload.get('stderr')):
        return
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', iid):
        raise ValueError('Unsafe task ID')
    path = WORK / 'setup_artifacts' / str(current.get('setup_fix', SETUP_FIX)) / (iid + '.jsonl')
    path.parent.mkdir(parents=True, exist_ok=True)
    if 'setup_output_artifact' not in current:
        path.write_text('')
    with path.open('a') as stream:
        stream.write(json.dumps(payload) + '\n')
    current['setup_output_artifact'] = str(path)


def base_cache_key(wheels, harness_version):
    identity = (str(harness_version), sorted((p.name, p.stat().st_size) for p in wheels))
    return 'timing_' + hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:24]


def inject_base(cs, wheels, destination, current):
    from importlib.metadata import version
    harness_version = version('swegemma')
    row = current['setup_calls'][-1]
    row.update(selected_wheels=sorted(p.name for p in wheels), harness_version=harness_version,
               cache_key=base_cache_key(wheels, harness_version))
    archive = cs._build_unpacked_wheels_tar(wheels, row['cache_key'], '.swegemma_base_injected')
    with tarfile.open(archive) as tf:
        members = tf.getmembers()
        row['tar_member_count'] = len(members)
        payload = [m for m in members if m.isfile() and
                   Path(m.name).name not in ('', '.swegemma_base_injected')]
        if wheels and not payload:
            raise RuntimeError('Selected wheels but base tar contains only marker/empty entries')
        tf.extractall(destination, filter='data')


def record_distributions(docker, container_id, repo, row):
    # Query the same interpreter and metadata selection pip uses, never host metadata.
    package = repo.rsplit('/', 1)[-1].lower()
    probe = """import json
from importlib.metadata import distribution, PackageNotFoundError
names = NAMES
result = {}
for name in names:
    try:
        d = distribution(name)
        result[name] = dict(location=str(d.locate_file('')), version=d.version,
                            metadata_location=str(d._path), record_exists=d.read_text('RECORD') is not None)
    except PackageNotFoundError:
        result[name] = dict(location=None, version=None, metadata_location=None, record_exists=False)
print(json.dumps(result))
""".replace('NAMES', repr([package]))
    # Diagnostic only: a probe problem must never change the harness path.
    try:
        result = docker.exec(container_id, 'python3 -c ' + shlex.quote(probe), timeout=30)
        row['dist_probe_rc'] = result.exit_code
        if result.exit_code != 0:
            row['dist_probe_error'] = 'rc'
            return
        row['distributions'] = json.loads(result.stdout)
    except Exception as exc:
        row['dist_probe_error'] = type(exc).__name__


def setup_step(current, name, action, *, fatal=True):
    """Time setup steps and retain bounded output plus retry counts."""
    start = time.perf_counter()
    row = dict(step=name, start_offset_s=round(start-current['started'], 6),
               duration_s=0.0, rc=None, stdout='', stderr='', retrying_lines=0)
    current['setup_calls'].append(row)
    try:
        result = action()
        row['rc'] = getattr(result, 'exit_code', getattr(result, 'returncode', 0))
        setup_artifact(current, dict(step=name, stdout=getattr(result, 'stdout', '') or '',
                                     stderr=getattr(result, 'stderr', '') or ''))
        for field in ('stdout', 'stderr'):
            value = getattr(result, field, '') or ''
            row['retrying_lines'] += sum('Retrying' in line for line in value.splitlines())
            row[field] = value.encode('utf-8', errors='replace')[-2048:].decode('utf-8', errors='ignore')
        return result
    except Exception as exc:
        row.update(rc=-1, stderr=type(exc).__name__)
        if fatal:
            current['setup_failed'] = True
            raise
    finally:
        row['duration_s'] = round(time.perf_counter()-start, 6)
        current['retrying_lines'] = sum(c['retrying_lines'] for c in current['setup_calls'])
        if fatal and row['rc'] != 0:
            current['setup_failed'] = True


def fallback_wheel(wheels, package):
    """Prefer the wheelhouse, then the running interpreter's ensurepip bundle."""
    from packaging.utils import parse_wheel_filename
    found = list(Path(wheels).glob(package + '-*-py3-none-any.whl'))
    if not found and package == 'pip':
        try:
            import ensurepip
            found = list((Path(ensurepip.__file__).parent / '_bundled').glob('pip-*.whl'))
        except ImportError:
            pass
    return max(found, key=lambda p: parse_wheel_filename(p.name)[1]) if found else None


def runtime_copyable(name):
    """(dist, files) if copy_runtime_package can copy this runtime package, else None. Copies nothing."""
    from importlib.metadata import distribution, PackageNotFoundError
    try:
        dist = distribution(name)
    except PackageNotFoundError:
        return None
    if name == 'pytest-timeout' and dist.version != '2.1.0':
        return None
    # Distribution names need not match import names (trove-classifiers, PyYAML).
    files = list(dist.files or [])
    if not files or any(str(p).endswith(('.so', '.pyd', '.dll', '.dylib')) for p in files):
        return None
    files = [p for p in files if '..' not in p.parts and not p.is_absolute()
             and not p.parts[0].endswith('.data')]
    if not any(str(p).endswith('.py') and not p.parts[0].endswith('.dist-info') for p in files):
        return None
    return dist, files


def copy_runtime_package(name, destination):
    """Copy only the pure Python image package and metadata; no host path injection."""
    found = runtime_copyable(name)
    if found is None:
        return 'missing'
    dist, files = found
    for entry in files:
        target = destination / entry
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(dist.locate_file(entry), target)
    return 'runtime-site-packages:' + str(dist.locate_file(''))


def wheel_metadata(path):
    from email.parser import BytesParser
    import zipfile
    with zipfile.ZipFile(path) as archive:
        name = next(n for n in archive.namelist() if n.endswith('.dist-info/METADATA'))
        return BytesParser().parsebytes(archive.read(name))


def close_tool_dependencies(roots, wheels, tags, environment, destination, install_wheel):
    """Walk runtime requirements only, using sandbox markers and no pip resolver.

    Existing sandbox metadata describes base wheels and copied tools. Each requirement
    edge is checked, while each installed distribution/version is expanded only once.
    Missing edges are returned to the caller, which must fail setup.
    """
    from importlib.metadata import distributions, distribution, PackageNotFoundError
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name, parse_wheel_filename
    installed = {canonicalize_name(d.metadata['Name']): d.metadata
                 for d in distributions(path=[str(destination)])}
    queue = list(roots)
    installed.update({canonicalize_name(m['Name']): m for m in queue})
    sources = {name: 'runtime-site-packages:' + str(destination) for name in installed}
    for path in compatible_wheels(wheels, tags).values():
        name, version, _, _ = parse_wheel_filename(path.name)
        if name in installed and installed[name]['Version'] == str(version):
            sources[name] = str(path)
    visited, entries, missing = set(), [], []
    while queue:
        metadata = queue.pop(0)
        key = (canonicalize_name(metadata['Name']), metadata['Version'])
        if key in visited:
            continue
        visited.add(key)
        for raw in metadata.get_all('Requires-Dist', []):
            req = Requirement(raw)
            if req.marker and not req.marker.evaluate(dict(environment, extra='')):
                continue
            name = canonicalize_name(req.name)
            current = installed.get(name)
            row = dict(name=name, required_spec=str(req.specifier), requirement=raw,
                       source='missing', version_installed=None)
            if current is not None and current['Version'] in req.specifier:
                row.update(source=sources.get(name, 'sandbox metadata'),
                           version_installed=current['Version'])
            else:
                # Wheelhouse first, then the embedded official PyPI wheels (pip-installed like the image), then runtime copy.
                candidate = compatible_wheels(wheels, tags, req).get(name) or compatible_wheels(extra_wheels(), tags, req).get(name)
                current = None
                if candidate:
                    result = install_wheel(candidate)
                    row['rc'] = result.exit_code
                    for field in ('stdout', 'stderr'):
                        row[field] = (getattr(result, field, '') or '').encode()[-2048:].decode(errors='ignore')
                    if result.exit_code == 0:
                        current = wheel_metadata(candidate)
                        row['source'] = str(candidate)
                else:
                    try:
                        runtime = distribution(name)
                    except PackageNotFoundError:
                        runtime = None
                    if runtime is not None and runtime.version in req.specifier:
                        source = copy_runtime_package(name, destination)
                        if source != 'missing':
                            current = runtime.metadata
                            row['source'] = source
                if current is not None:
                    installed[name] = current
                    sources[name] = row['source']
                    row['version_installed'] = current['Version']
            entries.append(row)
            if current is not None:
                queue.append(current)
            elif name not in missing:
                missing.append(name)
    return entries, missing


# Capture setup.py's otherwise discarded subprocess output without changing setup.py.
# Write after EVERY call so an outer timeout still leaves completed calls visible.
SETUP_OBSERVER = r'''import json, runpy, subprocess, sys, time
from pathlib import Path
original = subprocess.run
calls = []
log = Path(__file__).with_name('setup_subprocesses.json')
log.write_text('[]')
full_log = log.with_name('setup_subprocesses_full.jsonl')
full_log.write_text('')
def run(*args, **kwargs):
    start = time.perf_counter()
    argv = args[0] if args else kwargs.get('args')
    result = None
    try:
        result = original(*args, **kwargs)
        return result
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        result = exc
        raise
    finally:
        def decode(value):
            return value.decode(errors='replace') if isinstance(value, bytes) else (value or '')
        out, err = decode(getattr(result, 'stdout', '')), decode(getattr(result, 'stderr', ''))
        with full_log.open('a') as stream:
            stream.write(json.dumps(dict(argv=argv, stdout=out, stderr=err)) + '\n')
        calls.append(dict(argv=argv, duration_s=time.perf_counter()-start,
            start_offset_s=start-origin, rc=getattr(result, 'returncode', None),
            stdout=out.encode()[-2048:].decode(errors='ignore'),
            stderr=err.encode()[-2048:].decode(errors='ignore'),
            retrying_lines=sum('Retrying' in line for line in (out+'\n'+err).splitlines()),
            interpreter_version=sys.version))
        log.write_text(json.dumps(calls))
origin = time.perf_counter()
subprocess.run = run
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name='__main__')
'''


def patch_subprocess_deps(data_dir, state=None):
    """Install scorer tools in each venv, using that interpreter's ABI, entirely offline."""
    import swegemma.harness.container_setup as cs
    from packaging.utils import parse_wheel_filename
    orig = getattr(cs.install_test_dependencies, '_timing_original', cs.install_test_dependencies)
    wheels = data_dir / 'wheels'
    if not wheels.is_dir():
        wheels = WHEELHOUSE
    setup = data_dir / 'sandbox' / 'setup.py'
    if not setup.exists():
        setup = next(iter(data_dir.rglob('setup.py')), setup)

    def install(docker, container_id, repo='', *, fast_path=True, config=None):
        if type(docker).__name__ not in {'SubprocessManager', 'SubprocessSandbox'}:
            return orig(docker, container_id, repo, fast_path=fast_path, config=config)
        current = state.get() if state is not None else dict(
            started=time.perf_counter(), setup_calls=[], setup_failed=False)
        fixed = os.environ.get('SETUP_FIX', '1') == '1'
        current['setup_fix'] = int(fixed)
        venv = docker.sandboxes[container_id]['venv']
        sp = next(iter(sorted(venv.glob('lib/python3*/site-packages'))))
        if not fixed:
            # Preserve the original injector's wheel selection and base tar exactly.
            def original_base():
                base, large, _modules, _requirements = cs._inspect_wheels_dir(wheels)
                if large:
                    raise RuntimeError('large wheels present; workspace-import scan not emulated')
                current['wheel_tags_chosen'] = [p.name for p in base]
                inject_base(cs, base, sp, current)
            setup_step(current, 'base_tar_extraction', original_base)
            record_distributions(docker, container_id, repo, current['setup_calls'][-1])
        else:
            # A subprocess venv otherwise exposes every kernel package via _host_env.pth.
            # Only the scorer's image tools and public base wheels belong here.
            def isolate_venv():
                for pth in sp.glob('_host_env.pth'):
                    pth.unlink()
                cfg = venv / 'pyvenv.cfg'
                if cfg.exists():
                    cfg.write_text(cfg.read_text().replace(
                        'include-system-site-packages = true', 'include-system-site-packages = false'))
            setup_step(current, 'venv_fidelity', isolate_venv)
            pip_wheel = fallback_wheel(wheels, 'pip')
            def bootstrap_pip():
                if pip_wheel:
                    current['setup_calls'][-1]['source'] = str(pip_wheel)
                    import zipfile
                    with zipfile.ZipFile(pip_wheel) as zf:
                        zf.extractall(sp)
                else:
                    current['setup_calls'][-1]['source'] = copy_runtime_package('pip', sp)
                    if current['setup_calls'][-1]['source'] == 'missing':
                        raise RuntimeError('No offline pip source available')
                return docker.exec(container_id, 'python3 -m pip --version', timeout=30)
            result = setup_step(current, 'pip_bootstrap', bootstrap_pip)
            if result.exit_code != 0:
                raise RuntimeError('Sandbox pip bootstrap failed')
            probe = ("import sys,json;from pip._vendor.packaging.tags import sys_tags;"
                     "from pip._vendor.packaging.markers import default_environment;"
                     "print(json.dumps({'version':sys.version,'tags':[str(t) for t in sys_tags()],"
                     "'environment':default_environment()}))")
            result = setup_step(current, 'interpreter_probe', lambda: docker.exec(
                container_id, 'python3 -c ' + shlex.quote(probe), timeout=30))
            if result.exit_code != 0:
                raise RuntimeError('Sandbox interpreter probe failed')
            identity = json.loads(result.stdout)
            current['interpreter_version'] = identity['version']
            selected = compatible_wheels(wheels, identity['tags'])
            # The image pins pytest-timeout, even if a newer wheel is present.
            selected.pop('pytest-timeout', None)
            for path in pytest_timeout_wheels(wheels):
                if {str(t) for t in parse_wheel_filename(path.name)[3]} & set(identity['tags']):
                    selected['pytest-timeout'] = path
                    break
            current['wheel_tags_chosen'] = [p.name for p in selected.values()]
            def validate_tools():
                missing = [n for n in SCORER_TOOLS if n not in selected and n not in ('pip', 'pytest-timeout')]
                if missing:
                    raise RuntimeError('Required compatible tools missing: ' + ', '.join(missing))
            setup_step(current, 'tool_sources', validate_tools)
            def timeout_source():
                source = selected.get('pytest-timeout')
                current['setup_calls'][-1]['source'] = str(source) if source else copy_runtime_package('pytest-timeout', sp)
                if current['setup_calls'][-1]['source'] == 'missing':
                    raise RuntimeError('No offline pytest-timeout 2.1.0 source available')
            setup_step(current, 'pytest_timeout_source', timeout_source)
            def install_tools():
                for path in selected.values():
                    docker.copy_to(container_id, path, '/wheels/' + path.name)
                tools = ['/wheels/' + selected[n].name for n in SCORER_TOOLS
                         if n in selected and n != 'pip']
                return docker.exec(container_id,
                    'python3 -m pip install --ignore-installed --no-index --find-links=/wheels --no-deps ' +
                    ' '.join(shlex.quote(n) for n in tools), timeout=60)
            result = setup_step(current, 'tool_install', install_tools)
            if result.exit_code != 0:
                raise RuntimeError('Offline scorer tool installation failed')
            def tool_deps():
                from importlib.metadata import distributions
                roots = [wheel_metadata(selected[n]) for n in SCORER_TOOLS if n in selected]
                roots.extend(d.metadata for d in distributions(path=[str(sp)])
                             if d.metadata['Name'].lower() in ('pip', 'pytest-timeout')
                             and d.metadata['Name'].lower() not in selected)
                def install_dependency(path):
                    docker.copy_to(container_id, path, '/wheels/' + path.name)
                    result = docker.exec(container_id,
                        'python3 -m pip install --ignore-installed --no-index --find-links=/wheels --no-deps ' +
                        shlex.quote('/wheels/' + path.name), timeout=60)
                    setup_artifact(current, dict(step='tool_deps', wheel=path.name,
                        stdout=result.stdout, stderr=result.stderr))
                    current['setup_calls'][-1]['retrying_lines'] += sum(
                        'Retrying' in line for line in (result.stdout + '\n' + result.stderr).splitlines())
                    return result
                entries, missing = close_tool_dependencies(
                    roots, wheels, identity['tags'], identity['environment'], sp, install_dependency)
                current['setup_calls'][-1]['dependencies'] = entries
                current['missing_tool_deps'] = missing
                if missing:
                    current.update(status='failed', reason='missing_tool_deps')
                    raise RuntimeError('missing_tool_deps: ' + ', '.join(missing))
            setup_step(current, 'tool_deps', tool_deps)
            setup_step(current, 'pip_check', lambda: docker.exec(
                container_id, 'python3 -m pip check', timeout=30), fatal=False)
            # Docker's hook ignores failure, but observe the real pip rc and both streams.
            setup_step(current, 'workspace_editable', lambda: docker.exec(container_id,
                'python3 -m pip install --no-index --find-links=/wheels --no-build-isolation --no-deps -e /workspace',
                timeout=280), fatal=False)
            current['workspace_editable_rc'] = current['setup_calls'][-1]['rc']
            current['editable_failed'] = current['workspace_editable_rc'] != 0
            current['setup_failed'] |= current['editable_failed']
            record_distributions(docker, container_id, repo, current['setup_calls'][-1])
            def extract_base():
                base = [p for name, p in selected.items() if name not in BASE_SKIP]
                if any(p.stat().st_size >= cs._LARGE_WHEEL_THRESHOLD_BYTES for p in base):
                    raise RuntimeError('large wheels present; workspace-import scan not emulated')
                inject_base(cs, base, sp, current)
            setup_step(current, 'base_tar_extraction', extract_base)
            record_distributions(docker, container_id, repo, current['setup_calls'][-1])
        def run_setup():
            docker.copy_to(container_id, setup, '/tmp/setup.py')
            # All observer files are scratch files, never workspace patch inputs.
            observer = docker.sandboxes[container_id]['tmp'] / 'setup_observer.py'
            observer.write_text(SETUP_OBSERVER)
            return docker.exec(container_id, setup_command(repo, fast_path), timeout=280)
        try:
            setup_step(current, 'setup.py', run_setup)
        finally:
            log = docker.sandboxes[container_id]['tmp'] / 'setup_subprocesses.json'
            calls = json.loads(log.read_text()) if log.exists() else []
            full_log = log.with_name('setup_subprocesses_full.jsonl')
            if full_log.exists():
                for line in full_log.read_text().splitlines():
                    setup_artifact(current, dict(step='setup.py', **json.loads(line)))
            current['setup_subprocesses'] = calls
            setup_row = next(c for c in reversed(current['setup_calls']) if c['step'] == 'setup.py')
            setup_row['subprocesses'] = calls
            setup_row['retrying_lines'] += sum(c['retrying_lines'] for c in calls)
            current['retrying_lines'] = sum(c['retrying_lines'] for c in current['setup_calls'])
            editable = [c for c in calls if isinstance(c['argv'], list) and '-e' in c['argv']]
            current['editable_rc'] = editable[0]['rc'] if editable else None
            current['editable_final_rc'] = editable[-1]['rc'] if editable else None
            current['editable_failed'] = any(c['rc'] != 0 for c in editable) or current.get('workspace_editable_rc', 0) != 0
            current['setup_failed'] |= current['editable_failed']
            record_distributions(docker, container_id, repo, setup_row)
            if calls:
                current['interpreter_version'] = calls[0]['interpreter_version']
            else:
                current.setdefault('interpreter_version', None)
        current['status'] = 'failed' if current['setup_failed'] else 'passed'
        return current
    install._timing_original = orig
    for name, module in list(sys.modules.items()):
        if name.startswith('swegemma.') and hasattr(module, 'install_test_dependencies'):
            module.install_test_dependencies = install
    return install

def classify_patch(patch, repo, protected=None, test_targets=()):
    """Parse file headers outside hunks, including quoted paths and renames."""
    files, new = set(), set()
    current, added, in_hunk = set(), False, False
    def path_value(raw):
        raw = raw.split('\t', 1)[0]
        value = json.loads(raw) if raw.startswith('"') else raw
        return value[2:] if value.startswith(('a/', 'b/')) else value
    for line in patch.splitlines() + ['diff --git ']:
        if line.startswith('diff --git '):
            files.update(current)
            if added:
                new.update(current)
            current, added, in_hunk = set(), False, False
            match = re.match(r'^diff --git ("a/.*?"|a/.*?) ("b/.*?"|b/.*)$', line)
            if match:
                current.update(path_value(p) for p in match.groups())
        elif line.startswith('@@'):
            in_hunk = True
        elif not in_hunk:
            if line.startswith(('--- ', '+++ ')):
                p = path_value(line[4:])
                if p != '/dev/null':
                    current.add(p)
                elif line.startswith('--- '):
                    added = True
            elif line.startswith('new file mode '):
                added = True
            elif line.startswith(('rename from ', 'rename to ')):
                current.add(path_value(line.split(' ', 2)[2]))
    if protected is None:
        protected = lambda p: bool(re.search(r'(^|/)(tests?/|test_[^/]*\.py$|conftest\.py$)|_test\.py$', p))
    tests = sorted(p for p in files if protected(p) or p in test_targets)
    package = repo.split('/')[-1].replace('-', '_').lower()
    source_roots = (package + '/', 'src/' + package + '/')
    stray = sorted(p for p in new if not (p.endswith('.py') and p.lower().startswith(source_roots)
                                         and p not in tests))
    return dict(patch_bytes=len(patch.encode()), patch_files=sorted(files),
                test_files_edited=tests, stray_files=stray, empty_patch=not patch.strip())

def trace_counts(trace):
    entries = trace.entries if trace else []
    counts = Counter(e.tool_name for e in entries if e.event_type == 'tool_call')
    tokens = {}
    for key in ('prompt_tokens', 'completion_tokens'):
        values = [e.usage[key] for e in entries if e.usage and isinstance(e.usage.get(key), (int, float))]
        tokens[key] = sum(values) if values else None
    return dict(counts), tokens, tool_seconds(entries)

def tool_seconds(entries):
    """Per tool name: wall seconds from each tool_call to its tool_response (FIFO per name)."""
    pending, out = {}, {}
    for e in entries:
        if e.event_type == 'tool_call':
            pending.setdefault(e.tool_name, []).append(e.timestamp)
        elif e.event_type == 'tool_response' and pending.get(e.tool_name):
            stat = out.setdefault(e.tool_name, dict(n=0, total=0.0, max=0.0))
            dt = max(0.0, e.timestamp - pending[e.tool_name].pop(0))
            stat['n'] += 1
            stat['total'] = round(stat['total'] + dt, 3)
            stat['max'] = round(max(stat['max'], dt), 3)
    return out

def observe_patch_strip(original, state):
    """Retain the agent's diff before the harness removes protected edits."""
    def strip(patch, *pos, **kw):
        current = state.get(None)
        filtered = original(patch, *pos, **kw)
        if current is not None and current.get('agent_active'):
            if patch != current.get('filtered_patch'):
                current['raw_patch'] = patch
            current['filtered_patch'] = filtered
        return filtered
    return strip

def test_run_stats(trace, agent_seconds):
    pending, n, total = {}, 0, 0.0
    for e in trace.entries if trace else []:
        if e.event_type == 'tool_call':
            command = (e.tool_args or {}).get('command', '')
            is_test = e.tool_name == 'run_command' and any(s in command for s in ('pytest', 'unittest', 'tox', 'nox', 'run_tests'))
            n += int(is_test)
            pending.setdefault(e.tool_name, []).append((e.timestamp, is_test))
        elif e.event_type == 'tool_response' and pending.get(e.tool_name):
            start, is_test = pending[e.tool_name].pop(0)
            if is_test:
                total += max(0.0, e.timestamp - start)
    return dict(n=n, total_seconds=total, share_of_agent_seconds=total / agent_seconds if agent_seconds else None)

def should_stop(elapsed, cap_minutes, verification_timeout, observed_max, budget, setup_reserve=0):
    return elapsed + 1.5 * max(cap_minutes * 60 + verification_timeout + setup_reserve, observed_max) > budget


def setup_reserve_seconds(skip_verification):
    return SETUP_PASS_SECONDS * (1 if skip_verification else 3)


class AsyncioTimingProxy:
    """Observe only agent_runner's timeout context, without changing asyncio itself."""
    def __init__(self, original, state):
        self._original, self._state = original, state

    def __getattr__(self, name):
        return getattr(self._original, name)

    def timeout(self, *args, **kwargs):
        cm = self._original.timeout(*args, **kwargs)
        state = self._state
        delay = args[0] if args else kwargs.get('delay')

        class ObservedTimeout:
            async def __aenter__(self):
                self.current = state.get(None)
                if self.current is not None:
                    self.current.update(agent_timeout_seconds=delay, timeout_enter=time.perf_counter())
                return await cm.__aenter__()

            async def __aexit__(self, *exc_info):
                exit_exc = exc_info[1]
                try:
                    return await cm.__aexit__(*exc_info)
                except BaseException as exc:
                    exit_exc = exc
                    raise
                finally:
                    if self.current is not None:
                        self.current.update(timeout_exit=time.perf_counter(),
                            agent_timeout_fired=bool(getattr(cm, 'expired', lambda: False)())
                                or isinstance(exit_exc, TimeoutError))

        return ObservedTimeout()


def observe_sandbox(original, state, name):
    """Forward identical arguments/results/exceptions and time sandbox boundaries."""
    async def observed(*args, **kwargs):
        current = state.get(None)
        start = time.perf_counter()
        row = None
        if current is not None:
            if name == 'sandbox_start':
                current['sandbox_start_begin'] = start
            elif name == 'sandbox_exec' and current.get('timeout_exit') is not None:
                cmd = args[2] if len(args) > 2 else kwargs.get('command', kwargs.get('cmd', ''))
                row = dict(cmd=str(cmd)[:40], duration_s=None, rc=None)
                current.setdefault('finalization_exec', []).append(row)
        try:
            result = await original(*args, **kwargs)
            if row is not None:
                row['rc'] = getattr(result, 'exit_code', None)
            return result
        except BaseException as exc:
            if row is not None:
                row['exception'] = type(exc).__name__
            raise
        finally:
            end = time.perf_counter()
            if current is not None:
                if name in ('sandbox_start', 'sandbox_stop'):
                    current[name + '_end'] = end
                    current[name + '_duration'] = end - start
                if row is not None:
                    row['duration_s'] = end - start
    return observed


async def skip_verification(docker, config, task, snapshot_path, *, agent_patch='',
                            agent_error=None, trace=None, start_time=0.0, **kwargs):
    """Return the harness result type without starting Container B or running tests."""
    from swegemma.models import TaskResult
    result = TaskResult(instance_id=task.instance_id, repo=task.repo, resolved=False,
        agent_patch=agent_patch, test_output='', test_exit_code=0,
        duration_seconds=time.perf_counter() - start_time, error=agent_error, trace=trace)
    # swegemma 0.2.11 annotates this field int, with assignment validation disabled.
    result.test_exit_code = None
    return result


def phase1_fields(current, run_seconds, total, context, patch):
    def difference(end, start):
        return current[end] - current[start] if current.get(end) is not None and current.get(start) is not None else None
    phase1 = difference('sandbox_stop_end', 'sandbox_start_begin')
    source = 'sandbox_wrappers' if phase1 is not None else 'run_agent_sandbox'
    phase1 = run_seconds if phase1 is None else phase1
    submitted = bool(context.patch_submitted) if context is not None else None
    return dict(agent_timeout_seconds=current.get('agent_timeout_seconds'),
        agent_clock_seconds=difference('timeout_exit', 'timeout_enter'),
        agent_timeout_fired=current.get('agent_timeout_fired'),
        finalization_seconds=difference('sandbox_stop_end', 'timeout_exit'),
        finalization_exec=current.get('finalization_exec', []),
        teardown_seconds=current.get('sandbox_stop_duration'),
        phase1_wall_seconds=phase1, phase1_source=source,
        pre_agent_seconds=difference('timeout_enter', 'sandbox_start_begin'),
        post_phase1_seconds=total - phase1, patch_submitted=submitted,
        fallback_patch_used=(not submitted and bool(patch.strip())) if submitted is not None else None,
        verification_skipped=SKIP_VERIFICATION)


# Normal agent end states that swegemma reports through agent_error (agent_runner.py 0.2.11).
AGENT_OUTCOMES = (('timeout', re.compile(r'Agent exceeded session timeout\b')),
                  ('turns', re.compile(r'Agent exceeded (turns budget|maximum allowed LLM turns)\b')),
                  ('tool_calls', re.compile(r'Agent exceeded tool call budget\b')),
                  ('no_submit', re.compile(r'Agent completed execution without calling submit_patch\b')))
IMAGE_EMULATION_STEPS = ('venv_fidelity', 'pip_bootstrap', 'interpreter_probe', 'tool_sources',
                         'pytest_timeout_source', 'tool_install', 'tool_deps', 'pip_check')


def agent_outcome(message):
    """Name of a known normal agent end state, else None (including for empty messages)."""
    text = (message or '').strip()
    return next((name for name, pattern in AGENT_OUTCOMES if pattern.match(text)), None)


def harness_error(result, agent_error):
    """Fail closed: any error that is not a known normal agent end state is a harness failure."""
    messages = [m for m in ((result.error if result is not None else None), agent_error) if m]
    return 'Harness task failure' if any(agent_outcome(m) is None for m in messages) else None


def platform_probe(host='pypi.org', port=443, timeout=10.0):
    """P2 (plan 006 addendum): docker presence, DNS, and one TCP connect. Sends no payload."""
    out = dict(docker_which=shutil.which('docker'), docker_sock=os.path.exists('/var/run/docker.sock'),
               host=host, port=port, dns=None, dns_seconds=None, tcp=None, tcp_seconds=None, tcp_errno=None)
    box = {}
    def resolve():
        try:
            box['addrs'] = sorted({ai[4][0] for ai in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})
        except Exception as exc:
            box['error'] = type(exc).__name__
    start = time.perf_counter()
    worker = threading.Thread(target=resolve, daemon=True)
    worker.start(); worker.join(timeout)
    out['dns_seconds'] = round(time.perf_counter() - start, 3)
    if worker.is_alive():
        out['dns'], out['tcp'] = 'timeout', 'skipped'
        return out
    if 'error' in box or not box.get('addrs'):
        out['dns'], out['tcp'] = 'failed:' + box.get('error', 'empty'), 'skipped'
        return out
    out['dns'] = 'resolved'
    out['dns_addr_count'] = len(box['addrs'])
    start = time.perf_counter()
    try:
        sock = socket.create_connection((box['addrs'][0], port), timeout=timeout)
        sock.close()
        out['tcp'] = 'connected'
    except socket.timeout:
        out['tcp'] = 'timeout'  # blackhole: SYN dropped
    except ConnectionRefusedError:
        out['tcp'] = 'refused'
    except OSError as exc:
        out['tcp'], out['tcp_errno'] = 'unreachable', exc.errno
    out['tcp_seconds'] = round(time.perf_counter() - start, 3)
    return out

def stock_setup_probe(config, iid, repo):
    """P1 (plan 006 addendum): time swegemma's STOCK subprocess setup sequence on this task's snapshot.
    Mirrors eval/tools/stock_subprocess_setup_timing.py (agent_runner.py ~l.553-584); the stock
    install_test_dependencies is used even though patch_subprocess_deps rebinds it. Never raises."""
    steps, error, mgr, sid = {}, None, None, None
    t0 = time.perf_counter()
    deadline = t0 + P1_DEADLINE_SECONDS
    # BaseException prevents stock helpers' broad Exception handlers from swallowing the deadline.
    class Deadline(BaseException):
        pass
    def expired(*args):
        raise Deadline()
    def remaining():
        left = deadline - time.perf_counter()
        if left <= 0:
            raise Deadline()
        return left
    old_handler, old_timer = None, None
    try:
        old_handler = signal.signal(signal.SIGALRM, expired)
        old_timer = signal.setitimer(signal.ITIMER_REAL, remaining())
        import swegemma.harness.container_setup as cs
        from swegemma.sandbox.subprocess import SubprocessManager
        install_deps = getattr(cs.install_test_dependencies, '_timing_original', cs.install_test_dependencies)
        mgr = SubprocessManager(timeout_seconds=120)
        original_exec = mgr.exec
        def bounded_exec(*args, **kwargs):
            kwargs['timeout'] = min(120, remaining())
            return original_exec(*args, **kwargs)
        mgr.exec = bounded_exec
        remaining()
        s = time.perf_counter(); sid = mgr.start(); steps['start_venv'] = round(time.perf_counter() - s, 3)
        for name, fn, args, kwargs in (
                ('setup_container_wheels', cs.setup_container_wheels, (mgr, sid, config), {}),
                ('extract_snapshot', cs.extract_snapshot, (mgr, sid, Path(config.snapshots_dir) / f'{iid}.tgz'), {}),
                ('setup_git_exclude', cs.setup_git_exclude, (mgr, sid), {}),
                ('install_editable_package', cs.install_editable_package, (mgr, sid), {}),
                ('install_test_dependencies', install_deps, (mgr, sid, repo), dict(config=config)),
                ('setup_workspace_test_config', cs.setup_workspace_test_config, (mgr, sid), dict(repo=repo)),
                ('setup_baseline_commit', cs.setup_baseline_commit, (mgr, sid, 'baseline'), {})):
            remaining()
            s = time.perf_counter()
            try:
                fn(*args, **kwargs)
                remaining()
            finally:
                steps[name] = round(time.perf_counter() - s, 3)
    except Deadline:
        error = 'deadline'
    except Exception as exc:
        error = type(exc).__name__
    finally:
        try:
            if old_timer is not None:
                # Cleanup always gets a bounded chance, even after the overall deadline.
                signal.setitimer(signal.ITIMER_REAL, max(.001, min(30, deadline - time.perf_counter()))
                                 if time.perf_counter() < deadline else 30)
            if mgr is not None:
                mgr.cleanup_all()
        except Deadline:
            error = 'deadline'
        except Exception as exc:
            error = error or 'cleanup ' + type(exc).__name__
        finally:
            if time.perf_counter() >= deadline:
                error = 'deadline'
            if old_timer is not None:
                signal.setitimer(signal.ITIMER_REAL, 0)
            if old_handler is not None:
                signal.signal(signal.SIGALRM, old_handler)
            if old_timer is not None:
                if old_timer[0]:
                    signal.setitimer(signal.ITIMER_REAL,
                                     max(.001, old_timer[0] - (time.perf_counter() - t0)), old_timer[1])
    return dict(total_s=round(time.perf_counter() - t0, 3), steps_s=steps, error=error)

def llm_calls(trace, limit=200):
    """P3 (plan 006 addendum): one row per trace entry carrying usage (ADK attaches usage once per
    model event), with the gap since the previous entry of any type (approx. model latency)."""
    rows, prev = [], None
    entries = trace.entries if trace else []
    first = entries[0].timestamp if entries else None
    for e in entries:
        if e.usage:
            rows.append(dict(t=round(e.timestamp - first, 3), gap_s=round(e.timestamp - prev, 3) if prev is not None else None,
                             event_type=e.event_type,
                             completion_tokens=e.usage.get('completion_tokens'), prompt_tokens=e.usage.get('prompt_tokens')))
        prev = e.timestamp
    return rows[:limit]

def image_emulation_seconds(setup_calls):
    """Seconds spent emulating Dockerfile.public image layers the scorer image already has."""
    return sum(c.get('duration_s') or 0 for c in setup_calls if c.get('step') in IMAGE_EMULATION_STEPS)

def distribution(values):
    values = sorted(values)
    def percentile(q):
        x = (len(values) - 1) * q
        lo = int(x)
        return values[lo] + (values[min(lo + 1, len(values)-1)] - values[lo]) * (x-lo)
    return dict(mean=sum(values)/len(values), p50=percentile(.5), p90=percentile(.9), max=max(values)) if values else dict.fromkeys(('mean', 'p50', 'p90', 'max'))

def extract_bundle(encoded, destination):
    payload = base64.b64decode(encoded, validate=True)
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(payload), mode='r:gz') as tf:
        tf.extractall(destination, filter='data')
    return hashlib.sha256(payload).hexdigest(), hashlib.sha256((destination / 'agent.yaml').read_bytes()).hexdigest()

def append(stream, row):
    stream.write(json.dumps(row, allow_nan=False) + '\n')
    stream.flush(); os.fsync(stream.fileno())

async def evaluate(config, journal, started, caps, totals):
    from contextvars import ContextVar
    from swegemma.evaluate import Evaluator
    from swegemma.models import load_tasks
    from swegemma.harness.verification import _is_protected_test_or_config_path
    import swegemma.evaluate as ev
    import swegemma.harness.verification as vf
    import swegemma.harness.agent_runner as ar
    state = ContextVar('timing')
    original_asyncio = ar.asyncio
    original_sandbox = {name: getattr(ar, name) for name in ('sandbox_start', 'sandbox_stop', 'sandbox_exec')}
    ar.asyncio = AsyncioTimingProxy(original_asyncio, state)
    for name, original in original_sandbox.items():
        setattr(ar, name, observe_sandbox(original, state, name))
    original_verify, original_strip = ev.verify_task, vf.strip_protected_files_from_patch
    vf.strip_protected_files_from_patch = observe_patch_strip(original_strip, state)
    async def verify(*args, **kwargs):
        start = time.perf_counter()
        try:
            return await (skip_verification if SKIP_VERIFICATION else original_verify)(*args, **kwargs)
        finally:
            state.get()['verification'] = time.perf_counter() - start
    ev.verify_task = verify
    class TimingEvaluator(Evaluator):
        agent_seconds, patch, trace, agent_error = 0.0, '', None, ''
        def _hydrate_task_from_secret(self, task):
            return task
        def _get_secret_bundle_data(self):
            return {}, {}, None
        async def _run_agent_sandbox(self, task, *args, **kwargs):
            safe = dataclasses.replace(task, patch='', test_patch='', FAIL_TO_PASS=(), PASS_TO_PASS=())
            self.context = kwargs['context']
            self.context.task = safe
            start = time.perf_counter()
            state.get()['agent_active'] = True
            try:
                self.patch, self.agent_error, self.trace = await super()._run_agent_sandbox(safe, *args, **kwargs)
                return self.patch, self.agent_error, self.trace
            finally:
                self.agent_seconds = time.perf_counter() - start
                state.get()['agent_active'] = False
    try:
        inventory = {t.instance_id: t for t in load_tasks(config.tasks_path)}
        if len(set(TASK_IDS)) != len(TASK_IDS) or set(TASK_IDS) - inventory.keys():
            raise ValueError('Duplicate or missing task IDs')
        patch_subprocess_deps(DATA, state)
        for iid in TASK_IDS:
            if should_stop(time.monotonic()-started + (P1_DEADLINE_SECONDS + 30 if STOCK_PROBE else 0), caps['max_time_minutes'], 0 if SKIP_VERIFICATION else caps['verification_timeout_seconds'], max([*totals, OBSERVED_MAX_SEED_SECONDS]), float(os.environ.get('KERNEL_BUDGET_SECONDS', KERNEL_BUDGET_SECONDS)), setup_reserve_seconds(SKIP_VERIFICATION)):
                append(journal, {'_stopped': 'insufficient remaining budget for next task'})
                break
            task = dataclasses.replace(inventory[iid], patch='')
            stock = stock_setup_probe(config, iid, task.repo) if STOCK_PROBE else None
            if STOCK_PROBE and should_stop(time.monotonic()-started, caps['max_time_minutes'], 0 if SKIP_VERIFICATION else caps['verification_timeout_seconds'], max([*totals, OBSERVED_MAX_SEED_SECONDS]), float(os.environ.get('KERNEL_BUDGET_SECONDS', KERNEL_BUDGET_SECONDS)), setup_reserve_seconds(SKIP_VERIFICATION)):
                append(journal, {'_stopped': 'insufficient remaining budget for next task'})
                break
            times = dict(instance_id=task.instance_id, verification=0.0, started=time.perf_counter(), setup_calls=[], setup_failed=False)
            state.set(times)
            evaluator, result, error = TimingEvaluator(config), None, None
            original_start = evaluator.docker.start
            evaluator.docker.start = lambda: setup_step(times, 'venv', original_start)
            start = time.perf_counter()
            try:
                result = await evaluator.evaluate_task(task)
                error = harness_error(result, evaluator.agent_error)
            except Exception as exc:
                error = 'Evaluation exception (' + type(exc).__name__ + ')'
            finally:
                try:
                    evaluator.docker.cleanup_all()
                except Exception as exc:
                    error = 'Cleanup exception (' + type(exc).__name__ + ')'
            total = time.perf_counter() - start
            totals.append(total)
            patch = times.get('raw_patch', result.agent_patch if result else evaluator.patch) or ''
            try:
                counts, tokens, seconds = trace_counts(evaluator.trace)
            except Exception as exc:  # never lose the run over trace parsing
                counts, tokens, seconds = {}, dict(prompt_tokens=None, completion_tokens=None), {}
                error = (error or '') + ' trace parse (' + type(exc).__name__ + ')'
            code = result.test_exit_code if result else None
            raw_error = (result.error or '') if result else error or ''
            phase = phase1_fields(times, evaluator.agent_seconds, total,
                                  getattr(evaluator, 'context', None),
                                  result.agent_patch if result else evaluator.patch)
            phase.update(agent_outcome=agent_outcome(evaluator.agent_error or raw_error),
                         image_emulation_seconds=image_emulation_seconds(times['setup_calls']))
            try:
              append(journal, dict(instance_id=iid, repo=task.repo, resolved=bool(result and result.resolved), exit_code=code, error=error,
                **phase,
                wall_seconds=dict(agent=evaluator.agent_seconds, verification=times['verification'], total=total), sandbox_setup_seconds=sum(c['duration_s'] for c in times['setup_calls']),
                setup_calls=times['setup_calls'], setup_failed=times['setup_failed'],
                editable_failed=times.get('editable_failed', False),
                setup_output_artifact=times.get('setup_output_artifact'),
                missing_tool_deps=times.get('missing_tool_deps', []),
                setup_fix=times.get('setup_fix'), setup_subprocesses=times.get('setup_subprocesses', []),
                editable_rc=times.get('editable_rc'), retrying_lines=times.get('retrying_lines', 0),
                llm_turns=evaluator.context.llm_calls_used if hasattr(evaluator, 'context') else None, tool_calls=dict(total=sum(counts.values()) if evaluator.trace else (result.tool_calls if result else None), per_tool=counts),
                tool_seconds=seconds, test_run=test_run_stats(evaluator.trace, evaluator.agent_seconds), **tokens,
                completion_tokens_per_second=tokens['completion_tokens']/evaluator.agent_seconds if tokens['completion_tokens'] is not None and evaluator.agent_seconds else None,
                stock_setup=stock, llm_calls=llm_calls(evaluator.trace),
                **classify_patch(patch, task.repo, _is_protected_test_or_config_path, task.test_files),
                timed_out=bool(re.search(r'timeout|timed out', raw_error + ' ' + (evaluator.agent_error or ''), re.I)) or code == 124))
            except Exception as exc:
                append(journal, dict(instance_id=iid, repo=task.repo, resolved=bool(result and result.resolved),
                                     **phase,
                                     wall_seconds=dict(agent=evaluator.agent_seconds, verification=times['verification'], total=total),
                                     setup_calls=times['setup_calls'], setup_failed=times['setup_failed'],
                editable_failed=times.get('editable_failed', False),
                setup_output_artifact=times.get('setup_output_artifact'),
                missing_tool_deps=times.get('missing_tool_deps', []),
                setup_fix=times.get('setup_fix'), setup_subprocesses=times.get('setup_subprocesses', []),
                stock_setup=stock,
                editable_rc=times.get('editable_rc'), retrying_lines=times.get('retrying_lines', 0), error='Row build exception (' + type(exc).__name__ + ')'))
            # Raw artifacts are diagnostics written after the row; never lose the remaining tasks over them.
            try:
                raw = WORK / 'runs' / iid
                raw.mkdir(parents=True, exist_ok=True)
                (raw / 'agent.patch').write_text(patch)
                (raw / 'trace.json').write_text(json.dumps(evaluator.trace.to_dict(format='legacy') if evaluator.trace else {}, default=str))
                (raw / 'result.json').write_text(json.dumps(result.model_dump(exclude={'trace'}) if result else {'error': error}, default=str))
            except Exception as exc:
                append(journal, {'_artifact_error': dict(instance_id=iid, type=type(exc).__name__)})
    finally:
        ev.verify_task, vf.strip_protected_files_from_patch = original_verify, original_strip
        ar.asyncio = original_asyncio
        for name, original in original_sandbox.items():
            setattr(ar, name, original)

def start_server(holder):
    import torch
    from adk_submission import VllmConfig, VllmServer, discover_adapters
    from adk_submission.discovery import discover_declared_models
    from swegemma.config import ALLOWED_ADAPTER_EXTENSIONS
    MODEL_VLLM_EXTRA_ARGS = {'gemma-4-12b-it-qat-w4a16-ct': (
        '--hf-overrides', '{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}')}
    _SAFE_PATH_COMPONENT = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]*')
    declared_models = discover_declared_models(BUNDLE)
    assert len(declared_models) == 1, f'Expected exactly 1 declared model, got: {sorted(declared_models)}'
    declared_model = next(iter(declared_models))
    assert declared_model in {'gemma-4-' + x + '-it-qat-w4a16-ct' for x in ('31b', '12b', 'e4b', 'e2b')}, 'Unsupported declared model'
    MODEL_PATH = Path(f'/kaggle/input/models/google/gemma-4/other/{declared_model}/2')
    assert MODEL_PATH.exists(), f'Model weights not found at {MODEL_PATH}. Ensure the model input is attached.'
    adapters = discover_adapters(str(BUNDLE), adapter_extensions=ALLOWED_ADAPTER_EXTENSIONS)
    adapter_map = getattr(adapters, 'adapters', None) or {}
    for adapter_name in adapter_map:
        assert _SAFE_PATH_COMPONENT.fullmatch(adapter_name), 'Unsafe adapter name'
    detected_ranks = [r for info in adapter_map.values() if (r := getattr(info, 'rank', None)) is not None and r > 0]
    gpu_count = torch.cuda.device_count() if torch.cuda.is_available() else 1
    tp_size = 4 if gpu_count >= 4 else (2 if gpu_count >= 2 else 1)
    vllm_cfg = VllmConfig(
        model=str(MODEL_PATH), port=8000, host='127.0.0.1',
        tool_call_parser='gemma4', reasoning_parser='gemma4', max_model_len=32768,
        dtype='bfloat16' if (torch.cuda.is_available() and torch.cuda.is_bf16_supported()) else 'auto',
        gpu_memory_utilization=0.90, enable_auto_tool_choice=True,
        enable_lora=bool(adapter_map), max_loras=max(1, len(adapter_map)),
        max_lora_rank=max(detected_ranks) if detected_ranks else 128,
        scheduler_reserve_full_isl=False, tensor_parallel_size=tp_size, startup_timeout=60 * 20,
        extra_args=MODEL_VLLM_EXTRA_ARGS.get(declared_model, ()),
    )
    server_instance = VllmServer(vllm_cfg, adapter_manifest=adapters)
    holder.append(server_instance)
    start = time.perf_counter()
    server_instance.start()
    startup = time.perf_counter() - start
    return server_instance, adapters, declared_model, startup

class WrongAccelerator(RuntimeError):
    pass


def gpu_preflight():
    """Raise WrongAccelerator unless nvidia-smi lists >= 4 L4 GPUs; skip if nvidia-smi is unavailable."""
    try:
        gpus = subprocess.run(['nvidia-smi', '-L'], capture_output=True, text=True, timeout=60).stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        return
    if len(gpus) < 4 or not all('L4' in g for g in gpus):
        raise WrongAccelerator('expected 4x L4 (nvidia-smi -L preflight)')


def check_hook_targets():
    """The observation hooks in evaluate() need these swegemma attributes; check before vLLM starts."""
    import swegemma.evaluate as ev
    import swegemma.harness.agent_runner as ar
    import swegemma.harness.verification as vf
    import swegemma.harness.container_setup as cs
    wanted = ((ar, ('asyncio', 'sandbox_start', 'sandbox_stop', 'sandbox_exec')),
              (cs, ('install_test_dependencies', '_inspect_wheels_dir', '_LARGE_WHEEL_THRESHOLD_BYTES')),
              (ev, ('verify_task', 'Evaluator')),
              (vf, ('strip_protected_files_from_patch', '_is_protected_test_or_config_path')))
    missing = [m.__name__ + '.' + n for m, names in wanted for n in names if not hasattr(m, n)]
    if missing:
        raise RuntimeError('swegemma hook targets missing: ' + ', '.join(missing))


def setup_task(data_dir, wheels_dir, iid, repo, state):
    """Real agent_runner setup path through dependency installation; no agent/verification."""
    from types import SimpleNamespace
    from swegemma.sandbox import SubprocessManager
    from swegemma.deduplication import resolve_task_snapshot_paths
    import swegemma.harness.container_setup as cs
    current = dict(instance_id=iid, setup_fix=int(os.environ.get('SETUP_FIX', '1')),
                   started=time.perf_counter(), setup_calls=[], setup_failed=False,
                   editable_rc=None, retrying_lines=0, interpreter_version=None,
                   wheel_tags_chosen=[], setup_subprocesses=[])
    state.set(current)
    manager = SubprocessManager(timeout_seconds=300)
    try:
        install_deps = patch_subprocess_deps(data_dir, state)
        sid = setup_step(current, 'venv', manager.start)
        config = SimpleNamespace(wheels_dir=wheels_dir, tasks_path=data_dir / 'tasks.jsonl',
                                 snapshots_dir=data_dir / 'snapshots')
        setup_step(current, 'setup_container_wheels', lambda: cs.setup_container_wheels(manager, sid, config))
        snapshot, base, patch = resolve_task_snapshot_paths(data_dir / 'snapshots', iid, repo)
        setup_step(current, 'extract_snapshot', lambda: cs.extract_snapshot(
            manager, sid, snapshot, base_snapshot_path=base, patch_path=patch))
        setup_step(current, 'setup_git_exclude', lambda: cs.setup_git_exclude(manager, sid))
        if current['setup_fix'] == 0:
            setup_step(current, 'install_editable_package', lambda: cs.install_editable_package(manager, sid))
        install_deps(manager, sid, repo)
    except Exception as exc:
        current.update(setup_failed=True, status='failed', error=type(exc).__name__ + ': ' + str(exc)[:2048])
    finally:
        current['setup_s_total'] = round(time.perf_counter()-current['started'], 6)
        try:
            setup_step(current, 'teardown', manager.cleanup_all)
        except Exception as exc:
            current['teardown_error'] = type(exc).__name__
        current.pop('started')
    return current


def setup_only_main():
    from contextvars import ContextVar
    WORK.mkdir(parents=True, exist_ok=True)
    with (WORK / 'setup_check.jsonl').open('w') as journal:
        append(journal, dict(_schema='kaggle_setup_cpu_check_v1', task_ids=TASK_IDS,
                             setup_fix=int(os.environ.get('SETUP_FIX', '1')), git_sha=GIT_SHA,
                             concurrency=1, interpreter_version=sys.version))
        n = 0
        try:
            install()
            from swegemma.models import load_tasks
            inventory = {t.instance_id: t.repo for t in load_tasks(DATA / 'tasks.jsonl')}
            if not TASK_IDS or len(set(TASK_IDS)) != len(TASK_IDS) or set(TASK_IDS)-inventory.keys():
                raise ValueError('Nonempty unique known task IDs required')
            state = ContextVar('setup_check')
            for iid in TASK_IDS:
                append(journal, setup_task(DATA, DATA / 'wheels' if (DATA / 'wheels').is_dir()
                                          else WHEELHOUSE, iid, inventory[iid], state))
                n += 1
        except BaseException as exc:
            append(journal, dict(_stopped=type(exc).__name__))
            raise
        finally:
            append(journal, dict(_done=dict(n=n)))


def main():
    os.environ.setdefault('SETUP_FIX', str(SETUP_FIX))
    if os.environ['SETUP_FIX'] not in ('0', '1'):
        raise ValueError('SETUP_FIX must be 0 or 1')
    if SETUP_ONLY:
        os.environ.setdefault('SETUP_ONLY', '1')
    if os.environ.get('SETUP_ONLY') == '1':
        return setup_only_main()
    started, totals, servers, startup = time.monotonic(), [], [], None
    WORK.mkdir(exist_ok=True, parents=True)
    with (WORK / 'timing.jsonl').open('w') as journal:
        header = dict(_schema='kaggle_timing_v1', git_sha=GIT_SHA, task_ids=TASK_IDS, concurrency=1,
                      created_utc=datetime.now(timezone.utc).isoformat(), caps=None,
                      bundle_sha256=None, agent_yaml_sha256=None, gpu_names=[], gpu_count=0,
                      mcp_import_ok=None, vllm_startup_seconds=None, platform_probe=None,
                      fields=dict(instance_id='Task ID', repo='Repository', wall_seconds='Agent (including setup), verification, total wall seconds',
                          vllm_startup_seconds='Header: perf_counter seconds spent starting vLLM; null on startup failure',
                          verification_skipped='Container B and verification tests skipped',
                          agent_outcome='timeout/turns/tool_calls/no_submit from agent_error, or null',
                          image_emulation_seconds='Setup steps emulating image layers the scorer image already has (inside Phase-1)',
                          agent_timeout_seconds='Delay passed to agent_runner asyncio.timeout, or null',
                          agent_clock_seconds='Timeout context exit minus enter (perf_counter), or null',
                          agent_timeout_fired='Real timeout expired or exit TimeoutError; null if not entered',
                          finalization_seconds='Sandbox stop end minus timeout exit, or null',
                          finalization_exec='Post-timeout sandbox_exec calls: cmd (first 40 chars), duration_s, rc or exception type',
                          teardown_seconds='sandbox_stop duration including failed stop, or null',
                          phase1_wall_seconds='sandbox_start begin to sandbox_stop end, otherwise _run_agent_sandbox duration',
                          phase1_source='sandbox_wrappers or run_agent_sandbox fallback',
                          pre_agent_seconds='Timeout enter minus sandbox_start begin, or null',
                          post_phase1_seconds='Total wall seconds minus phase1_wall_seconds',
                          patch_submitted='Context patch_submitted; null if no context',
                          fallback_patch_used='No submitted patch and non-empty returned harness patch; null if no context',
                          sandbox_setup_seconds='Sum of measured setup steps', setup_calls='Bounded setup command timings/output', setup_failed='Any setup failure', resolved='Harness verdict', exit_code='Verification exit code or null',
                          error='Sanitized failure category or null', llm_turns='LLM calls or null', tool_calls='Total and per_tool requests',
                          tool_seconds='Per-tool n,total,max call->response seconds, FIFO per name', test_run='Test requests n, matched total_seconds, share_of_agent_seconds',
                          prompt_tokens='Trace usage or null', completion_tokens='Trace usage or null', completion_tokens_per_second='Completion usage / agent seconds or null',
                          patch_bytes='UTF-8 diff bytes before stripping', patch_files='Diff paths', test_files_edited='Protected/test target paths',
                          stray_files='New files outside package Python source', empty_patch='Blank diff', timed_out='Timeout error or exit 124',
                          platform_probe='Header (P2): docker binary/socket, DNS + one 10 s TCP connect to pypi.org:443, no payload',
                          stock_setup='P1: stock subprocess setup sequence on the same snapshot, run before the task (outside its Phase-1): total_s, steps_s, error',
                          llm_calls='P3: per usage-bearing trace entry: t since first entry, gap_s since previous entry, tokens'))
        # Write the header even if installation or extraction fails; enrich before startup.
        try:
            header['bundle_sha256'], header['agent_yaml_sha256'] = extract_bundle(BUNDLE_B64, BUNDLE)
            print('bundle_sha256=', header['bundle_sha256'], 'agent_yaml_sha256=', header['agent_yaml_sha256'], flush=True)
            header['platform_probe'] = platform_probe()  # P2: <= ~20 s, no payload
            print('platform_probe=', header['platform_probe'], flush=True)
            gpu_preflight()  # cheap fail-fast before the multi-minute install (torch check below stays authoritative)
            install()
            check_hook_targets()  # fail before vLLM startup if the wheelhouse swegemma lacks the hook targets
            if os.environ.get('SETUP_FIX') == '1':  # only the fixed path installs the line-9 tools
                check_tool_sources(DATA / 'wheels' if (DATA / 'wheels').is_dir() else WHEELHOUSE)  # same choice as patch_subprocess_deps
            try:
                import mcp  # noqa: F401
                header['mcp_import_ok'] = True
            except Exception:
                header['mcp_import_ok'] = False
            print('import mcp:', header['mcp_import_ok'], flush=True)
            import torch
            import yaml
            import litellm
            from google.adk.agents.context_cache_config import ContextCacheConfig
            from google.adk.apps._configs import EventsCompactionConfig
            from swegemma.config import EvalConfig, build_submission_limits
            litellm.drop_params = True
            header.update(gpu_count=torch.cuda.device_count(), gpu_names=[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())])
            # Fail fast (saves quota) if Kaggle fell back to another accelerator (v2 silently got T4 x2).
            if header['gpu_count'] < 4 or not all('L4' in n for n in header['gpu_names']):
                raise WrongAccelerator('expected 4x L4')
            cfg_file = next((BUNDLE / n for n in ('eval_config.yaml', 'eval_config.yml') if (BUNDLE / n).is_file()), None)
            raw = (yaml.safe_load(cfg_file.read_text()) or {}) if cfg_file else {}
            section = raw.get('evaluation', raw)
            turns = section.get('max_turns', section.get('max_llm_calls'))
            caps = dict(timeout_seconds=int(section.get('timeout_seconds', 300)), verification_timeout_seconds=int(section.get('verification_timeout_seconds', 300)),
                        max_tool_calls=int(section.get('max_tool_calls', 100)), max_time_minutes=float(section.get('max_time_minutes', 60.0)), max_turns=int(turns) if turns is not None else None)
            header['caps'] = caps
            server, adapters, model, startup = start_server(servers)
            header['vllm_startup_seconds'] = startup
            append(journal, header)
            append(journal, {'_vllm': dict(startup_seconds=startup)})
            models = server.create_model_registry(aliases=[model], model_prefix='openai/', api_key=os.environ.get('LOCAL_API_KEY', 'EMPTY'))
            limits, constraints = build_submission_limits()
            config = EvalConfig(tasks_path=DATA / 'tasks.jsonl', snapshots_dir=DATA / 'snapshots', results_dir=WORK / 'runs', submission_dir=BUNDLE,
                models=models, sandbox='subprocess', **caps, limits=limits, generation_constraints=constraints, adapter_manifest=adapters,
                context_cache_config=ContextCacheConfig(min_tokens=2048, ttl_seconds=1800, cache_intervals=10),
                events_compaction_config=EventsCompactionConfig(compaction_interval=15, overlap_size=2, token_threshold=14336, event_retention_size=5),
                graph_dir=str(DATA / 'graphs'), embeddings_dir=str(DATA / 'embeddings'), wheels_dir=DATA / 'wheels', verbose=False)
            asyncio.run(evaluate(config, journal, started, caps, totals))
        except BaseException as exc:
            if journal.tell() == 0:
                append(journal, header)
            append(journal, {'_stopped': 'Kernel exception (' + type(exc).__name__ + ')'})
            raise
        finally:
            try:
                for server in servers:
                    server.stop()
            finally:
                append(journal, {'_done': dict(n=len(totals), total_seconds=distribution(totals), startup_seconds=startup)})

if __name__ == '__main__':
    main()
