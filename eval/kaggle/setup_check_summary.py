"""Summarize a CPU setup journal without dropping failures or missing task IDs."""
import argparse
import json
from pathlib import Path


def diagnose(row):
    calls = [c for c in row.get('setup_subprocesses', [])
             if isinstance(c.get('argv'), list) and '-e' in c['argv']]
    if not calls:
        return dict(cause='unobserved', evidence=[])
    first = calls[0]
    if first['rc'] == 0:
        return dict(cause='offline_install_succeeded', evidence=[])
    output = first.get('stdout_full', first.get('stdout', '')) + '\n' + first.get('stderr_full', first.get('stderr', ''))
    lower = output.lower()
    if 'no module named pip' in lower:
        cause = 'pip_absent_in_venv'
    elif any(s in lower for s in ('backendunavailable', 'cannot import', 'no module named', 'backend is not available')):
        cause = 'build_backend_absent_in_venv'
    elif any(s in lower for s in ('not a supported wheel', 'no matching distribution', 'could not find a version')):
        cause = 'wheel_or_abi_failure_stop_and_report'
    else:
        cause = 'unresolved_offline_install_failure'
    evidence = [line for line in output.splitlines() if any(s in line.lower() for s in
                ('error', 'no module named', 'cannot import', 'backendunavailable', 'not a supported wheel'))]
    return dict(cause=cause, evidence=evidence[-12:])


def summarize(path):
    records = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    header = records[0]
    if header.get('_schema') != 'kaggle_setup_cpu_check_v1':
        raise ValueError('Unexpected journal schema')
    rows = [r for r in records if 'instance_id' in r]
    ids = [r['instance_id'] for r in rows]
    expected = header['task_ids']
    complete = bool(expected) and len(set(ids)) == len(ids) and sorted(ids) == sorted(expected)
    done = [r['_done']['n'] for r in records if '_done' in r]
    complete = complete and done == [len(expected)] and not any('_stopped' in r for r in records)
    for row in rows:
        if row['setup_fix'] == 0:
            row['offline_install_diagnosis'] = diagnose(row)
    gates = dict(complete=complete,
                 per_task_setup_le_30s=all(isinstance(r.get('setup_s_total'), (float, int)) and
                                          0 <= r['setup_s_total'] <= 30 for r in rows),
                 editable_rc_zero=all(r.get('editable_rc') == 0 for r in rows),
                 zero_retrying_lines=all(r.get('retrying_lines') == 0 for r in rows),
                 no_missing_tool_deps=all(not r.get('missing_tool_deps') for r in rows),
                 no_editable_failures=all(not r.get('editable_failed', False) for r in rows),
                 no_setup_failures=all(not r.get('setup_failed', True) for r in rows))
    return dict(_schema='kaggle_setup_cpu_check_v1', task_ids=expected, n=len(rows),
                rows=rows, gates=gates, decision='PASS' if all(gates.values()) else 'FAIL')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('journal', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    text = json.dumps(summarize(args.journal), indent=2) + '\n'
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
