"""Frozen Plan 007 rev 4 classifier for timing journal rows (stdlib only)."""
import argparse
from collections import Counter
import hashlib
import json
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
    text = (message or '').strip()
    return next((name for name, pattern in AGENT_END if pattern.match(text)), None)


def output_text(entry):
    return (entry.get('stdout') or '') + (entry.get('stderr') or '')


def classify(row: dict) -> dict:
    """Classify one task row, preserving the stock verdict even for H rows."""
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
    elif error is None or error == 'Harness task failure':
        messages = (row.get('result_error'), row.get('agent_error_text'))
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

    setup_reasons = []
    diagnostic = False
    if row.get('missing_tool_deps'):
        setup_reasons.append('s1:missing_tool_deps')
    for entry in row.get('setup_calls', []):
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
        if 'instance_id' in row:
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
