"""Offline plan-009 checks; saved-run checks skip when artifacts are absent."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'eval'))
import plan008_metrics as m

# Frozen pre-extension source, retained in git; no network needed.
LEGACY_BLOB = '9119467d4ec6de8b4fec253f5379608fd1c1bda4'
SAVED = ROOT if (ROOT / 'runs').exists() else Path('/home/ubuntu/work/gemma')


@pytest.fixture
def legacy(tmp_path):
    source = subprocess.check_output(['git', 'show', LEGACY_BLOB], cwd=ROOT)
    path = tmp_path / 'legacy.py'
    path.write_bytes(source)
    spec = importlib.util.spec_from_file_location('plan008_legacy', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def registered(monkeypatch, tmp_path):
    ids = tmp_path / 'ids.txt'
    ids.write_text('repo__a\nrepo__b\nrepo__c\n')
    screened = tmp_path / 'screened.txt'
    screened.write_text('repo__c\n')
    monkeypatch.setattr(m.base, 'ARM_IDS', str(ids))
    monkeypatch.setattr(m.base, 'SCREENED_IDS', str(screened))
    return m.base.ids_file(ids)


def make_run(tmp_path, name, ids, *, h=(), resolved=(), blocks=3):
    directory = tmp_path / name
    directory.mkdir()
    rows = [dict(instance_id=i, resolved=i in resolved, verified_patch_bytes=1,
                 agent_clock_seconds=200, finalization_seconds=10, timed_out=False,
                 patch_submitted=False, test_files_edited=[], stray_files=[],
                 wall_seconds=dict(total=300, verification=20), sandbox_setup_seconds=80) for i in ids]
    header = dict(_schema='test', agent_yaml_sha256='a'*64, bundle_sha256='b'*64,
                  model_id='test', versions={'vllm': '1'}, kernel_code={'agent_path_sha256': 'c'*64})
    timing = directory / 'timing.jsonl'
    timing.write_text('\n'.join(map(json.dumps, [header, *rows])) + '\n')
    files = []
    for name, sha in [('d4.json', m.base.D4_SHA), ('a2.json', m.base.A2_SHA)]:
        path = directory / name
        path.write_text(json.dumps(dict(classifier_sha256=sha, input_sha256=m.base.sha(timing),
                         rows=[dict(instance_id=i, h='H' if i in h else None, known_diag=False) for i in ids])))
        files.append(str(path))
    for i in set(ids):
        tr = directory / 'runs' / i / 'trace.json'
        tr.parent.mkdir(parents=True)
        tr.write_text(json.dumps(dict(entries=[dict(author=m.ROOT, type='thinking', content='x'*40)] * blocks)))
    return str(directory), {str(directory): files}


def assert_no_text(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key != 'definitions':
                assert_no_text(item)
    elif isinstance(value, list):
        for item in value:
            assert_no_text(item)
    elif isinstance(value, str):
        assert len(value) <= 200


@pytest.mark.parametrize('a,b,p', [(0,0,1.), (4,0,.125), (5,1,.21875), (6,0,.03125)])
def test_sign(a, b, p):
    assert m.sign_test(a, b) == p
    assert m.sign_test(b, a) == p


def test_first_attempt_and_inventory(tmp_path, registered):
    d1, c1 = make_run(tmp_path, 'first', registered[:2])
    d2, c2 = make_run(tmp_path, 'second', registered[1:], resolved=registered)
    records, inv, _, _ = m.aggregate_arm([d1,d2], c1 | c2)
    assert len(records) == 3
    assert records[1][0]['resolved'] is False
    assert inv['duplicates'] == [dict(instance_id=registered[1], dirs=[d1,d2])]
    assert inv['complete']


@pytest.mark.parametrize('duplicate', [False, True])
def test_bad_inventory_exit_no_file(tmp_path, registered, duplicate, capsys):
    ids = registered + [registered[0]] if duplicate else registered[:-1]
    directory, cs = make_run(tmp_path, 'bad', ids)
    out = tmp_path / 'output.json'
    rc = m.main(['metrics', 'arm3', 'arm2', str(out), '--arm3', directory,
                 '--base-dirs', directory, '--classifiers', directory + '=' + ','.join(cs[directory])])
    assert rc == 3 and not out.exists()
    assert 'inventory' in capsys.readouterr().out


def test_smoke_positive_and_missing(tmp_path, registered):
    directory, cs = make_run(tmp_path, 'smoke', registered[:2])
    result = m.arm3smoke_metrics(directory, cs[directory][0])
    assert result['overall'] == 'PASS'
    assert result['criteria']['i']['total_blocks'] == 6
    assert_no_text(result)
    trace = Path(directory) / 'runs' / registered[0] / 'trace.json'
    trace.unlink()
    result = m.arm3smoke_metrics(directory, cs[directory][0])
    assert result['criteria']['i']['status'] == 'UNVERIFIABLE'
    assert result['overall'] == 'FAIL'


@pytest.mark.parametrize('field', ['agent_clock_seconds', 'finalization_seconds'])
@pytest.mark.parametrize('value', [None, -1, float('nan'), float('inf'), '200', True, 221])
def test_timing_missing_invalid(field, value):
    row = dict(instance_id='a', agent_clock_seconds=220, finalization_seconds=30)
    assert m.arm3_timing([row])['timing_pass']
    row[field] = value
    assert not m.arm3_timing([row])['timing_pass']


@pytest.mark.parametrize('change,status', [('identity', 'FAIL'), ('missing', 'UNVERIFIABLE'),
                                          ('verdict', 'UNVERIFIABLE'), ('h', 'FAIL')])
def test_smoke_iii(tmp_path, registered, change, status):
    directory, cs = make_run(tmp_path, 'smoke', registered[:2], h=registered[:1] if change == 'h' else ())
    timing = Path(directory) / 'timing.jsonl'
    data = [json.loads(l) for l in timing.read_text().splitlines()]
    if change == 'identity':
        data.append(dict(data[0], bundle_sha256='c'*64))
    elif change == 'missing':
        del data[0]['bundle_sha256']
    elif change == 'verdict':
        data[1]['resolved'] = None
    timing.write_text('\n'.join(map(json.dumps, data)))
    for path in cs[directory]:
        c = json.loads(Path(path).read_text())
        c['input_sha256'] = m.base.sha(timing)
        Path(path).write_text(json.dumps(c))
    assert m.arm3smoke_metrics(directory, cs[directory][0])['criteria']['iii']['status'] == status


@pytest.mark.parametrize('field', ['classifier_sha256', 'input_sha256'])
def test_classifier_binding(tmp_path, registered, field):
    directory, cs = make_run(tmp_path, 'test', registered)
    path = Path(cs[directory][0])
    c = json.loads(path.read_text()); c[field] = 'wrong'; path.write_text(json.dumps(c))
    with pytest.raises(AssertionError):
        m.aggregate_arm([directory], cs)


@pytest.mark.parametrize('on,off,p,h,smoke,vetoes,expected', [
    (4,0,.125,0,False,[], 'ON-ADOPT'),
    (4,0,.125,0,False,['timing'], 'ON-BETTER-VETOED'),
    (0,0,1.,0,False,[], 'KEEP-OFF'),
    (5,1,.21875,0,False,[], 'NO-DIFFERENCE'),
    (4,0,.125,5,False,[], 'INVALID'),
    (4,0,.125,0,True,[], 'INVALID'),
])
def test_decision(on, off, p, h, smoke, vetoes, expected):
    assert m.arm3_decision(on, off, p, h, smoke, vetoes) == expected


def test_full_synthetic(tmp_path, registered):
    d1, c1 = make_run(tmp_path, 'on', registered, resolved=registered[:1])
    d2, c2 = make_run(tmp_path, 'off', registered)
    result = m.arm3_metrics('arm2', [d1], [d2], c1 | c2)
    assert result['primary']['on_only']['count'] == 1
    assert result['decision'] == 'NO-DIFFERENCE'
    assert result['arms']['arm3']['safety']['submitted_without_test']['count'] == 0
    assert result['env_drift']['pairing_void_candidate'] is False
    assert_no_text(result)
    paths = result['_schema']['input_shas']
    assert str(Path(d1) / 'runs' / registered[0] / 'trace.json') in paths
    smoke = tmp_path / 'smoke.json'; smoke.write_text('{"overall":"FAIL"}')
    result = m.arm3_metrics('arm2', [d1], [d2], c1 | c2, str(smoke))
    assert result['decision'] == 'INVALID'
    assert str(smoke) in result['_schema']['input_shas']


@pytest.mark.skipif(not (SAVED / 'runs/31b-v009-p7a1-main').exists(), reason='saved run artifacts absent')
def test_real_pair_and_smoke(monkeypatch):
    monkeypatch.chdir(SAVED)
    dirs = [str(Path(t).parent) for _, t, _, _ in m.base.PARTS]
    classifiers = {str(Path(t).parent): (d,a) for _,t,d,a in m.base.PARTS}
    result = m.arm3_metrics('arm1', dirs, [], classifiers)
    primary = result['primary']
    assert primary['on_only']['count'] == primary['off_only']['count'] == 0
    assert primary['p'] == 1.
    assert primary['arm3_resolved']['k'] == primary['base_resolved']['k'] == 4
    assert primary['arm3_resolved']['n'] == 33
    assert result['arms']['arm3']['safety']['empty_patch']['count'] == 12
    # Acceptance (b)'s KEEP-OFF conflicts with literal H>=5: saved arm1 has 7 H rows.
    assert result['arms']['arm3']['h_rows']['count'] == 7
    assert result['decision'] == 'INVALID'
    assert_no_text(result)
    smoke = m.arm3smoke_metrics(dirs[0], m.base.PARTS[0][2])
    assert smoke['criteria']['i']['status'] == 'FAIL'
    assert smoke['verdict'] == 'INVALID (smoke i)'
    traces = sorted((SAVED / 'runs/31b-v003-p5t4-timing/runs').glob('*/trace.json'))
    assert len(traces) == 8
    assert m.thinking_criterion(traces[:2])['status'] == 'PASS'


@pytest.mark.skipif(not (SAVED / 'runs/31b-v009-p7a1-main').exists(), reason='saved run artifacts absent')
def test_legacy_base_identical(legacy, monkeypatch):
    monkeypatch.chdir(SAVED)
    # Same inputs and module paths, including all absolute paths in the schema.
    assert json.dumps(m.base_metrics(), indent=2) == json.dumps(legacy.base_metrics(), indent=2)


def test_legacy_other_modes_identical(legacy, monkeypatch, tmp_path, registered):
    directory, _ = make_run(tmp_path, 'legacy', registered)
    for mod in (m, legacy):
        monkeypatch.setattr(mod, 'expected_ids', lambda kind: registered)
        monkeypatch.setattr(mod, '_tasks_path', lambda: tmp_path / 'absent-tasks')
    for function in ('smoke_metrics', 'arm2_metrics'):
        assert json.dumps(getattr(m, function)(directory), indent=2) == json.dumps(getattr(legacy, function)(directory), indent=2)


def test_missing_safety_and_environment(tmp_path, registered):
    d1, c1 = make_run(tmp_path, 'on', registered)
    d2, c2 = make_run(tmp_path, 'off', registered)
    records, _, _, headers = m.aggregate_arm([d1], c1)
    for row, _, _, _ in records:
        row.pop('test_files_edited')
        row.pop('verified_patch_bytes')
        row.pop('patch_submitted')
    summary = m.summarize_arm(records)
    assert summary['safety']['test_files_edited'] == 'not available'
    assert not summary['safety']['empty_patch_complete']
    assert summary['safety']['submitted_without_test']['count'] == 3
    env = m.environment_metrics(headers, records)
    assert env['vllm_version'] == '1'
    assert env['docker_image_digest'] is None
    # Drift and kernel-path differences are reported, not silently ruled upon.
    timing = Path(d2) / 'timing.jsonl'
    data = [json.loads(l) for l in timing.read_text().splitlines()]
    data[0]['kernel_code']['agent_path_sha256'] = 'd'*64
    data[0]['gpu_count'] = 2
    timing.write_text('\n'.join(map(json.dumps, data)))
    for path in c2[d2]:
        c = json.loads(Path(path).read_text())
        c['input_sha256'] = m.base.sha(timing)
        Path(path).write_text(json.dumps(c))
    out = m.arm3_metrics('arm2', [d1], [d2], c1 | c2)
    assert out['env_drift']['pairing_void_candidate'] is True
    assert set(out['env_drift']['differences']) == {'kernel_code', 'gpu_count'}
    assert out['decision'] == 'KEEP-OFF'
