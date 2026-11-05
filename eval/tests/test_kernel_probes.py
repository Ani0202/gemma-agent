"""Plan 006 addendum probes P1-P3 and the dec 034 item 2 / dec 036 item 1 stock-path gate."""
import importlib.util
import json
import pytest
import socket
from pathlib import Path
from types import SimpleNamespace as E

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'eval/kaggle' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


timing, summary = load('agent_timing'), load('timing_summary')


def test_platform_probe_classifies_without_payload(monkeypatch):
    monkeypatch.setattr(timing.shutil, 'which', lambda name: None)
    monkeypatch.setattr(timing.socket, 'getaddrinfo', lambda *a, **k: [(0, 0, 0, '', ('192.0.2.1', 443))])
    sent = []

    class Sock:
        def sendall(self, data):
            sent.append(data)

        def close(self):
            pass

    for exc, label in ((None, 'connected'), (socket.timeout(), 'timeout'), (ConnectionRefusedError(), 'refused'),
                       (OSError(101, 'unreachable'), 'unreachable')):
        def connect(addr, timeout, exc=exc):
            assert addr == ('192.0.2.1', 443) and timeout == 10.0
            if exc is not None:
                raise exc
            return Sock()
        monkeypatch.setattr(timing.socket, 'create_connection', connect)
        out = timing.platform_probe()
        assert out['tcp'] == label and out['dns'] == 'resolved' and out['docker_which'] is None
        assert isinstance(out['docker_sock'], bool)
        json.dumps(out, allow_nan=False)
    assert out['tcp_errno'] == 101
    assert sent == []


def test_platform_probe_dns_failure_skips_tcp(monkeypatch):
    def fail(*a, **k):
        raise socket.gaierror('no dns')
    monkeypatch.setattr(timing.socket, 'getaddrinfo', fail)
    monkeypatch.setattr(timing.socket, 'create_connection', lambda *a, **k: (_ for _ in ()).throw(AssertionError('no tcp')))
    out = timing.platform_probe()
    assert out['dns'] == 'failed:gaierror' and out['tcp'] == 'skipped'


def test_stock_setup_probe_never_raises():
    # The test environment stubs/lacks swegemma; the probe must report, not raise.
    out = timing.stock_setup_probe(E(snapshots_dir='/nonexistent'), 'x_1', 'r')
    assert set(out) == {'total_s', 'steps_s', 'error'}
    json.dumps(out, allow_nan=False)


def test_llm_calls_rows():
    tr = E(entries=[E(timestamp=100.0, usage=None, event_type='task_prompt'),
                    E(timestamp=104.5, usage={'completion_tokens': 90, 'prompt_tokens': 3000}, event_type='tool_call'),
                    E(timestamp=106.0, usage=None, event_type='tool_response'),
                    E(timestamp=111.0, usage={'completion_tokens': 50, 'prompt_tokens': 3500}, event_type='text')])
    rows = timing.llm_calls(tr)
    assert [r['t'] for r in rows] == [4.5, 11.0] and [r['gap_s'] for r in rows] == [4.5, 5.0]
    assert rows[1]['completion_tokens'] == 50
    assert timing.llm_calls(None) == []


def write(path, phase1=(250.0, 300.0), image=(200.0, 10.0), cap=4.0, stock=(3.0, 12.0), setup_py=(0.0, 0.0)):
    ids = [f't_{i}' for i in range(len(phase1))]
    rows = [dict(_schema='kaggle_timing_v1', task_ids=ids, caps=dict(max_time_minutes=cap), vllm_startup_seconds=500,
                 platform_probe=dict(docker_which=None, docker_sock=False, tcp='timeout'))]
    for i, iid in enumerate(ids):
        rows.append(dict(instance_id=iid, repo='r', error=None, phase1_wall_seconds=phase1[i], phase1_source='sandbox_wrappers',
                         image_emulation_seconds=image[i], setup_calls=[dict(step='setup.py', duration_s=setup_py[i], rc=0, retrying_lines=0)],
                         agent_clock_seconds=90.0, finalization_seconds=8.0, wall_seconds=dict(agent=100.0, total=phase1[i] + 5),
                         patch_files=['src/a.py'], empty_patch=False, stock_setup=dict(total_s=stock[i], steps_s={}, error=None),
                         llm_calls=[dict(t=1.0, gap_s=2.0, completion_tokens=40), dict(t=3.0, gap_s=2.0, completion_tokens=60)]))
    rows += [{'_vllm': dict(startup_seconds=500)}, {'_done': dict(n=len(ids))}]
    path.write_text('\n'.join(json.dumps(r) for r in rows) + '\n')


def test_stock_path_gate(tmp_path):
    path = tmp_path / 't.jsonl'
    write(path, setup_py=(0.0, 3.0))  # stock-path = 50, 300-10-3 = 287; bound = 4.0*60+37 = 277
    out = summary.summarize(path, gate_mode='stock-path')
    assert out['gate']['b_max_stockpath_phase1'] == dict(status='FAIL', value=287.0, threshold=277.0)
    assert out['gate']['status'] == 'FAIL' and out['gate']['mode'] == 'stock-path'
    write(path, phase1=(250.0, 277.0 + 10.0 + 20.0), setup_py=(0.0, 20.0))  # 307 - 10 - 20 = 277 <= 277
    out = summary.summarize(path, gate_mode='stock-path')
    assert out['gate']['b_max_stockpath_phase1']['status'] == 'PASS'
    assert [t['setup_py_emulation_seconds'] for t in out['tasks']] == [0.0, 20.0]
    assert out['gate']['c_mean_phase1'].startswith('NOT_GATED') and out['gate']['status'] == 'PASS'
    h1 = out['probes']['h1_composite']  # agent_clock 90 + finalization 8 + stock 3 / 12
    assert h1['tasks'] == {'t_0': 101.0, 't_1': 110.0} and h1['max_s'] == 110.0 and h1['n_missing'] == 0
    assert out['probes']['stock_setup']['max_s'] == 12.0 and out['probes']['stock_setup']['all_le_30s'] is True
    assert out['probes']['platform_probe']['tcp'] == 'timeout'
    llm = out['probes']['llm'][0]
    assert llm['n_calls'] == 2 and llm['completion_tokens'] == 100 and llm['gap_tokens_per_second'] == 25.0
    assert llm['calls_per_minute'] == 1.2 and out['probes']['mean_agent_seconds'] == 100.0
    write(path, stock=(3.0, 31.0))
    assert summary.summarize(path, gate_mode='stock-path')['probes']['stock_setup']['all_le_30s'] is False
    # default mode is unchanged (dec 028): total Phase-1 against 296; the old mode name is gone
    assert 'b_max_phase1' in summary.summarize(path)['gate']
    with pytest.raises(ValueError):
        summary.summarize(path, gate_mode='minus-image')


def test_stock_path_gate_fails_on_missing_measurement(tmp_path):
    path = tmp_path / 't.jsonl'
    write(path, image=(200.0, None))
    assert summary.summarize(path, gate_mode='stock-path')['gate']['b_max_stockpath_phase1']['status'] == 'FAIL'
    write(path, setup_py=(0.0, None))  # no setup.py duration -> unmeasured -> FAIL, never silently 0
    assert summary.summarize(path, gate_mode='stock-path')['gate']['b_max_stockpath_phase1']['status'] == 'FAIL'
    write(path, stock=(3.0, None))
    assert summary.summarize(path, gate_mode='stock-path')['probes']['h1_composite']['max_s'] is None


V5_RICH_3067 = {"instance_id": "rich_3067", "repo": "Textualize/rich", "phase1_wall_seconds": 303.241871703, "image_emulation_seconds": 11.522305, "agent_clock_seconds": 84.00572919699994, "finalization_seconds": 0.15654274799999257, "total": 303.2490266929999, "setup_calls": [{"step": "venv", "duration_s": 0.387685}, {"step": "venv_fidelity", "duration_s": 0.000311}, {"step": "pip_bootstrap", "duration_s": 0.542832}, {"step": "interpreter_probe", "duration_s": 0.104123}, {"step": "tool_sources", "duration_s": 2e-05}, {"step": "pytest_timeout_source", "duration_s": 7e-06}, {"step": "tool_install", "duration_s": 2.832135}, {"step": "tool_deps", "duration_s": 7.725879}, {"step": "pip_check", "duration_s": 0.316998}, {"step": "workspace_editable", "duration_s": 1.233287}, {"step": "base_tar_extraction", "duration_s": 0.515932}, {"step": "setup.py", "duration_s": 202.194855}]}  # copied from results/kaggle_timing_e4b_v001.json (main) tasks[rich_3067]


def test_stock_path_on_v5_rich_3067(tmp_path):
    """Dec 036 item 1 unit test: real v5 numbers (cap 1.4), exact setup.py duration from setup_calls."""
    src = V5_RICH_3067
    results = ROOT / 'results/kaggle_timing_e4b_v001.json'
    if results.exists():  # on main: the fixture must match the committed v5 summary exactly
        real = next(t for t in json.loads(results.read_text())['tasks'] if t['instance_id'] == 'rich_3067')
        assert [(c['step'], c['duration_s']) for c in real['setup_calls']] == [(c['step'], c['duration_s']) for c in src['setup_calls']]
        assert real['phase1_wall_seconds'] == src['phase1_wall_seconds'] and real['image_emulation_seconds'] == src['image_emulation_seconds']
    setup_py = [c['duration_s'] for c in src['setup_calls'] if c['step'] == 'setup.py']
    assert len(setup_py) == 1 and abs(setup_py[0] - 202.194855) < 1e-6
    row = dict(instance_id=src['instance_id'], repo=src['repo'], error=None, phase1_wall_seconds=src['phase1_wall_seconds'],
               phase1_source='sandbox_wrappers', image_emulation_seconds=src['image_emulation_seconds'],
               setup_calls=src['setup_calls'], agent_clock_seconds=src['agent_clock_seconds'],
               finalization_seconds=src['finalization_seconds'], wall_seconds=dict(agent=100.0, total=src['total']),
               patch_files=['src/a.py'], empty_patch=False)
    path = tmp_path / 'v5.jsonl'
    path.write_text('\n'.join(json.dumps(r) for r in (
        dict(_schema='kaggle_timing_v1', task_ids=[src['instance_id']], caps=dict(max_time_minutes=1.4), vllm_startup_seconds=500),
        row, {'_vllm': dict(startup_seconds=500)}, {'_done': dict(n=1)})) + '\n')
    out = summary.summarize(path, gate_mode='stock-path')
    task = out['tasks'][0]
    expected = 303.241871703 - 11.522305 - 202.194855  # = 89.52 s (Director estimate ~91 s used setup.py ~200.7)
    assert abs(task['stockpath_phase1_seconds'] - expected) < 1e-6 and 89.0 < task['stockpath_phase1_seconds'] < 90.0
    assert out['gate']['b_max_stockpath_phase1']['threshold'] == 1.4 * 60 + 37


@pytest.mark.parametrize('bad', ['missing', 'error', 'nan', 'negative', 'mismatched_id'])
def test_stock_evidence_requires_every_expected_id(tmp_path, bad):
    path = tmp_path / 't.jsonl'
    write(path)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if bad == 'missing':
        del rows[2]['stock_setup']
    elif bad == 'error':
        rows[2]['stock_setup']['error'] = 'deadline'
    elif bad == 'mismatched_id':
        rows[2]['stock_setup']['instance_id'] = 'wrong'
    else:
        rows[2]['stock_setup']['total_s'] = float('nan') if bad == 'nan' else -.000001
    path.write_text('\n'.join(json.dumps(r) for r in rows))
    stock = summary.summarize(path)['probes']['stock_setup']
    assert stock['all_le_30s'] is False
    assert stock['n_expected'] == 2 and stock['n_ok'] == 1
    assert stock['n_missing'] == 1 and stock['missing_ids'] == ['t_1']


@pytest.mark.parametrize('mode', ['total', 'stock-path'])
def test_signed_residual_and_raw_rounding_noise(tmp_path, mode):
    path = tmp_path / 't.jsonl'
    write(path, phase1=(29.999999,), image=(10,), setup_py=(20,), stock=(3,))
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[1]['finalization_seconds'] = -.000001
    path.write_text('\n'.join(json.dumps(r) for r in rows))
    out = summary.summarize(path, gate_mode=mode)
    assert out['gate']['status'] == 'PASS'
    assert out['tasks'][0]['stockpath_phase1_seconds'] == pytest.approx(-.000001)
    assert out['stockpath_phase1_seconds']['max'] == pytest.approx(-.000001)
    assert out['tasks'][0]['finalization_seconds'] == 0.0
    assert out['finalization_max_seconds'] == 0.0
    assert out['tasks'][0]['h1_composite_seconds'] == 93.0
    write(path, phase1=(9,), image=(10,), setup_py=(20,), stock=(3,))
    assert summary.summarize(path, gate_mode=mode)['phase1_minus_image_seconds']['max'] == -1


@pytest.mark.parametrize('key', ['phase1_wall_seconds', 'image_emulation_seconds', 'agent_clock_seconds',
                                 'sandbox_setup_seconds', 'finalization_seconds'])
@pytest.mark.parametrize('value', [-.00101, float('nan'), float('inf'), '1', True])
def test_summary_rejects_invalid_raw_measurements(tmp_path, key, value):
    path = tmp_path / 't.jsonl'
    write(path)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[1][key] = value
    path.write_text('\n'.join(json.dumps(r) for r in rows))
    with pytest.raises(ValueError, match='Invalid measurement'):
        summary.summarize(path)


def test_retained_emulation_diagnostic(tmp_path):
    path = tmp_path / 't.jsonl'
    write(path)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[1]['setup_calls'] += [dict(step='workspace_editable', duration_s=1.2),
                               dict(step='base_tar_extraction', duration_s=.5),
                               dict(step='workspace_editable', duration_s=.1)]
    path.write_text('\n'.join(json.dumps(r) for r in rows))
    out = summary.summarize(path, gate_mode='stock-path')
    assert out['tasks'][0]['stockpath_retained_emulation_seconds'] == pytest.approx(1.8)
    assert out['tasks'][1]['stockpath_retained_emulation_seconds'] is None
    assert out['tasks'][0]['stockpath_phase1_seconds'] == 50
    assert out['gate']['b_note'] == ('conservative: stock-path residual still includes workspace_editable and '
        'base_tar_extraction emulation steps (skipped by the stock path); biases (b) toward FAIL by their duration')


@pytest.mark.parametrize('slow_step', ['start', 'copy', 'exec', 'cleanup'])
def test_stock_probe_overall_deadline(monkeypatch, slow_step):
    import sys
    import time
    from types import ModuleType
    names = ('swegemma', 'swegemma.harness', 'swegemma.harness.container_setup',
             'swegemma.sandbox', 'swegemma.sandbox.subprocess')
    modules = {name: ModuleType(name) for name in names}
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    cs = modules['swegemma.harness.container_setup']
    calls, timeouts = [], []
    def slow():
        time.sleep(2)
    class Manager:
        def __init__(self, **kw):
            pass
        def start(self):
            calls.append('start')
            if slow_step == 'start':
                slow()
            return 'sid'
        def exec(self, *args, **kw):
            timeouts.append(kw['timeout'])
            slow()
        def cleanup_all(self):
            calls.append('cleanup')
            if slow_step == 'cleanup':
                slow()
    modules['swegemma.sandbox.subprocess'].SubprocessManager = Manager
    def copy(mgr, sid, *args, **kw):
        calls.append('copy')
        if slow_step == 'copy':
            slow()
        if slow_step == 'exec':
            mgr.exec(sid, 'sleep', timeout=999)
    cs.setup_container_wheels = copy
    for name in ('extract_snapshot', 'setup_git_exclude', 'install_editable_package',
                 'install_test_dependencies', 'setup_workspace_test_config', 'setup_baseline_commit'):
        setattr(cs, name, lambda *a, **kw: calls.append('step'))
    monkeypatch.setattr(timing, 'P1_DEADLINE_SECONDS', .05)
    start = time.perf_counter()
    out = timing.stock_setup_probe(E(snapshots_dir='/tmp'), 'x_1', 'r')
    duration = time.perf_counter() - start
    assert out['error'] == 'deadline'
    assert .04 <= out['total_s'] < .5 and duration < .5
    assert calls[-1] == 'cleanup'
    if slow_step != 'cleanup':
        assert 'step' not in calls
    if slow_step == 'exec':
        assert 0 < timeouts[0] <= .05
