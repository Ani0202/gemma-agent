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
        es += invoke('submit_patch', result={'status': 'ok', 'patch_size': size}, author='submit_patch')
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
        bounce_no_followup=0, gate_internal_visible=True)
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


def test_smoke_pass():
    criteria = m.smoke_check(row(), gate(), YAML)
    assert statuses(criteria) == dict.fromkeys(['i', 'ii', 'iii', 'iv', 'v'], 'PASS')
    assert all(c['reason'] for c in criteria.values())
    es = gate(m.BOUNCE) + invoke('edit_file') + gate()
    assert all(c['status'] == 'PASS' for c in m.smoke_check(row(), es, YAML).values())


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
    assert m.smoke_check(r, es, YAML)['i']['status'] == 'FAIL'


def test_smoke_ii_fail_and_missing():
    assert m.smoke_check(row(verified_patch_bytes=24), gate(), YAML)['ii']['status'] == 'FAIL'
    assert m.smoke_check(row(verified_patch_bytes=None), gate(), YAML)['ii']['status'] == 'UNVERIFIABLE'
    es = gate()
    es[4]['result'] = '{}'
    assert m.smoke_check(row(), es, YAML)['ii']['status'] == 'UNVERIFIABLE'


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
    assert m.smoke_check(r, es, YAML)['iii']['status'] == 'FAIL'


def test_smoke_iv_and_v_fail():
    assert m.smoke_check(row(agent_clock_seconds=210.01), gate(), YAML)['iv']['status'] == 'FAIL'
    # Agent wall time is not the timeout-context clock.
    r = row(agent_clock_seconds=None)
    r['wall_seconds'] = {'agent': 1}
    assert m.smoke_check(r, gate(), YAML)['iv']['status'] == 'UNVERIFIABLE'
    assert m.smoke_check(row(), gate(m.BOUNCE) * 3 + gate(), YAML)['v']['status'] == 'FAIL'


def test_smoke_unverifiable_and_fallback():
    hidden = invoke('submit_patch', result={'raw': 'SUBMITTED'})
    assert m.smoke_check(row(), hidden, YAML)['i']['status'] == 'UNVERIFIABLE'
    r = row(patch_submitted=False, agent_timeout_fired=True)
    r['fallback_patch_bytes'] = 23
    cs = m.smoke_check(r, [], YAML)
    assert cs['i']['status'] == cs['ii']['status'] == 'PASS'
    # A bounced gate can also end on the runner's fallback diff.
    assert m.smoke_check(r, gate(m.BOUNCE), YAML)['ii']['status'] == 'PASS'
    del r['fallback_patch_bytes']
    assert m.smoke_check(r, [], YAML)['ii']['status'] == 'UNVERIFIABLE'


def test_smoke_cli_counts_only(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT_DIR)
    run = tmp_path / 'run'
    (run / 'runs' / 'synthetic').mkdir(parents=True)
    (run / 'timing.jsonl').write_text(json.dumps(dict(row(), instance_id='synthetic')) + '\n')
    (run / 'runs' / 'synthetic' / 'trace.json').write_text(json.dumps({'entries': gate()}))
    dest = tmp_path / 'out.json'
    assert m.main(['metrics', 'smoke', str(run), str(dest)]) == 0
    out = json.loads(dest.read_text())
    assert out['overall'] == 'PASS'
    assert 'gate_run_cmds' not in out['rows'][0]
    assert out['_schema']['script_sha256'] == old.sha(m.__file__)
    assert len(out['_schema']['input_shas']) == 3
    r = dict(row(patch_submitted=False, agent_timeout_fired=True), instance_id='synthetic', fallback_patch_bytes=23)
    (run / 'timing.jsonl').write_text(json.dumps(r) + '\n')
    (run / 'runs' / 'synthetic' / 'trace.json').write_text(json.dumps({'entries': []}))
    assert m.main(['metrics', 'smoke', str(run), str(dest)]) == 0
    out = json.loads(dest.read_text())
    assert out['overall'] == 'FAIL'
    assert out['rows'][0]['criteria']['i']['status'] == 'UNVERIFIABLE'


@pytest.mark.skipif(not (ROOT_DIR / 'runs/31b-v009-p7a1-main').exists(), reason='real arm-1 inputs absent')
def test_real_base_cli(tmp_path):
    dest = tmp_path / 'base.json'
    completed = subprocess.run([sys.executable, str(ROOT_DIR / 'eval/plan008_metrics.py'), 'base', str(dest)],
                               cwd=ROOT_DIR, capture_output=True, text=True)
    assert completed.returncode == 0, 'base CLI failed (task content suppressed)'
    out = json.loads(dest.read_text())
    assert out['totals']['mechanism2'] == 17
    assert out['totals']['mechanism1_empty'] == 12
