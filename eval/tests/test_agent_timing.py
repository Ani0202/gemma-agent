"""Offline timing-kernel generation, instrumentation and runtime-gate checks."""
import ast
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import py_compile
import subprocess
from types import SimpleNamespace as Entry

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'eval/kaggle' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


timing = load('agent_timing')
summary = load('timing_summary')


def test_generated_script_and_bundle(tmp_path):
    bundle = tmp_path / 'bundle'
    bundle.mkdir()
    (bundle / 'agent.yaml').write_text('model: gemma-4-e4b-it-qat-w4a16-ct\n')
    (bundle / 'prompt.md').write_text('example prompt')
    ids = tmp_path / 'ids'
    ids.write_text('task-1\ntask-2\n')
    proc = subprocess.run(['bash', str(ROOT / 'eval/kaggle/timing_push.sh'), '--dry-run',
                           'example/timing-test', str(bundle), str(ids), '1000'], check=True, capture_output=True, text=True)
    stage = Path(proc.stdout.split('Dry run: no push. Staged: ')[1].strip())
    try:
        generated = stage / 'agent_timing.py'
        py_compile.compile(str(generated), cfile=str(tmp_path / 'compiled.pyc'), doraise=True)
        tree = ast.parse(generated.read_text())
        constants = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body
                     if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                     and n.targets[0].id in ('BUNDLE_B64', 'TASK_IDS', 'GIT_SHA', 'KERNEL_BUDGET_SECONDS')}
        assert constants['TASK_IDS'] == ['task-1', 'task-2']
        assert constants['KERNEL_BUDGET_SECONDS'] == 1000
        assert len(constants['GIT_SHA']) == 40
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom):
                assert not n.level and not n.module.startswith(('eval', 'gold_calibration', 'run_agent_eval'))
            if isinstance(n, ast.Import):
                assert all(not a.name.startswith(('eval.', 'gold_calibration', 'run_agent_eval')) for a in n.names)
        digest, yaml_digest = timing.extract_bundle(constants['BUNDLE_B64'], tmp_path / 'extracted')
        assert digest == hashlib.sha256(base64.b64decode(constants['BUNDLE_B64'])).hexdigest()
        assert yaml_digest == hashlib.sha256((bundle / 'agent.yaml').read_bytes()).hexdigest()
        assert (tmp_path / 'extracted/prompt.md').read_text() == 'example prompt'
        metadata = json.loads((stage / 'kernel-metadata.json').read_text())
        assert metadata['model_sources'] == ['google/gemma-4/Other/gemma-4-e4b-it-qat-w4a16-ct/2']
        assert metadata['docker_image'].startswith('gcr.io/kaggle-private-byod/python@sha256:')
        assert metadata['kernel_type'] == 'script'
        assert metadata['enable_gpu'] is True and metadata['enable_internet'] is False
    finally:
        import shutil
        shutil.rmtree(stage)


def trace_entry(event, timestamp, command='', tool='run_command'):
    return Entry(event_type=event, timestamp=timestamp, tool_name=tool, tool_args={'command': command}, usage=None)


@pytest.mark.parametrize('command', ['pytest -q', 'python -m unittest', 'tox', 'nox -s test', './run_tests.sh'])
def test_test_run_classification(command):
    trace = Entry(entries=[trace_entry('tool_call', 1, command), trace_entry('tool_response', 4),
                           trace_entry('tool_call', 5, 'ls'), trace_entry('tool_response', 7),
                           trace_entry('tool_call', 8, command, 'read_file'), trace_entry('tool_response', 9, tool='read_file')])
    assert timing.test_run_stats(trace, 10) == dict(n=1, total_seconds=3, share_of_agent_seconds=.3)
    assert timing.tool_seconds(trace.entries)['run_command'] == dict(n=2, total=5, max=3)
    assert timing.trace_counts(trace)[1] == dict(prompt_tokens=None, completion_tokens=None)


def test_unmatched_test_call_and_fifo():
    trace = Entry(entries=[trace_entry('tool_call', 1, 'ls'), trace_entry('tool_call', 2, 'pytest'),
                           trace_entry('tool_response', 4), trace_entry('tool_response', 7),
                           trace_entry('tool_call', 8, 'pytest')])
    assert timing.test_run_stats(trace, 10) == dict(n=2, total_seconds=5, share_of_agent_seconds=.5)


def test_timebox_boundary():
    assert not timing.should_stop(100, 5, 300, 0, 1000)
    assert timing.should_stop(100.01, 5, 300, 0, 1000)
    assert timing.should_stop(100, 5, 300, 601, 1000)


@pytest.fixture(autouse=True)
def _kernel_work_dir(monkeypatch, tmp_path):
    """Kernel writes (e.g. extra_wheels) go to a temp dir, never /kaggle/working; tests may override."""
    monkeypatch.setattr(timing, 'WORK', tmp_path / 'kernel-work')


def journal(path, cap=5.04, startup=1800, seconds=302.4):
    header = dict(_schema='kaggle_timing_v1', task_ids=['a', 'b'], caps={'max_time_minutes': cap})
    rows = [dict(instance_id=iid, wall_seconds={'total': seconds}, test_run=dict(n=n, share_of_agent_seconds=share),
                 empty_patch=n == 0, test_files_edited=['tests/test_a.py'] if n else [], stray_files=['x'] if n else [])
            for iid, n, share in [('a', 0, 0), ('b', 2, .5)]]
    path.write_text('\n'.join(json.dumps(r) for r in [header, {'_vllm': {'startup_seconds': startup}}, *rows, {'_done': {'n': 2}}]) + '\n')


def test_summary_boundary_and_cli(tmp_path):
    path, output = tmp_path / 'timing.jsonl', tmp_path / 'summary.json'
    journal(path)
    result = summary.summarize(path)
    assert result['legacy_projection_decision'] == 'PASS'
    assert result['projected_minutes'] == 660
    assert result['cap_worst_case_minutes'] == 660
    assert result['test_run_share']['p90'] == .45
    assert result['test_runs_per_task']['mean'] == 1
    assert result['test_runs_per_task']['max'] == 2
    assert result['n'] == 2 and result['vllm_startup_seconds'] == 1800
    assert result['empty_patch_count'] == result['test_files_edited_count'] == result['stray_files_count'] == 1
    subprocess.run(['python3', str(ROOT / 'eval/kaggle/timing_summary.py'), str(path), '--output', str(output)], check=True, capture_output=True)
    assert json.loads(output.read_text())['_schema'] == 'kaggle_timing_summary_v1'
    journal(path, seconds=302.40001)
    assert summary.summarize(path)['legacy_projection_decision'] == 'FAIL'
    journal(path, cap=5.04001)
    assert summary.summarize(path)['legacy_projection_decision'] == 'FAIL'


def test_summary_rejects_dropped_or_duplicate_rows(tmp_path):
    path = tmp_path / 'timing.jsonl'
    journal(path)
    rows = path.read_text().splitlines()
    path.write_text('\n'.join(rows[:2] + rows[3:]))
    with pytest.raises(ValueError, match='Done count'):
        summary.summarize(path)


def test_kernel_exception_still_writes_header_and_done(tmp_path, monkeypatch):
    import io
    import tarfile
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as archive:
        payload = b'model: gemma-4-e4b-it-qat-w4a16-ct\n'
        info = tarfile.TarInfo('agent.yaml')
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    monkeypatch.setattr(timing, 'BUNDLE_B64', base64.b64encode(stream.getvalue()).decode())
    monkeypatch.setattr(timing, 'WORK', tmp_path)
    monkeypatch.setattr(timing, 'BUNDLE', tmp_path / 'bundle')
    def fail_install():
        raise RuntimeError('TASK_TEXT_SECRET')
    monkeypatch.setattr(timing, 'install', fail_install)
    with pytest.raises(RuntimeError):
        timing.main()
    text = (tmp_path / 'timing.jsonl').read_text()
    rows = [json.loads(line) for line in text.splitlines()]
    assert rows[0]['_schema'] == 'kaggle_timing_v1'
    assert rows[0]['agent_yaml_sha256'] == hashlib.sha256(payload).hexdigest()
    assert rows[-1]['_done']['n'] == 0
    assert rows[-1]['_done']['startup_seconds'] is None
    assert rows[-2] == {'_stopped': 'Kernel exception (RuntimeError)'}
    assert 'TASK_TEXT_SECRET' not in text



def test_wheels_follow_sandbox_abi(tmp_path):
    for name in ['native-1-cp312-cp312-manylinux_2_17_x86_64.whl',
                 'native-2-cp313-cp313-manylinux_2_17_x86_64.whl',
                 'native-3-cp312-cp312-win_amd64.whl', 'pure-1-py3-none-any.whl']:
        (tmp_path / name).touch()
    selected = timing.compatible_wheels(tmp_path, ['cp312-cp312-manylinux_2_17_x86_64', 'py3-none-any'])
    assert selected['native'].name.startswith('native-1-')
    assert selected['pure'].name == 'pure-1-py3-none-any.whl'


@pytest.mark.parametrize('setup_rc', [0, 7])
@pytest.mark.parametrize('missing_dep', [False, True])
@pytest.mark.parametrize('workspace_rc', [0, 9])
def test_injected_install_bootstraps_and_retains_failure(tmp_path, monkeypatch, setup_rc, missing_dep, workspace_rc):
    monkeypatch.setenv('SETUP_FIX', '1')
    import contextvars
    import sys
    import tarfile
    import zipfile
    from types import ModuleType, SimpleNamespace
    cs = ModuleType('swegemma.harness.container_setup')
    cs.install_test_dependencies = lambda *a, **k: None
    cs._LARGE_WHEEL_THRESHOLD_BYTES = 20 * 1024 * 1024
    archive = tmp_path / 'base.tar'
    with tarfile.open(archive, 'w') as tf:
        import io
        info = tarfile.TarInfo('package.py')
        info.size = 1
        tf.addfile(info, io.BytesIO(b'x'))
    selections = []
    def build(wheels, key, marker):
        selections.extend(wheels)
        assert key.startswith('timing_')
        return archive
    cs._build_unpacked_wheels_tar = build
    for name in ['swegemma', 'swegemma.harness']:
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    monkeypatch.setitem(sys.modules, 'swegemma.harness.container_setup', cs)
    wheels = tmp_path / 'wheels'
    wheels.mkdir()
    for tool in timing.SCORER_TOOLS:
        version = '2.1.0' if tool == 'pytest-timeout' else '1.0'
        make_wheel(wheels, tool, version)
    (tmp_path / 'sandbox').mkdir()
    (tmp_path / 'sandbox/setup.py').touch()
    sp = tmp_path / 'venv/lib/python3.12/site-packages'
    sp.mkdir(parents=True)
    commands = []
    (tmp_path / 'tmp').mkdir()
    class SubprocessManager:
        sandboxes = {'id': {'venv': tmp_path / 'venv', 'tmp': tmp_path / 'tmp'}}
        def copy_to(self, *args):
            pass
        def exec(self, sid, command, **kw):
            commands.append(command)
            if 'PackageNotFoundError' in command:
                return SimpleNamespace(exit_code=0, stdout=json.dumps({'repo': dict(location='/sandbox/site', version='1', record_exists=True)}), stderr='')
            if 'sys_tags' in command:
                return SimpleNamespace(exit_code=0, stdout=json.dumps(dict(version='3.12', tags=['py3-none-any'], environment=sandbox_markers())), stderr='')
            return SimpleNamespace(exit_code=setup_rc if '/tmp/setup.py' in command else (workspace_rc if '-e /workspace' in command else (1 if 'pip check' in command else 0)),
                                   stdout='x' * 5000, stderr='é' * 5000)
    current = dict(started=timing.time.perf_counter(), setup_calls=[], setup_failed=False)
    state = contextvars.ContextVar('test_setup')
    state.set(current)
    install = timing.patch_subprocess_deps(tmp_path, state)
    if missing_dep:
        monkeypatch.setattr(timing, 'close_tool_dependencies', lambda *a: ([], ['required-child']))
        with pytest.raises(RuntimeError, match='missing_tool_deps'):
            install(SubprocessManager(), 'id', 'example/repo')
        assert current['setup_failed'] and current['status'] == 'failed'
        assert current['reason'] == 'missing_tool_deps'
        assert current['missing_tool_deps'] == ['required-child']
        assert not selections
        assert current['setup_calls'][-1]['step'] == 'tool_deps'
        return
    install(SubprocessManager(), 'id', 'example/repo')
    assert current['setup_failed'] == bool(setup_rc or workspace_rc)
    assert current['editable_failed'] == bool(workspace_rc)
    assert current['setup_calls'][-1]['rc'] == setup_rc
    assert [r['step'] for r in current['setup_calls']] == [
        'venv_fidelity', 'pip_bootstrap', 'interpreter_probe', 'tool_sources',
        'pytest_timeout_source', 'tool_install', 'tool_deps', 'pip_check',
        'workspace_editable', 'base_tar_extraction', 'setup.py']
    assert all(len(r['stdout'].encode()) <= 2048 and len(r['stderr'].encode()) <= 2048
               and r['duration_s'] >= 0 and r['start_offset_s'] >= 0 for r in current['setup_calls'])
    assert commands[-2].startswith('python3 /tmp/setup_observer.py /tmp/setup.py')
    for step in ('workspace_editable', 'base_tar_extraction', 'setup.py'):
        row = next(c for c in current['setup_calls'] if c['step'] == step)
        assert row['distributions']['repo']['record_exists'] is True
    assert next(i for i,c in enumerate(commands) if 'install --ignore-installed' in c) < next(i for i,c in enumerate(commands) if '-e /workspace' in c)
    assert any('--no-index --find-links=/wheels --no-deps' in c for c in commands)
    assert current['missing_tool_deps'] == []
    assert next(r for r in current['setup_calls'] if r['step'] == 'pip_check')['rc'] == 1
    assert 'pip' not in [p.name.split('-')[0] for p in selections]
    (wheels / 'hatchling-1.0-py3-none-any.whl').unlink()
    with pytest.raises(RuntimeError, match='hatchling'):
        install(SubprocessManager(), 'id')
    assert current['setup_calls'][-1]['rc'] == -1


def test_gold_single_file_staging_still_compiles(tmp_path):
    generated = tmp_path / 'gold.py'
    load('stage_kernel').stage_kernel(generated)
    compile(generated.read_text(), str(generated), 'exec')
    assert '_shared_env = types.ModuleType' in generated.read_text()
    assert '# BEGIN SHARED ENV IMPORT' not in generated.read_text()


def sandbox_markers():
    from packaging.markers import default_environment
    return dict(default_environment(), python_version='3.12', python_full_version='3.12.0')


def make_wheel(directory, name, version='1.0', requires=()):
    import zipfile
    normalized = name.replace('-', '_')
    path = directory / f'{normalized}-{version}-py3-none-any.whl'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr(f'{normalized}-{version}.dist-info/METADATA',
                         f'Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n' +
                         ''.join(f'Requires-Dist: {req}\n' for req in requires))
    return path


def test_dependency_closure_markers_extras_and_cycles(tmp_path, monkeypatch):
    root = make_wheel(tmp_path, 'root', requires=[
        'dep>=1; python_version < "3.13"', 'wrong; python_version >= "3.13"',
        'optional; extra == "test"'])
    dep = make_wheel(tmp_path, 'dep', requires=['root', 'leaf[optional]'])
    make_wheel(tmp_path, 'leaf', requires=['excluded; extra == "optional"'])
    calls = []
    def install(path):
        calls.append(path.name)
        return Entry(exit_code=0, stdout='', stderr='')
    def no_runtime(*args):
        pytest.fail('wheelhouse must be preferred')
    monkeypatch.setattr(timing, 'copy_runtime_package', no_runtime)
    entries, missing = timing.close_tool_dependencies(
        [timing.wheel_metadata(root)], tmp_path, ['py3-none-any'], sandbox_markers(),
        tmp_path / 'site', install)
    assert not missing
    assert [e['name'] for e in entries] == ['dep', 'root', 'leaf']
    assert entries[0]['source'] == str(dep)
    assert entries[0]['version_installed'] == '1.0'
    assert len(calls) == 2


def test_dependency_closure_runtime_and_missing(tmp_path, monkeypatch):
    import importlib.metadata
    root = make_wheel(tmp_path, 'root', requires=['runtime-package>=2', 'absent', 'old>=2'])
    runtime = timing.wheel_metadata(make_wheel(tmp_path, 'metadata', requires=['transitive']))
    runtime.replace_header('Name', 'runtime-package')
    runtime.replace_header('Version', '2.0')
    from importlib.metadata import PackageNotFoundError
    def distribution(name):
        if name == 'runtime-package':
            return Entry(version='2.0', metadata=runtime)
        if name == 'old':
            return Entry(version='1.0', metadata=runtime)
        raise PackageNotFoundError(name)
    monkeypatch.setattr(importlib.metadata, 'distribution', distribution)
    copies = []
    def copy(name, destination):
        copies.append(name)
        return 'runtime-site-packages:/image'
    monkeypatch.setattr(timing, 'copy_runtime_package', copy)
    entries, missing = timing.close_tool_dependencies(
        [timing.wheel_metadata(root)], tmp_path, ['py3-none-any'], sandbox_markers(),
        tmp_path / 'site', lambda path: pytest.fail('no matching wheel'))
    assert copies == ['runtime-package']
    assert missing == ['absent', 'old', 'transitive']
    assert entries[0]['source'] == 'runtime-site-packages:/image'
    assert entries[0]['version_installed'] == '2.0'
    assert entries[1]['source'] == 'missing' and entries[1]['version_installed'] is None


def test_dependency_closure_selects_satisfying_wheel(tmp_path):
    root = make_wheel(tmp_path, 'root', requires=['dep<2'])
    expected = make_wheel(tmp_path, 'dep')
    make_wheel(tmp_path, 'dep', '2.0')
    calls = []
    def install(path):
        calls.append(path)
        return Entry(exit_code=0, stdout='', stderr='')
    entries, missing = timing.close_tool_dependencies(
        [timing.wheel_metadata(root)], tmp_path, ['py3-none-any'], sandbox_markers(),
        tmp_path / 'site', install)
    assert calls == [expected] and not missing
    assert entries[0]['required_spec'] == '<2'


def test_copy_runtime_package_handles_distribution_import_names(tmp_path, monkeypatch):
    import importlib.metadata
    source = tmp_path / 'image'
    (source / 'trove_classifiers').mkdir(parents=True)
    (source / 'trove_classifiers/__init__.py').write_text('')
    (source / 'trove_classifiers-1.dist-info').mkdir()
    (source / 'trove_classifiers-1.dist-info/METADATA').write_text('Name: trove-classifiers')
    files = [importlib.metadata.PackagePath(str(p.relative_to(source)))
             for p in source.rglob('*') if p.is_file()]
    monkeypatch.setattr(importlib.metadata, 'distribution', lambda name: Entry(
        version='1', files=files, locate_file=lambda path: source / path))
    dest = tmp_path / 'site'
    assert timing.copy_runtime_package('trove-classifiers', dest).startswith('runtime-site-packages:')
    assert (dest / 'trove_classifiers/__init__.py').exists()
    files.append(importlib.metadata.PackagePath('native.so'))
    assert timing.copy_runtime_package('trove-classifiers', dest) == 'missing'


def test_diagnostic_step_exception_is_nonfatal():
    current = dict(started=timing.time.perf_counter(), setup_calls=[], setup_failed=False)
    def fail():
        raise TimeoutError('private output')
    timing.setup_step(current, 'pip_check', fail, fatal=False)
    assert not current['setup_failed']
    assert current['setup_calls'][0]['rc'] == -1
    assert current['setup_calls'][0]['stderr'] == 'TimeoutError'


def test_dependency_closure_expands_already_installed_base_wheel(tmp_path):
    import zipfile
    root = make_wheel(tmp_path, 'root', requires=['base-package>=1'])
    base = make_wheel(tmp_path, 'base-package', requires=['missing-child'])
    site = tmp_path / 'site'
    with zipfile.ZipFile(base) as archive:
        archive.extractall(site)
    entries, missing = timing.close_tool_dependencies(
        [timing.wheel_metadata(root)], tmp_path, ['py3-none-any'], sandbox_markers(), site,
        lambda path: pytest.fail('satisfied base wheel should not be installed again'))
    assert entries[0]['source'] == str(base)
    assert entries[0]['version_installed'] == '1.0'
    assert missing == ['missing-child']


@pytest.mark.parametrize('with_verification', [False, True])
def test_dry_run_verification_constant(tmp_path, with_verification):
    ids = tmp_path / 'ids'
    ids.write_text('task-1\n')
    flags = ['--with-verification', '--dry-run'] if with_verification else ['--dry-run']
    proc = subprocess.run(['bash', str(ROOT / 'eval/kaggle/timing_push.sh'), *flags,
        'x/y', str(ROOT / 'bundles/e4b/v001'), str(ids)], check=True, capture_output=True, text=True)
    stage = Path(proc.stdout.split('Dry run: no push. Staged: ')[1].strip())
    try:
        source = (stage / 'agent_timing.py').read_text()
        compile(source, 'generated.py', 'exec')
        node = next(n for n in ast.parse(source).body if isinstance(n, ast.Assign)
                    and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'SKIP_VERIFICATION')
        assert ast.literal_eval(node.value) is (not with_verification)
    finally:
        import shutil
        shutil.rmtree(stage)


@pytest.mark.parametrize('fired', [False, True])
@pytest.mark.parametrize('error', [None, TimeoutError('timeout'), ValueError('other')])
def test_timeout_proxy_preserves_context_and_exceptions(monkeypatch, fired, error):
    import asyncio
    from contextvars import ContextVar
    state = ContextVar('timeout')
    state.set({})
    now = iter([10, 15])
    monkeypatch.setattr(timing.time, 'perf_counter', lambda: next(now))
    marker, calls = object(), []
    class CM:
        async def __aenter__(self):
            return marker
        async def __aexit__(self, *exc):
            calls.append(exc)
            return False
        def expired(self):
            return fired
    def timeout(*args, **kwargs):
        assert args == (84,) and kwargs == {}
        return CM()
    original = Entry(timeout=timeout, sleep=asyncio.sleep)
    proxy = timing.AsyncioTimingProxy(original, state)
    assert proxy.sleep is asyncio.sleep
    async def run():
        async with proxy.timeout(84) as value:
            assert value is marker
            if error:
                raise error
    if error:
        with pytest.raises(type(error)) as caught:
            asyncio.run(run())
        assert caught.value is error
    else:
        asyncio.run(run())
    assert calls[0][1] is error
    assert state.get() == dict(agent_timeout_seconds=84, timeout_enter=10,
        timeout_exit=15, agent_timeout_fired=fired or isinstance(error, TimeoutError))


def test_real_timeout_proxy_expiration():
    import asyncio
    from contextvars import ContextVar
    state = ContextVar('real_timeout')
    state.set({})
    async def run():
        async with timing.AsyncioTimingProxy(asyncio, state).timeout(0):
            await asyncio.sleep(0)
    with pytest.raises(TimeoutError):
        asyncio.run(run())
    assert state.get()['agent_timeout_fired'] is True


@pytest.mark.parametrize('name', ['sandbox_start', 'sandbox_stop', 'sandbox_exec'])
@pytest.mark.parametrize('error', [None, RuntimeError('same'), TimeoutError('same')])
def test_sandbox_wrapper_forwarding(monkeypatch, name, error):
    import asyncio
    from contextvars import ContextVar
    current = dict(timeout_exit=1)
    state = ContextVar('sandbox')
    state.set(current)
    times = iter([3, 7])
    monkeypatch.setattr(timing.time, 'perf_counter', lambda: next(times))
    marker = Entry(exit_code=9)
    args, kwargs = (object(), 'sandbox', 'a' * 60), dict(timeout=31)
    async def original(*a, **kw):
        assert a == args and kw == kwargs
        if error:
            raise error
        return marker
    wrapped = timing.observe_sandbox(original, state, name)
    if error:
        with pytest.raises(type(error)) as caught:
            asyncio.run(wrapped(*args, **kwargs))
        assert caught.value is error
    else:
        assert asyncio.run(wrapped(*args, **kwargs)) is marker
    if name == 'sandbox_exec':
        expected = dict(cmd='a' * 40, duration_s=4, rc=None if error else 9)
        if error:
            expected['exception'] = type(error).__name__
        assert current['finalization_exec'] == [expected]
    else:
        assert current[name + '_duration'] == 4
        assert current[name + '_end'] == 7
        if name == 'sandbox_start':
            assert current['sandbox_start_begin'] == 3


def test_finalization_only_after_timeout_and_phase_fields():
    import asyncio
    from contextvars import ContextVar
    current = {}
    state = ContextVar('finalization')
    state.set(current)
    async def original(*a, **kw):
        return Entry(exit_code=0)
    wrapped = timing.observe_sandbox(original, state, 'sandbox_exec')
    asyncio.run(wrapped(None, 'id', 'before'))
    assert 'finalization_exec' not in current
    current.update(sandbox_start_begin=1, timeout_enter=4, timeout_exit=10,
                   sandbox_stop_end=15, sandbox_stop_duration=2)
    asyncio.run(wrapped(None, 'id', 'after'))
    assert [c['cmd'] for c in current['finalization_exec']] == ['after']
    fields = timing.phase1_fields(current, 14, 20, Entry(patch_submitted=False), 'diff')
    assert fields['phase1_wall_seconds'] == 14
    assert fields['phase1_source'] == 'sandbox_wrappers'
    assert fields['pre_agent_seconds'] == 3
    assert fields['agent_clock_seconds'] == 6
    assert fields['finalization_seconds'] == 5
    assert fields['teardown_seconds'] == 2
    assert fields['post_phase1_seconds'] == 6
    assert fields['fallback_patch_used'] is True
    fields = timing.phase1_fields({}, 2, 3, None, '')
    assert fields['phase1_wall_seconds'] == 2 and fields['phase1_source'] == 'run_agent_sandbox'
    assert fields['agent_clock_seconds'] is fields['agent_timeout_fired'] is None
    assert fields['patch_submitted'] is fields['fallback_patch_used'] is None


@pytest.mark.parametrize('failure', [None, 'runner', 'setup', 'cleanup'])
@pytest.mark.parametrize('skip', [True, False])
def test_skip_verification_result_and_task_row(tmp_path, monkeypatch, failure, skip, budget_scenario=None):
    import asyncio
    from contextvars import ContextVar
    import dataclasses
    import sys
    from types import ModuleType
    modules = {}
    for name in ('swegemma', 'swegemma.evaluate', 'swegemma.models', 'swegemma.harness',
                 'swegemma.harness.verification', 'swegemma.harness.agent_runner'):
        modules[name] = ModuleType(name)
        monkeypatch.setitem(sys.modules, name, modules[name])
    ev, vf, ar, models = [modules['swegemma.' + n] for n in (
        'evaluate', 'harness.verification', 'harness.agent_runner', 'models')]
    class TaskResult(Entry):
        tool_calls = 0
        def model_dump(self, **kwargs):
            return vars(self)
    models.TaskResult = TaskResult
    task = dataclasses.make_dataclass('Task', [('instance_id', str), ('repo', str),
        ('patch', str), ('test_patch', str), ('FAIL_TO_PASS', tuple), ('PASS_TO_PASS', tuple),
        ('test_files', tuple)])('task', 'org/repo', '', '', (), (), ())
    result = asyncio.run(timing.skip_verification(None, None, task, None, agent_patch='diff'))
    assert isinstance(result, TaskResult)
    assert result.resolved is False and result.test_exit_code is None
    assert result.agent_patch == 'diff' and result.error is None and result.trace is None
    assert timing.harness_error(result, '') is None
    assert timing.harness_error(result, 'Sandbox execution error: failed') == 'Harness task failure'
    models.load_tasks = lambda path: [task]
    verification_calls = []
    async def original_verify(*a, **kw):
        assert not skip, 'real verification must not run when skipped'
        verification_calls.append((a, kw))
        result = await timing.skip_verification(*a, **kw)
        result.resolved, result.test_exit_code = True, 0
        return result
    ev.verify_task = original_verify
    vf.strip_protected_files_from_patch = lambda patch, **kw: patch
    vf._is_protected_test_or_config_path = lambda path: False
    ar.asyncio = asyncio
    async def sandbox(*a, **kw):
        if failure == 'setup':
            raise RuntimeError('container setup failed')
        return 'sid'
    ar.sandbox_start = ar.sandbox_stop = ar.sandbox_exec = sandbox
    originals = dict(vars(ar))
    class Evaluator:
        def __init__(self, config):
            assert budget_scenario is None, "measured task must not start"
            def cleanup():
                if failure == 'cleanup':
                    raise RuntimeError('cleanup failed')
            self.docker = Entry(start=lambda: None, cleanup_all=cleanup)
        async def _run_agent_sandbox(self, task, *args, **kw):
            assert not task.patch and not task.test_patch
            if failure == 'runner':
                raise RuntimeError('runner failed')
            sid = await ar.sandbox_start(self.docker)
            async with ar.asyncio.timeout(10):
                pass
            await ar.sandbox_stop(self.docker, sid)
            return 'diff --git a/repo/a.py b/repo/a.py\n', '', None
        async def evaluate_task(self, task):
            context = Entry(task=task, patch_submitted=False, llm_calls_used=0)
            patch, error, trace = await self._run_agent_sandbox(task, context=context)
            return await ev.verify_task(self.docker, None, task, None,
                                        agent_patch=patch, agent_error=error, trace=trace)
    ev.Evaluator = Evaluator
    monkeypatch.setattr(timing, 'TASK_IDS', ['task'])
    monkeypatch.setattr(timing, 'WORK', tmp_path)
    monkeypatch.setattr(timing, 'SKIP_VERIFICATION', skip)
    monkeypatch.setattr(timing, 'patch_subprocess_deps', lambda *a: None)
    seen = []
    monkeypatch.setattr(timing, 'should_stop', lambda *a: seen.append(a) or False)
    totals = []
    if budget_scenario:
        # Review example: 5200 + 1.5*463 fits 6000, but P1's reservation does not.
        # The second case admits P1, then catches an unexpectedly long fake probe.
        clock = [5200.0 if budget_scenario == 'reserve' else 5000.0]
        real_should_stop = load('agent_timing').should_stop
        monkeypatch.setattr(timing.time, 'monotonic', lambda: clock[0])
        monkeypatch.setenv('KERNEL_BUDGET_SECONDS', '6000')
        monkeypatch.setattr(timing, 'STOCK_PROBE', True)
        monkeypatch.setattr(timing, 'should_stop', lambda *a: seen.append(a) or real_should_stop(*a))
        probes = []
        def fake_probe(*args):
            probes.append(True)
            clock[0] += 360
            return dict(total_s=360, error='deadline', steps_s={})
        monkeypatch.setattr(timing, 'stock_setup_probe', fake_probe)
        totals = [463.0]
    with (tmp_path / 'journal').open('w+') as stream:
        asyncio.run(timing.evaluate(Entry(tasks_path=None), stream, 0 if budget_scenario else timing.time.monotonic(),
                    dict(max_time_minutes=1.4, verification_timeout_seconds=300), totals))
        stream.seek(0)
        row = json.loads(stream.read())
    if budget_scenario:
        assert row == {'_stopped': 'insufficient remaining budget for next task'}
        assert len(probes) == (0 if budget_scenario == 'reserve' else 1)
        assert len(seen) == (1 if budget_scenario == 'reserve' else 2)
        assert totals == [463.0]
        assert ev.verify_task is original_verify
        return
    assert row['verification_skipped'] is skip
    assert (row['error'] is not None) is bool(failure)
    verified = not skip and failure not in ('runner', 'setup')
    assert row['resolved'] is verified
    assert row['exit_code'] == (0 if verified else None)
    assert len(verification_calls) == int(verified)
    assert row['fallback_patch_used'] is (failure not in ('runner', 'setup'))
    assert row['phase1_source'] == ('run_agent_sandbox' if failure in ('runner', 'setup') else 'sandbox_wrappers')
    assert seen[0][2] == (0 if skip else 300)
    assert ev.verify_task is original_verify
    assert all(getattr(ar, key) is originals[key] for key in ('asyncio', 'sandbox_start', 'sandbox_stop', 'sandbox_exec'))


@pytest.mark.parametrize('key,value,check', [
    ('phase1_wall_seconds', 296.00001, 'b_max_phase1'),
    ('phase1_wall_seconds', 270.00001, 'c_mean_phase1'),
    ('phase1_source', 'run_agent_sandbox', 'a_all_tasks_complete_no_harness_error'),
    ('error', 'Harness task failure', 'a_all_tasks_complete_no_harness_error'),
    ('empty_patch', True, 'e_nonempty_source_diff'),
    ('phase1_wall_seconds', None, 'b_max_phase1'),
])
def test_summary_phase1_gate_edges(tmp_path, key, value, check):
    path = tmp_path / 'journal'
    journal(path, startup=600)
    records = [json.loads(s) for s in path.read_text().splitlines()]
    for row, phase1 in zip(records[2:4], [296, 244]):
        row.update(repo='org/repo', phase1_wall_seconds=phase1, sandbox_setup_seconds=10,
                   finalization_seconds=3, patch_files=['repo/a.py'], empty_patch=False,
                   test_files_edited=[], stray_files=[], error=None, agent_timeout_fired=True,
                   fallback_patch_used=True, setup_calls=[dict(step='setup.py', duration_s=10,
                       rc=0, retrying_lines=2, subprocesses=[dict(
                           argv=['python', '-m', 'pip', 'install', '-e', '.'], retrying_lines=2)])])
    def save():
        path.write_text('\n'.join(json.dumps(r) for r in records))
    save()
    result = summary.summarize(path)
    assert result['gate']['status'] == 'PASS'
    assert result['gate']['b_max_phase1']['value'] == 296
    assert result['gate']['c_mean_phase1']['value'] == 270
    assert result['n_complete_no_error'] == 2
    assert result['fallback_count'] == 6 and result['tasks_with_retrying_lines'] == 2
    assert result['timeout_fired_count'] == result['fallback_patch_count'] == 2
    assert result['tasks'][0]['nonempty_source_diff'] is True
    for row in records[2:4]:
        row[key] = value
    save()
    assert summary.summarize(path)['gate'][check]['status'] == 'FAIL'
    assert summary.summarize(path)['gate']['status'] == 'FAIL'


def test_summary_cli_thresholds(tmp_path):
    path, output = tmp_path / 'journal', tmp_path / 'summary'
    journal(path, startup=600.01)
    subprocess.run(['python3', str(ROOT / 'eval/kaggle/timing_summary.py'), str(path),
        '--output', str(output), '--gate-vllm-seconds', '600.01', '--gate-max-phase1', '300',
        '--gate-mean-phase1', '280', '--gate-min-nonempty', '0'], check=True, capture_output=True)
    assert json.loads(output.read_text())['gate']['d_vllm_seconds']['status'] == 'PASS'
    assert summary.summarize(path)['gate']['d_vllm_seconds']['status'] == 'FAIL'


def test_installed_agent_runner_observation_attributes():
    path = Path('/home/ubuntu/gemma-local/venv/lib/python3.13/site-packages/swegemma/harness/agent_runner.py')
    if not path.exists():
        pytest.skip('local swegemma source not installed')
    tree = ast.parse(path.read_text())
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(a.asname or a.name.split('.')[0] for a in node.names)
    assert {'asyncio', 'sandbox_start', 'sandbox_stop', 'sandbox_exec'} <= names


@pytest.mark.parametrize('error', [TimeoutError('exit timeout'), ValueError('exit other')])
def test_proxy_exit_exception_without_expired_is_unchanged(error):
    import asyncio
    from contextvars import ContextVar
    state = ContextVar('exit_error')
    state.set({})
    class CM:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *exc):
            raise error
    proxy = timing.AsyncioTimingProxy(Entry(timeout=lambda **kw: CM()), state)
    async def run():
        async with proxy.timeout(delay=4):
            pass
    with pytest.raises(type(error)) as caught:
        asyncio.run(run())
    assert caught.value is error
    assert state.get()['agent_timeout_fired'] is isinstance(error, TimeoutError)
    assert state.get()['agent_timeout_seconds'] == 4


def test_summary_incomplete_row_is_retained_and_fails_gate(tmp_path):
    path = tmp_path / 'journal'
    path.write_text('\n'.join(json.dumps(row) for row in [
        dict(_schema='kaggle_timing_v1', task_ids=['broken'], vllm_startup_seconds=500),
        dict(instance_id='broken', wall_seconds=dict(total=5), error='Row build exception')]))
    result = summary.summarize(path)
    assert result['n'] == 1 and result['n_complete_no_error'] == 0
    assert result['tasks'][0]['instance_id'] == 'broken'
    assert result['gate']['status'] == 'FAIL'


def test_kernel_header_contains_vllm_startup(tmp_path, monkeypatch):
    import io
    import sys
    import tarfile
    from types import ModuleType
    bundle_stream = io.BytesIO()
    with tarfile.open(fileobj=bundle_stream, mode='w:gz') as archive:
        payload = b'model: gemma-4-e4b-it-qat-w4a16-ct\n'
        info = tarfile.TarInfo('agent.yaml')
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    monkeypatch.setattr(timing, 'BUNDLE_B64', base64.b64encode(bundle_stream.getvalue()).decode())
    monkeypatch.setattr(timing, 'WORK', tmp_path)
    monkeypatch.setattr(timing, 'BUNDLE', tmp_path / 'bundle')
    monkeypatch.setattr(timing, 'install', lambda: None)
    monkeypatch.setattr(timing, 'gpu_preflight', lambda: None)
    monkeypatch.setattr(timing, 'check_hook_targets', lambda: None)
    monkeypatch.setattr(timing, 'check_tool_sources', lambda wheels: [])
    for name in ('mcp', 'torch', 'yaml', 'litellm', 'google', 'google.adk',
                 'google.adk.agents', 'google.adk.agents.context_cache_config',
                 'google.adk.apps', 'google.adk.apps._configs', 'swegemma', 'swegemma.config'):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    torch = sys.modules['torch']
    torch.cuda = Entry(device_count=lambda: 4, get_device_name=lambda i: 'L4')
    sys.modules['google.adk.agents.context_cache_config'].ContextCacheConfig = lambda **kw: kw
    sys.modules['google.adk.apps._configs'].EventsCompactionConfig = lambda **kw: kw
    sys.modules['swegemma.config'].EvalConfig = lambda **kw: kw
    sys.modules['swegemma.config'].build_submission_limits = lambda: (None, None)
    server = Entry(create_model_registry=lambda **kw: {}, stop=lambda: None)
    monkeypatch.setattr(timing, 'start_server', lambda holder: (server, None, 'model', 345.6))
    async def evaluate(*args):
        pass
    monkeypatch.setattr(timing, 'evaluate', evaluate)
    timing.main()
    rows = [json.loads(line) for line in (tmp_path / 'timing.jsonl').read_text().splitlines()]
    assert rows[0]['vllm_startup_seconds'] == 345.6
    assert rows[1]['_vllm']['startup_seconds'] == 345.6
    assert rows[-1]['_done']['startup_seconds'] == 345.6
    expected_fields = timing.phase1_fields({}, 0, 0, None, '').keys()
    assert set(expected_fields) <= rows[0]['fields'].keys()


# --- Builder fix (dec 029, ops/reviews/claude-review-fix5.md findings 1-3, 6, 9-11) ---

@pytest.mark.parametrize('message,outcome', [
    ('Agent exceeded session timeout (1.4 min)', 'timeout'),
    ('Agent exceeded turns budget (40 turns)', 'turns'),
    ('Agent exceeded maximum allowed LLM turns', 'turns'),
    ('Agent exceeded tool call budget (100 calls)', 'tool_calls'),
    ('Agent completed execution without calling submit_patch.', 'no_submit'),
    ('Sandbox execution error: boom', None),
    ('Something new', None),
    ('', None),
    (None, None),
])
def test_agent_outcome_and_harness_error(message, outcome):
    assert timing.agent_outcome(message) == outcome
    result = Entry(error=message)
    expected = None if (outcome is not None or not message) else 'Harness task failure'
    assert timing.harness_error(result, message) == expected
    assert timing.harness_error(None, message) == expected
    # A known agent outcome never masks a different, unknown result error.
    assert timing.harness_error(Entry(error='Evaluation broke'), message) == 'Harness task failure'


def test_image_emulation_seconds():
    calls = [dict(step='tool_install', duration_s=2.0), dict(step='pip_check', duration_s=0.5),
             dict(step='setup.py', duration_s=100.0), dict(step='venv_fidelity', duration_s=None)]
    assert timing.image_emulation_seconds(calls) == 2.5


@pytest.mark.parametrize('exec_result', ['rc', 'json', 'raise'])
def test_record_distributions_is_non_fatal(exec_result):
    def exec_(container_id, cmd, timeout):
        if exec_result == 'raise':
            raise TimeoutError('slow')
        return Entry(exit_code=1 if exec_result == 'rc' else 0, stdout='not json')
    row = {}
    timing.record_distributions(Entry(exec=exec_), 'cid', 'org/repo', row)
    assert row['dist_probe_error'] in ('rc', 'JSONDecodeError', 'TimeoutError')
    assert 'distributions' not in row


def _gate_journal(path, task_ids=('a', 'b'), done=True, stopped=None, **row_extra):
    header = dict(_schema='kaggle_timing_v1', task_ids=list(task_ids), caps={'max_time_minutes': 1.4},
                  git_sha='abc', bundle_sha256='b' * 64, agent_yaml_sha256='y' * 64, gpu_count=4)
    rows = [{**dict(instance_id=iid, repo='org/repo', wall_seconds={'total': 300}, phase1_wall_seconds=250,
                 phase1_source='sandbox_wrappers', image_emulation_seconds=3.0, sandbox_setup_seconds=10,
                 finalization_seconds=3, patch_files=['repo/a.py'], empty_patch=False, test_files_edited=[],
                 stray_files=[], error=None, agent_outcome='timeout', agent_timeout_fired=True,
                 setup_failed=False, editable_failed=False, setup_calls=[]), **row_extra}
            for iid in ('a', 'b')]
    records = [header, {'_vllm': {'startup_seconds': 400}}, *rows]
    if stopped:
        records.append({'_stopped': stopped})
    if done:
        records.append({'_done': {'n': len(rows)}})
    path.write_text('\n'.join(json.dumps(r) for r in records) + '\n')


def test_gate_a_passes_with_timeouts_and_nonfatal_setup_failures(tmp_path):
    path = tmp_path / 'j'
    _gate_journal(path, setup_failed=True, editable_failed=True)
    result = summary.summarize(path)
    assert result['gate']['a_all_tasks_complete_no_harness_error']['status'] == 'PASS'
    assert result['gate']['status'] == 'PASS'
    assert result['setup_failed_count'] == result['editable_failed_count'] == 2
    assert result['agent_outcome_counts'] == {'timeout': 2}
    assert result['phase1_minus_image_seconds']['max'] == 247
    assert result['provenance']['git_sha'] == 'abc' and result['provenance']['gpu_count'] == 4


@pytest.mark.parametrize('kwargs', [
    dict(task_ids=('a', 'b', 'c')),          # kernel stopped before the planned third task
    dict(done=False),                         # no _done record
    dict(stopped='insufficient remaining budget for next task'),
])
def test_gate_a_fails_on_incomplete_run(tmp_path, kwargs):
    path = tmp_path / 'j'
    _gate_journal(path, **kwargs)
    result = summary.summarize(path)
    assert result['gate']['n_expected'] == len(kwargs.get('task_ids', ('a', 'b')))
    assert result['gate']['a_all_tasks_complete_no_harness_error']['status'] == 'FAIL'
    assert result['gate']['status'] == 'FAIL'


def test_fallback_units_reported_separately(tmp_path):
    path = tmp_path / 'j'
    _gate_journal(path)
    records = [json.loads(x) for x in path.read_text().splitlines()]
    records[2]['setup_calls'] = [dict(step='setup.py', duration_s=1, rc=0, retrying_lines=5, subprocesses=[dict(
        argv=['python', '-m', 'pip', 'install', '-e', '.'], retrying_lines=5)])]
    path.write_text('\n'.join(json.dumps(r) for r in records))
    result = summary.summarize(path)
    assert result['fallback_invocations'] == 1 and result['retrying_lines_total'] == 5
    assert result['fallback_count'] == 6  # legacy combined figure kept for continuity


@pytest.mark.parametrize('lines,ok', [
    (['GPU %d: NVIDIA L4 (UUID: x)' % i for i in range(4)], True),
    (['GPU %d: Tesla T4 (UUID: x)' % i for i in range(2)], False),
    (['GPU 0: NVIDIA L4 (UUID: x)'], False),
])
def test_gpu_preflight(monkeypatch, lines, ok):
    monkeypatch.setattr(timing.subprocess, 'run', lambda *a, **kw: Entry(stdout='\n'.join(lines) + '\n'))
    if ok:
        timing.gpu_preflight()
    else:
        with pytest.raises(timing.WrongAccelerator):
            timing.gpu_preflight()


def test_gpu_preflight_skips_without_nvidia_smi(monkeypatch):
    def missing(*a, **kw):
        raise FileNotFoundError('nvidia-smi')
    monkeypatch.setattr(timing.subprocess, 'run', missing)
    timing.gpu_preflight()


# --- pytest-timeout 2.1.0 embedded wheel (kernel v4 failed: no offline source on Kaggle) ---

VENDOR = ROOT / 'eval/kaggle/vendor/pytest_timeout-2.1.0-py3-none-any.whl'


def _embed(monkeypatch, tmp_path, data=None, digest=None):
    data = VENDOR.read_bytes() if data is None else data
    digest = hashlib.sha256(data).hexdigest() if digest is None else digest
    monkeypatch.setattr(timing, 'WORK', tmp_path / 'work')
    monkeypatch.setattr(timing, 'EXTRA_WHEELS', {VENDOR.name: [digest, base64.b64encode(data).decode()]})


def test_vendored_wheel_is_official():
    assert hashlib.sha256(VENDOR.read_bytes()).hexdigest() == 'f6f50101443ce70ad325ceb4473c4255e9d74e3c7cd0ef827309dfa4c0d975c6'


def test_extra_wheels_verified(monkeypatch, tmp_path):
    _embed(monkeypatch, tmp_path)
    assert (timing.extra_wheels() / VENDOR.name).read_bytes() == VENDOR.read_bytes()
    _embed(monkeypatch, tmp_path, digest='0' * 64)
    with pytest.raises(RuntimeError, match='verification'):
        timing.extra_wheels()


def test_pytest_timeout_prefers_wheelhouse_then_embedded(monkeypatch, tmp_path):
    _embed(monkeypatch, tmp_path)
    house = tmp_path / 'house'
    house.mkdir()
    assert [p.name for p in timing.pytest_timeout_wheels(house)] == [VENDOR.name]
    (house / VENDOR.name).write_bytes(VENDOR.read_bytes())
    found = timing.pytest_timeout_wheels(house)
    assert found[0].parent == house and len(found) == 2


def test_check_tool_sources(monkeypatch, tmp_path):
    monkeypatch.setattr(timing, 'missing_tool_closure', lambda wheels: [])
    house = tmp_path / 'house'
    house.mkdir()
    names = {'pdm-backend': 'pdm_backend', 'setuptools': 'setuptools', 'wheel': 'wheel', 'poetry-core': 'poetry_core',
             'hatchling': 'hatchling', 'flit-core': 'flit_core', 'editables': 'editables', 'pytest': 'pytest', 'typer': 'typer'}
    for dist in names.values():
        (house / f'{dist}-1.0-py3-none-any.whl').write_bytes(b'')
    (house / 'pip-26.0-py3-none-any.whl').write_bytes(b'')
    _embed(monkeypatch, tmp_path)
    timing.check_tool_sources(house)
    monkeypatch.setattr(timing, 'EXTRA_WHEELS', {})
    monkeypatch.setattr(timing, 'WORK', tmp_path / 'fresh-work')
    with pytest.raises(RuntimeError, match='pytest-timeout==2.1.0'):
        timing.check_tool_sources(house)
    _embed(monkeypatch, tmp_path)
    (house / 'typer-1.0-py3-none-any.whl').unlink()
    with pytest.raises(RuntimeError, match='typer'):
        timing.check_tool_sources(house)


def test_push_embeds_vendored_wheel(tmp_path):
    ids = tmp_path / 'ids.txt'
    ids.write_text('rich_3063\n')
    bundle = tmp_path / 'bundle'
    bundle.mkdir()
    (bundle / 'agent.yaml').write_text('model: gemma-4-e4b-it-qat-w4a16-ct\n')
    out = subprocess.run(['bash', str(ROOT / 'eval/kaggle/timing_push.sh'), '--dry-run', 'u/s', str(bundle), str(ids)],
                         check=True, capture_output=True, text=True).stdout
    stage = Path(out.strip().splitlines()[-1].split('Staged: ')[1])
    text = (stage / 'agent_timing.py').read_text()
    assert "'pytest_timeout-2.1.0-py3-none-any.whl': ['f6f50101" in text
    for line in (ROOT / 'eval/kaggle/vendor/SHA256SUMS').read_text().splitlines():
        digest, name = line.split()
        assert f"'{name}': ['{digest}'" in text


def _wheel(directory, name, version, requires=()):
    import zipfile
    dist = name.replace('-', '_')
    path = directory / f'{dist}-{version}-py3-none-any.whl'
    meta = f'Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n' + ''.join(f'Requires-Dist: {r}\n' for r in requires)
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr(f'{dist}-{version}.dist-info/METADATA', meta)
    return path


def test_missing_tool_closure_uses_wheelhouse_extra_and_runtime(monkeypatch, tmp_path):
    house, extra = tmp_path / 'house', tmp_path / 'extra'
    house.mkdir(); extra.mkdir()
    monkeypatch.setattr(timing, 'extra_wheels', lambda: extra)
    monkeypatch.setattr(timing, 'SCORER_TOOLS', ('pip', 'hatchling', 'typer', 'pytest-timeout'))
    _wheel(house, 'hatchling', '1.0', ['pathspec>=0.10', 'trove-classifiers', 'tomli; python_version < "3.0"'])
    _wheel(house, 'typer', '1.0', ['shellingham>=1.3', 'zz-not-anywhere-pkg', 'zz-extra-only-pkg>=2'])
    _wheel(house, 'zz-old-dep', '1.0', ['zz-legacy-only-pkg'])
    _wheel(house, 'zz-old-dep', '2.0')
    _wheel(extra, 'pytest-timeout', '2.1.0', ['pytest>=5', 'zz-old-dep'])
    _wheel(extra, 'pathspec', '1.1.1')
    tags = ['py3-none-any']
    missing = timing.missing_tool_closure(house, tags)
    assert 'pathspec' not in missing and 'tomli' not in missing
    assert 'zz-legacy-only-pkg' not in missing  # highest matching version (2.0) is walked, not 1.0
    assert 'zz-not-anywhere-pkg' in missing and 'zz-extra-only-pkg' in missing
    _wheel(extra, 'zz-extra-only-pkg', '2.5')
    assert 'zz-extra-only-pkg' not in timing.missing_tool_closure(house, tags)
    # a cp313-only newer wheel is ignored with py3 tags
    _wheel(house, 'zz-old-dep', '9.0', ['zz-tagged-only-pkg'])
    (house / 'zz_old_dep-9.0-py3-none-any.whl').rename(house / 'zz_old_dep-9.0-cp313-cp313-linux_x86_64.whl')
    assert 'zz-tagged-only-pkg' not in timing.missing_tool_closure(house, tags)


def test_vendored_closure_complete_against_local_wheelhouse():
    """The real offline wheelhouse copy plus vendored wheels must close the line-9 tool dependencies."""
    wheels = Path('/home/ubuntu/work/gemma/data/raw/wheels')
    if not wheels.is_dir():
        pytest.skip('local wheelhouse copy not present')
    import base64 as b64
    vendor = ROOT / 'eval/kaggle/vendor'
    extra = {}
    for line in (vendor / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split()
        extra[name] = [digest, b64.b64encode((vendor / name).read_bytes()).decode()]
    timing.EXTRA_WHEELS = extra
    try:
        # Strict: no runtime fallback, so a local venv package cannot hide a gap Kaggle might have.
        assert timing.missing_tool_closure(wheels, runtime=False) == []
    finally:
        timing.EXTRA_WHEELS = {}


def test_check_tool_sources_accepts_runtime_pip(monkeypatch, tmp_path):
    """Kaggle: no pip wheel, no ensurepip bundle, but a pure-Python runtime pip (bootstrap_pip copies it)."""
    house = tmp_path / 'house'
    house.mkdir()
    monkeypatch.setattr(timing, 'missing_tool_closure', lambda wheels: [])
    monkeypatch.setattr(timing, 'SCORER_TOOLS', ('pip', 'pytest-timeout'))
    monkeypatch.setattr(timing, 'fallback_wheel', lambda wheels, package: None)
    _embed(monkeypatch, tmp_path)
    monkeypatch.setattr(timing, 'runtime_copyable', lambda name: (Entry(version='26.0'), []) if name == 'pip' else None)
    timing.check_tool_sources(house)
    monkeypatch.setattr(timing, 'runtime_copyable', lambda name: None)
    with pytest.raises(RuntimeError, match='pip'):
        timing.check_tool_sources(house)


def test_runtime_copyable_matches_copy_runtime_package(tmp_path):
    found = timing.runtime_copyable('pytest')
    result = timing.copy_runtime_package('pytest', tmp_path / 'dest')
    assert (found is None) == (result == 'missing')


@pytest.mark.parametrize('calls,ok', [
    ([dict(cmd='git diff', duration_s=.1, rc=0)] * 2, True),
    ([], True),                                                   # no timeout: no finalization commands
    ([dict(cmd='git diff', duration_s=60, rc=124)], False),       # fix5c review BLOCKING 1 reproduction
    ([dict(cmd='git diff', duration_s=.1, rc=0), dict(cmd='git add', duration_s=None, rc=None, exception='TimeoutError')], False),
    ([dict(cmd='git diff', duration_s=.1, rc=None)], False),      # unknown result fails closed
])
def test_gate_a_rejects_failed_finalization_exec(tmp_path, calls, ok):
    path = tmp_path / 'j'
    _gate_journal(path)
    records = [json.loads(x) for x in path.read_text().splitlines()]
    for r in records:
        if 'instance_id' in r and '_schema' not in r:
            r['finalization_exec'] = calls
    path.write_text('\n'.join(json.dumps(r) for r in records))
    result = summary.summarize(path)
    want = 'PASS' if ok else 'FAIL'
    assert result['gate']['a_all_tasks_complete_no_harness_error']['status'] == want
    assert result['gate']['status'] == want
    assert all(bool(t['finalization_failed']) is (not ok) for t in result['tasks'])


@pytest.mark.parametrize('scenario', ['reserve', 'after-probe'])
def test_p1_budget_stops_before_measured_task(tmp_path, monkeypatch, scenario):
    test_skip_verification_result_and_task_row(tmp_path, monkeypatch, None, True, scenario)
