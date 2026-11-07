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


@pytest.fixture(autouse=True)
def synthetic_manifest(tmp_path, monkeypatch):
    root = tmp_path / 'bundles'
    manifest = root / 'v012' / 'MANIFEST.md'
    manifest.parent.mkdir(parents=True)
    manifest.write_text('zip sha256: ' + 'd'*64 + '\n')
    monkeypatch.setattr(m, 'BUNDLES_ROOT', root)


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
    timing.write_text('\n'.join(map(json.dumps, [header, *rows, {'_vllm': {'startup_seconds': 1}}])) + '\n')
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


def evidence(tmp_path, directory, cs):
    identity = tmp_path / 'identity.json'
    identity.write_text(json.dumps(dict(records=[dict(event=e, bundles={'v012': dict(
        zip_ok=True, content_ok=True, **{'pass': True}, agent_yaml_sha256='a'*64,
        zip_sha256='d'*64, manifest_zip_sha256='d'*64, zip_path='dist/31b-v012.zip',
        only_in_zip=[], only_in_dir=[], byte_mismatch=[], duplicate_members=[])})
        for e in ('smoke', 'main', 'chunk1') ])))
    opts = dict(identity_json=str(identity), bundle='v012', transports={directory: 'b'*64}, push_events={directory: 'smoke'})
    timing = Path(directory) / 'timing.jsonl'
    traces = [Path(directory) / 'runs' / iid / 'trace.json'
              for iid in m.base.ids_file(m.base.ARM_IDS)[:2]]
    smoke = dict(overall='PASS', _schema=m._schema('arm3smoke', [timing, cs[directory][0], *(p for p in traces if p.is_file())]))
    path = tmp_path / 'smoke.json'
    path.write_text(json.dumps(smoke))
    verdict = tmp_path / 'base.json'
    verdict.write_text(json.dumps(dict(decision='SHIP-ELIGIBLE')))
    return dict(**opts, smoke_json=str(path), base_verdict_json=str(verdict))


def pair_evidence(tmp_path, smoke, main, cs):
    opts = evidence(tmp_path, smoke, cs)
    opts['transports'][main] = 'b'*64
    opts['push_events'][main] = 'main'
    return opts


def smoke_options(tmp_path, directory, cs):
    opts = evidence(tmp_path, directory, cs)
    return {k: opts[k] for k in ('identity_json', 'bundle', 'transports', 'push_events')}


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
    assert inv['duplicates'][0]['dirs'] == [d1, d2]
    assert inv['duplicates'][0]['attempts'] == [
        dict(dir=d1, resolved=False, timeout=False, empty_patch=False),
        dict(dir=d2, resolved=True, timeout=False, empty_patch=False)]
    assert inv['complete']


@pytest.mark.parametrize('duplicate', [False, True])
def test_bad_inventory_exit_no_file(tmp_path, registered, duplicate, capsys):
    ids = registered + [registered[0]] if duplicate else registered[:-1]
    directory, cs = make_run(tmp_path, 'bad', ids)
    out = tmp_path / 'output.json'
    opts = evidence(tmp_path, directory, cs)
    main, cm = make_run(tmp_path, 'main', [])
    rc = m.main(['metrics', 'arm3', 'arm2', str(out), '--arm3', directory, main,
                 '--base-dirs', directory, '--classifiers', directory + '=' + ','.join(cs[directory]),
                 '--identity-json', opts['identity_json'], '--bundle', 'v012',
                 '--transport', directory + '=' + 'b'*64, '--push-event', directory + '=smoke',
                 '--push-event', main + '=main', '--transport', main + '=' + 'b'*64,
                 '--classifiers', main + '=' + ','.join(cm[main]), '--smoke-json', opts['smoke_json']])
    assert rc == 3 and not out.exists()
    assert 'inventory' in capsys.readouterr().out


def test_smoke_positive_and_missing(tmp_path, registered):
    directory, cs = make_run(tmp_path, 'smoke', registered[:2])
    result = m.arm3smoke_metrics(directory, cs[directory][0], **smoke_options(tmp_path, directory, cs))
    assert result['overall'] == 'PASS'
    assert result['criteria']['i']['total_blocks'] == 6
    assert_no_text(result)
    trace = Path(directory) / 'runs' / registered[0] / 'trace.json'
    trace.unlink()
    result = m.arm3smoke_metrics(directory, cs[directory][0], **smoke_options(tmp_path, directory, cs))
    assert result['criteria']['i']['status'] == 'UNVERIFIABLE'
    assert result['overall'] == 'FAIL'


@pytest.mark.parametrize('field', ['agent_clock_seconds', 'finalization_seconds'])
@pytest.mark.parametrize('value', [None, -1, float('nan'), float('inf'), '200', True, 221])
def test_timing_missing_invalid(field, value):
    row = dict(instance_id='a', agent_clock_seconds=220, finalization_seconds=30)
    assert m.arm3_timing([row])['timing_pass']
    row[field] = value
    assert not m.arm3_timing([row])['timing_pass']


@pytest.mark.parametrize('change,status', [('identity', 'FAIL'), ('missing', 'FAIL'),
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
    assert m.arm3smoke_metrics(directory, cs[directory][0], **smoke_options(tmp_path, directory, cs))['criteria']['iii']['status'] == status


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
    d1, c1 = make_run(tmp_path, 'on', registered[:2], resolved=registered[:1])
    main, cm = make_run(tmp_path, 'main', registered[2:])
    c1 |= cm
    d2, c2 = make_run(tmp_path, 'off', registered)
    result = m.arm3_metrics('arm2', [d1, main], [d2], c1 | c2, **pair_evidence(tmp_path, d1, main, c1))
    assert result['primary']['on_only']['count'] == 1
    assert result['decision'] == 'NO-DIFFERENCE'
    assert result['arms']['arm3']['safety']['submitted_without_test']['count'] == 0
    assert result['env_drift']['pairing_void_candidate'] is False
    assert_no_text(result)
    paths = result['_schema']['input_shas']
    assert str(Path(d1) / 'runs' / registered[0] / 'trace.json') in paths
    smoke = tmp_path / 'smoke.json'; smoke.write_text('{"overall":"FAIL"}')
    opts = pair_evidence(tmp_path, d1, main, c1)
    smoke.write_text('{"overall":"FAIL"}')
    result = m.arm3_metrics('arm2', [d1, main], [d2], c1 | c2, **opts)
    assert result['decision'].startswith('INVALID')
    assert str(smoke) in result['_schema']['input_shas']


@pytest.mark.skipif(not (SAVED / 'runs/31b-v009-p7a1-main').exists(), reason='saved run artifacts absent')
def test_real_pair_and_smoke(monkeypatch):
    monkeypatch.chdir(SAVED)
    dirs = [str(Path(t).parent) for _, t, _, _ in m.base.PARTS]
    classifiers = {str(Path(t).parent): (d,a) for _,t,d,a in m.base.PARTS}
    result = m.arm3_metrics('arm1', dirs, [], classifiers)
    sensitivity = result.get('uncounted_sensitivity', result)
    primary = sensitivity['primary']
    assert primary['on_only']['count'] == primary['off_only']['count'] == 0
    assert primary['p'] == 1.
    assert primary['arm3_resolved']['k'] == primary['base_resolved']['k'] == 4
    assert primary['arm3_resolved']['n'] == 33
    assert sensitivity['arms']['arm3']['safety']['empty_patch']['count'] == 12
    # Acceptance (b)'s KEEP-OFF conflicts with literal H>=5: saved arm1 has 7 H rows.
    assert sensitivity['arms']['arm3']['h_rows']['count'] == 7
    assert result['decision'].startswith('INVALID')
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
    d1, c1 = make_run(tmp_path, 'on', registered[:2])
    main, cm = make_run(tmp_path, 'main', registered[2:])
    c1 |= cm
    d2, c2 = make_run(tmp_path, 'off', registered)
    records, _, _, headers = m.aggregate_arm([d1, main], c1)
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
    out = m.arm3_metrics('arm2', [d1, main], [d2], c1 | c2, **pair_evidence(tmp_path, d1, main, c1))
    assert out['env_drift']['pairing_void_candidate'] is True
    assert set(out['env_drift']['differences']) == {'kernel_code', 'gpu_count'}
    assert out['decision'].startswith('INVALID (pairing voided:')


def rewrite_timing(directory, classifiers, edit):
    timing = Path(directory) / 'timing.jsonl'
    records = [json.loads(line) for line in timing.read_text().splitlines()]
    edit(records)
    timing.write_text('\n'.join(map(json.dumps, records)) + '\n')
    for file in classifiers[directory]:
        data = json.loads(Path(file).read_text())
        data['input_sha256'] = m.base.sha(timing)
        Path(file).write_text(json.dumps(data))


@pytest.fixture
def full_pair(tmp_path, monkeypatch):
    ids = [f'repo__{i}' for i in range(33)]
    path = tmp_path / 'ids.txt'; path.write_text('\n'.join(ids) + '\n')
    screened = tmp_path / 'screened.txt'; screened.write_text('')
    monkeypatch.setattr(m.base, 'ARM_IDS', str(path))
    monkeypatch.setattr(m.base, 'SCREENED_IDS', str(screened))
    smoke, c1 = make_run(tmp_path, 'smoke', ids[:2], resolved=ids[:2])
    main, c2 = make_run(tmp_path, 'main', ids[2:], resolved=ids[2:4])
    off, c3 = make_run(tmp_path, 'off', ids)
    opts = evidence(tmp_path, smoke, c1)
    opts['transports'][main] = 'b'*64
    opts['push_events'][main] = 'main'
    actual_smoke = m.arm3smoke_metrics(smoke, c1[smoke][0], **{
        k: ({smoke: opts[k][smoke]} if k in ('transports', 'push_events') else opts[k])
        for k in ('identity_json', 'bundle', 'transports', 'push_events')})
    assert actual_smoke['overall'] == 'PASS'
    Path(opts['smoke_json']).write_text(json.dumps(actual_smoke))
    return [smoke, main], [off], c1 | c2 | c3, opts, ids


@pytest.mark.parametrize('quality,expected', [
    ('adopt', 'ON-ADOPT'), ('off', 'KEEP-OFF'),
    ('noise', 'NO-DIFFERENCE'), ('veto', 'ON-BETTER-VETOED')])
def test_full_33_quality_verdicts(full_pair, quality, expected):
    dirs, off, cs, opts, ids = full_pair
    if quality == 'off':
        rewrite_timing(off[0], cs, lambda rs: [r.update(resolved=True) for r in rs if 'instance_id' in r])
    elif quality == 'noise':
        rewrite_timing(off[0], cs, lambda rs: [r.update(resolved=r['instance_id'] == ids[0])
                                               for r in rs if 'instance_id' in r])
    elif quality == 'veto':
        rewrite_timing(dirs[1], cs, lambda rs: [r.update(agent_clock_seconds=221)
                                               for r in rs if 'instance_id' in r])
    result = m.arm3_metrics('arm2', dirs, off, cs, **opts)
    assert result['decision'] == expected
    assert result['n_rows'] == 33
    assert m.base.sha(opts['identity_json']) == result['_schema']['input_shas'][opts['identity_json']]
    assert m.base.sha(opts['base_verdict_json']) == result['_schema']['input_shas'][opts['base_verdict_json']]
    assert_no_text(result)


@pytest.mark.parametrize('change,expected', [
    ('foreign_smoke', 'INVALID (smoke evidence not bound)'),
    ('zero_thinking', 'INVALID (smoke recomputed: i)'),
    ('failed_smoke', 'INVALID'),
    ('agent_path', 'INVALID (pairing voided:'),
    ('verification_path', 'INVALID (pairing voided:'),
    ('conflicting_agent', 'INVALID (identity mismatch)'),
    ('transport', 'INVALID (identity mismatch)'),
    ('missing_identity', 'INVALID (identity mismatch)'),
    ('failed_identity', 'INVALID (identity mismatch)'),
    ('no_main_event', 'INVALID (identity mismatch)'),
    ('invalid_base', 'INVALID (base invalid/unruled)'),
    ('missing_base', 'INVALID (base invalid/unruled)'),
    ('unreadable_base', 'INVALID (base invalid/unruled)'),
    ('unruled_base', 'INVALID (base invalid/unruled)'),
    ('harm_base', 'INVALID (base invalid/unruled)'),
    ('arm2_output_base', 'INVALID (base invalid/unruled)'),
])
def test_full_33_fail_closed(full_pair, change, expected):
    dirs, off, cs, opts, ids = full_pair
    if change == 'foreign_smoke':
        smoke = json.loads(Path(opts['smoke_json']).read_text())
        smoke['_schema']['input_shas'][str(Path(dirs[0]) / 'timing.jsonl')] = '0'*64
        Path(opts['smoke_json']).write_text(json.dumps(smoke))
    elif change == 'zero_thinking':
        for iid in ids[:2]:
            (Path(dirs[0]) / 'runs' / iid / 'trace.json').write_text('{"entries":[]}')
        # Even hash-bound PASS evidence cannot substitute for recomputing criterion i.
        smoke = json.loads(Path(opts['smoke_json']).read_text())
        for iid in ids[:2]:
            tr = Path(dirs[0]) / 'runs' / iid / 'trace.json'
            smoke['_schema']['input_shas'][str(tr)] = m.base.sha(tr)
        Path(opts['smoke_json']).write_text(json.dumps(smoke))
    elif change == 'failed_smoke':
        smoke = json.loads(Path(opts['smoke_json']).read_text()); smoke['overall'] = 'FAIL'
        Path(opts['smoke_json']).write_text(json.dumps(smoke))
    elif change in ('agent_path', 'verification_path'):
        rewrite_timing(off[0], cs, lambda rs: rs[0]['kernel_code'].update({change + '_sha256': 'e'*64}))
    elif change == 'conflicting_agent':
        rewrite_timing(dirs[1], cs, lambda rs: rs[0].update(agent_yaml_sha256='e'*64))
    elif change == 'transport':
        opts['transports'][dirs[1]] = 'e'*64
    elif change in ('missing_identity', 'failed_identity', 'no_main_event'):
        data = json.loads(Path(opts['identity_json']).read_text())
        if change == 'missing_identity':
            data['records'] = []
        elif change == 'no_main_event':
            data['records'] = [r for r in data['records'] if r['event'] != 'main']
        else:
            for r in data['records']:
                r['bundles']['v012']['pass'] = False
        Path(opts['identity_json']).write_text(json.dumps(data))
    elif change == 'missing_base':
        opts['base_verdict_json'] = None
    elif change == 'unreadable_base':
        opts['base_verdict_json'] += '.absent'
    else:
        Path(opts['base_verdict_json']).write_text(json.dumps(
            dict(decision='INVALID') if change == 'invalid_base' else
            dict(verdict='HARM') if change == 'harm_base' else
            dict(totals={}, rows=[]) if change == 'arm2_output_base' else {}))
    result = m.arm3_metrics('arm2', dirs, off, cs, **opts)
    assert result['decision'].startswith(expected)
    if change in ('conflicting_agent', 'transport'):
        assert result['decision_inputs']['identity']['mismatching_dirs'] == [dirs[1]]
        assert result['n_rows'] == 2
        assert len(result['inventory']['arm3']['counted_missing']) == 31
        assert 'primary' not in result


@pytest.mark.parametrize('change,status', [('startup', 'UNVERIFIABLE'), ('transport', 'FAIL'),
                                          ('record', 'FAIL'), ('pass', 'FAIL')])
def test_smoke_mechanics_bound(tmp_path, registered, change, status):
    directory, cs = make_run(tmp_path, 'smoke', registered[:2])
    opts = smoke_options(tmp_path, directory, cs)
    if change == 'startup':
        rewrite_timing(directory, cs, lambda rs: rs.pop())
    elif change == 'transport':
        opts['transports'][directory] = 'e'*64
    else:
        data = json.loads(Path(opts['identity_json']).read_text())
        if change == 'record':
            data['records'] = []
        else:
            for r in data['records']:
                r['bundles']['v012']['pass'] = False
        Path(opts['identity_json']).write_text(json.dumps(data))
    result = m.arm3smoke_metrics(directory, cs[directory][0], **opts)
    assert result['criteria']['iii']['status'] == status
    assert result['overall'] != 'PASS'


@pytest.mark.parametrize('missing', ['smoke-json', 'identity-json', 'bundle', 'transport', 'push-event'])
def test_required_cli_evidence(full_pair, tmp_path, missing):
    dirs, off, cs, opts, _ = full_pair
    argv = ['metrics', 'arm3', 'arm2', str(tmp_path / 'out.json'), '--arm3', *dirs,
            '--base-dirs', *off]
    for name, value in [('smoke-json', opts['smoke_json']), ('identity-json', opts['identity_json']),
                        ('bundle', 'v012'), ('transport', dirs[0] + '=' + 'b'*64),
                        ('transport', dirs[1] + '=' + 'b'*64),
                        ('push-event', dirs[0] + '=smoke'), ('push-event', dirs[1] + '=main')]:
        if name != missing:
            argv.extend(['--' + name, value])
    for d, pair in cs.items():
        argv.extend(['--classifiers', d + '=' + ','.join(pair)])
    with pytest.raises(SystemExit) as exc:
        m.main(argv)
    assert exc.value.code != 0


def test_chunk_identity_and_duplicate_outcomes(full_pair, tmp_path):
    dirs, off, cs, opts, ids = full_pair
    chunk, extra = make_run(tmp_path, 'chunk', [ids[2]], resolved=ids[2:3])
    data = json.loads(Path(opts['identity_json']).read_text())
    for record in data['records']:
        if record['event'] == 'chunk1':
            record['event'] = 'chunk7'
    Path(opts['identity_json']).write_text(json.dumps(data))
    opts['transports'][chunk] = 'f'*64
    opts['push_events'][chunk] = 'chunk7'
    rewrite_timing(chunk, extra, lambda rs: rs[0].update(bundle_sha256='f'*64))
    result = m.arm3_metrics('arm2', dirs + [chunk], off, cs | extra, **opts)
    assert result['decision'] == 'ON-ADOPT'
    duplicate = result['inventory']['arm3']['duplicates'][0]
    assert duplicate['dirs'] == [dirs[1], chunk]
    assert duplicate['attempts'][1] == dict(dir=chunk, resolved=True, timeout=False, empty_patch=False)
    data = json.loads(Path(opts['identity_json']).read_text())
    data['records'] = [r for r in data['records'] if r['event'] != 'chunk7']
    Path(opts['identity_json']).write_text(json.dumps(data))
    rejected = m.arm3_metrics('arm2', dirs + [chunk], off, cs | extra, **opts)
    assert rejected['decision'] == 'INVALID (identity mismatch)'
    assert rejected['inventory']['arm3']['identity_excluded_dirs'] == [chunk]


@pytest.mark.parametrize('field', ['zip_ok', 'content_ok'])
def test_smoke_requires_both_identity_checks(tmp_path, registered, field):
    directory, cs = make_run(tmp_path, 'smoke', registered[:2])
    opts = smoke_options(tmp_path, directory, cs)
    data = json.loads(Path(opts['identity_json']).read_text())
    for rec in data['records']:
        rec['bundles']['v012'][field] = False
    Path(opts['identity_json']).write_text(json.dumps(data))
    assert m.arm3smoke_metrics(directory, cs[directory][0], **opts)['criteria']['iii']['status'] == 'FAIL'


def test_arm1_self_pair_literal_h(full_pair, monkeypatch):
    dirs, _, cs, opts, ids = full_pair
    # Reclassify seven rows H, with unchanged timing bindings and both classifiers present.
    for directory in dirs:
        path = Path(cs[directory][0])
        data = json.loads(path.read_text())
        for row in data['rows']:
            row['h'] = 'H' if row['instance_id'] in ids[:7] else None
        path.write_text(json.dumps(data))
    monkeypatch.setattr(m.base, 'PARTS', [(str(n), str(Path(d) / 'timing.jsonl'), *cs[d])
                                         for n, d in enumerate(dirs)])
    result = m.arm3_metrics('arm1', dirs, [], cs, **opts)
    assert result['decision'].startswith('INVALID')
    assert result['arms']['arm3']['h_rows']['count'] == 7
    assert result['decision_inputs']['base_valid'] is True
    assert 'ENV CONTROL' in result['base_validity']


@pytest.mark.parametrize('mode', ['arm3', 'arm3smoke'])
def test_transport_required_for_each_dir(full_pair, tmp_path, mode):
    dirs, off, cs, opts, _ = full_pair
    common = ['--identity-json', opts['identity_json'], '--bundle', 'v012',
              '--transport', dirs[1] + '=' + 'b'*64]
    if mode == 'arm3':
        argv = ['metrics', mode, 'arm2', str(tmp_path / 'out.json'), '--arm3', *dirs,
                '--base-dirs', *off, '--smoke-json', opts['smoke_json'], *common]
        for d, pair in cs.items():
            argv.extend(['--classifiers', d + '=' + ','.join(pair)])
    else:
        argv = ['metrics', mode, dirs[0], cs[dirs[0]][0], str(tmp_path / 'out.json'), *common]
    with pytest.raises(SystemExit) as exc:
        m.main(argv)
    assert exc.value.code == 2


def test_zero_thinking_with_stale_pass_smoke(full_pair):
    dirs, off, cs, opts, ids = full_pair
    for iid in ids[:2]:
        (Path(dirs[0]) / 'runs' / iid / 'trace.json').write_text('{"entries":[]}')
    assert m.arm3_metrics('arm2', dirs, off, cs, **opts)['decision'] == 'INVALID (smoke recomputed: i)'


@pytest.mark.parametrize('mode', ['arm3', 'arm3smoke'])
def test_cli_valid_evidence(full_pair, tmp_path, mode):
    dirs, off, cs, opts, _ = full_pair
    out = tmp_path / 'cli-output.json'
    common = ['--identity-json', opts['identity_json'], '--bundle', 'v012',
              '--transport', dirs[0] + '=' + 'b'*64, '--push-event', dirs[0] + '=smoke']
    if mode == 'arm3':
        argv = ['metrics', mode, 'arm2', str(out), '--arm3', *dirs, '--base-dirs', *off,
                '--smoke-json', opts['smoke_json'], '--base-verdict-json', opts['base_verdict_json'],
                '--transport', dirs[1] + '=' + 'b'*64, '--push-event', dirs[1] + '=main', *common]
        for d, pair in cs.items():
            argv.extend(['--classifiers', d + '=' + ','.join(pair)])
    else:
        argv = ['metrics', mode, dirs[0], cs[dirs[0]][0], str(out), *common]
    assert m.main(argv) == 0
    result = json.loads(out.read_text())
    assert result.get('decision', result.get('overall')) == ('ON-ADOPT' if mode == 'arm3' else 'PASS')


def edit_identity(opts, edit):
    path = Path(opts['identity_json'])
    data = json.loads(path.read_text())
    edit(data['records'])
    path.write_text(json.dumps(data))


def test_two_chunks_need_two_proofs(full_pair, tmp_path):
    dirs, off, cs, opts, ids = full_pair
    chunks = []
    for n in (1, 2):
        directory, pair = make_run(tmp_path, f'chunk{n}', [ids[n + 1]])
        chunks.append(directory)
        cs |= pair
        opts['push_events'][directory] = f'chunk{n}'
        opts['transports'][directory] = 'b'*64
    result = m.arm3_metrics('arm2', dirs + chunks, off, cs, **opts)
    assert result['decision'] == 'INVALID (identity mismatch)'
    assert result['inventory']['arm3']['identity_excluded_dirs'] == [chunks[1]]
    runs = result['decision_inputs']['identity']['runs']
    assert runs[-1]['event'] == 'chunk2' and runs[-1]['record_count'] == 0
    assert runs[-2]['checked']


@pytest.mark.parametrize('field', ['pass', 'zip_ok', 'content_ok', 'zip_sha256',
    'manifest_zip_sha256', 'agent_yaml_sha256', 'only_in_zip', 'only_in_dir',
    'byte_mismatch', 'duplicate_members', 'zip_path'])
def test_partial_identity_rejected(full_pair, field):
    dirs, off, cs, opts, _ = full_pair
    edit_identity(opts, lambda rs: rs[1]['bundles']['v012'].pop(field))
    assert m.arm3_metrics('arm2', dirs, off, cs, **opts)['decision'] == 'INVALID (identity mismatch)'


@pytest.mark.parametrize('change', ['different_zip', 'manifest_mismatch', 'manifest_missing',
                                  'manifest_unparseable', 'nonempty_list', 'not_list'])
def test_registered_zip_proof(full_pair, change):
    dirs, off, cs, opts, _ = full_pair
    if change.startswith('manifest_'):
        path = m.BUNDLES_ROOT / 'v012/MANIFEST.md'
        if change == 'manifest_missing':
            path.unlink()
        else:
            path.write_text('zip sha256: ' + ('e'*64 if change == 'manifest_mismatch' else 'invalid'))
    else:
        def mutate(rs):
            proof = rs[1]['bundles']['v012']
            if change == 'different_zip':
                proof.update(zip_sha256='e'*64, manifest_zip_sha256='e'*64)
            else:
                proof['duplicate_members'] = ['agent.yaml'] if change == 'nonempty_list' else ''
        edit_identity(opts, mutate)
    result = m.arm3_metrics('arm2', dirs, off, cs, **opts)
    assert result['decision'] == 'INVALID (identity mismatch)'
    path = m.BUNDLES_ROOT / 'v012/MANIFEST.md'
    if path.is_file():
        assert result['_schema']['input_shas'][str(path)] == m.base.sha(path)


@pytest.mark.parametrize('latest_pass', [False, True])
def test_latest_exact_event_record(full_pair, latest_pass):
    dirs, off, cs, opts, _ = full_pair
    def mutate(rs):
        newer = json.loads(json.dumps(rs[1]))
        rs[1]['bundles']['v012']['pass'] = not latest_pass
        newer['bundles']['v012']['pass'] = latest_pass
        rs.append(newer)
    edit_identity(opts, mutate)
    result = m.arm3_metrics('arm2', dirs, off, cs, **opts)
    assert result['decision'] == ('ON-ADOPT' if latest_pass else 'INVALID (identity mismatch)')
    assert result['decision_inputs']['identity']['runs'][1]['record_count'] == 2


@pytest.mark.parametrize('criterion', ['h', 'timing', 'startup', 'verification'])
def test_recompute_full_smoke(full_pair, criterion):
    dirs, off, cs, opts, _ = full_pair
    if criterion == 'h':
        path = Path(cs[dirs[0]][0])
        data = json.loads(path.read_text()); data['rows'][0]['h'] = 'H'
        path.write_text(json.dumps(data))
    else:
        def mutate(rs):
            if criterion == 'timing':
                rs[1]['agent_clock_seconds'] = 221
            elif criterion == 'startup':
                rs.pop()
            else:
                rs[1]['resolved'] = None
        rewrite_timing(dirs[0], cs, mutate)
    # Bind the modified inputs to isolate current mechanics from saved-json binding.
    smoke = json.loads(Path(opts['smoke_json']).read_text())
    for path in (str(Path(dirs[0]) / 'timing.jsonl'), cs[dirs[0]][0]):
        smoke['_schema']['input_shas'][path] = m.base.sha(path)
    Path(opts['smoke_json']).write_text(json.dumps(smoke))
    result = m.arm3_metrics('arm2', dirs, off, cs, **opts)
    assert result['decision'].startswith('INVALID (smoke recomputed:')
    kwargs = {k: opts[k] for k in ('identity_json', 'bundle')}
    kwargs.update(transports={dirs[0]: opts['transports'][dirs[0]]}, push_events={dirs[0]: 'smoke'})
    assert m.arm3smoke_metrics(dirs[0], cs[dirs[0]][0], **kwargs)['overall'] == 'FAIL'


def test_missing_classifier_binding(full_pair):
    dirs, off, cs, opts, _ = full_pair
    path = Path(opts['smoke_json'])
    smoke = json.loads(path.read_text())
    assert smoke['_schema']['input_shas'].pop(cs[dirs[0]][0]) == m.base.sha(cs[dirs[0]][0])
    path.write_text(json.dumps(smoke))
    assert m.arm3_metrics('arm2', dirs, off, cs, **opts)['decision'] == 'INVALID (smoke evidence not bound)'


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'two_main', 'foreign_event', 'foreign_transport', 'wrong_smoke'])
def test_push_mapping_fail_closed(full_pair, change):
    dirs, off, cs, opts, _ = full_pair
    if change == 'missing':
        opts['push_events'].pop(dirs[1])
    elif change in ('duplicate', 'two_main'):
        opts['push_events'][dirs[0]] = 'main'
    elif change == 'foreign_event':
        opts['push_events']['/tmp/foreign'] = 'chunk2'
    elif change == 'foreign_transport':
        opts['transports']['/tmp/foreign'] = 'b'*64
    else:
        opts['push_events'] = {dirs[0]: 'main', dirs[1]: 'smoke'}
    assert m.arm3_metrics('arm2', dirs, off, cs, **opts)['decision'] == 'INVALID (identity mismatch)'


def test_changed_classifier_with_stale_pass(full_pair):
    dirs, off, cs, opts, _ = full_pair
    path = Path(cs[dirs[0]][0])
    data = json.loads(path.read_text()); data['rows'][0]['h'] = 'H'
    path.write_text(json.dumps(data))
    result = m.arm3_metrics('arm2', dirs, off, cs, **opts)
    assert not result['decision_inputs']['smoke_bound']
    assert result['decision'] == 'INVALID (smoke recomputed: iii)'


@pytest.mark.parametrize('mode', ['arm3', 'arm3smoke'])
@pytest.mark.parametrize('change', ['missing', 'duplicate', 'foreign_event', 'foreign_transport', 'invalid_event'])
def test_cli_rejects_bad_push_mapping(full_pair, tmp_path, mode, change):
    dirs, off, cs, opts, _ = full_pair
    events = dict(opts['push_events']) if mode == 'arm3' else {dirs[0]: 'smoke'}
    transports = dict(opts['transports']) if mode == 'arm3' else {dirs[0]: 'b'*64}
    if change == 'missing':
        events.pop(dirs[0])
    elif change == 'duplicate':
        events[dirs[0]] = 'main'
    elif change == 'foreign_event':
        events['/tmp/foreign'] = 'chunk2'
    elif change == 'foreign_transport':
        transports['/tmp/foreign'] = 'b'*64
    else:
        events[dirs[0]] = 'chunk0'
    out = tmp_path / 'rejected.json'
    argv = ['metrics', mode]
    if mode == 'arm3':
        argv += ['arm2', str(out), '--arm3', *dirs, '--base-dirs', *off,
                 '--smoke-json', opts['smoke_json']]
        for d, pair in cs.items():
            argv += ['--classifiers', d + '=' + ','.join(pair)]
    else:
        argv += [dirs[0], cs[dirs[0]][0], str(out)]
    argv += ['--identity-json', opts['identity_json'], '--bundle', 'v012']
    for d, event in events.items():
        argv += ['--push-event', d + '=' + event]
    for d, transport in transports.items():
        argv += ['--transport', d + '=' + transport]
    with pytest.raises(SystemExit) as exc:
        m.main(argv)
    assert exc.value.code == 2
    assert not out.exists()


# Plan 009 Addendum S81 (dec 081 items 2-4): governing vs literal stray, unrounded comparisons.
GOLD = ('--- a/pkg/mod.py\n+++ b/pkg/mod.py\n@@ -1,2 +1,3 @@\n x\n+y\n'
        '--- a/scripts/new_tool.py\n+++ b/scripts/new_tool.py\n@@ -0,0 +1,2 @@\n+a\n+b\n')


def gold_tasks(tmp_path, patches):
    path = tmp_path / 'tasks.jsonl'
    path.write_text(''.join(json.dumps(dict(instance_id=i, patch=p)) + '\n' for i, p in patches.items()))
    m._GOLD_DIRS.clear()
    return path


def test_s81_gold_created_parser():
    assert m.gold_created_files(GOLD) == {'scripts/new_tool.py'}
    assert m.gold_created_files('--- /dev/null\n+++ b/a/b.txt\n@@ -0,0 +1 @@\n+x\n') == {'a/b.txt'}
    assert m.gold_created_files('--- a/x.py\n+++ b/x.py\n@@ -3,0 +4 @@\n+x\n') == set()


def test_s81_exact_dir_only():
    literal = ['scripts/other_name.py', 'scripts/sub/x.py', 'scripts2/x.py', 'x.txt', 'docs/scripts/x.md']
    governing, exempted = m.amended_stray(literal, {'scripts'})
    assert exempted == [dict(path='scripts/other_name.py', gold_dir='scripts')]
    assert governing == ['scripts/sub/x.py', 'scripts2/x.py', 'x.txt', 'docs/scripts/x.md']
    assert m.amended_stray(['scripts/a.py'], None) == (['scripts/a.py'], [])


def test_s81_stray_safety_literal_unchanged(tmp_path):
    tasks = gold_tasks(tmp_path, {'t1': GOLD, 't2': GOLD, 't3': '--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+b\n'})
    rows = [dict(instance_id='t1', stray_files=['scripts/other.py']),          # exempted (gold dir)
            dict(instance_id='t2', stray_files=['scripts/sub/child.py', 'scripts/ok.py']),  # child dir NOT exempted
            dict(instance_id='t3', stray_files=['scripts/x.py']),               # no gold-created file -> stray
            dict(instance_id='t4', stray_files=[])]                             # empty: no gold lookup needed
    governing, literal, per_row = m.stray_safety(rows, tasks)
    assert literal == dict(count=3, instance_ids=['t1', 't2', 't3'])
    assert governing == dict(count=2, instance_ids=['t2', 't3'])
    t2 = next(r for r in per_row if r['instance_id'] == 't2')
    assert t2['governing'] == ['scripts/sub/child.py'] and t2['exempted'] == [dict(path='scripts/ok.py', gold_dir='scripts')]


def test_s81_missing_evidence_fails(tmp_path):
    tasks = gold_tasks(tmp_path, {'t1': GOLD})
    governing, literal, _ = m.stray_safety([dict(instance_id='zz', stray_files=['scripts/a.py'])], tasks)
    assert governing == 'not available' and literal['count'] == 1
    assert m.stray_safety([dict(instance_id='t1', stray_files=None)], tasks)[0] == 'not available'
    assert m.stray_safety([dict(instance_id='t1')], tasks)[0] == 'not available'
    m._GOLD_DIRS.clear()
    assert m.stray_safety([dict(instance_id='t1', stray_files=['scripts/a.py'])], tmp_path / 'nope.jsonl')[0] == 'not available'
    m._GOLD_DIRS.clear()


def test_s81_unrounded_percentile():
    vals = [100.0, 210.0009]
    assert m.base.pct(vals, 1.0) == 210.0
    assert m.pct_raw(vals, 1.0) == 210.0009
    assert m.pct_raw([1.0, 2.0, 3.0], .5) == 2.0 and m.pct_raw([None], .9) is None
    assert m.arm3_timing([dict(instance_id='a', agent_clock_seconds=220.0009, finalization_seconds=1)])['timing_pass'] is False
