"""Frozen Plan 007 rev 5 classifier for timing journal rows (stdlib only)."""
import argparse
from collections import Counter
import hashlib
import json
import math
import re
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
REQUIRED = ('result_error', 'agent_error_text', 'verified_patch_bytes', 'setup_calls', 'exit_code', 'resolved',
            'error', 'setup_failed', 'missing_tool_deps')


def agent_end(message):
    text = message.strip() if isinstance(message, str) else ''
    return next((name for name, pattern in AGENT_END if pattern.match(text)), None)


# Names passed to setup_step by agent_timing (including setup-only journals).
SETUP_STEPS = frozenset(('venv', 'venv_fidelity', 'pip_bootstrap', 'interpreter_probe',
    'tool_sources', 'pytest_timeout_source', 'tool_install', 'tool_deps', 'pip_check',
    'workspace_editable', 'base_tar_extraction', 'setup.py', 'setup_container_wheels',
    'extract_snapshot', 'setup_git_exclude', 'install_editable_package', 'teardown'))
STEP_REQUIRED = ('step', 'rc', 'duration_s', 'stdout', 'stderr')
SUB_REQUIRED = ('argv', 'rc', 'stdout', 'stderr')


def has_record(entry):
    return any(RECORD in (entry.get(stream) or '') for stream in ('stdout', 'stderr'))


def opt_str(value):
    return value is None or isinstance(value, str)


def opt_rc(value):
    return value is None or type(value) is int


def finite_nonnegative(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except (OverflowError, ValueError, TypeError):
        return False


def nonblank(value):
    return isinstance(value, str) and bool(value.strip())


def setup_shape_ok(calls):
    """Validate emitted evidence before any diagnostic exemption is considered."""
    if not isinstance(calls, list):
        return False
    for entry in calls:
        if not isinstance(entry, dict) or any(k not in entry for k in STEP_REQUIRED):
            return False
        if not isinstance(entry['step'], str) or entry['step'] not in SETUP_STEPS:
            return False
        if not (opt_rc(entry['rc']) and opt_str(entry['stdout']) and opt_str(entry['stderr'])):
            return False
        if entry['duration_s'] is not None and not finite_nonnegative(entry['duration_s']):
            return False
        if 'subprocesses' in entry and entry['step'] != 'setup.py':
            return False
        subs = entry.get('subprocesses', [])
        if not isinstance(subs, list):
            return False
        for sub in subs:
            if not isinstance(sub, dict) or any(k not in sub for k in SUB_REQUIRED):
                return False
            if not isinstance(sub['argv'], list) or not sub['argv'] or not all(map(nonblank, sub['argv'])):
                return False
            if not (opt_rc(sub['rc']) and opt_str(sub['stdout']) and opt_str(sub['stderr'])):
                return False
            if 'duration_s' in sub and sub['duration_s'] is not None and not finite_nonnegative(sub['duration_s']):
                return False
    return True


def not_run(entry):
    return (entry['rc'] is None and entry['duration_s'] == 0
            and not entry['stdout'] and not entry['stderr'])


def failed(entry):
    return type(entry['rc']) is int and entry['rc'] != 0


def editable_identity(argv, offline):
    """Exact setup.py pip command after SubprocessManager path rewriting."""
    flags = ['--no-index', '--find-links=/wheels', '--no-build-isolation'] if offline else []
    if len(argv) != 7 + len(flags):
        return None
    if argv[1:-1] != ['-m', 'pip', 'install', *flags, '--no-deps', '-e']:
        return None
    interpreter = Path(argv[0])
    if not re.fullmatch(r'/tmp/swegemma_sandbox_[^/]+/venv/bin/python3', argv[0]):
        return None
    target = str(interpreter.parents[2] / 'workspace')
    return (argv[0], target) if argv[-1] == target else None


def message_category(message):
    if not message:
        return None
    return agent_end(message) or next((p for p in VERIFY_AGENT_PREFIXES if message.startswith(p)), None)


def classify(row: dict) -> dict:
    """Classify one task row, preserving the stock verdict even for H rows."""
    if not isinstance(row, dict):
        raise TypeError('Row is not a JSON object')
    row_reasons = []
    if not all(nonblank(row.get(k)) for k in ('instance_id', 'repo')):
        row_reasons.append('r14:invalid_identity')
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
        for field_index, message in enumerate(messages):
            if (message and agent_end(message) is None and not message.startswith(VERIFY_AGENT_PREFIXES)
                    and not (row.get('resolved') is True and field_index == 0)):
                row_reasons.append('r4:unrecognized_message' if error else 'r5:unrecognized_message')
                break
        if (error and not any(isinstance(m, str) and m.strip() for m in messages)
                and not (row.get('resolved') is True and isinstance(messages[0], str) and messages[0])):
            row_reasons.append('r6:unexplained_harness_failure')
    if all(isinstance(m, str) and m for m in messages):
        categories = [message_category(m) for m in messages]
        if all(categories) and categories[0] != categories[1]:
            row_reasons.append('r15:contradictory_messages')
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
        step, rc = entry['step'], entry['rc']
        if not_run(entry):
            continue
        if step not in ('pip_check', 'workspace_editable', 'setup.py'):
            if rc != 0:
                setup_reasons.append('s2:setup_step_failed')
        elif step == 'workspace_editable' and rc != 0:
            if failed(entry) and has_record(entry):
                diagnostic = True
            else:
                setup_reasons.append('s4:workspace_editable_failed')
        elif step == 'setup.py':
            if rc != 0:
                setup_reasons.append('s3:setup_py_failed')
            pending = None
            for sub in entry.get('subprocesses', []):
                previous, pending = pending, None
                argv = sub['argv']
                if '-e' not in argv or sub['rc'] == 0:
                    continue
                identity = editable_identity(argv, offline=True)
                if failed(sub) and identity and has_record(sub):
                    pending = identity
                    diagnostic = True
                elif failed(sub) and previous and editable_identity(argv, offline=False) == previous:
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
    patch_apply = any(isinstance(m, str) and m.startswith(VERIFY_AGENT_PREFIXES[0]) for m in messages)
    if h is None and patch_bytes > 0 and not patch_apply and not (
        type(code) is int and code in (0, 1, 2, 3, 4, 5, 124)
    ):
        h = 'H-VERIFY'
        reasons.append('verify:unexpected_exit_code')
    # A stock PASS must be backed by a verified run: non-empty applied patch and pytest exit 0.
    if h is None and stock_resolved is True and not (patch_bytes > 0 and not patch_apply and code == 0):
        h = 'H-VERIFY'
        reasons.append('verify:contradictory_resolved')
    if h is None and stock_resolved is True and any(
            isinstance(m, str) and m.startswith(VERIFY_AGENT_PREFIXES) for m in messages):
        h = 'H-VERIFY'
        reasons.append('verify:resolved_with_verify_failure')
    if h is None and stock_resolved is True and result_error:
        h = 'H-VERIFY'
        reasons.append('verify:resolved_with_result_error')
    verify_failure = any(isinstance(m, str) and m.startswith(VERIFY_AGENT_PREFIXES[1:]) for m in messages)
    apply_failure = any(isinstance(m, str) and m.startswith(VERIFY_AGENT_PREFIXES[0]) for m in messages)
    if h is None and (verify_failure and code != 0
            or apply_failure and not (patch_bytes > 0 and (code is None or type(code) is int and code != 0))
            or patch_bytes == 0 and code not in (None, -1)):
        h = 'H-VERIFY'
        reasons.append('verify:contradictory_failure_evidence')
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
    rows, header, done = [], None, None
    def unique_object(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError(f'Duplicate JSON key: {key!r}')
            obj[key] = value
        return obj

    for line_number, line in enumerate(payload.decode('utf-8').splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line, object_pairs_hook=unique_object)
        if isinstance(row, dict) and row.get('_schema') in ('kaggle_timing_v1', 'kaggle_setup_cpu_check_v1') and 'instance_id' not in row:
            if header is not None or rows or done is not None:
                raise ValueError('Header must occur once before task rows')
            header = row
            continue
        if isinstance(row, dict) and set(row) == {'_done'} and isinstance(row['_done'], dict):
            if done is not None:
                raise ValueError('Duplicate _done record')
            done = row['_done']
            continue
        # These auxiliary records are also emitted by agent_timing.main.
        if isinstance(row, dict) and set(row) == {'_vllm'}:
            meta = row['_vllm']
            if isinstance(meta, dict) and set(meta) == {'startup_seconds'} and finite_nonnegative(meta['startup_seconds']):
                continue
        if isinstance(row, dict) and set(row) == {'_stopped'} and isinstance(row['_stopped'], str):
            if (row['_stopped'] == 'insufficient remaining budget for next task'
                    or re.fullmatch(r'Kernel exception \([A-Za-z_][A-Za-z_0-9]*\)', row['_stopped'])):
                continue
        if not isinstance(row, dict) or not all(nonblank(row.get(k)) for k in ('instance_id', 'repo')):
            raise ValueError(f'Invalid task record at line {line_number}: instance_id and repo must be non-blank strings')
        if done is not None:
            raise ValueError('Task row after _done')
        if any(r['instance_id'] == row['instance_id'] for r in rows):
            raise ValueError(f'Duplicate instance_id in one timing file: {row["instance_id"]!r}')
        rows.append(dict(instance_id=row['instance_id'], repo=row['repo'], **classify(row)))
    if header is not None and 'task_ids' in header:
        ids = header['task_ids']
        if (not isinstance(ids, list) or not all(map(nonblank, ids)) or len(set(ids)) != len(ids)
                or [r['instance_id'] for r in rows] != ids[:len(rows)]):
            raise ValueError('Row ids must be an in-order prefix of header task_ids')
    if done is not None and 'n' in done and (type(done['n']) is not int or done['n'] != len(rows)):
        raise ValueError('_done.n must equal row count')
    void_reasons = []
    if header is not None:
        if 'vllm_startup_seconds' in header and header['vllm_startup_seconds'] is None:
            void_reasons.append('vllm_not_up')
        if header.get('mcp_import_ok') is False:
            void_reasons.append('mcp_import_failed')
    if void_reasons:
        for row in rows:
            row.update(h='H-ROW', agent=None)
            row['reasons'].append('kernel:void')
    result = dict(_schema='plan007_row_classes/v1',
                  kernel_void=bool(void_reasons), kernel_void_reasons=void_reasons,
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
