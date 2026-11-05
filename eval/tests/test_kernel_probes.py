"""Plan 006 addendum probes P1-P3 and the dec 034 item 2 minus-image gate."""
import importlib.util
import json
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


def write(path, phase1=(250.0, 300.0), image=(200.0, 10.0), cap=4.0, stock=(3.0, 12.0)):
    ids = [f't_{i}' for i in range(len(phase1))]
    rows = [dict(_schema='kaggle_timing_v1', task_ids=ids, caps=dict(max_time_minutes=cap), vllm_startup_seconds=500,
                 platform_probe=dict(docker_which=None, docker_sock=False, tcp='timeout'))]
    for i, iid in enumerate(ids):
        rows.append(dict(instance_id=iid, repo='r', error=None, phase1_wall_seconds=phase1[i], phase1_source='sandbox_wrappers',
                         image_emulation_seconds=image[i], wall_seconds=dict(agent=100.0, total=phase1[i] + 5),
                         patch_files=['src/a.py'], empty_patch=False, stock_setup=dict(total_s=stock[i], steps_s={}, error=None),
                         llm_calls=[dict(t=1.0, gap_s=2.0, completion_tokens=40), dict(t=3.0, gap_s=2.0, completion_tokens=60)]))
    rows += [{'_vllm': dict(startup_seconds=500)}, {'_done': dict(n=len(ids))}]
    path.write_text('\n'.join(json.dumps(r) for r in rows) + '\n')


def test_minus_image_gate(tmp_path):
    path = tmp_path / 't.jsonl'
    write(path)  # minus-image = 50, 290; bound = 4.0*60+37 = 277
    out = summary.summarize(path, gate_mode='minus-image')
    assert out['gate']['b_max_phase1_minus_image'] == dict(status='FAIL', value=290.0, threshold=277.0)
    assert out['gate']['status'] == 'FAIL' and out['gate']['mode'] == 'minus-image'
    write(path, phase1=(250.0, 277.0 + 10.0))  # 287 - 10 = 277 <= 277
    out = summary.summarize(path, gate_mode='minus-image')
    assert out['gate']['b_max_phase1_minus_image']['status'] == 'PASS'
    assert out['gate']['c_mean_phase1'].startswith('NOT_GATED') and out['gate']['status'] == 'PASS'
    assert out['probes']['stock_setup']['max_s'] == 12.0 and out['probes']['stock_setup']['all_le_30s'] is True
    assert out['probes']['platform_probe']['tcp'] == 'timeout'
    llm = out['probes']['llm'][0]
    assert llm['n_calls'] == 2 and llm['completion_tokens'] == 100 and llm['gap_tokens_per_second'] == 25.0
    assert llm['calls_per_minute'] == 1.2 and out['probes']['mean_agent_seconds'] == 100.0
    write(path, stock=(3.0, 31.0))
    assert summary.summarize(path, gate_mode='minus-image')['probes']['stock_setup']['all_le_30s'] is False
    # default mode is unchanged (dec 028): total Phase-1 against 296
    assert 'b_max_phase1' in summary.summarize(path)['gate']


def test_minus_image_gate_fails_on_missing_measurement(tmp_path):
    path = tmp_path / 't.jsonl'
    write(path, image=(200.0, None))
    assert summary.summarize(path, gate_mode='minus-image')['gate']['b_max_phase1_minus_image']['status'] == 'FAIL'
