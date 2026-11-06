"""Offline synthetic checks for the binding plan-008 definitions. No task content."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / 'eval'))
import plan008_metrics as m
import plan007_arm1_summary as old

YAML = ROOT_DIR / m.GATE_YAML


def call(tool, args=None, author=m.ROOT):
    return dict(type='tool_call', author=author, tool=tool, args=args or {})


def response(tool, result, author=m.ROOT):
    return dict(type='tool_response', author=author, tool=tool,
                result=json.dumps(result) if not isinstance(result, str) else result)


def invoke(tool, args=None, result=None, author=m.ROOT):
    return [call(tool, args, author), response(tool, result, author)]


def gate(reply='SUBMITTED', reason='changes', size=23):
    es = [call('submit_patch', {'request': 'submit'})]
    es += invoke('run_command', {'command': m._gate_command(YAML)},
                 {'status': 'ok', 'stdout': 'GATE call=1 kept_files=1\n' +
                  ('VERDICT=EDIT_FIRST' if reply.startswith('NOT SUBMITTED') else f'VERDICT=SUBMIT reason={reason}')}, 'submit_patch')
    if not reply.startswith('NOT SUBMITTED'):
        result = {'error': 'synthetic'} if reply.startswith('SUBMIT FAILED') else {'status': 'ok', 'patch_size': size}
        es += invoke('submit_patch', result=result, author='submit_patch')
    es += [response('submit_patch', {'raw': reply})]
    return es


def row(**kw):
    return dict(dict(verified_patch_bytes=23, agent_clock_seconds=210, patch_submitted=True), **kw)


def statuses(criteria):
    return {k: v['status'] for k, v in criteria.items()}


def test_root_filter_and_repeats(tmp_path):
    es = []
    for _ in range(5):
        es += gate()
    roots = m.root_tool_calls(es)
    assert len(roots) == 5
    assert all(m._reply(c['response']) == 'SUBMITTED' for c in roots)
    assert m.identical_runs_root(es) == dict(max_run=5, runs_ge3=1, runs_ge5=1, repeated_calls=4)
    path = tmp_path / 'trace.json'
    path.write_text(json.dumps({'entries': es}))
    assert old.identical_runs(path)['max_run'] == 1
    assert m.identical_runs_root([])['max_run'] == 0


def test_pairing_fifo_author_and_missing():
    es = [call('run_command'), call('run_command', author='code_analyzer_agent'),
          response('run_command', 'nested', 'code_analyzer_agent'),
          response('run_command', 'root'), call('read_file')]
    pairs = m.root_tool_calls(es)
    assert [c['response'] for c in pairs] == ['root', None]
    assert m.root_tool_calls(es, 'code_analyzer_agent')[0]['response'] == 'nested'
    es = [call('read_file'), call('read_file'), response('read_file', 'one'), response('read_file', 'two')]
    assert [c['response'] for c in m.root_tool_calls(es)] == ['one', 'two']


@pytest.mark.parametrize('command', ['pytest -q', 'python -m unittest', 'tox -e py'])
def test_success_boundary(command):
    es = gate(m.BOUNCE) + invoke('edit_file') + invoke('run_command', {'command': command}) + gate()
    assert m.successful_submit_index(es) == 3
    assert m.submitted_without_test(es) is False
    # A test between the bounce and success counts, even with no edit.
    assert m.submitted_without_test(gate(m.BOUNCE) + invoke('run_command', {'command': command}) + gate()) is False


def test_no_test_and_never_success():
    assert m.submitted_without_test(gate()) is True
    assert m.submitted_without_test(gate() + invoke('run_command', {'command': 'pytest'})) is True
    assert m.submitted_without_test(gate(m.BOUNCE)) is None
    assert m.submitted_without_test([]) is None
    assert m.submitted_without_test(invoke('submit_patch', result={'status': 'error', 'patch_size': 4})) is None
    assert m.submitted_without_test(invoke('submit_patch', result={'status': 'ok', 'patch_size': 0})) is True
    assert m.successful_submit_index(gate('SUBMIT FAILED: failure')) is None
    # Nested tests and incidental substrings do not count.
    es = invoke('run_command', {'command': 'pytest'}, author='code_analyzer_agent')
    es += invoke('run_command', {'command': 'echo pytestish; unittest'}) + gate()
    assert m.submitted_without_test(es) is True


def test_gate_descriptives():
    es = gate(m.BOUNCE) + invoke('edit_file') + gate(m.BOUNCE) + gate(reason='forced')
    d = m.gate_descriptives(es)
    assert {k: v for k, v in d.items() if k != 'gate_run_cmds'} == dict(
        gate_calls=3, bounces=2, forced=1, check_error=0, submit_failed=0,
        bounce_no_followup=0, gate_llm_limit=0, unacknowledged_inner_submits=0, gate_internal_visible=True)
    assert d['gate_run_cmds'] == [m._gate_command(YAML)] * 3
    assert m.gate_descriptives(gate(m.BOUNCE))['bounce_no_followup'] == 1
    assert m.gate_descriptives(gate(reason='check_error'))['check_error'] == 1
    assert m.gate_descriptives(gate('SUBMIT FAILED: error'))['submit_failed'] == 1
    hidden = invoke('submit_patch', result={'raw': 'SUBMITTED'})
    assert m.gate_descriptives(hidden)['gate_internal_visible'] is False


NEW = 'diff --git a/a.py b/a.py\nnew file mode 100644\n--- /dev/null\n+++ b/a.py\n@@ -0,0 +1 @@\n+x\n'
MOD = 'diff --git a/b.py b/b.py\nindex 123..456 100644\n--- a/b.py\n+++ b/b.py\n'


@pytest.mark.parametrize('patch,expected', [('', False), (' \n', False), ('hello', False),
    (NEW, True), (NEW + NEW, True), (NEW + MOD, False), (MOD, False),
    ('diff --git a/a b/a\ndeleted file mode 100644\n', False)])
def test_untracked_only(patch, expected):
    assert m.untracked_only(patch) is expected


def check(r, es, yaml=YAML, patch='x' * 23, loaded=True):
    return m.smoke_check(r, es, yaml, scored_patch=patch, test_files_loaded=loaded)


def test_smoke_pass():
    criteria = check(row(), gate(), YAML)
    assert statuses(criteria) == dict.fromkeys(['i', 'ii', 'iii', 'iv', 'v'], 'PASS')
    assert all(c['reason'] for c in criteria.values())
    es = gate(m.BOUNCE) + invoke('edit_file') + gate()
    assert all(c['status'] == 'PASS' for c in check(row(), es, YAML).values())


@pytest.mark.parametrize('change', ['command', 'missing_submit', 'late_root', 'not_submitted', 'submit_before_check', 'extra_command'])
def test_smoke_i_fail(change):
    es = gate()
    r = row()
    if change == 'command':
        es[1]['args']['command'] += ' '
    elif change == 'missing_submit':
        del es[3:5]
    elif change == 'late_root':
        es.append(dict(type='thinking', author=m.ROOT, content='synthetic'))
    elif change == 'not_submitted':
        r['patch_submitted'] = False
    elif change == 'submit_before_check':
        es[1:5] = es[3:5] + es[1:3]
    elif change == 'extra_command':
        es[1:1] = invoke('run_command', {'command': m._gate_command(YAML)}, {}, 'submit_patch')
    assert check(r, es, YAML)['i']['status'] == 'FAIL'


def test_smoke_ii_fail_and_missing():
    assert check(row(verified_patch_bytes=24), gate(), YAML)['ii']['status'] == 'FAIL'
    assert check(row(verified_patch_bytes=None), gate(), YAML)['ii']['status'] == 'UNVERIFIABLE'
    es = gate()
    es[4]['result'] = '{}'
    assert check(row(), es, YAML)['ii']['status'] == 'UNVERIFIABLE'


@pytest.mark.parametrize('change', ['check_error', 'failed', 'malformed', 'agent_error', 'tool_error', 'unknown_tool', 'compile_error'])
def test_smoke_iii_fail(change):
    es, r = gate(), row()
    if change == 'check_error':
        es = gate(reason='check_error')
    elif change == 'failed':
        es = gate('SUBMIT FAILED: synthetic')
    elif change == 'malformed':
        es[-1]['result'] = json.dumps({'raw': 'SUBMITTED extra'})
    elif change == 'agent_error':
        r['agent_error_text'] = 'synthetic failure'
    elif change == 'tool_error':
        es[2]['result'] = json.dumps({'error': {'type': 'ToolErrorPlugin'}})
    elif change == 'unknown_tool':
        es += invoke('missing', result='Unknown tool')
    elif change == 'compile_error':
        r['result_error'] = 'compile error'
    assert check(r, es, YAML)['iii']['status'] == 'FAIL'


def test_smoke_iv_and_v_fail():
    assert check(row(agent_clock_seconds=210.01), gate(), YAML)['iv']['status'] == 'FAIL'
    # Agent wall time is not the timeout-context clock.
    r = row(agent_clock_seconds=None)
    r['wall_seconds'] = {'agent': 1}
    assert check(r, gate(), YAML)['iv']['status'] == 'UNVERIFIABLE'
    assert check(row(), gate(m.BOUNCE) * 3 + gate(), YAML)['v']['status'] == 'FAIL'


def test_smoke_unverifiable_and_no_exemption():
    hidden = invoke('submit_patch', result={'raw': 'SUBMITTED'})
    assert check(row(), hidden)['i']['status'] == 'UNVERIFIABLE'
    r = row(patch_submitted=False, agent_timeout_fired=True)
    r['fallback_patch_bytes'] = 23
    cs = check(r, [])
    assert cs['i']['status'] == 'FAIL'
    assert cs['ii']['status'] == 'UNVERIFIABLE'
    assert check(r, gate(m.BOUNCE))['ii']['status'] == 'UNVERIFIABLE'


def make_run(tmp_path, entries, r=None, patch=NEW, nested=True, header=None):
    run = tmp_path / 'run'
    artifacts = run / 'runs' / 'synthetic' if nested else run / 'synthetic'
    artifacts.mkdir(parents=True)
    r = dict(row() if r is None else r, instance_id='synthetic')
    lines = ([json.dumps(header)] if header else []) + [json.dumps(r)]
    (run / 'timing.jsonl').write_text('\n'.join(lines) + '\n')
    (artifacts / 'trace.json').write_text(json.dumps({'entries': entries}))
    (artifacts / 'agent.patch').write_text(patch)
    (artifacts / 'result.json').write_text(json.dumps({'agent_patch': patch}))
    return run, artifacts


def task_inventory(tmp_path, test_patch=''):
    path = tmp_path / 'tasks.jsonl'
    path.write_text(json.dumps(dict(instance_id='synthetic', repo='synthetic/repo', base_commit='abc',
                                   problem_statement='', patch='', test_patch=test_patch)) + '\n')
    return path


def test_smoke_cli_counts_only(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(ROOT_DIR)
    tasks = task_inventory(tmp_path)
    monkeypatch.setenv('PLAN008_TASKS_PATH', str(tasks))
    run, artifacts = make_run(tmp_path, gate(size=len(NEW)), row(verified_patch_bytes=len(NEW.encode())))
    dest = tmp_path / 'out.json'
    assert m.main(['metrics', 'smoke', str(run), str(dest)]) == 0
    out = json.loads(dest.read_text())
    assert out['overall'] == 'PASS'
    assert 'gate_run_cmds' not in out['rows'][0]
    assert NEW not in dest.read_text()
    assert m._gate_command(YAML) not in dest.read_text()
    assert out['_schema']['script_sha256'] == old.sha(m.__file__)
    assert len(out['_schema']['input_shas']) == 5
    assert set(json.loads(capsys.readouterr().out)) == {'n_rows', 'overall'}
    r = dict(row(patch_submitted=False, agent_timeout_fired=True), instance_id='synthetic', fallback_patch_bytes=len(NEW))
    (run / 'timing.jsonl').write_text(json.dumps(r) + '\n')
    (artifacts / 'trace.json').write_text(json.dumps({'entries': []}))
    assert m.main(['metrics', 'smoke', str(run), str(dest)]) == 0
    out = json.loads(dest.read_text())
    assert out['overall'] == 'FAIL'
    assert out['rows'][0]['criteria']['i']['status'] == 'FAIL'


@pytest.mark.parametrize('args', [{}, {'request': ''}, {'request': None},
    {'request': 1}, {'request': []}, {'request': 'submit', 'extra': 1}, [], None])
def test_malformed_root_gate_args(args):
    es = gate()
    es[0]['args'] = args
    assert check(row(), es)['iii']['status'] == 'FAIL'
    # Even submit_patch({}) can execute successfully in ADK; evidence still fails schema.
    assert m.successful_submit_index(es) == 0


@pytest.mark.parametrize('index,args', [(1, {}), (1, {'command': 'other'}),
    (1, {'command': m._gate_command(YAML), 'extra': 1}), (1, []),
    (3, {'extra': 1}), (3, None), (3, [])])
def test_malformed_child_args(index, args):
    es = gate()
    es[index]['args'] = args
    assert check(row(), es)['iii']['status'] == 'FAIL'


def test_canonical_replies_and_mirrored_display():
    es = gate(m.BOUNCE)
    es.append(dict(type='final', author=m.ROOT, content=m.BOUNCE))
    es.append(dict(type='final', author='submit_patch', content=m.BOUNCE))
    es += gate(m.BOUNCE)
    es.append(dict(type='final', author=m.ROOT, content=m.BOUNCE))
    es += gate()
    es.append(dict(type='final', author=m.ROOT, content='SUBMITTED'))
    assert all(c['status'] == 'PASS' for c in check(row(), es).values())
    assert m.gate_descriptives(es)['bounces'] == 2
    assert check(row(), es + [call('read_file')])['i']['status'] == 'FAIL'
    assert check(row(), es + [dict(type='final', author=m.ROOT, content='other')])['i']['status'] == 'FAIL'
    es[-2]['author'] = 'other'
    assert check(row(), es)['iii']['status'] == 'FAIL'


@pytest.mark.parametrize('change', ['wrong_author', 'missing_check_reply', 'inner_error', 'edit_first_submit', 'missing_flag'])
def test_smoke_i_missing_and_failed_evidence(change):
    es, r = gate(), row()
    if change == 'wrong_author':
        for e in es[1:5]:
            e['author'] = 'other'
    elif change == 'missing_check_reply':
        del es[2]
    elif change == 'inner_error':
        es[4]['result'] = json.dumps({'error': 'synthetic'})
    elif change == 'edit_first_submit':
        es[2]['result'] = json.dumps({'stdout': 'VERDICT=EDIT_FIRST'})
    elif change == 'missing_flag':
        del r['patch_submitted']
    assert check(r, es)['i']['status'] in ('FAIL', 'UNVERIFIABLE')


@pytest.mark.parametrize('patch,loaded', [(None, True), ('x' * 23, False)])
def test_smoke_ii_missing_patch_or_tasks(patch, loaded):
    assert check(row(), gate(), patch=patch, loaded=loaded)['ii']['status'] == 'UNVERIFIABLE'


def test_smoke_ii_utf8_and_final_capture():
    text = 'é' * 23
    es = gate(size=1) + gate(size=len(text))
    assert check(row(verified_patch_bytes=len(text.encode())), es, patch=text)['ii']['status'] == 'PASS'
    assert check(row(verified_patch_bytes=len(text)), es, patch=text)['ii']['status'] == 'FAIL'
    assert check(row(verified_patch_bytes=len(text.encode())), gate(size=24), patch=text)['ii']['status'] == 'FAIL'


def test_smoke_real_strip_with_task_extras(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT_DIR)
    from swegemma.harness.verification import strip_protected_files_from_patch
    source = NEW.replace('+x', '+é')
    protected = NEW.replace('a.py', 'custom/checks.py')
    raw = source + protected
    tasks = task_inventory(tmp_path, protected)
    assert m.load_task_test_files(tasks) == {'synthetic': ['custom/checks.py']}
    scored = strip_protected_files_from_patch(raw, extra_protected_paths=['custom/checks.py'])
    assert scored == source
    r = row(verified_patch_bytes=len(scored.encode()))
    run, artifacts = make_run(tmp_path, gate(size=len(scored)), r, patch=raw)
    assert m.smoke_metrics(run, tasks)['overall'] == 'PASS'
    # Without loadable task test_files, criterion ii must fail closed.
    assert m.smoke_metrics(run, tmp_path / 'missing')['rows'][0]['criteria']['ii']['status'] == 'UNVERIFIABLE'
    other_tasks = json.loads(tasks.read_text())
    other_tasks['instance_id'] = 'other'
    tasks.write_text(json.dumps(other_tasks) + '\n')
    assert m.smoke_metrics(run, tasks)['rows'][0]['criteria']['ii']['status'] == 'UNVERIFIABLE'
    artifacts.joinpath('agent.patch').unlink()
    assert m.smoke_metrics(run, tasks)['overall'] == 'FAIL'


@pytest.mark.parametrize('clock', [-1, float('nan'), float('inf'), '210', True])
def test_smoke_clock_invalid(clock):
    assert check(row(agent_clock_seconds=clock), gate())['iv']['status'] == 'UNVERIFIABLE'


def test_deadline_between_capture_and_ack():
    es = gate()[:-1]
    r = row(agent_error_text='Agent exceeded session timeout (3.5 min)')
    assert m.successful_submit_index(es) == 0
    assert m.submitted_without_test(es) is True
    assert m.gate_descriptives(es, r)['unacknowledged_inner_submits'] == 1
    assert m.submit_evidence(r, es)['submit_unverifiable'] is False
    assert check(r, es)['iii']['status'] == 'FAIL'  # smoke still requires canonical reply
    # A test after the root gate call is outside the safety boundary.
    es[3:3] = invoke('run_command', {'command': 'pytest'})
    assert m.submitted_without_test(es) is None  # the root call closes the enclosing interval


@pytest.mark.parametrize('flag,success,unverifiable', [(True, True, False), (False, False, False),
    (False, True, True), (True, False, True), (None, True, True), (None, False, True)])
def test_submit_consistency(flag, success, unverifiable):
    es = gate()[:-1] if success else gate(m.BOUNCE)
    evidence = m.submit_evidence(row(patch_submitted=flag), es)
    assert evidence['submit_unverifiable'] is unverifiable
    assert evidence['successful_submit'] is success
    if flag is None:
        assert evidence['patch_submitted'] is success
        assert evidence['patch_submitted_source'] == 'derived_from_harness_response'


def test_gate_llm_limit_attribution():
    es = gate()[:3]
    r = row(patch_submitted=False, agent_error_text='Agent exceeded turns budget (50 turns)')
    assert m.gate_descriptives(es, r)['gate_llm_limit'] == 1
    assert m.gate_descriptives([], r)['gate_llm_limit'] == 0
    assert m.gate_descriptives(gate(m.BOUNCE), r)['gate_llm_limit'] == 0
    assert m.gate_descriptives(es + [dict(type='error', author='submit_patch', content='LlmCallsLimitExceededError')])['gate_llm_limit'] == 1


@pytest.mark.parametrize('nested', [True, False])
@pytest.mark.parametrize('builtin', [True, False])
def test_arm2_cli(tmp_path, monkeypatch, nested, builtin):
    monkeypatch.chdir(ROOT_DIR)
    es = invoke('submit_patch', result={'patch_size': len(NEW)}) if builtin else gate(size=len(NEW))[:-1]
    run, _ = make_run(tmp_path, es, nested=nested,
                      header={'_schema': 'synthetic', 'bundle': 'v011' if builtin else 'v010'})
    dest = tmp_path / 'out.json'
    assert m.main(['metrics', 'arm2', str(run), str(dest)]) == 0
    out = json.loads(dest.read_text())
    totals = out['totals']
    assert totals['mechanism2'] == totals['mechanism1_empty'] == totals['count_no_successful_submit'] == 0
    assert totals['submitted_without_test'] == 1
    assert totals['submit_unverifiable'] == 0
    if builtin:
        assert all(totals[k] == 'n/a (no gate)' for k in m.GATE_COUNTS)
    else:
        assert totals['unacknowledged_inner_submits'] == 1
        assert totals['untracked_only_submits'] == 0  # D72 descriptive still requires acknowledgement
    assert 'gate_run_cmds' not in dest.read_text()
    assert NEW not in dest.read_text()


def test_arm2_mismatch_and_derived_flag(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT_DIR)
    run, artifacts = make_run(tmp_path, gate()[:-1], row(patch_submitted=False))
    out = m.arm2_metrics(run)
    assert out['totals']['submitted_without_test'] == 1
    assert out['totals']['submit_unverifiable'] == 1
    assert out['submit_unverifiable_rows'] == ['synthetic']
    r = json.loads((run / 'timing.jsonl').read_text())
    del r['patch_submitted']
    (run / 'timing.jsonl').write_text(json.dumps(r) + '\n')
    assert m.arm2_metrics(run)['rows'][0]['patch_submitted_source'] == 'derived_from_harness_response'
    artifacts.joinpath('trace.json').unlink()
    out = m.arm2_metrics(run)
    assert out['n_rows'] == 1
    assert out['totals']['submit_unverifiable'] == 1


def test_builtin_and_gate_response_authority():
    # A gate's own patch_size-shaped reply is not an inner harness capture.
    es = [call('submit_patch', {'request': 'submit'}), response('submit_patch', {'patch_size': 23})]
    assert m.successful_submit_index(es) is None
    # The same shape is authoritative for the builtin arm, independent of arguments.
    assert m.successful_submit_index(es, gate_mode=False) == 0
    assert m.successful_submit_index(es, gate_mode=True) is None
    es = gate()[:-1]
    es += invoke('submit_patch', result={'patch_size': 23}, author='submit_patch')
    assert m.gate_descriptives(es)['unacknowledged_inner_submits'] == 2


def test_trace_terminal_flag():
    es = gate() + [dict(type='state', patch_submitted=True)]
    r = row()
    del r['patch_submitted']
    assert m.submit_evidence(r, es)['patch_submitted_source'] == 'trace'
    assert m.submit_evidence(r, es)['submit_unverifiable'] is False
    assert check(r, es)['i']['status'] == 'PASS'


def test_smoke_iii_budget_does_not_hide_compile_error():
    assert check(row(agent_error_text='compile error after budget'), gate())['iii']['status'] == 'FAIL'
    es = gate()
    es[0]['args'] = {'request': ' '}
    assert check(row(), es)['iii']['status'] == 'PASS'  # non-empty string, exact D73 schema


def test_smoke_saved_crlf_patch(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT_DIR)
    tasks = task_inventory(tmp_path)
    patch = NEW.replace('+x\n', '+x\r\n')
    r = row(verified_patch_bytes=len(patch.encode()))
    run, _ = make_run(tmp_path, gate(size=len(patch)), r, patch=patch)
    assert m.smoke_metrics(run, tasks)['overall'] == 'PASS'


@pytest.mark.parametrize('missing', ['patch', 'result', 'tasks'])
def test_arm2_acknowledged_untracked_evidence(tmp_path, monkeypatch, missing):
    monkeypatch.chdir(ROOT_DIR)
    tasks = task_inventory(tmp_path)
    monkeypatch.setenv('PLAN008_TASKS_PATH', str(tasks))
    run, artifacts = make_run(tmp_path, gate())
    if missing == 'patch':
        artifacts.joinpath('agent.patch').unlink()
    else:
        artifacts.joinpath('result.json').unlink()
        if missing == 'tasks':
            tasks.unlink()
    out = m.arm2_metrics(run)
    assert out['totals']['untracked_only_submits'] == (0 if missing == 'tasks' else 1)
    assert out['totals']['untracked_only_unverifiable'] == int(missing == 'tasks')


def test_arm2_multirow_totals(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT_DIR)
    run = tmp_path / 'v010'
    run.mkdir()
    sequences = [invoke('read_file') * 5 + invoke('run_command', {'command': 'pytest'}) + gate()[:-1],
                 gate(m.BOUNCE), gate()[:3]]
    timing = []
    for i, es in enumerate(sequences):
        iid = f'synthetic{i}'
        artifacts = run / 'runs' / iid
        artifacts.mkdir(parents=True)
        artifacts.joinpath('trace.json').write_text(json.dumps({'entries': es}))
        r = dict(row(patch_submitted=i != 1, verified_patch_bytes=0 if i == 1 else 23), instance_id=iid)
        if i == 2:
            r['agent_error_text'] = 'Agent exceeded turns budget (50 turns)'
        timing.append(r)
    run.joinpath('timing.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in timing))
    out = m.arm2_metrics(run)
    t = out['totals']
    assert out['n_rows'] == 3
    assert t['mechanism2'] == t['mechanism1_empty'] == 1
    assert t['submitted_without_test'] == 0
    assert t['count_no_successful_submit'] == 2
    assert t['repeated_calls'] == 4
    assert t['bounces'] == t['bounce_no_followup'] == t['unacknowledged_inner_submits'] == t['gate_llm_limit'] == 1
    assert out['submit_unverifiable_rows'] == ['synthetic2']


@pytest.mark.skipif(not (ROOT_DIR / 'runs/31b-v009-p7a1-main').exists(), reason='real arm-1 inputs absent')
def test_real_base_cli(tmp_path):
    dest = tmp_path / 'base.json'
    completed = subprocess.run([sys.executable, str(ROOT_DIR / 'eval/plan008_metrics.py'), 'base', str(dest)],
                               cwd=ROOT_DIR, capture_output=True, text=True)
    assert completed.returncode == 0, 'base CLI failed (task content suppressed)'
    out = json.loads(dest.read_text())
    assert out['totals']['mechanism2'] == 17
    assert out['totals']['mechanism1_empty'] == 12
    assert out['totals']['submitted_without_test'] == 23
    assert out['totals']['count_no_successful_submit'] == 7
