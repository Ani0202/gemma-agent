"""Summarize a downloaded kaggle_timing_v1 journal without reading raw task artifacts."""
import argparse
import json
import math
from collections import Counter
from pathlib import Path


def distribution(values):
    values = sorted(values)
    def percentile(q):
        pos = (len(values) - 1) * q
        low = int(pos)
        return values[low] + (values[min(low + 1, len(values) - 1)] - values[low]) * (pos - low)
    return dict(mean=sum(values) / len(values), p50=percentile(.5), p90=percentile(.9), max=max(values)) if values else dict.fromkeys(('mean', 'p50', 'p90', 'max'))


def retrying_lines(call):
    children = call.get('subprocesses', [])
    return max(call.get('retrying_lines', 0), sum(c.get('retrying_lines', 0) for c in children))


def fallback_invocations(call):
    return setup_evidence(call) - retrying_lines(call)


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
              gate_vllm_seconds=600, gate_min_nonempty=1, gate_mode='total'):
    """gate_mode 'total' = dec 028 item 4 (a)-(e) on TOTAL Phase-1. gate_mode 'minus-image' = dec 034 item 2:
    (b) max(Phase-1 minus image emulation) <= cap x 60 + 37 s (cap from the header), (c) not gated."""
    if gate_mode not in ('total', 'minus-image'):
        raise ValueError('gate_mode must be total or minus-image')
    records = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if not records or records[0].get('_schema') != 'kaggle_timing_v1':
        raise ValueError('Expected kaggle_timing_v1 header')
    header, rows, startup, done, stopped = records[0], [], records[0].get('vllm_startup_seconds'), None, []
    artifact_errors = []
    for row in records[1:]:
        if 'instance_id' in row:
            rows.append(row)
        elif '_vllm' in row:
            startup = row['_vllm']['startup_seconds']
        elif '_done' in row:
            done = row['_done']
        elif '_stopped' in row:
            stopped.append(row['_stopped'])
        elif '_artifact_error' in row:
            artifact_errors.append(row['_artifact_error'])
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
                'phase1_wall_seconds', 'phase1_source', 'error', 'agent_outcome', 'fallback_patch_used',
                'image_emulation_seconds', 'setup_failed', 'editable_failed')},
            phase1_minus_image_seconds=(row['phase1_wall_seconds'] - row['image_emulation_seconds']
                if row.get('phase1_wall_seconds') is not None and row.get('image_emulation_seconds') is not None else None),
            total=row['wall_seconds']['total'],
            nonempty_source_diff=not row.get('empty_patch', True) and bool(source_files)))
    def measured(key):
        return numbers([r[key] for r in tasks if r[key] is not None])
    phase1, setup = distribution(measured('phase1_wall_seconds')), distribution(measured('sandbox_setup_seconds'))
    finalization = distribution(measured('finalization_seconds'))
    # Dec 028 (a): harness errors only. Non-fatal setup results (setup_failed/editable_failed) and
    # normal agent end states (timeout, no submit) are diagnostics, not gate failures. A Phase-1 value
    # from the run_agent_sandbox fallback means the sandbox wrappers never fired: not complete.
    def wrapped(r):
        return r['phase1_wall_seconds'] is not None and r.get('phase1_source') != 'run_agent_sandbox'
    complete = sum(r['error'] is None and wrapped(r) for r in tasks)
    n_expected = len(header['task_ids'])
    missing = [iid for iid in header['task_ids'] if iid not in ids]
    nonempty = sum(t['nonempty_source_diff'] for t in tasks)
    def check(passed, value, threshold):
        return dict(status='PASS' if passed else 'FAIL', value=value, threshold=threshold)
    all_phase1 = bool(tasks) and all(wrapped(r) for r in tasks)
    gate = dict(n_expected=n_expected,
        a_all_tasks_complete_no_harness_error=check(n_expected > 0 and complete == n_expected and not missing
                                                    and not stopped and done is not None, complete, n_expected),
        d_vllm_seconds=None, e_nonempty_source_diff=None)
    if gate_mode == 'total':
        gate.update(b_max_phase1=check(all_phase1 and phase1['max'] <= gate_max_phase1, phase1['max'], gate_max_phase1),
                    c_mean_phase1=check(all_phase1 and phase1['mean'] <= gate_mean_phase1, phase1['mean'], gate_mean_phase1))
    else:
        minus = [t['phase1_minus_image_seconds'] for t in tasks]
        bound = cap * 60 + 37 if cap is not None else None
        ok = all_phase1 and bound is not None and all(v is not None for v in minus)
        worst = max(minus) if ok and minus else None
        gate.update(b_max_phase1_minus_image=check(ok and worst <= bound, worst, bound),
                    c_mean_phase1='NOT_GATED (dec 034 item 2)')
    gate.update(
        d_vllm_seconds=check(startup is not None and startup <= gate_vllm_seconds, startup, gate_vllm_seconds),
        e_nonempty_source_diff=check(nonempty >= gate_min_nonempty, nonempty, gate_min_nonempty))
    gate['mode'] = gate_mode
    gate['status'] = 'PASS' if all(v['status'] == 'PASS' for v in gate.values() if isinstance(v, dict)) else 'FAIL'
    stock = [dict(instance_id=r['instance_id'], **(r.get('stock_setup') or {})) for r in rows if 'stock_setup' in r]
    stock_totals = [x['total_s'] for x in stock if x.get('total_s') is not None and not x.get('error')]
    def llm_stats(r):
        calls = r.get('llm_calls') or []
        comp = [c['completion_tokens'] for c in calls if isinstance(c.get('completion_tokens'), (int, float))]
        gaps = [c['gap_s'] for c in calls if isinstance(c.get('gap_s'), (int, float)) and c['gap_s'] > 0]
        agent = r.get('wall_seconds', {}).get('agent')
        return dict(instance_id=r['instance_id'], n_calls=len(calls), completion_tokens=sum(comp) if comp else None,
                    calls_per_minute=len(calls) / agent * 60 if agent else None, mean_gap_s=sum(gaps) / len(gaps) if gaps else None,
                    gap_tokens_per_second=sum(comp) / sum(gaps) if comp and gaps else None)
    probes = dict(platform_probe=header.get('platform_probe'),
                  stock_setup=dict(tasks=stock, n_ok=len(stock_totals), max_s=max(stock_totals) if stock_totals else None,
                                   all_le_30s=bool(stock) and len(stock_totals) == len(stock) and max(stock_totals) <= 30),
                  llm=[llm_stats(r) for r in rows if 'llm_calls' in r],
                  mean_agent_seconds=distribution(numbers([r['wall_seconds']['agent'] for r in rows if r['wall_seconds'].get('agent') is not None]))['mean'])
    return dict(_schema='kaggle_timing_summary_v1',
                fields=dict(n='Number of task rows (gate expected n)',
                    n_complete_no_error='Rows with a sandbox-wrapper phase1 measurement and no harness error (setup_failed is diagnostic only)',
                    provenance='Kernel header: git_sha, bundle_sha256, agent_yaml_sha256, gpu_names, gpu_count, caps, created_utc, concurrency, mcp_import_ok',
                    agent_outcome_counts='Rows per agent_outcome (timeout/turns/tool_calls/no_submit/null)',
                    setup_failed_count='Rows with a non-fatal setup rc!=0 (diagnostic, not gated)',
                    editable_failed_count='Rows whose editable install returned rc!=0 (diagnostic, not gated)',
                    image_emulation_seconds='Distribution of in-Phase-1 seconds emulating image layers the scorer image already has',
                    phase1_minus_image_seconds='Distribution of phase1_wall_seconds minus image_emulation_seconds (not gated; reported for the Director)',
                    fallback_invocations='Index-enabled editable fallback invocations across setup calls',
                    retrying_lines_total='pip Retrying lines across setup calls, nested output counted once',
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
                    gate='a-e checks: PASS/FAIL, observed value, CLI threshold; overall status requires all checks; mode total (dec 028) or minus-image (dec 034 item 2)',
                    probes='Plan 006 addendum P1-P3: platform_probe (header), stock_setup per task (+max_s, all_le_30s = G1 P1 leg), llm per-task call stats, mean_agent_seconds',
                    decision_note='decision is the legacy total-wall/cap projection, NOT the gate (dec 032 item 5)',
                    total_seconds='Total task wall seconds distribution',
                    test_run_share='Agent test time share distribution', test_runs_per_task='Test request count distribution',
                    empty_patch_count='Blank patches', test_files_edited_count='Tasks editing protected/test files',
                    stray_files_count='Tasks adding stray files', test_files_edited_files='Total protected/test paths',
                    stray_files_files='Total stray paths', decision='Legacy total-wall/cap projection check',
                    projected_minutes='p90 total seconds times 125 plus vLLM, in minutes',
                    cap_worst_case_minutes='Configured cap times 125 plus 30 minutes', cap_minutes='Configured agent cap',
                    artifact_errors='Raw artifact write failures (diagnostic; rows unaffected)',
                    missing_task_ids='Header task IDs absent from task rows', done_present='Journal contains _done', stopped='Journal stop reasons'),
                tasks=tasks, gate=gate, probes=probes, n_complete_no_error=complete,
                decision_note='decision is the legacy total-wall/cap projection, NOT the gate (dec 032 item 5)',
                provenance={k: header.get(k) for k in ('git_sha', 'bundle_sha256', 'agent_yaml_sha256', 'gpu_names',
                    'gpu_count', 'caps', 'created_utc', 'concurrency', 'mcp_import_ok')},
                agent_outcome_counts=dict(Counter(str(t['agent_outcome']) for t in tasks)),
                setup_failed_count=sum(bool(t['setup_failed']) for t in tasks),
                editable_failed_count=sum(bool(t['editable_failed']) for t in tasks),
                image_emulation_seconds=distribution(measured('image_emulation_seconds')),
                phase1_minus_image_seconds=distribution(measured('phase1_minus_image_seconds')),
                fallback_invocations=sum(fallback_invocations(c) for r in rows for c in r.get('setup_calls', [])),
                retrying_lines_total=sum(retrying_lines(c) for r in rows for c in r.get('setup_calls', [])),
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
                cap_minutes=cap, missing_task_ids=missing,
                done_present=done is not None, stopped=stopped, artifact_errors=artifact_errors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('timing_jsonl', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--gate-max-phase1', type=float, default=296)
    parser.add_argument('--gate-mean-phase1', type=float, default=270)
    parser.add_argument('--gate-vllm-seconds', type=float, default=600)
    parser.add_argument('--gate-min-nonempty', type=int, default=1)
    parser.add_argument('--gate-mode', choices=('total', 'minus-image'), default='total')
    args = parser.parse_args()
    summary = summarize(args.timing_jsonl, gate_max_phase1=args.gate_max_phase1,
                        gate_mean_phase1=args.gate_mean_phase1,
                        gate_vllm_seconds=args.gate_vllm_seconds,
                        gate_min_nonempty=args.gate_min_nonempty, gate_mode=args.gate_mode)
    args.output.write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
