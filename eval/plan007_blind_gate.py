#!/usr/bin/env python3
"""Plan 007 blind gate (dec 065 items 2-3).

Prints ONLY: vLLM up (y/n), row count, rows parse (y/n), per-task wall seconds (agent/verification/total),
and the COUNT of H rows under a pinned classifier file (sha256 checked). Never prints PASS/FAIL/resolved
values, agent outcome classes, H-row ids, error text or patches.

Usage: plan007_blind_gate.py TIMING_JSONL CLASSIFIER_PY EXPECTED_SHA256 [EXPECTED_ROWS]
"""
import hashlib
import importlib.util
import json
import math
import os
import sys

KAGGLE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kaggle')  # pinned classifier imports agent_timing


def load_classifier(path, expected_sha):
    data = open(path, 'rb').read()
    sha = hashlib.sha256(data).hexdigest()
    if sha != expected_sha:
        sys.exit(f'classifier sha mismatch: {sha} != {expected_sha}')
    sys.path.insert(0, KAGGLE_DIR)
    spec = importlib.util.spec_from_file_location('pinned_classifier', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.classify, sha


def main():
    if len(sys.argv) not in (4, 5):
        sys.exit(__doc__)
    path, cls_path, expected_sha = sys.argv[1:4]
    expected_rows = int(sys.argv[4]) if len(sys.argv) == 5 else None
    classify, sha = load_classifier(cls_path, expected_sha)
    parse_ok, rows, vllm_up, ids = True, [], False, []
    for n, line in enumerate(open(path), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            parse_ok = False
            print(f'line {n}: JSON parse error')
            continue
        if not isinstance(rec, dict):
            parse_ok = False
            print(f'line {n}: not an object')
            continue
        if '_vllm' in rec:
            s = (rec['_vllm'] or {}).get('startup_seconds') if isinstance(rec['_vllm'], dict) else None
            vllm_up = vllm_up or (isinstance(s, (int, float)) and math.isfinite(s) and s > 0)
        if 'instance_id' in rec:
            rows.append(rec)
            ids.append(rec['instance_id'])
    h_count, cls_errors = 0, 0
    walls = []
    for r in rows:
        try:
            if classify(r).get('h') is not None:
                h_count += 1
        except Exception:
            cls_errors += 1  # a row the classifier cannot handle counts as H (fail closed)
            h_count += 1
        w = r.get('wall_seconds') if isinstance(r.get('wall_seconds'), dict) else {}
        walls.append((r['instance_id'], w.get('agent'), w.get('verification'), w.get('total')))
    print(f'classifier_sha256 {sha}')
    print(f'vllm_up {"y" if vllm_up else "n"}')
    print(f'rows {len(rows)}' + (f' (expected {expected_rows})' if expected_rows is not None else ''))
    print(f'rows_parse {"y" if parse_ok else "n"}')
    print(f'duplicate_ids {len(ids) - len(set(ids))}')
    for iid, a, v, t in walls:
        fmt = lambda x: f'{x:.1f}' if isinstance(x, (int, float)) else 'NA'
        print(f'wall {iid} agent={fmt(a)} verification={fmt(v)} total={fmt(t)}')
    totals = [t for _, _, _, t in walls if isinstance(t, (int, float))]
    print(f'max_total {max(totals):.1f} seed_max_ceil {math.ceil(max(totals))}' if totals else 'max_total NA')
    print(f'h_count {h_count} (classifier exceptions counted as H: {cls_errors})')
    gate = vllm_up and parse_ok and h_count == 0 and len(ids) == len(set(ids)) and \
        (expected_rows is None or len(rows) == expected_rows)
    print(f'mechanical_gate {"HOLD" if gate else "FAIL"}')


if __name__ == '__main__':
    main()
