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
                     exit_code=0, resolved=False, error=None, setup_failed=False), **updates)


def editable(offline=True, record=True, rc=1):
    return dict(argv=['pip', 'install', '-e', '/workspace'] + (['--no-index'] if offline else []),
                rc=rc, stdout='' if offline else 'subprocess-exited-with-error',
                stderr=classifier.RECORD if record else 'other failure')


def chain():
    return dict(step='setup.py', rc=0,
                subprocesses=[editable(), editable(offline=False, record=False)])


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
    result = classifier.classify(row(setup_calls=[dict(step='setup.py', rc=0, subprocesses=subprocesses)]))
    assert result['h'] == 'H-SETUP'
    assert result['known_diag'] is False
    assert 's5:unexpected_editable_failure' in result['reasons']


def test_later_pass_failure_is_retained():
    calls = [chain(), dict(step='setup.py', rc=0, subprocesses=[editable(record=False)])]
    result = classifier.classify(row(setup_calls=calls))
    assert result['h'] == 'H-SETUP'
    assert result['known_diag'] is False


@pytest.mark.parametrize('updates,reason', [
    (dict(setup_calls=[dict(step='tool_deps', rc=-1)]), 's2:setup_step_failed'),
    (dict(missing_tool_deps=['x']), 's1:missing_tool_deps'),
    (dict(setup_failed=True), 's6:setup_failed_unexplained'),
    (dict(setup_calls=[dict(step='setup.py', rc=1)]), 's3:setup_py_failed'),
    (dict(setup_calls=[dict(step='workspace_editable', rc=1)]), 's4:workspace_editable_failed'),
])
def test_setup_failures(updates, reason):
    result = classifier.classify(row(**updates))
    assert result['h'] == 'H-SETUP'
    assert result['known_diag'] is False
    assert reason in result['reasons']


@pytest.mark.parametrize('duration,stderr,expected', [(0, '', None), (1, '', 'H-SETUP'), (0, 'failure', 'H-SETUP')])
def test_not_run_step(duration, stderr, expected):
    result = classifier.classify(row(setup_calls=[dict(step='tool_deps', rc=None, duration_s=duration, stderr=stderr)]))
    assert result['h'] == expected


def test_workspace_record_and_pip_check():
    result = classifier.classify(row(setup_failed=True, setup_calls=[
        dict(step='workspace_editable', rc=1, stdout=classifier.RECORD),
        dict(step='pip_check', rc=1), dict(step='setup.py', rc=0)]))
    assert result['h'] is None and result['known_diag'] is True


@pytest.mark.parametrize('message,code,expected', [
    ('Failed to apply agent patch: xyz', 1, 'PATCH_APPLY'),
    ('Failed to apply agent patch: xyz', None, 'PATCH_APPLY'),
    ('Required test node did not pass: a::b', 0, 'EXIT0_UNRESOLVED'),
    ('Test failures/errors recorded in JUnit XML (failures=1, errors=0)', 1, 'PYTEST_1'),
])
def test_verification_agent_errors(message, code, expected):
    result = classifier.classify(row(error='Harness task failure', result_error=message,
                                     exit_code=code, verified_patch_bytes=50))
    assert result['h'] is None and result['agent'] == expected


@pytest.mark.parametrize('prefix', classifier.VERIFY_AGENT_PREFIXES)
def test_all_verification_agent_prefixes(prefix):
    result = classifier.classify(row(error='Harness task failure', result_error=prefix + ' synthetic'))
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
    result = classifier.classify(row(error='Harness task failure', result_error=message, exit_code=1))
    assert result['h'] is None and result['agent'] == 'PYTEST_1'


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
    with pytest.raises(ValueError):
        classifier.classify({'_schema': 'example'})


def test_cli(tmp_path):
    source, output = tmp_path / 'timing.jsonl', tmp_path / 'classes.json'
    source.write_text('\n'.join(json.dumps(r) for r in [
        {'_schema': 'example'}, {'_vllm': {}}, row(resolved=True),
        row(instance_id='bad', error='Harness task failure', result_error='Evaluation error: boom'),
        row(instance_id='diag', setup_calls=[chain()], setup_failed=True),
        {'_stopped': 'example'}, {'_done': {'n': 3}},
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
