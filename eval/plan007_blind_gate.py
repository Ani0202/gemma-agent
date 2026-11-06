#!/usr/bin/env python3
"""Plan 007 blind gate (dec 065 items 2-3; dec 066 item 1 one-pass review folded).

Prints ONLY these lines (whitelist):
  vllm_up y|n
  rows <n> (expected <m>)
  rows_parse y|n
  wall <ordinal> <instance_id> agent=<s> verification=<s> total=<s>   (one per row; id omitted if it fails validation)
  max_total <s> seed_max_ceil <int>   |   max_total NA
  h_count <n>
  mechanical_gate HOLD|FAIL
Never prints PASS/FAIL/resolved values, agent outcome classes, H-row ids, error text, diagnostics or patches.
Any unexpected error ends in 'mechanical_gate FAIL' with no traceback. Exit 0 on HOLD, 3 on FAIL, 2 on usage/sha.

Usage: plan007_blind_gate.py TIMING_JSONL CLASSIFIER_PY EXPECTED_SHA256 EXPECTED_ROWS
"""
import hashlib
import importlib.util
import json
import math
import os
import re
import sys

KAGGLE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kaggle')  # pinned classifier imports agent_timing
ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.\-]{0,199}$')


def load_classifier(path, expected_sha):
    data = open(path, 'rb').read()
    sha = hashlib.sha256(data).hexdigest()
    if sha != expected_sha:
        print('classifier sha mismatch')
        sys.exit(2)
    sys.path.insert(0, KAGGLE_DIR)
    spec = importlib.util.spec_from_file_location('pinned_classifier', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.classify


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def evaluate(path, classify, expected_rows):
    """Returns (lines, gate_bool). Raises on anything unexpected (caller fails closed)."""
    parse_ok, rows, vllm_up = True, [], False
    with open(path, encoding='utf-8', errors='strict') as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                parse_ok = False
                continue
            if not isinstance(rec, dict):
                parse_ok = False
                continue
            if '_vllm' in rec:
                v = rec['_vllm']
                s = v.get('startup_seconds') if isinstance(v, dict) else None
                vllm_up = vllm_up or (_num(s) and s > 0)
            if 'instance_id' in rec:
                rows.append(rec)
    ids = [r['instance_id'] for r in rows]
    ids_ok = all(isinstance(i, str) and ID_RE.match(i) for i in ids)
    dup_free = ids_ok and len(ids) == len(set(ids))
    h_count, walls_ok = 0, True
    out_walls, totals = [], []
    for n, r in enumerate(rows, 1):
        try:
            res = classify(r)
            if not isinstance(res, dict) or res.get('h') is not None:
                h_count += 1
        except Exception:
            h_count += 1  # fail closed: unclassifiable row counts as H
        w = r.get('wall_seconds')
        w = w if isinstance(w, dict) else {}
        a, v, t = w.get('agent'), w.get('verification'), w.get('total')
        if not _num(t):
            walls_ok = False
        else:
            totals.append(t)
        fmt = lambda x: f'{x:.1f}' if _num(x) else 'NA'
        iid = r['instance_id'] if (isinstance(r['instance_id'], str) and ID_RE.match(r['instance_id'])) else '?'
        out_walls.append(f'wall {n} {iid} agent={fmt(a)} verification={fmt(v)} total={fmt(t)}')
    lines = [f'vllm_up {"y" if vllm_up else "n"}',
             f'rows {len(rows)} (expected {expected_rows})',
             f'rows_parse {"y" if parse_ok else "n"}'] + out_walls
    lines.append(f'max_total {max(totals):.1f} seed_max_ceil {math.ceil(max(totals))}' if totals else 'max_total NA')
    lines.append(f'h_count {h_count}')
    gate = (vllm_up and parse_ok and ids_ok and dup_free and walls_ok and h_count == 0
            and len(rows) == expected_rows and expected_rows > 0)
    return lines, gate


def main(argv):
    if len(argv) != 5:
        print('usage: plan007_blind_gate.py TIMING_JSONL CLASSIFIER_PY EXPECTED_SHA256 EXPECTED_ROWS')
        return 2
    path, cls_path, expected_sha, exp = argv[1:5]
    if not re.fullmatch(r'[1-9][0-9]{0,3}', exp):
        print('usage: EXPECTED_ROWS must be a positive integer')
        return 2
    classify = load_classifier(cls_path, expected_sha)
    try:
        lines, gate = evaluate(path, classify, int(exp))
    except BaseException:  # noqa: BLE001 - fail closed, never print the exception (could carry row content)
        print('mechanical_gate FAIL')
        return 3
    for ln in lines:
        print(ln)
    print(f'mechanical_gate {"HOLD" if gate else "FAIL"}')
    return 0 if gate else 3


if __name__ == '__main__':
    sys.exit(main(sys.argv))
