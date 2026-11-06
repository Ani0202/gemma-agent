"""Frozen Plan 007 rev 5 classifier for timing journal rows (stdlib only)."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

if __package__:
    from .agent_timing import AGENT_OUTCOMES as AGENT_END
else:
    from agent_timing import AGENT_OUTCOMES as AGENT_END

RECORD = 'uninstall-no-record-file'
WRAPPER_H = ('Evaluation exception (', 'Cleanup exception (', 'trace parse (', 'Row build exception (')
VERIFY_AGENT_PREFIXES = (
    'Failed to apply agent patch:',
    'Missing or empty JUnit XML report', 'Malformed JUnit XML report:',
    'No <testsuite> elements found in JUnit XML',
    'No passing tests recorded in JUnit XML', 'Test failures/errors recorded in JUnit XML',
    'Required test node did not pass:',
    'Pytest stdout summary indicates zero or no passing tests',
    'Missing JUnit XML report (possible premature os._exit(0))',
)
REQUIRED = ('result_error', 'agent_error_text', 'verified_patch_bytes', 'setup_calls', 'exit_code', 'resolved')


def agent_end(message):
    text = message.strip() if isinstance(message, str) else ''
    return next((name for name, pattern in AGENT_END if pattern.match(text)), None)


def output_text(entry):
    return (entry.get('stdout') or '') + (entry.get('stderr') or '')


def opt_str(value):
    return value is None or isinstance(value, str)


def opt_rc(value):
    return value is None or type(value) is int


def setup_shape_ok(calls):
    """setup_calls must be a list of step dicts as written by agent_timing.setup_step (empty list allowed)."""
    if not isinstance(calls, list):
        return False
    for entry in calls:
        if not isinstance(entry, dict) or not isinstance(entry.get('step'), str) or not entry['step']:
            return False
        if not (opt_rc(entry.get('rc')) and opt_str(entry.get('stdout')) and opt_str(entry.get('stderr'))):
            return False
        duration = entry.get('duration_s')
        if duration is not None and (type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0):
            return False
        subs = entry.get('subprocesses', [])
        if not isinstance(subs, list):
            return False
        for sub in subs:
            if not isinstance(sub, dict) or not isinstance(sub.get('argv'), list):
                return False
            if not all(isinstance(arg, str) for arg in sub['argv']):
                return False
            if not (opt_rc(sub.get('rc')) and opt_str(sub.get('stdout')) and opt_str(sub.get('stderr'))):
                return False
    return True


def classify(row: dict) -> dict:
    """Classify one task row, preserving the stock verdict even for H rows."""
    if not isinstance(row, dict):
        raise TypeError('Row is not a JSON object')
    if 'instance_id' not in row:
        raise ValueError('Meta row has no instance_id')
    row_reasons = []
    error = row.get('error')
    if any(key not in row for key in REQUIRED):
        row_reasons.append('r1:missing_schema')
    if isinstance(error, str) and any(marker in error for marker in WRAPPER_H):
        row_reasons.append('r2:wrapper_exception')
    elif error is not None and error != 'Harness task failure':
        row_reasons.append('r3:unexpected_error')
    messages = (row.get('result_error'), row.get('agent_error_text'))
    if not all(opt_str(m) for m in messages):
        row_reasons.append('r10:invalid_message_type')
    elif error is None or error == 'Harness task failure':
        for message in messages:
            if message and agent_end(message) is None and not message.startswith(VERIFY_AGENT_PREFIXES):
                row_reasons.append('r4:unrecognized_message' if error else 'r5:unrecognized_message')
                break
        if error and not any(isinstance(m, str) and m.strip() for m in messages):
            row_reasons.append('r6:unexplained_harness_failure')
    patch_evidence = row.get('verified_patch_bytes')
    if 'verified_patch_bytes' in row and not (type(patch_evidence) is int and patch_evidence >= 0):
        row_reasons.append('r7:invalid_patch_evidence')
    stock_resolved = row.get('resolved')
    if 'resolved' in row and type(stock_resolved) is not bool:
        row_reasons.append('r8:invalid_resolved')
    code = row.get('exit_code')
    if 'exit_code' in row and code is not None and type(code) is not int:
        row_reasons.append('r9:invalid_exit_code')

    calls = row.get('setup_calls', [])
    if not setup_shape_ok(calls):
        row_reasons.append('r11:invalid_setup_evidence')
        calls = []
    deps = row.get('missing_tool_deps')
    if not (deps is None or (isinstance(deps, list) and all(isinstance(d, str) for d in deps))):
        row_reasons.append('r12:invalid_missing_tool_deps')
    if row.get('setup_failed') is not None and type(row.get('setup_failed')) is not bool:
        row_reasons.append('r13:invalid_setup_failed')

    setup_reasons = []
    diagnostic = False
    if isinstance(deps, list) and deps:
        setup_reasons.append('s1:missing_tool_deps')
    for entry in calls:
        step, rc = entry.get('step'), entry.get('rc')
        if step not in ('pip_check', 'workspace_editable', 'setup.py'):
            if rc != 0 and (rc is not None or (entry.get('duration_s') or 0) > 0 or entry.get('stderr')):
                setup_reasons.append('s2:setup_step_failed')
        elif step == 'workspace_editable' and rc != 0:
            if RECORD in output_text(entry):
                diagnostic = True
            else:
                setup_reasons.append('s4:workspace_editable_failed')
        elif step == 'setup.py':
            if rc != 0:
                setup_reasons.append('s3:setup_py_failed')
            earlier_offline_record = False
            for sub in entry.get('subprocesses', []):
                argv = sub.get('argv')
                if not isinstance(argv, list) or '-e' not in argv or sub.get('rc') == 0:
                    continue
                if '--no-index' in argv and RECORD in output_text(sub):
                    earlier_offline_record = diagnostic = True
                elif '--no-index' not in argv and earlier_offline_record:
                    pass
                else:
                    setup_reasons.append('s5:unexpected_editable_failure')
    if row.get('setup_failed') is True and not setup_reasons and not diagnostic:
        setup_reasons.append('s6:setup_failed_unexplained')
    known_diag = diagnostic and not setup_reasons
    reasons = row_reasons + setup_reasons
    if known_diag:
        reasons.append('known_diag:record_chain')
    h = 'H-ROW' if row_reasons else ('H-SETUP' if setup_reasons else None)
    patch_bytes = row.get('verified_patch_bytes')
    result_error = row.get('result_error')
    patch_apply = isinstance(result_error, str) and result_error.startswith('Failed to apply agent patch:')
    if h is None and patch_bytes > 0 and not patch_apply and not (
        type(code) is int and code in (0, 1, 2, 3, 4, 5, 124)
    ):
        h = 'H-VERIFY'
        reasons.append('verify:unexpected_exit_code')
    # A stock PASS must be backed by a verified run: non-empty applied patch and pytest exit 0.
    if h is None and stock_resolved is True and not (patch_bytes > 0 and not patch_apply and code == 0):
        h = 'H-VERIFY'
        reasons.append('verify:contradictory_resolved')
    # A stock PASS next to an explicit verification-failure message (either field) is contradictory.
    if h is None and stock_resolved is True and any(
            isinstance(m, str) and m.strip().startswith(VERIFY_AGENT_PREFIXES) for m in messages):
        h = 'H-VERIFY'
        reasons.append('verify:resolved_with_verify_failure')
    agent = None
    if h is None:
        if stock_resolved is True:
            agent = 'PASS'
        elif patch_bytes == 0:
            agent = 'NO_PATCH'
        elif patch_apply:
            agent = 'PATCH_APPLY'
        elif code == 124:
            agent = 'VERIFY_TIMEOUT_124'
        elif code == 1:
            agent = 'PYTEST_1'
        elif code in (2, 3, 4, 5):
            agent = 'PYTEST_2_5'
        elif code == 0:
            agent = 'EXIT0_UNRESOLVED'
        else:
            agent = 'OTHER_FAIL'
    return dict(h=h, known_diag=known_diag, agent=agent,
                agent_end=agent_end(row.get('agent_error_text')), resolved=stock_resolved,
                reasons=list(dict.fromkeys(reasons)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('timing', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    payload = args.timing.read_bytes()
    rows = []
    for line in payload.decode('utf-8').splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if isinstance(row, dict) and 'instance_id' in row:
            if any(r['instance_id'] == row['instance_id'] for r in rows):
                raise ValueError(f'Duplicate instance_id in one timing file: {row["instance_id"]!r}')
            rows.append(dict(instance_id=row['instance_id'], repo=row.get('repo'), **classify(row)))
    result = dict(_schema='plan007_row_classes/v1',
                  classifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  input=str(args.timing), input_sha256=hashlib.sha256(payload).hexdigest(),
                  n_rows=len(rows),
                  counts=dict(h=dict(Counter(r['h'] for r in rows if r['h'] is not None)),
                              agent=dict(Counter(r['agent'] for r in rows if r['agent'] is not None)),
                              known_diag=sum(r['known_diag'] for r in rows)),
                  h_rows=[r['instance_id'] for r in rows if r['h'] is not None], rows=rows)
    output = json.dumps(result, indent=2) + '\n'
    if args.out:
        args.out.write_text(output, encoding='utf-8')
    print(output, end='')


if __name__ == '__main__':
    main()
