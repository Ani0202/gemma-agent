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
    """gate_mode 'total' = dec 028 item 4 (a)-(e) on TOTAL Phase-1. gate_mode 'stock-path' = dec 034 item 2 as
    corrected by dec 036 item 1: (b) max(stockpath_phase1) <= cap x 60 + 37 s (cap from the header), where
    stockpath_phase1 = phase1_wall - image_emulation_seconds - setup_py_emulation_seconds; (c) not gated."""
    if gate_mode not in ('total', 'stock-path'):
        raise ValueError('gate_mode must be total or stock-path')
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
    def numbers(values, *, signed=False, raw=False):
        floor = -1e-3 if raw else 0
        if any(type(v) not in (int, float) or not math.isfinite(v) or (not signed and v < floor) for v in values):
            raise ValueError('Invalid measurement')
        return [max(0.0, v) for v in values] if raw else values
    # Clamp raw clock rounding noise before arithmetic, per-task reporting and gating.
    for row in rows:
        for key in ('sandbox_setup_seconds', 'agent_clock_seconds', 'finalization_seconds',
                    'teardown_seconds', 'phase1_wall_seconds', 'image_emulation_seconds'):
            if row.get(key) is not None:
                row[key] = numbers([row[key]], raw=True)[0]
        for key, value in row['wall_seconds'].items():
            if value is not None:
                row['wall_seconds'][key] = numbers([value], raw=True)[0]
        for call in row.get('setup_calls', []):
            if call.get('duration_s') is not None:
                call['duration_s'] = numbers([call['duration_s']], raw=True)[0]
    totals = distribution(numbers([r['wall_seconds']['total'] for r in rows]))
    shares = distribution(numbers([r.get('test_run', {}).get('share_of_agent_seconds') for r in rows if r.get('test_run', {}).get('share_of_agent_seconds') is not None]))
    runs = distribution(numbers([r.get('test_run', {}).get('n', 0) for r in rows]))
    caps = header.get('caps') or {}
    cap = caps.get('max_time_minutes')
    if startup is not None:
        startup = numbers([startup], raw=True)[0]
    if cap is not None:
        cap = numbers([cap])[0]
    timing_minutes = totals['p90'] * 125 / 60 + startup / 60 if totals['p90'] is not None and startup is not None else None
    cap_minutes = cap * 125 + 30 if cap is not None else None
    def step_seconds(row, names):
        # Every named step must be measured; repeated steps are summed. Missing -> None.
        calls = [c for c in row.get('setup_calls', []) if c.get('step') in names]
        if {c['step'] for c in calls} != set(names) or any(c.get('duration_s') is None for c in calls):
            return None
        return sum(c['duration_s'] for c in calls)
    def stock_total(row):
        st = row.get('stock_setup') or {}
        v = st.get('total_s')
        return v if type(v) in (int, float) and math.isfinite(v) and v >= 0 and not st.get('error') else None
    tasks = []
    for row in rows:
        # Dec 036: setup.py emulation is skipped by the stock dependency hooks.
        setup_py = step_seconds(row, ('setup.py',))
        stock_s = stock_total(row)
        parts = [row.get('agent_clock_seconds'), row.get('finalization_seconds'), stock_s]
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
            setup_py_emulation_seconds=setup_py,
            stockpath_retained_emulation_seconds=step_seconds(row, ('workspace_editable', 'base_tar_extraction')),
            stockpath_phase1_seconds=(row['phase1_wall_seconds'] - row['image_emulation_seconds'] - setup_py
                if row.get('phase1_wall_seconds') is not None and row.get('image_emulation_seconds') is not None
                and setup_py is not None else None),
            stock_setup_seconds=stock_s,
            h1_composite_seconds=sum(parts) if all(type(v) in (int, float) for v in parts) else None,
            # fix5c review BLOCKING 1: a post-timeout finalization command (fallback git diff) that raised or
            # returned rc != 0 is a harness error even when result.error/agent_error look normal. Fail closed:
            # rc None without a recorded exception (unknown result) counts as failed too.
            finalization_failed=[{key: call.get(key) for key in ('cmd', 'rc', 'exception')}
                                 for call in row.get('finalization_exec') or []
                                 if call.get('exception') or call.get('rc') != 0],
            total=row['wall_seconds']['total'],
            nonempty_source_diff=not row.get('empty_patch', True) and bool(source_files)))
    def measured(key):
        return numbers([r[key] for r in tasks if r[key] is not None],
                       signed=key in ('phase1_minus_image_seconds', 'stockpath_phase1_seconds'))
    phase1, setup = distribution(measured('phase1_wall_seconds')), distribution(measured('sandbox_setup_seconds'))
    finalization = distribution(measured('finalization_seconds'))
    # Dec 028 (a): harness errors only. Non-fatal setup results (setup_failed/editable_failed) and
    # normal agent end states (timeout, no submit) are diagnostics, not gate failures. A Phase-1 value
    # from the run_agent_sandbox fallback means the sandbox wrappers never fired: not complete.
    def wrapped(r):
        return r['phase1_wall_seconds'] is not None and r.get('phase1_source') != 'run_agent_sandbox'
    complete = sum(r['error'] is None and not r['finalization_failed'] and wrapped(r) for r in tasks)
    n_expected = len(header['task_ids'])
    missing = [iid for iid in header['task_ids'] if iid not in ids]
    nonempty = sum(t['nonempty_source_diff'] for t in tasks)
    def check(passed, value, threshold):
        return dict(status='PASS' if passed else 'FAIL', value=value, threshold=threshold)
    all_phase1 = bool(tasks) and all(wrapped(r) for r in tasks)
    gate = dict(n_expected=n_expected,
        b_note='conservative: stock-path residual still includes workspace_editable and base_tar_extraction emulation steps (skipped by the stock path); biases (b) toward FAIL by their duration',
        a_all_tasks_complete_no_harness_error=check(n_expected > 0 and complete == n_expected and not missing
                                                    and not stopped and done is not None, complete, n_expected),
        d_vllm_seconds=None, e_nonempty_source_diff=None)
    if gate_mode == 'total':
        gate.update(b_max_phase1=check(all_phase1 and phase1['max'] <= gate_max_phase1, phase1['max'], gate_max_phase1),
                    c_mean_phase1=check(all_phase1 and phase1['mean'] <= gate_mean_phase1, phase1['mean'], gate_mean_phase1))
    else:
        stock_path = [t['stockpath_phase1_seconds'] for t in tasks]
        bound = cap * 60 + 37 if cap is not None else None
        ok = all_phase1 and bound is not None and all(v is not None for v in stock_path)
        worst = max(stock_path) if ok and stock_path else None
        gate.update(b_max_stockpath_phase1=check(ok and worst <= bound, worst, bound),
                    c_mean_phase1='NOT_GATED (dec 034 item 2)')
    gate.update(
        d_vllm_seconds=check(startup is not None and startup <= gate_vllm_seconds, startup, gate_vllm_seconds),
        e_nonempty_source_diff=check(nonempty >= gate_min_nonempty, nonempty, gate_min_nonempty))
    gate['mode'] = gate_mode
    gate['status'] = 'PASS' if all(v['status'] == 'PASS' for v in gate.values() if isinstance(v, dict)) else 'FAIL'
    stock = [dict(r.get('stock_setup') or {}, instance_id=r['instance_id']) for r in rows if 'stock_setup' in r]
    valid_stock = {r['instance_id']: stock_total(r) for r in rows
                   if stock_total(r) is not None
                   and (r.get('stock_setup') or {}).get('instance_id', r['instance_id']) == r['instance_id']}
    stock_totals = list(valid_stock.values())
    stock_missing = [iid for iid in header['task_ids'] if iid not in valid_stock]
    def llm_stats(r):
        calls = r.get('llm_calls') or []
        comp = [c['completion_tokens'] for c in calls if isinstance(c.get('completion_tokens'), (int, float))]
        gaps = [c['gap_s'] for c in calls if isinstance(c.get('gap_s'), (int, float)) and c['gap_s'] > 0]
        agent = r.get('wall_seconds', {}).get('agent')
        return dict(instance_id=r['instance_id'], n_calls=len(calls), completion_tokens=sum(comp) if comp else None,
                    calls_per_minute=len(calls) / agent * 60 if agent else None, mean_gap_s=sum(gaps) / len(gaps) if gaps else None,
                    gap_tokens_per_second=sum(comp) / sum(gaps) if comp and gaps else None)
    h1 = [t['h1_composite_seconds'] for t in tasks]
    probes = dict(platform_probe=header.get('platform_probe'),
                  h1_composite=dict(not_gated='agent_clock + finalization + P1 stock_setup total_s (dec 036 item 1); G1 rests on it',
                                    tasks={t['instance_id']: t['h1_composite_seconds'] for t in tasks},
                                    max_s=max(h1) if h1 and all(v is not None for v in h1) else None,
                                    n_missing=sum(v is None for v in h1)),
                  stock_setup=dict(tasks=stock, n_expected=n_expected,
                                   n_missing=len(stock_missing), missing_ids=stock_missing, n_ok=len(stock_totals), max_s=max(stock_totals) if stock_totals else None,
                                   all_le_30s=n_expected > 0 and not stock_missing and len(valid_stock) == n_expected and max(stock_totals) <= 30),
                  llm=[llm_stats(r) for r in rows if 'llm_calls' in r],
                  mean_agent_seconds=distribution(numbers([r['wall_seconds']['agent'] for r in rows if r['wall_seconds'].get('agent') is not None]))['mean'])
    return dict(_schema='kaggle_timing_summary_v1',
                fields=dict(n='Number of task rows (gate expected n)',
                    n_complete_no_error='Rows with a sandbox-wrapper phase1 measurement, no harness error and no failed finalization command (setup_failed is diagnostic only)',
                    provenance='Kernel header: git_sha, bundle_sha256, agent_yaml_sha256, gpu_names, gpu_count, caps, created_utc, concurrency, mcp_import_ok',
                    agent_outcome_counts='Rows per agent_outcome (timeout/turns/tool_calls/no_submit/null)',
                    setup_failed_count='Rows with a non-fatal setup rc!=0 (diagnostic, not gated)',
                    editable_failed_count='Rows whose editable install returned rc!=0 (diagnostic, not gated)',
                    image_emulation_seconds='Distribution of in-Phase-1 seconds emulating image layers the scorer image already has',
                    phase1_minus_image_seconds='Distribution of phase1_wall_seconds minus image_emulation_seconds (not gated; reported for the Director)',
                    setup_py_emulation_seconds='Distribution of per-task seconds in setup_calls step setup.py (Dockerfile.public setup.py emulation: install_editable_package + install_test_dependencies)',
                    stockpath_retained_emulation_seconds='Per-task sum of workspace_editable and base_tar_extraction steps retained by the conservative stock-path formula; null if missing',
                    stockpath_phase1_seconds='Distribution of phase1_wall - image_emulation - setup_py_emulation (gate b in stock-path mode)',
                    h1_composite_seconds='Distribution of agent_clock + finalization + P1 stock_setup total_s (not gated)',
                    fallback_invocations='Index-enabled editable fallback invocations across setup calls',
                    retrying_lines_total='pip Retrying lines across setup calls, nested output counted once',
                    tasks='Per-task instance_id, repo, setup_calls [{step,duration_s,rc,retrying_lines}], sandbox_setup_seconds, agent_clock_seconds, agent_timeout_fired, finalization_seconds, teardown_seconds, phase1_wall_seconds, setup_py_emulation_seconds, stockpath_phase1_seconds, stock_setup_seconds, stockpath_retained_emulation_seconds, h1_composite_seconds, total, error, finalization_failed [{cmd,rc,exception}] (post-timeout commands with rc!=0, exception or unknown rc; any entry fails gate a), nonempty_source_diff, fallback_patch_used; unavailable measurements are null',
                    nonempty_source_diff='Nonblank classified patch with a path outside protected/test and stray files',
                    phase1_seconds='Phase-1 wall seconds: mean/p50/p90/max of available measurements',
                    setup_seconds='Setup S seconds: mean/p50/p90/max of available measurements',
                    finalization_max_seconds='Maximum finalization seconds, or null',
                    fallback_count='Index-enabled editable fallback invocations plus Retrying lines across setup calls, nested output counted once',
                    tasks_with_retrying_lines='Task count with setup retrying_lines > 0',
                    timeout_fired_count='Tasks whose observed agent timeout fired',
                    fallback_patch_count='Tasks using a non-empty fallback patch',
                    vllm_startup_seconds='Measured vLLM startup seconds',
                    gate='a-e checks: PASS/FAIL, observed value, CLI threshold; overall status requires all checks; mode total (dec 028) or stock-path (dec 034 item 2 / dec 036 item 1: b = max stockpath_phase1 <= cap*60+37)',
                    probes='Plan 006 addendum P1-P3: platform_probe (header), h1_composite (not gated; per task + max_s, null if any part missing), stock_setup per task (+n_expected, n_missing, missing_ids, max_s, all_le_30s = valid successful P1 for every expected ID <=30s, G1 P1 leg), llm per-task call stats, mean_agent_seconds',
                    decision_note='legacy_projection_decision is the legacy total-wall/cap projection, NOT the gate (dec 032 item 5)',
                    total_seconds='Total task wall seconds distribution',
                    test_run_share='Agent test time share distribution', test_runs_per_task='Test request count distribution',
                    empty_patch_count='Blank patches', test_files_edited_count='Tasks editing protected/test files',
                    stray_files_count='Tasks adding stray files', test_files_edited_files='Total protected/test paths',
                    stray_files_files='Total stray paths', legacy_projection_decision='Legacy total-wall/cap projection check',
                    projected_minutes='p90 total seconds times 125 plus vLLM, in minutes',
                    cap_worst_case_minutes='Configured cap times 125 plus 30 minutes', cap_minutes='Configured agent cap',
                    artifact_errors='Raw artifact write failures (diagnostic; rows unaffected)',
                    missing_task_ids='Header task IDs absent from task rows', done_present='Journal contains _done', stopped='Journal stop reasons'),
                tasks=tasks, gate=gate, probes=probes, n_complete_no_error=complete,
                decision_note='legacy_projection_decision is the legacy total-wall/cap projection, NOT the gate (dec 032 item 5)',
                provenance={k: header.get(k) for k in ('git_sha', 'bundle_sha256', 'agent_yaml_sha256', 'gpu_names',
                    'gpu_count', 'caps', 'created_utc', 'concurrency', 'mcp_import_ok')},
                agent_outcome_counts=dict(Counter(str(t['agent_outcome']) for t in tasks)),
                setup_failed_count=sum(bool(t['setup_failed']) for t in tasks),
                editable_failed_count=sum(bool(t['editable_failed']) for t in tasks),
                image_emulation_seconds=distribution(measured('image_emulation_seconds')),
                phase1_minus_image_seconds=distribution(measured('phase1_minus_image_seconds')),
                setup_py_emulation_seconds=distribution(measured('setup_py_emulation_seconds')),
                stockpath_phase1_seconds=distribution(measured('stockpath_phase1_seconds')),
                h1_composite_seconds=distribution(measured('h1_composite_seconds')),
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
                legacy_projection_decision='PASS' if timing_minutes is not None and cap_minutes is not None and timing_minutes <= 660 and cap_minutes <= 660 else 'FAIL',
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
    parser.add_argument('--gate-mode', choices=('total', 'stock-path'), default='total')
    args = parser.parse_args()
    summary = summarize(args.timing_jsonl, gate_max_phase1=args.gate_max_phase1,
                        gate_mean_phase1=args.gate_mean_phase1,
                        gate_vllm_seconds=args.gate_vllm_seconds,
                        gate_min_nonempty=args.gate_min_nonempty, gate_mode=args.gate_mode)
    args.output.write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
