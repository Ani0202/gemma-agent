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
    assert result['decision'] == 'PASS'
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
    assert summary.summarize(path)['decision'] == 'FAIL'
    journal(path, cap=5.04001)
    assert summary.summarize(path)['decision'] == 'FAIL'


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
def test_injected_install_bootstraps_and_retains_failure(tmp_path, monkeypatch, setup_rc):
    import contextvars
    import sys
    import tarfile
    import zipfile
    from types import ModuleType, SimpleNamespace
    cs = ModuleType('swegemma.harness.container_setup')
    cs.install_test_dependencies = lambda *a, **k: None
    cs._LARGE_WHEEL_THRESHOLD_BYTES = 20 * 1024 * 1024
    archive = tmp_path / 'base.tar'
    with tarfile.open(archive, 'w'):
        pass
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
            if 'sys_tags' in command:
                return SimpleNamespace(exit_code=0, stdout=json.dumps(dict(version='3.12', tags=['py3-none-any'], environment=sandbox_markers())), stderr='')
            return SimpleNamespace(exit_code=setup_rc if '/tmp/setup.py' in command else (1 if 'pip check' in command else 0),
                                   stdout='x' * 5000, stderr='é' * 5000)
    current = dict(started=timing.time.perf_counter(), setup_calls=[], setup_failed=False)
    state = contextvars.ContextVar('test_setup')
    state.set(current)
    install = timing.patch_subprocess_deps(tmp_path, state)
    install(SubprocessManager(), 'id', 'example/repo')
    assert current['setup_failed'] == bool(setup_rc)
    assert current['setup_calls'][-1]['rc'] == setup_rc
    assert [r['step'] for r in current['setup_calls']] == [
        'venv_fidelity', 'pip_bootstrap', 'interpreter_probe', 'base_tar_extraction',
        'pytest_timeout_source', 'tool_install', 'tool_deps', 'pip_check', 'setup.py']
    assert all(len(r['stdout'].encode()) <= 2048 and len(r['stderr'].encode()) <= 2048
               and r['duration_s'] >= 0 and r['start_offset_s'] >= 0 for r in current['setup_calls'])
    assert commands[-1].startswith('python3 /tmp/setup_observer.py /tmp/setup.py')
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
