"""Summarize a downloaded kaggle_timing_v1 journal without reading raw task artifacts."""
import argparse
import json
import math
from pathlib import Path


def distribution(values):
    values = sorted(values)
    def percentile(q):
        pos = (len(values) - 1) * q
        low = int(pos)
        return values[low] + (values[min(low + 1, len(values) - 1)] - values[low]) * (pos - low)
    return dict(mean=sum(values) / len(values), p50=percentile(.5), p90=percentile(.9), max=max(values)) if values else dict.fromkeys(('mean', 'p50', 'p90', 'max'))


def setup_evidence(call):
    """Count index fallback invocations and retry lines, without counting nested output twice."""
    children = call.get('subprocesses', [])
    retries = max(call.get('retrying_lines', 0), sum(c.get('retrying_lines', 0) for c in children))
    fallbacks = 0
    for child in children or [call]:
        argv = child.get('argv') or []
        if isinstance(argv, str):
            import shlex
            argv = shlex.split(argv)
        fallbacks += int('install' in argv and '-e' in argv and '--no-index' not in argv)
    return retries + fallbacks


def summarize(path, *, gate_max_phase1=296, gate_mean_phase1=270,
              gate_vllm_seconds=600, gate_min_nonempty=1):
    records = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if not records or records[0].get('_schema') != 'kaggle_timing_v1':
        raise ValueError('Expected kaggle_timing_v1 header')
    header, rows, startup, done, stopped = records[0], [], records[0].get('vllm_startup_seconds'), None, []
    for row in records[1:]:
        if 'instance_id' in row:
            rows.append(row)
        elif '_vllm' in row:
            startup = row['_vllm']['startup_seconds']
        elif '_done' in row:
            done = row['_done']
        elif '_stopped' in row:
            stopped.append(row['_stopped'])
        else:
            raise ValueError('Unknown journal record')
    ids = [r['instance_id'] for r in rows]
    if len(ids) != len(set(ids)) or set(ids) - set(header['task_ids']):
        raise ValueError('Duplicate or unexpected task records')
    if done is not None and done['n'] != len(rows):
        raise ValueError('Done count does not match task records')
    def numbers(values):
        if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values):
            raise ValueError('Invalid measurement')
        return values
    totals = distribution(numbers([r['wall_seconds']['total'] for r in rows]))
    shares = distribution(numbers([r.get('test_run', {}).get('share_of_agent_seconds') for r in rows if r.get('test_run', {}).get('share_of_agent_seconds') is not None]))
    runs = distribution(numbers([r.get('test_run', {}).get('n', 0) for r in rows]))
    caps = header.get('caps') or {}
    cap = caps.get('max_time_minutes')
    numbers([v for v in (startup, cap) if v is not None])
    timing_minutes = totals['p90'] * 125 / 60 + startup / 60 if totals['p90'] is not None and startup is not None else None
    cap_minutes = cap * 125 + 30 if cap is not None else None
    tasks = []
    for row in rows:
        source_files = set(row.get('patch_files', [])) - set(row.get('test_files_edited', [])) - set(row.get('stray_files', []))
        tasks.append(dict(instance_id=row['instance_id'], repo=row.get('repo'),
            setup_calls=[{key: call.get(key) for key in ('step', 'duration_s', 'rc', 'retrying_lines')}
                         for call in row.get('setup_calls', [])],
            **{key: row.get(key) for key in ('sandbox_setup_seconds', 'agent_clock_seconds',
                'agent_timeout_fired', 'finalization_seconds', 'teardown_seconds',
                'phase1_wall_seconds', 'error', 'fallback_patch_used')},
            total=row['wall_seconds']['total'],
            nonempty_source_diff=not row.get('empty_patch', True) and bool(source_files)))
    def measured(key):
        return numbers([r[key] for r in tasks if r[key] is not None])
    phase1, setup = distribution(measured('phase1_wall_seconds')), distribution(measured('sandbox_setup_seconds'))
    finalization = distribution(measured('finalization_seconds'))
    complete = sum(r['error'] is None and r['phase1_wall_seconds'] is not None
                   and not original.get('setup_failed', False)
                   for r, original in zip(tasks, rows))
    nonempty = sum(t['nonempty_source_diff'] for t in tasks)
    def check(passed, value, threshold):
        return dict(status='PASS' if passed else 'FAIL', value=value, threshold=threshold)
    all_phase1 = bool(tasks) and len(measured('phase1_wall_seconds')) == len(tasks)
    gate = dict(n_expected=len(rows),
        a_all_tasks_complete_no_harness_error=check(bool(tasks) and complete == len(tasks), complete, len(tasks)),
        b_max_phase1=check(all_phase1 and phase1['max'] <= gate_max_phase1, phase1['max'], gate_max_phase1),
        c_mean_phase1=check(all_phase1 and phase1['mean'] <= gate_mean_phase1, phase1['mean'], gate_mean_phase1),
        d_vllm_seconds=check(startup is not None and startup <= gate_vllm_seconds, startup, gate_vllm_seconds),
        e_nonempty_source_diff=check(nonempty >= gate_min_nonempty, nonempty, gate_min_nonempty))
    gate['status'] = 'PASS' if all(v['status'] == 'PASS' for v in gate.values() if isinstance(v, dict)) else 'FAIL'
    return dict(_schema='kaggle_timing_summary_v1',
                fields=dict(n='Number of task rows (gate expected n)',
                    n_complete_no_error='Rows with phase1 measurement, no harness error and no setup failure',
                    tasks='Per-task instance_id, repo, setup_calls [{step,duration_s,rc,retrying_lines}], sandbox_setup_seconds, agent_clock_seconds, agent_timeout_fired, finalization_seconds, teardown_seconds, phase1_wall_seconds, total, error, nonempty_source_diff, fallback_patch_used; unavailable measurements are null',
                    nonempty_source_diff='Nonblank classified patch with a path outside protected/test and stray files',
                    phase1_seconds='Phase-1 wall seconds: mean/p50/p90/max of available measurements',
                    setup_seconds='Setup S seconds: mean/p50/p90/max of available measurements',
                    finalization_max_seconds='Maximum finalization seconds, or null',
                    fallback_count='Index-enabled editable fallback invocations plus Retrying lines across setup calls, nested output counted once',
                    tasks_with_retrying_lines='Task count with setup retrying_lines > 0',
                    timeout_fired_count='Tasks whose observed agent timeout fired',
                    fallback_patch_count='Tasks using a non-empty fallback patch',
                    vllm_startup_seconds='Measured vLLM startup seconds',
                    gate='a-e checks: PASS/FAIL, observed value, CLI threshold; overall status requires all checks',
                    total_seconds='Total task wall seconds distribution',
                    test_run_share='Agent test time share distribution', test_runs_per_task='Test request count distribution',
                    empty_patch_count='Blank patches', test_files_edited_count='Tasks editing protected/test files',
                    stray_files_count='Tasks adding stray files', test_files_edited_files='Total protected/test paths',
                    stray_files_files='Total stray paths', decision='Legacy total-wall/cap projection check',
                    projected_minutes='p90 total seconds times 125 plus vLLM, in minutes',
                    cap_worst_case_minutes='Configured cap times 125 plus 30 minutes', cap_minutes='Configured agent cap',
                    missing_task_ids='Header task IDs absent from task rows', done_present='Journal contains _done', stopped='Journal stop reasons'),
                tasks=tasks, gate=gate, n_complete_no_error=complete,
                phase1_seconds=phase1, setup_seconds=setup, finalization_max_seconds=finalization['max'],
                fallback_count=sum(setup_evidence(c) for r in rows for c in r.get('setup_calls', [])),
                tasks_with_retrying_lines=sum(any(c.get('retrying_lines', 0) > 0 or
                    any(s.get('retrying_lines', 0) > 0 for s in c.get('subprocesses', []))
                    for c in r.get('setup_calls', [])) for r in rows),
                fallback_patch_count=sum(bool(r.get('fallback_patch_used')) for r in rows),
                timeout_fired_count=sum(bool(r.get('agent_timeout_fired')) for r in rows),
                n=len(rows), vllm_startup_seconds=startup,
                total_seconds=totals, test_run_share=shares, test_runs_per_task=runs,
                empty_patch_count=sum(bool(r.get('empty_patch', True)) for r in rows),
                test_files_edited_count=sum(bool(r.get('test_files_edited', [])) for r in rows),
                stray_files_count=sum(bool(r.get('stray_files', [])) for r in rows),
                test_files_edited_files=sum(len(r.get('test_files_edited', [])) for r in rows),
                stray_files_files=sum(len(r.get('stray_files', [])) for r in rows),
                decision='PASS' if timing_minutes is not None and cap_minutes is not None and timing_minutes <= 660 and cap_minutes <= 660 else 'FAIL',
                projected_minutes=timing_minutes, cap_worst_case_minutes=cap_minutes,
                cap_minutes=cap, missing_task_ids=[iid for iid in header['task_ids'] if iid not in ids],
                done_present=done is not None, stopped=stopped)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('timing_jsonl', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--gate-max-phase1', type=float, default=296)
    parser.add_argument('--gate-mean-phase1', type=float, default=270)
    parser.add_argument('--gate-vllm-seconds', type=float, default=600)
    parser.add_argument('--gate-min-nonempty', type=int, default=1)
    args = parser.parse_args()
    summary = summarize(args.timing_jsonl, gate_max_phase1=args.gate_max_phase1,
                        gate_mean_phase1=args.gate_mean_phase1,
                        gate_vllm_seconds=args.gate_vllm_seconds,
                        gate_min_nonempty=args.gate_min_nonempty)
    args.output.write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
