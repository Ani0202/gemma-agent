#!/usr/bin/env python3
"""Plan 007 arm-1 summary (Addendum B layout a-e + empty-patch headline).

Inputs: smoke + main kernel timing.jsonl (sealed) and their d4cdf0f0 / a208a023 class files.
Output: one schema-headed JSON. Counts only; no task text. Calls assert_paired on every row
before is_h_verify_empty_patch (Addendum B.1).

usage: plan007_arm1_summary.py OUT_JSON
"""
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plan007_report import assert_paired, is_h_verify_empty_patch  # noqa: E402

PARTS = [
    ('smoke', 'runs/31b-v009-p7a1-smoke/timing.jsonl',
     'results/plan007_arm1_smoke_d4cdf0f0.json', 'results/plan007_arm1_smoke_a208a023.json'),
    ('main', 'runs/31b-v009-p7a1-main/timing.jsonl',
     'results/plan007_arm1_main_d4cdf0f0.json', 'results/plan007_arm1_main_a208a023.json'),
]
ARM_IDS = 'eval/plans/007-arm1-ids.txt'
SCREENED_NOTE = 'plan-005/006 screen ids (tuned-on): see eval/plans/007.md Metrics'
D4_SHA = 'd4cdf0f012659c685789add3b8e5687362ba01673344bdc1f1bad97f81d8ae5e'
A2_SHA = 'a208a02343b43556e990271b8757044fdf51515f27ff9a067cd3af14c1fd4e6b'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def wilson(k, n, z=1.959963984540054):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def rate(k, n):
    return dict(k=k, n=n, rate=round(k / n, 4) if n else None, wilson95=wilson(k, n))


def pct(vals, q):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return None
    i = (len(vals) - 1) * q
    lo, hi = math.floor(i), math.ceil(i)
    return round(vals[lo] + (vals[hi] - vals[lo]) * (i - lo), 1)


def load_rows(path):
    out = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if 'instance_id' in r:
            out.append(r)
    return out


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    rows, inputs = [], []
    for part, tpath, d4path, a2path in PARTS:
        d4 = json.loads(Path(d4path).read_text())
        a2 = json.loads(Path(a2path).read_text())
        assert d4['classifier_sha256'] == D4_SHA and a2['classifier_sha256'] == A2_SHA
        assert d4['input_sha256'] == sha(tpath) == a2['input_sha256']
        trows = load_rows(tpath)
        d4rows = {r['instance_id']: r for r in d4['rows']}
        a2rows = {r['instance_id']: r for r in a2['rows']}
        assert set(d4rows) == set(a2rows) == {r['instance_id'] for r in trows}
        assert len(d4rows) == len(trows)
        for t in trows:
            c = d4rows[t['instance_id']]
            assert_paired(c, t)
            assert_paired(a2rows[t['instance_id']], t)
            rows.append((part, t, c, a2rows[t['instance_id']]))
        inputs.append(dict(part=part, timing=tpath, timing_sha256=sha(tpath),
                           d4cdf0f0=d4path, a208a023=a2path, n=len(trows)))

    order = [ln.strip() for ln in Path(ARM_IDS).read_text().splitlines()
             if ln.strip() and not ln.lstrip().startswith('#')]
    got = [t['instance_id'] for _, t, _, _ in rows]
    assert got == order, 'row order/ids differ from the fixed arm-1 order'
    n = len(rows)

    def res(t):
        return t.get('resolved') is True

    def is_h(c):
        return c['h'] is not None

    ep = {t['instance_id'] for _, t, c, _ in rows if is_h(c) and is_h_verify_empty_patch(c, t)}
    per_repo = {}
    for repo in sorted({t['repo'] for _, t, _, _ in rows}):
        sub = [t for _, t, _, _ in rows if t['repo'] == repo]
        per_repo[repo] = rate(sum(res(t) for t in sub), len(sub))

    non_h = [t for _, t, c, _ in rows if not is_h(c)]
    non_h_but_ep = [t for _, t, c, _ in rows if not is_h(c) or t['instance_id'] in ep]
    h_rows = [dict(instance_id=t['instance_id'], part=p, h=c['h'], reasons=c['reasons'],
                   h_verify_empty_patch=t['instance_id'] in ep,
                   verified_patch_bytes=t.get('verified_patch_bytes'), exit_code=t.get('exit_code'),
                   patch_submitted=t.get('patch_submitted'))
              for p, t, c, _ in rows if is_h(c)]

    def timeout(t):
        return bool(t.get('timed_out')) or bool(t.get('agent_timeout_fired'))

    empty = [(p, t) for p, t, _, _ in rows if t.get('verified_patch_bytes') == 0]
    empty_rows = [dict(instance_id=t['instance_id'], timeout=timeout(t), llm_turns=t.get('llm_turns'),
                       per_tool=(t.get('tool_calls') or {}).get('per_tool'))
                  for _, t in empty]
    walls = [t.get('wall_seconds') or {} for _, t, _, _ in rows]

    out = {
        '_schema': 'plan007_arm1_summary/v1',
        'header': {
            'arm': '31b-v009-p7a1 (v006 + cap 3.5; dist/31b-v009.zip d38c55c7...)',
            'kernel_code_sha': '078f4ea (pre-fold; dec 065 deviation: smoke+main ran before the rev-5 re-freeze)',
            'governing_classifier_sha256': D4_SHA, 'also_counted_classifier_sha256': A2_SHA,
            'agent_timing_py_sha256': sha('eval/kaggle/agent_timing.py'),
            'report_predicate_sha256': sha('eval/plan007_report.py'),
            'summary_script_sha256': sha(__file__),
            'k': 1, 'env_caveat': 'env agreement with the local gold calibration unmeasured in the kernel path',
            'fastapi_hint_caveat': 'v000-v002 carry the FastAPI hint; this arm (v009 from v006) per dec 057/060 notes',
            'footnote_l239': ('classifier l.239 clause patch_bytes == 0 and code not in (None, -1) flags an empty '
                              'patch with a failing verification exit as contradictory; a false-positive assumption, '
                              'not a kernel defect (dec 068).'),
            'inputs': inputs,
        },
        'n_rows': n,
        'a_primary': dict(resolved=rate(sum(res(t) for _, t, _, _ in rows), n), per_repo=per_repo),
        'b_d4cdf0f0_counts': dict(
            h=dict(Counter(c['h'] for _, _, c, _ in rows if is_h(c))),
            agent=dict(Counter(c['agent'] for _, _, c, _ in rows if c['agent'])),
            known_diag=sum(bool(c['known_diag']) for _, _, c, _ in rows),
            h_total=sum(is_h(c) for _, _, c, _ in rows)),
        'h_rows': h_rows,
        'c_sens_excl_all_h': rate(sum(res(t) for t in non_h), len(non_h)),
        'd_sens_excl_h_except_empty_patch': rate(sum(res(t) for t in non_h_but_ep), len(non_h_but_ep)),
        'e_a208a023_counts': dict(
            h=dict(Counter(a['h'] for _, _, _, a in rows if a['h'])),
            agent=dict(Counter(a['agent'] for _, _, _, a in rows if a['agent'])),
            known_diag=sum(bool(a['known_diag']) for _, _, _, a in rows)),
        'headline_empty_patch': dict(
            all=rate(len(empty), n),
            timeout=sum(r['timeout'] for r in empty_rows),
            non_timeout=sum(not r['timeout'] for r in empty_rows),
            empty_with_submit_patch_called=sum(bool(t.get('patch_submitted')) for _, t in empty),
            rows=empty_rows),
        'secondary': dict(
            timeouts=sum(timeout(t) for _, t, _, _ in rows),
            submit_patch_called=sum(bool(t.get('patch_submitted')) for _, t, _, _ in rows),
            test_files_edited_rows=sum(bool(t.get('test_files_edited')) for _, t, _, _ in rows),
            stray_files_rows=sum(bool(t.get('stray_files')) for _, t, _, _ in rows),
            agent_wall_p50_p90=[pct([w.get('agent') for w in walls], .5), pct([w.get('agent') for w in walls], .9)],
            verification_wall_p50_p90=[pct([w.get('verification') for w in walls], .5),
                                       pct([w.get('verification') for w in walls], .9)],
            total_wall_p50_p90_max=[pct([w.get('total') for w in walls], .5), pct([w.get('total') for w in walls], .9),
                                    pct([w.get('total') for w in walls], 1.0)],
            agent_clock_max=pct([t.get('agent_clock_seconds') for _, t, _, _ in rows], 1.0),
            llm_turns_p50_p90=[pct([t.get('llm_turns') for _, t, _, _ in rows], .5),
                               pct([t.get('llm_turns') for _, t, _, _ in rows], .9)],
            tool_calls_p50=pct([(t.get('tool_calls') or {}).get('total') for _, t, _, _ in rows], .5)),
        'invalidity_rule': dict(text='Arm 1 INVALID iff H rows >= 5 of 33 (eval/plans/007.md Decision rules)',
                                h_total=sum(is_h(c) for _, _, c, _ in rows),
                                literal_verdict='INVALID' if sum(is_h(c) for _, _, c, _ in rows) >= 5 else 'VALID'),
        'note': SCREENED_NOTE,
    }
    Path(argv[1]).write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps({k: out[k] for k in ('a_primary', 'b_d4cdf0f0_counts', 'c_sens_excl_all_h',
                                          'd_sens_excl_h_except_empty_patch', 'invalidity_rule')}, indent=1))
    hp = out['headline_empty_patch']
    print('empty_patch', hp['all'], 'timeout', hp['timeout'], 'non_timeout', hp['non_timeout'],
          'submit_called', hp['empty_with_submit_patch_called'])
    print('secondary', json.dumps(out['secondary']))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
