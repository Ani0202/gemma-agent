"""Offline synthetic tests for the frozen Plan 007 row classifier."""
import hashlib
from importlib import import_module
import json
from pathlib import Path
import subprocess
import sys

import pytest

classifier = import_module('eval.kaggle.classify_rows')
timing = import_module('eval.kaggle.agent_timing')


def row(**updates):
    return dict(dict(instance_id='task-1', repo='example/repo', result_error=None,
                     agent_error_text=None, verified_patch_bytes=10, setup_calls=[],
                     exit_code=0, resolved=False, error=None, setup_failed=False, missing_tool_deps=[]), **updates)


def step(**updates):
    return dict(dict(step='setup.py', rc=0, duration_s=1.0, stdout='', stderr=''), **updates)


def editable(offline=True, record=True, rc=1):
    root = '/tmp/swegemma_sandbox_synthetic'
    return dict(argv=[root + '/venv/bin/python3', '-m', 'pip', 'install']
                + (['--no-index', '--find-links=/wheels', '--no-build-isolation'] if offline else [])
                + ['--no-deps', '-e', root + '/workspace'],
                rc=rc, stdout='' if offline else 'subprocess-exited-with-error',
                stderr=classifier.RECORD if record else 'other failure')


def chain():
    return step(subprocesses=[editable(), editable(offline=False, record=False)])


def test_agent_patterns_are_stock():
    assert [(n, p.pattern, p.flags) for n, p in classifier.AGENT_END] == [
        (n, p.pattern, p.flags) for n, p in timing.AGENT_OUTCOMES]


@pytest.mark.parametrize('passes', [1, 3])
def test_record_chain_all_passes(passes):
    result = classifier.classify(row(setup_calls=[chain() for _ in range(passes)],
                                     setup_failed=True, editable_failed=True))
    assert result['h'] is None
    assert result['known_diag'] is True


@pytest.mark.parametrize('subprocesses', [
    [editable(record=False)], [editable(offline=False, record=False)],
    [editable(offline=False, record=False), editable()],
])
def test_unexpected_editable_failure(subprocesses):
    result = classifier.classify(row(setup_calls=[step(step='setup.py', rc=0, subprocesses=subprocesses)]))
    assert result['h'] == 'H-SETUP'
    assert result['known_diag'] is False
    assert 's5:unexpected_editable_failure' in result['reasons']


def test_later_pass_failure_is_retained():
    calls = [chain(), step(step='setup.py', rc=0, subprocesses=[editable(record=False)])]
    result = classifier.classify(row(setup_calls=calls))
    assert result['h'] == 'H-SETUP'
    assert result['known_diag'] is False


@pytest.mark.parametrize('updates,reason', [
    (dict(setup_calls=[step(step='tool_deps', rc=-1)]), 's2:setup_step_failed'),
    (dict(missing_tool_deps=['x']), 's1:missing_tool_deps'),
    (dict(setup_failed=True), 's6:setup_failed_unexplained'),
    (dict(setup_calls=[step(step='setup.py', rc=1)]), 's3:setup_py_failed'),
    (dict(setup_calls=[step(step='workspace_editable', rc=1)]), 's4:workspace_editable_failed'),
])
def test_setup_failures(updates, reason):
    result = classifier.classify(row(**updates))
    assert result['h'] == 'H-SETUP'
    assert result['known_diag'] is False
    assert reason in result['reasons']


@pytest.mark.parametrize('duration,stderr,expected', [(0, '', None), (1, '', 'H-SETUP'), (0, 'failure', 'H-SETUP')])
def test_not_run_step(duration, stderr, expected):
    result = classifier.classify(row(setup_calls=[step(step='tool_deps', rc=None, duration_s=duration, stderr=stderr)]))
    assert result['h'] == expected


def test_workspace_record_and_pip_check():
    result = classifier.classify(row(setup_failed=True, setup_calls=[
        step(step='workspace_editable', rc=1, stdout=classifier.RECORD),
        step(step='pip_check', rc=1), step(step='setup.py', rc=0)]))
    assert result['h'] is None and result['known_diag'] is True


@pytest.mark.parametrize('message,code,expected', [
    ('Failed to apply agent patch: xyz', 1, 'PATCH_APPLY'),
    ('Failed to apply agent patch: xyz', None, 'PATCH_APPLY'),
    ('Required test node did not pass: a::b', 0, 'EXIT0_UNRESOLVED'),
    ('Test failures/errors recorded in JUnit XML (failures=1, errors=0)', 0, 'EXIT0_UNRESOLVED'),
])
def test_verification_agent_errors(message, code, expected):
    result = classifier.classify(row(error='Harness task failure', result_error=message,
                                     exit_code=code, verified_patch_bytes=50))
    assert result['h'] is None and result['agent'] == expected


@pytest.mark.parametrize('prefix', classifier.VERIFY_AGENT_PREFIXES)
def test_all_verification_agent_prefixes(prefix):
    result = classifier.classify(row(error='Harness task failure', result_error=prefix + ' synthetic',
                                     exit_code=None if prefix == classifier.VERIFY_AGENT_PREFIXES[0] else 0))
    assert result['h'] is None


@pytest.mark.parametrize('code,expected', [(124, 'VERIFY_TIMEOUT_124'), (1, 'PYTEST_1'),
                                         (2, 'PYTEST_2_5'), (3, 'PYTEST_2_5'), (4, 'PYTEST_2_5'),
                                         (5, 'PYTEST_2_5'), (0, 'EXIT0_UNRESOLVED')])
def test_verification_outcomes(code, expected):
    result = classifier.classify(row(exit_code=code))
    assert result['h'] is None and result['agent'] == expected


@pytest.mark.parametrize('field,message', [
    ('result_error', 'Evaluation error: boom'),
    ('result_error', 'Failed to apply test_patch: x'),
    ('result_error', 'Missing test specification'),
    ('agent_error_text', 'Agent crashed'),
])
@pytest.mark.parametrize('error,reason', [('Harness task failure', 'r4:unrecognized_message'),
                                         (None, 'r5:unrecognized_message')])
def test_unrecognized_messages(field, message, error, reason):
    result = classifier.classify(row(error=error, **{field: message}))
    assert result['h'] == 'H-ROW' and result['agent'] is None
    assert reason in result['reasons']


@pytest.mark.parametrize('error', ['Cleanup exception (OSError)', 'Harness task failure trace parse (KeyError)',
                                 'Evaluation exception (ValueError)', 'Row build exception (TypeError)'])
def test_wrapper_errors_preserve_stock_verdict(error):
    result = classifier.classify(row(error=error, resolved=True))
    assert result['h'] == 'H-ROW' and result['resolved'] is True and result['agent'] is None


def test_other_row_error():
    assert classifier.classify(row(error='unexpected'))['reasons'] == ['r3:unexpected_error']


@pytest.mark.parametrize('code', [None, -1, 6])
def test_invalid_verification_codes(code):
    assert classifier.classify(row(verified_patch_bytes=30, exit_code=code))['h'] == 'H-VERIFY'


@pytest.mark.parametrize('code', ['0', False, 0.0])
def test_non_int_verification_codes_are_h_row(code):
    # rev 4: a non-int exit_code is invalid evidence (r9 -> H-ROW), checked before H-VERIFY.
    result = classifier.classify(row(verified_patch_bytes=30, exit_code=code))
    assert result['h'] == 'H-ROW' and 'r9:invalid_exit_code' in result['reasons']


def test_no_patch_with_agent_end():
    result = classifier.classify(row(verified_patch_bytes=0, exit_code=-1,
                                     agent_error_text='Agent exceeded turns budget'))
    assert result['h'] is None and result['agent'] == 'NO_PATCH' and result['agent_end'] == 'turns'


@pytest.mark.parametrize('name,message', [
    ('timeout', ' Agent exceeded session timeout (300s) '),
    ('turns', 'Agent exceeded maximum allowed LLM turns'),
    ('tool_calls', 'Agent exceeded tool call budget'),
    ('no_submit', 'Agent completed execution without calling submit_patch'),
])
def test_agent_end_is_descriptive(name, message):
    result = classifier.classify(row(exit_code=1, agent_error_text=message))
    assert result['agent'] == 'PYTEST_1' and result['agent_end'] == name


@pytest.mark.parametrize('key', classifier.REQUIRED)
def test_schema_guard(key):
    source = row()
    del source[key]
    assert classifier.classify(source)['h'] == 'H-ROW'


def test_pass_and_other_fail():
    assert classifier.classify(row(resolved=True))['agent'] == 'PASS'
    assert classifier.classify(row(verified_patch_bytes=10, exit_code=None, result_error='Agent exceeded tool call budget'))['h'] == 'H-VERIFY'


@pytest.mark.parametrize('patch_bytes,code', [(None, None), (-1, -1), (True, 0), (1.5, 0), ('10', 0)])
def test_invalid_patch_evidence_is_h(patch_bytes, code):
    result = classifier.classify(row(verified_patch_bytes=patch_bytes, exit_code=code))
    assert result['h'] == 'H-ROW' and result['agent'] is None
    assert 'r7:invalid_patch_evidence' in result['reasons']


@pytest.mark.parametrize('texts', [(None, None), ('', '  '), (None, '')])
def test_unexplained_harness_failure_is_h(texts):
    result = classifier.classify(row(error='Harness task failure', result_error=texts[0], agent_error_text=texts[1]))
    assert result['h'] == 'H-ROW' and 'r6:unexplained_harness_failure' in result['reasons']


@pytest.mark.parametrize('message', ['Agent exceeded tool call budget', 'Required test node did not pass: t::x'])
def test_explained_harness_failure_not_h(message):
    result = classifier.classify(row(error='Harness task failure', result_error=message, exit_code=0))
    assert result['h'] is None and result['agent'] == 'EXIT0_UNRESOLVED'


def test_zero_patch_without_exit_code_is_no_patch():
    result = classifier.classify(row(verified_patch_bytes=0, exit_code=None))
    assert result['h'] is None and result['agent'] == 'NO_PATCH'


def test_precedence_and_orthogonal_diagnostic():
    result = classifier.classify(row(error='unexpected', setup_calls=[chain()]))
    assert result['h'] == 'H-ROW' and result['known_diag'] is True
    result = classifier.classify(row(error='unexpected', setup_failed=True, exit_code=-1))
    assert result['h'] == 'H-ROW' and result['known_diag'] is False
    assert classifier.classify(row(setup_failed=True, exit_code=-1))['h'] == 'H-SETUP'


def test_meta_rejected():
    assert classifier.classify({'_schema': 'kaggle_timing_v1'})['h'] == 'H-ROW'


def test_cli(tmp_path):
    source, output = tmp_path / 'timing.jsonl', tmp_path / 'classes.json'
    source.write_text('\n'.join(json.dumps(r) for r in [
        {'_schema': 'kaggle_timing_v1'}, {'_vllm': {'startup_seconds': 1}}, row(resolved=True),
        row(instance_id='bad', error='Harness task failure', result_error='Evaluation error: boom'),
        row(instance_id='diag', setup_calls=[chain()], setup_failed=True),
        {'_stopped': 'insufficient remaining budget for next task'}, {'_done': {'n': 3}},
    ]) + '\n')
    proc = subprocess.run([sys.executable, classifier.__file__, str(source), '--out', str(output)],
                          check=True, capture_output=True, text=True)
    result = json.loads(proc.stdout)
    assert result == json.loads(output.read_text())
    assert result['_schema'] == 'plan007_row_classes/v1'
    assert result['n_rows'] == 3 and result['h_rows'] == ['bad']
    assert result['counts'] == dict(h={'H-ROW': 1}, agent={'PASS': 1, 'EXIT0_UNRESOLVED': 1}, known_diag=1)
    assert result['input_sha256'] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert result['classifier_sha256'] == hashlib.sha256(Path(classifier.__file__).read_bytes()).hexdigest()
    assert 'boom' not in proc.stdout and 'Evaluation error' not in proc.stdout
    assert classifier.RECORD not in proc.stdout
    assert proc.stderr == ''


# Rev 4 (codex review 20261106T070228 BLOCKING 1): invalid or contradictory verdict evidence fails closed.
@pytest.mark.parametrize('updates,reason', [
    (dict(resolved=None), 'r8:invalid_resolved'),
    (dict(resolved='false'), 'r8:invalid_resolved'),
    (dict(resolved='false', exit_code=0), 'r8:invalid_resolved'),
    (dict(resolved=1), 'r8:invalid_resolved'),
    (dict(result_error='Failed to apply agent patch: x', exit_code='garbage'), 'r9:invalid_exit_code'),
    (dict(verified_patch_bytes=0, exit_code='garbage'), 'r9:invalid_exit_code'),
    (dict(verified_patch_bytes=0, exit_code=True), 'r9:invalid_exit_code'),
    (dict(exit_code=1.0), 'r9:invalid_exit_code'),
])
def test_invalid_verdict_evidence_is_h_row(updates, reason):
    result = classifier.classify(row(**updates))
    assert result['h'] == 'H-ROW' and result['agent'] is None and reason in result['reasons']


@pytest.mark.parametrize('updates', [
    dict(resolved=True, exit_code=1), dict(resolved=True, exit_code=124), dict(resolved=True, exit_code=None),
    dict(resolved=True, exit_code=-1),
    dict(resolved=True, result_error='Failed to apply agent patch: x', exit_code=None),
    dict(resolved=True, result_error='Failed to apply agent patch: x', exit_code=0),
    dict(resolved=True, verified_patch_bytes=0, exit_code=0),
    dict(resolved=True, verified_patch_bytes=0, exit_code=None),
])
def test_contradictory_resolved_is_h(updates):
    result = classifier.classify(row(**updates))
    assert result['h'] is not None and result['agent'] is None
    assert result['resolved'] is True  # stock verdict preserved for reporting


def test_contradictory_resolved_reason():
    result = classifier.classify(row(resolved=True, exit_code=1))
    assert result['h'] == 'H-VERIFY' and 'verify:contradictory_resolved' in result['reasons']


def test_stock_resolved_preserved_on_h_row():
    assert classifier.classify(row(resolved='false'))['resolved'] == 'false'


@pytest.mark.parametrize('updates,agent', [
    (dict(verified_patch_bytes=0, exit_code=None), 'NO_PATCH'),
    (dict(verified_patch_bytes=0, exit_code=-1), 'NO_PATCH'),
    (dict(result_error='Failed to apply agent patch: x', exit_code=None), 'PATCH_APPLY'),
    (dict(result_error='Failed to apply agent patch: x', exit_code=-1), 'PATCH_APPLY'),
    (dict(exit_code=0), 'EXIT0_UNRESOLVED'),
    (dict(exit_code=124), 'VERIFY_TIMEOUT_124'),
    (dict(resolved=True, exit_code=0), 'PASS'),
])
def test_legitimate_verdicts_not_h(updates, agent):
    result = classifier.classify(row(**updates))
    assert result['h'] is None and result['agent'] == agent


# Rev 5 (codex review 20261106T070737 BLOCKING 1-3).
@pytest.mark.parametrize('field', ['result_error', 'agent_error_text'])
@pytest.mark.parametrize('error', [None, 'Harness task failure'])
@pytest.mark.parametrize('prefix', [p for p in classifier.VERIFY_AGENT_PREFIXES
                                    if not p.startswith('Failed to apply agent patch:')])
def test_resolved_with_verify_failure_is_h_verify(field, error, prefix):
    result = classifier.classify(row(resolved=True, exit_code=0, error=error, **{field: prefix + ' t::x'}))
    assert result['h'] == 'H-VERIFY' and result['agent'] is None and result['resolved'] is True
    assert 'verify:resolved_with_verify_failure' in result['reasons']


@pytest.mark.parametrize('field', ['result_error', 'agent_error_text'])
def test_unresolved_with_verify_failure_stays_agent(field):
    result = classifier.classify(row(exit_code=0, **{field: 'Required test node did not pass: t::x'}))
    assert result['h'] is None and result['agent'] == 'EXIT0_UNRESOLVED'


@pytest.mark.parametrize('field', ['result_error', 'agent_error_text'])
@pytest.mark.parametrize('value', [False, 0, [], {}, True, 1, ['x'], {'a': 1}, 1.5])
@pytest.mark.parametrize('error', [None, 'Harness task failure'])
def test_non_string_message_is_h_row(field, value, error):
    result = classifier.classify(row(error=error, **{field: value}))
    assert result['h'] == 'H-ROW' and result['agent'] is None
    assert 'r10:invalid_message_type' in result['reasons']


def test_non_string_message_with_recognized_companion_is_h_row():
    result = classifier.classify(row(error='Harness task failure', result_error=False,
                                     agent_error_text='Required test node did not pass: t::x'))
    assert result['h'] == 'H-ROW' and 'r10:invalid_message_type' in result['reasons']


@pytest.mark.parametrize('calls', [
    {}, '', 'x', None, 0, [{}], [[]], ['setup.py'], [dict(step='')], [dict(step=1)],
    [dict(step='setup.py', rc=False)], [dict(step='setup.py', rc=True)], [dict(step='pip_check', rc=0.0)],
    [dict(step='setup.py', rc=0, stdout=1)], [dict(step='setup.py', rc=0, stderr=[])],
    [dict(step='setup.py', rc=0, duration_s='1')], [dict(step='setup.py', rc=0, duration_s=-1.0)],
    [dict(step='setup.py', rc=0, duration_s=float('nan'))],
    [dict(step='setup.py', rc=0, subprocesses={})], [dict(step='setup.py', rc=0, subprocesses=[{}])],
    [dict(step='setup.py', rc=0, subprocesses=[dict(argv='pip install -e .', rc=1)])],
    [dict(step='setup.py', rc=0, subprocesses=[dict(argv=['pip', 1], rc=1)])],
    [dict(step='setup.py', rc=0, subprocesses=[dict(argv=['pip'], rc=False)])],
    [dict(step='setup.py', rc=0, subprocesses=[dict(argv=['pip'], rc=0, stderr=0)])],
])
def test_malformed_setup_evidence_is_h_row(calls):
    result = classifier.classify(row(setup_calls=calls))
    assert result['h'] == 'H-ROW' and result['agent'] is None
    assert 'r11:invalid_setup_evidence' in result['reasons']


@pytest.mark.parametrize('calls', [
    [], [dict(step='pip_check', duration_s=0.0, rc=None, stdout='', stderr='', retrying_lines=0)],
    [dict(step='setup.py', duration_s=1.5, rc=0, stdout='', stderr='', subprocesses=[])],
    [dict(step='workspace_editable', duration_s=1, rc=0, stdout=None, stderr=None)],
])
def test_legitimate_setup_evidence_not_h(calls):
    result = classifier.classify(row(setup_calls=calls))
    assert result['h'] is None and result['agent'] == 'EXIT0_UNRESOLVED'


@pytest.mark.parametrize('deps', ['x', 1, True, {}, {'a': 1}, [1], [None]])
def test_invalid_missing_tool_deps_is_h_row(deps):
    result = classifier.classify(row(missing_tool_deps=deps))
    assert result['h'] == 'H-ROW' and 'r12:invalid_missing_tool_deps' in result['reasons']


def test_missing_tool_deps_list():
    assert classifier.classify(row(missing_tool_deps=[]))['h'] is None
    assert classifier.classify(row(missing_tool_deps=None))['h'] is None
    assert classifier.classify(row(missing_tool_deps=['pytest']))['h'] == 'H-SETUP'


@pytest.mark.parametrize('flag', [0, 1, 'true', [], {}])
def test_invalid_setup_failed_is_h_row(flag):
    result = classifier.classify(row(setup_failed=flag))
    assert result['h'] == 'H-ROW' and 'r13:invalid_setup_failed' in result['reasons']


def test_non_dict_row_rejected():
    with pytest.raises(TypeError):
        classifier.classify(['instance_id'])


def test_cli_rejects_duplicate_ids(tmp_path):
    source = tmp_path / 'timing.jsonl'
    source.write_text(json.dumps(row()) + '\n' + json.dumps(row()) + '\n')
    proc = subprocess.run([sys.executable, str(Path(classifier.__file__)), str(source)],
                          capture_output=True, text=True)
    assert proc.returncode != 0 and 'Duplicate instance_id' in proc.stderr


# Exhaustive rev-5 regressions. The requested review file is empty in this checkout;
# row() is the complete synthetic baseline and each override follows the user spec.
@pytest.mark.parametrize('message', ['Agent exceeded turns budget', 'arbitrary error', ' '])
@pytest.mark.parametrize('error', [None, 'Harness task failure'])
def test_rev5_01_resolved_result_error(message, error):
    assert classifier.classify(row(resolved=True, result_error=message, error=error))['h'] == 'H-VERIFY'
    assert classifier.classify(row(resolved=True, agent_error_text='Agent exceeded turns budget'))['agent'] == 'PASS'


@pytest.mark.parametrize('messages', [
    ('Agent exceeded turns budget', 'Agent exceeded session timeout (300s)'),
    ('Missing or empty JUnit XML report', 'Required test node did not pass: t::x'),
])
def test_rev5_02_conflicting_messages(messages):
    assert classifier.classify(row(result_error=messages[0], agent_error_text=messages[1]))['h'] == 'H-ROW'


@pytest.mark.parametrize('field', ['result_error', 'agent_error_text'])
@pytest.mark.parametrize('code', [1, 2, 3, 4, 5, 124, None, -1])
@pytest.mark.parametrize('prefix', classifier.VERIFY_AGENT_PREFIXES[1:])
def test_rev5_03_junit_requires_exit_zero(field, code, prefix):
    assert classifier.classify(row(exit_code=code, **{field: prefix + ' synthetic'}))['h'] == 'H-VERIFY'


@pytest.mark.parametrize('patch,code', [(10, 0), (0, None), (0, -1), (0, 1)])
def test_rev5_04_apply_requires_patch_and_failure_exit(patch, code):
    assert classifier.classify(row(verified_patch_bytes=patch, exit_code=code,
                                  result_error='Failed to apply agent patch: x'))['h'] == 'H-VERIFY'


@pytest.mark.parametrize('code', [0, 1, 2, 3, 4, 5, 124, -2])
def test_rev5_05_no_patch_exit(code):
    assert classifier.classify(row(verified_patch_bytes=0, exit_code=code))['h'] == 'H-VERIFY'


@pytest.mark.parametrize('key', ['error', 'setup_failed', 'missing_tool_deps'])
def test_rev5_06_missing_vs_null(key):
    source = row(**{key: None})
    assert classifier.classify(source)['h'] is None
    del source[key]
    assert classifier.classify(source)['h'] == 'H-ROW'


@pytest.mark.parametrize('key', classifier.STEP_REQUIRED)
def test_rev5_07_missing_step_key(key):
    entry = step()
    del entry[key]
    assert classifier.classify(row(setup_calls=[entry]))['h'] == 'H-ROW'


def test_rev5_07_missing_subprocess_rc():
    entry = editable()
    del entry['rc']
    result = classifier.classify(row(setup_calls=[step(subprocesses=[entry])]))
    assert result['h'] == 'H-ROW' and not result['known_diag']


@pytest.mark.parametrize('entry', [step(step=' '), step(step='unknown'),
    step(step='pip_check', subprocesses=[]),
    step(subprocesses=[dict(editable(), argv=[])]),
    step(subprocesses=[dict(editable(), argv=['pip', ' '])])])
def test_rev5_08_step_and_argv(entry):
    assert classifier.classify(row(setup_calls=[entry]))['h'] == 'H-ROW'


def run_cli(tmp_path, records=None, raw=None):
    source = tmp_path / 'timing.jsonl'
    source.write_text(raw if raw is not None else '\n'.join(map(json.dumps, records)) + '\n')
    return subprocess.run([sys.executable, classifier.__file__, str(source)], capture_output=True, text=True)


@pytest.mark.parametrize('key', ['instance_id', 'repo'])
@pytest.mark.parametrize('value', ['', '  ', None, 1, []])
def test_rev5_09_identity_direct_and_cli(tmp_path, key, value):
    source = row(**{key: value})
    assert classifier.classify(source)['h'] == 'H-ROW'
    assert run_cli(tmp_path, [source]).returncode != 0


@pytest.mark.parametrize('updates', [dict(stdout='failure'), dict(stderr='failure'),
    dict(duration_s=1), dict(duration_s=None)])
def test_rev5_10_not_run_requires_empty_evidence(updates):
    entry = step(step='tool_deps', rc=None, duration_s=0, **updates) if 'duration_s' not in updates else step(step='tool_deps', rc=None, **updates)
    assert classifier.classify(row(setup_calls=[entry]))['h'] == 'H-SETUP'


@pytest.mark.parametrize('workspace', [False, True])
def test_rev5_11_diagnostic_requires_executed_rc(workspace):
    entry = (step(step='workspace_editable', rc=None, stderr=classifier.RECORD) if workspace
             else step(subprocesses=[editable(rc=None)]))
    result = classifier.classify(row(setup_calls=[entry]))
    assert result['h'] == 'H-SETUP' and not result['known_diag']


@pytest.mark.parametrize('workspace', [False, True])
def test_rev5_12_marker_per_stream(workspace):
    entry = dict(editable(), stdout='uninstall-no-', stderr='record-file')
    call = step(step='workspace_editable', rc=1, stdout=entry['stdout'], stderr=entry['stderr']) if workspace else step(subprocesses=[entry])
    result = classifier.classify(row(setup_calls=[call]))
    assert result['h'] == 'H-SETUP' and not result['known_diag']


@pytest.mark.parametrize('argv', [
    ['pip', 'install', '-e', '/workspace', '--no-index'],
    ['echo', '-e', '--no-index'],
    editable()['argv'] + ['--extra'],
    editable()['argv'][:-1] + ['/tmp/other/workspace'],
])
def test_rev5_13_exact_offline_command(argv):
    result = classifier.classify(row(setup_calls=[step(subprocesses=[dict(editable(), argv=argv)])]))
    assert result['h'] == 'H-SETUP' and not result['known_diag']


@pytest.mark.parametrize('subs', [
    [editable(), editable(offline=False), editable(offline=False)],
    [editable(), dict(argv=['echo', 'intervening'], rc=0, stdout='', stderr=''), editable(offline=False)],
    [editable(), dict(editable(offline=False), argv=[a.replace('synthetic', 'other') for a in editable(offline=False)['argv']])],
])
def test_rev5_14_fallback_immediate_same_identity_consumed(subs):
    result = classifier.classify(row(setup_calls=[step(subprocesses=subs)]))
    assert result['h'] == 'H-SETUP' and not result['known_diag']


@pytest.mark.parametrize('value', [[], None, 42, 'text', {}, {'repo': 'x'}, {'_schema': 'unknown'}, {'_vllm': 'bad'}, {'_vllm': {}}, {'_stopped': 'unknown'}])
def test_rev5_15_cli_rejects_unrecognized_records(tmp_path, value):
    proc = run_cli(tmp_path, [value])
    assert proc.returncode != 0 and 'Invalid task record' in proc.stderr


@pytest.mark.parametrize('raw', [
    '{"instance_id":"a","instance_id":"b"}',
    '{"_schema":"kaggle_timing_v1","fields":{"a":1,"a":2}}',
])
def test_rev5_16_duplicate_json_keys(tmp_path, raw):
    proc = run_cli(tmp_path, raw=raw)
    assert proc.returncode != 0 and 'Duplicate JSON key' in proc.stderr


@pytest.mark.parametrize('records', [
    [{'_schema': 'kaggle_timing_v1', 'task_ids': ['a', 'task-1']}, row()],
    [{'_schema': 'kaggle_timing_v1', 'task_ids': ['a']}, row()],
    [row(), {'_done': {'n': 2}}], [row(), {'_done': {'n': True}}],
])
def test_rev5_17_journal_accounting(tmp_path, records):
    assert run_cli(tmp_path, records).returncode != 0


def test_rev5_17_completed_prefix_without_done(tmp_path):
    proc = run_cli(tmp_path, [{'_schema': 'kaggle_timing_v1', 'task_ids': ['task-1', 'unrun']}, row()])
    assert proc.returncode == 0 and json.loads(proc.stdout)['n_rows'] == 1


@pytest.mark.parametrize('updates,reason', [(dict(vllm_startup_seconds=None), 'vllm_not_up'),
                                          (dict(mcp_import_ok=False), 'mcp_import_failed')])
def test_rev5_18_kernel_void(tmp_path, updates, reason):
    proc = run_cli(tmp_path, [dict(_schema='kaggle_timing_v1', **updates), row(resolved=True)])
    assert proc.returncode == 0
    result = json.loads(proc.stdout)
    assert result['kernel_void'] and reason in result['kernel_void_reasons']
    assert result['counts']['agent'] == {} and result['counts']['h'] == {'H-ROW': 1}
    assert 'kernel:void' in result['rows'][0]['reasons']


@pytest.mark.parametrize('number', [10**400, float('nan'), float('inf'), -float('inf')])
def test_rev5_19_numeric_overflow(number):
    assert classifier.classify(row(setup_calls=[step(duration_s=number)]))['h'] == 'H-ROW'


def test_rev5_false_h_01_setup_py_not_run():
    result = classifier.classify(row(setup_calls=[step(rc=None, duration_s=0)]))
    assert result['h'] is None and result['agent'] == 'EXIT0_UNRESOLVED'


def test_rev5_false_h_02_workspace_not_run():
    result = classifier.classify(row(setup_calls=[step(step='workspace_editable', rc=None, duration_s=0)]))
    assert result['h'] is None and result['agent'] == 'EXIT0_UNRESOLVED'


@pytest.mark.parametrize('message', [
    'Agent exceeded session timeout (300s)', 'Agent exceeded turns budget',
    'Agent exceeded tool call budget', 'Agent completed execution without calling submit_patch',
])
@pytest.mark.parametrize('field', ['result_error', 'agent_error_text'])
def test_rev5_no_false_h_recognized_agent_end_under_harness_failure(message, field):
    result = classifier.classify(row(error='Harness task failure', **{field: message}))
    assert result['h'] is None and result['agent'] == 'EXIT0_UNRESOLVED'
