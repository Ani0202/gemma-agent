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
        with zipfile.ZipFile(wheels / f'{tool.replace("-", "_")}-{version}-py3-none-any.whl', 'w'):
            pass
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
                return SimpleNamespace(exit_code=0, stdout=json.dumps(dict(version='3.12', tags=['py3-none-any'])), stderr='')
            return SimpleNamespace(exit_code=setup_rc if '/tmp/setup.py' in command else 0,
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
        'pytest_timeout_source', 'tool_install', 'setup.py']
    assert all(len(r['stdout'].encode()) <= 2048 and len(r['stderr'].encode()) <= 2048
               and r['duration_s'] >= 0 and r['start_offset_s'] >= 0 for r in current['setup_calls'])
    assert commands[-1].startswith('python3 /tmp/setup_observer.py /tmp/setup.py')
    assert any('--no-index --find-links=/wheels' in c for c in commands)
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
