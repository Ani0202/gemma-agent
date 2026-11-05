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


def summarize(path):
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
    shares = distribution(numbers([r['test_run']['share_of_agent_seconds'] for r in rows if r['test_run']['share_of_agent_seconds'] is not None]))
    runs = distribution(numbers([r['test_run']['n'] for r in rows]))
    caps = header.get('caps') or {}
    cap = caps.get('max_time_minutes')
    numbers([v for v in (startup, cap) if v is not None])
    timing_minutes = totals['p90'] * 125 / 60 + startup / 60 if totals['p90'] is not None and startup is not None else None
    cap_minutes = cap * 125 + 30 if cap is not None else None
    return dict(_schema='kaggle_timing_summary_v1', n=len(rows), vllm_startup_seconds=startup,
                total_seconds=totals, test_run_share=shares, test_runs_per_task=runs,
                empty_patch_count=sum(bool(r['empty_patch']) for r in rows),
                test_files_edited_count=sum(bool(r['test_files_edited']) for r in rows),
                stray_files_count=sum(bool(r['stray_files']) for r in rows),
                test_files_edited_files=sum(len(r['test_files_edited']) for r in rows),
                stray_files_files=sum(len(r['stray_files']) for r in rows),
                decision='PASS' if timing_minutes is not None and cap_minutes is not None and timing_minutes <= 660 and cap_minutes <= 660 else 'FAIL',
                projected_minutes=timing_minutes, cap_worst_case_minutes=cap_minutes,
                cap_minutes=cap, missing_task_ids=[iid for iid in header['task_ids'] if iid not in ids],
                done_present=done is not None, stopped=stopped)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('timing_jsonl', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    summary = summarize(args.timing_jsonl)
    args.output.write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
