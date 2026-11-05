"""Offline fidelity toggle, subprocess observation, CPU staging and failure gates."""
import contextvars
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tarfile
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'eval/kaggle' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


timing = load('agent_timing')
summary = load('setup_check_summary')


def test_observer_preserves_captured_output_and_original_argv(tmp_path):
    wrapper = tmp_path / 'setup_observer.py'
    wrapper.write_text(timing.SETUP_OBSERVER)
    script = tmp_path / 'setup.py'
    script.write_text('''import subprocess, sys
assert sys.argv[1:] == ['--fast-path', 'example/repo']
r = subprocess.run([sys.executable, '-c', "import sys; print('x'*6000); print('ERROR: No module named pip', file=sys.stderr); print('Retrying', file=sys.stderr); sys.exit(7)"], capture_output=True, text=True)
assert r.returncode == 7 and len(r.stdout) == 6001
''')
    subprocess.run([sys.executable, str(wrapper), str(script), '--fast-path', 'example/repo'], check=True)
    call, = json.loads((tmp_path / 'setup_subprocesses.json').read_text())
    assert call['rc'] == 7 and call['retrying_lines'] == 1
    full, = [json.loads(line) for line in (tmp_path / 'setup_subprocesses_full.jsonl').read_text().splitlines()]
    assert len(full['stdout']) == 6001
    assert 'stdout_full' not in call and 'stderr_full' not in call
    assert len(call['stdout'].encode()) == 2048
    assert 'No module named pip' in full['stderr']
    assert call['duration_s'] >= 0 and call['start_offset_s'] >= 0


def test_original_injector_has_only_base_and_observed_setup(tmp_path, monkeypatch):
    monkeypatch.setenv('SETUP_FIX', '0')
    cs = ModuleType('swegemma.harness.container_setup')
    cs.install_test_dependencies = lambda *a, **kw: None
    wheels = tmp_path / 'wheels'
    wheels.mkdir()
    base = wheels / 'original-cp313.whl'
    base.touch()
    cs._inspect_wheels_dir = lambda path: ([base], {}, {}, {})
    archive = tmp_path / 'base.tar'
    with tarfile.open(archive, 'w') as tf:
        import io
        info = tarfile.TarInfo('package.py')
        info.size = 1
        tf.addfile(info, io.BytesIO(b'x'))
    def build(paths, key, marker):
        assert paths == [base] and key == timing.base_cache_key([base], '0.2.11')
        return archive
    cs._build_unpacked_wheels_tar = build
    for name in ('swegemma', 'swegemma.harness'):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    monkeypatch.setitem(sys.modules, 'swegemma.harness.container_setup', cs)
    sp = tmp_path / 'venv/lib/python3.13/site-packages'
    sp.mkdir(parents=True)
    scratch = tmp_path / 'tmp'
    scratch.mkdir()
    commands = []
    class SubprocessManager:
        sandboxes = {'sid': dict(venv=tmp_path / 'venv', tmp=scratch)}
        def copy_to(self, *args):
            pass
        def exec(self, sid, command, **kw):
            commands.append(command)
            if 'PackageNotFoundError' in command:
                return SimpleNamespace(exit_code=0, stdout='{}', stderr='')
            (scratch / 'setup_subprocesses.json').write_text(json.dumps([
                dict(argv=['python3', '-m', 'pip', '-e', '/workspace'], rc=1,
                     stderr='No module named pip', retrying_lines=0, interpreter_version='3.13')]))
            return SimpleNamespace(exit_code=0, stdout='', stderr='')
    state = contextvars.ContextVar('test')
    current = dict(started=timing.time.perf_counter(), setup_calls=[], setup_failed=False)
    state.set(current)
    timing.patch_subprocess_deps(tmp_path, state)(SubprocessManager(), 'sid', 'example/repo')
    assert [c['step'] for c in current['setup_calls']] == ['base_tar_extraction', 'setup.py']
    assert len(commands) == 3
    assert commands[1] == 'python3 /tmp/setup_observer.py /tmp/setup.py --fast-path example/repo'
    assert current['setup_failed'] and current['editable_failed']
    assert current['setup_calls'][0]['tar_member_count'] == 1
    assert current['setup_calls'][0]['selected_wheels'] == [base.name]
    assert current['editable_rc'] == 1 and current['interpreter_version'] == '3.13'
    assert current['setup_calls'][-1]['subprocesses'] == current['setup_subprocesses']


@pytest.mark.parametrize('mode', ['0', '1'])
def test_cpu_staging_without_kaggle_or_model(tmp_path, mode):
    ids = tmp_path / 'ids'
    ids.write_text('rich_3006\nfastapi_14986\n')
    result = subprocess.run(['bash', str(ROOT / 'eval/kaggle/setup_check_push.sh'),
        '--dry-run', 'example/setup-check', mode, str(ids)], check=True, capture_output=True, text=True)
    stage = Path(result.stdout.split('Dry run: no push. Staged: ')[1].strip())
    try:
        metadata = json.loads((stage / 'kernel-metadata.json').read_text())
        assert metadata['enable_gpu'] is False and metadata['enable_internet'] is False
        assert metadata['model_sources'] == []
        assert metadata['docker_image'] in (ROOT / 'eval/kaggle/timing_push.sh').read_text()
        namespace = {'__name__': 'staged'}
        exec(compile((stage / 'agent_timing.py').read_text(), 'staged', 'exec'), namespace)
        assert namespace['SETUP_ONLY'] is True and namespace['SETUP_FIX'] == int(mode)
        assert namespace['TASK_IDS'] == ['rich_3006', 'fastapi_14986']
    finally:
        import shutil
        shutil.rmtree(stage)


def test_setup_only_routes_before_bundle_model_and_agent(monkeypatch):
    monkeypatch.setenv('SETUP_ONLY', '1')
    calls = []
    monkeypatch.setattr(timing, 'setup_only_main', lambda: calls.append('cpu'))
    monkeypatch.setattr(timing, 'extract_bundle', lambda *a: pytest.fail('bundle accessed'))
    monkeypatch.setattr(timing, 'start_server', lambda *a: pytest.fail('vLLM accessed'))
    timing.main()
    assert calls == ['cpu']


def test_summary_diagnoses_first_editable_failure_and_missing_rows(tmp_path):
    path = tmp_path / 'journal'
    header = dict(_schema='kaggle_setup_cpu_check_v1', task_ids=['a'])
    row = dict(instance_id='a', setup_fix=0, setup_s_total=30, editable_rc=1, retrying_lines=0,
               setup_failed=False, setup_subprocesses=[dict(argv=['python', '-m', 'pip', '-e'],
               rc=1, stderr_full='ERROR: No module named pip')])
    def write(rows):
        path.write_text('\n'.join(json.dumps(r) for r in rows))
    write([header, row, dict(_done=dict(n=1))])
    result = summary.summarize(path)
    assert result['decision'] == 'FAIL'
    assert result['rows'][0]['offline_install_diagnosis'] == dict(cause='pip_absent_in_venv', evidence=['ERROR: No module named pip'])
    row.update(setup_fix=1, editable_rc=0)
    write([header, row, dict(_done=dict(n=1))])
    assert summary.summarize(path)['decision'] == 'PASS'
    row['setup_s_total'] = 30.001
    write([header, row, dict(_done=dict(n=1))])
    assert summary.summarize(path)['decision'] == 'FAIL'
    row.update(setup_s_total=1, retrying_lines=1)
    write([header, row, dict(_done=dict(n=1))])
    assert summary.summarize(path)['decision'] == 'FAIL'
    write([header, dict(_done=dict(n=0))])
    assert summary.summarize(path)['gates']['complete'] is False
    write([header, row, row, dict(_done=dict(n=2))])
    assert summary.summarize(path)['gates']['complete'] is False


def test_pip_source_precedence_and_runtime_copy(tmp_path, monkeypatch):
    wheel = tmp_path / 'pip-99-py3-none-any.whl'
    wheel.touch()
    assert timing.fallback_wheel(tmp_path, 'pip') == wheel
    wheel.unlink()
    import ensurepip
    bundled = tmp_path / '_bundled'
    bundled.mkdir()
    (tmp_path / '__init__.py').touch()
    monkeypatch.setattr(ensurepip, '__file__', str(tmp_path / '__init__.py'))
    bundled_wheel = bundled / 'pip-98-py3-none-any.whl'
    bundled_wheel.touch()
    assert timing.fallback_wheel(tmp_path, 'pip') == bundled_wheel
    bundled_wheel.unlink()
    assert timing.fallback_wheel(tmp_path, 'pip') is None
    import importlib.metadata as metadata
    root = tmp_path / 'runtime'
    (root / 'pip').mkdir(parents=True)
    (root / 'pip/__init__.py').write_text('pure python')
    (root / 'pip-1.dist-info').mkdir()
    (root / 'pip-1.dist-info/METADATA').write_text('Version: 1')
    dist = SimpleNamespace(version='1', files=[Path('pip/__init__.py'), Path('pip-1.dist-info/METADATA')], locate_file=lambda p: root / p)
    monkeypatch.setattr(metadata, 'distribution', lambda name: dist)
    target = tmp_path / 'target'
    assert timing.copy_runtime_package('pip', target).startswith('runtime-site-packages:')
    assert (target / 'pip/__init__.py').read_text() == 'pure python'
    assert (target / 'pip-1.dist-info/METADATA').exists()
    assert timing.copy_runtime_package('pytest-timeout', target) == 'missing'


@pytest.mark.parametrize('fail_install', [False, True])
def test_setup_task_uses_harness_creation_sequence_and_always_tears_down(tmp_path, monkeypatch, fail_install):
    cs = ModuleType('swegemma.harness.container_setup')
    dedup = ModuleType('swegemma.deduplication')
    dedup.resolve_task_snapshot_paths = lambda path, iid, repo: (path / (iid + '.tgz'), None, None)
    monkeypatch.setitem(sys.modules, 'swegemma.deduplication', dedup)
    sandbox = ModuleType('swegemma.sandbox')
    calls = []
    class SubprocessManager:
        def __init__(self, **kw):
            # Match Evaluator's default system_site_packages/venv behavior.
            assert kw == dict(timeout_seconds=300)
        def start(self):
            calls.append('start')
            return 'sid'
        def cleanup_all(self):
            calls.append('cleanup')
    sandbox.SubprocessManager = SubprocessManager
    for name in ('setup_container_wheels', 'extract_snapshot', 'setup_git_exclude', 'install_editable_package'):
        setattr(cs, name, lambda *a, _name=name, **kw: calls.append(_name))
    for name in ('swegemma', 'swegemma.harness'):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    monkeypatch.setitem(sys.modules, 'swegemma.sandbox', sandbox)
    monkeypatch.setitem(sys.modules, 'swegemma.harness.container_setup', cs)
    def install(*args):
        calls.append('install')
        if fail_install:
            raise RuntimeError('offline failure')
    monkeypatch.setattr(timing, 'patch_subprocess_deps', lambda *a: install)
    state = contextvars.ContextVar('sequence')
    monkeypatch.setenv('SETUP_FIX', '0')
    monkeypatch.setattr(timing, 'WORK', tmp_path)
    row = timing.setup_task(tmp_path, tmp_path / 'wheels', 'rich_3006', 'Textualize/rich', state)
    assert calls == ['start', 'setup_container_wheels', 'extract_snapshot', 'setup_git_exclude',
                     'install_editable_package', 'install', 'cleanup']
    assert row['setup_failed'] == fail_install
    assert 'started' not in row and row['setup_s_total'] >= 0
    assert row['setup_calls'][-1]['step'] == 'teardown'


def test_cache_identity_and_stale_marker_tar_rejected(tmp_path):
    a, b = tmp_path / 'a.whl', tmp_path / 'b.whl'
    a.write_bytes(b'a')
    b.write_bytes(b'b')
    key = timing.base_cache_key([a], 'v1')
    assert key != timing.base_cache_key([a, b], 'v1')
    assert timing.base_cache_key([a, b], 'v1') == timing.base_cache_key([b, a], 'v1')
    assert key != timing.base_cache_key([a], 'v2')
    a.write_bytes(b'aa')
    assert key != timing.base_cache_key([a], 'v1')
    archive = tmp_path / 'stale.tar'
    with tarfile.open(archive, 'w') as tf:
        tf.addfile(tarfile.TarInfo('.'))
        tf.addfile(tarfile.TarInfo('.swegemma_base_injected'))
    cs = SimpleNamespace(_build_unpacked_wheels_tar=lambda *a: archive)
    current = dict(started=timing.time.perf_counter(), setup_calls=[], setup_failed=False)
    with pytest.raises(RuntimeError, match='only marker'):
        timing.setup_step(current, 'base_tar_extraction',
                          lambda: timing.inject_base(cs, [a], tmp_path / 'site', current))
    assert current['setup_failed']
    assert current['setup_calls'][0]['selected_wheels'] == ['a.whl']
    assert current['setup_calls'][0]['tar_member_count'] == 2


@pytest.mark.parametrize('field,value', [('missing_tool_deps', ['child']), ('editable_failed', True)])
def test_summary_rejects_explicit_failure_flags(tmp_path, field, value):
    path = tmp_path / 'journal'
    row = dict(instance_id='a', setup_fix=1, setup_s_total=1, editable_rc=0,
               setup_failed=False, retrying_lines=0)
    header = dict(_schema='kaggle_setup_cpu_check_v1', task_ids=['a'])
    records = [header, row, dict(_done=dict(n=1))]
    path.write_text('\n'.join(map(json.dumps, records)))
    assert summary.summarize(path)['decision'] == 'PASS'
    row[field] = value
    path.write_text('\n'.join(map(json.dumps, records)))
    assert summary.summarize(path)['decision'] == 'FAIL'


def test_acceptance_control_only_is_diagnostic(tmp_path, monkeypatch):
    monkeypatch.setenv('SETUP_FIX', '0')
    spec = importlib.util.spec_from_file_location('acceptance', ROOT / 'eval/repro/plan003_kernel_setup.py')
    acceptance = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(acceptance)
    # No sandbox bypass: stub only task execution for this CLI/status unit test.
    fake_timing = SimpleNamespace(setup_task=lambda *a: dict(instance_id=a[2], setup_fix=0,
        setup_calls=[], editable_rc=1, retrying_lines=5, setup_failed=True, setup_s_total=1))
    monkeypatch.setattr(acceptance.importlib.util, 'module_from_spec', lambda spec: fake_timing)
    monkeypatch.setattr(acceptance.importlib.util, 'spec_from_file_location',
                        lambda *a: SimpleNamespace(loader=SimpleNamespace(exec_module=lambda m: None)))
    output = tmp_path / 'result.json'
    monkeypatch.setattr(sys, 'argv', ['acceptance', '--inside-bwrap', '--setup-fix', '0',
                                     '--output', str(output), '--data-dir', str(tmp_path)])
    assert acceptance.main() == 0
    assert json.loads(output.read_text())['status'] == 'diagnostic'


def test_full_artifact_has_only_task_id_filename_and_bounded_journal(tmp_path, monkeypatch):
    monkeypatch.setattr(timing, 'WORK', tmp_path)
    current = dict(instance_id='rich_3006', setup_fix=1, started=timing.time.perf_counter(),
                   setup_calls=[], setup_failed=False)
    timing.setup_step(current, 'command', lambda: SimpleNamespace(exit_code=1,
        stdout='x' * 8000, stderr='Retrying\n' + 'é' * 8000))
    path = Path(current['setup_output_artifact'])
    assert path.name == 'rich_3006.jsonl'
    full = json.loads(path.read_text())
    assert len(full['stdout']) == 8000
    assert len(full['stderr']) > 8000
    call, = current['setup_calls']
    assert all(len(call[k].encode()) <= 2048 for k in ('stdout', 'stderr'))
    assert call['retrying_lines'] == 1
