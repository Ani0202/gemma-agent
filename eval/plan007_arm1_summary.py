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
from thinking_bound import task as thinking_task  # noqa: E402

PARTS = [
    ('smoke', 'runs/31b-v009-p7a1-smoke/timing.jsonl',
     'results/plan007_arm1_smoke_d4cdf0f0.json', 'results/plan007_arm1_smoke_a208a023.json'),
    ('main', 'runs/31b-v009-p7a1-main/timing.jsonl',
     'results/plan007_arm1_main_d4cdf0f0.json', 'results/plan007_arm1_main_a208a023.json'),
]
ARM_IDS = 'eval/plans/007-arm1-ids.txt'
SCREENED_IDS = 'eval/plans/004-gpu-retime-ids.txt'  # the 8 plan-005/006 screen ids (tuned-on), plan 006 l.3
META_KEYS = ({'_schema'}, {'_vllm'}, {'_done'})  # recognized non-row records (first key set must contain these)
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
        elif not any(m <= set(r) for m in META_KEYS):
            raise AssertionError(f'unrecognized non-row record in {path}: keys {sorted(r)[:8]}')
    ids = [r['instance_id'] for r in out]
    assert len(ids) == len(set(ids)), f'duplicate instance_id rows in {path}'
    return out


def unique_map(rows, what):
    ids = [r['instance_id'] for r in rows]
    assert len(ids) == len(set(ids)), f'duplicate classifier rows in {what}'
    return {r['instance_id']: r for r in rows}


def ids_file(path):
    return [ln.strip() for ln in Path(path).read_text().splitlines()
            if ln.strip() and not ln.lstrip().startswith('#')]


def keys_of_max(d):
    """(tool, args) key of the first longest identical run (same key as identical_runs)."""
    best, cur, prev = (0, None), 0, object()
    for e in d.get('entries') or []:
        if e.get('type') != 'tool_call':
            continue
        key = (e.get('tool'), json.dumps(e.get('args', e.get('arguments')), sort_keys=True))
        cur = cur + 1 if key == prev else 1
        prev = key
        if cur > best[0]:
            best = (cur, key)
    return [best[1]] if best[1] else []


def identical_runs(trace_path):
    """Dec 060 metric: runs of consecutive tool_call entries with the same tool + byte-identical args
    (plan005_armE_compare.max_identical_run key). Returns max run, number of runs >= 3 / >= 5, and
    total repeated calls = sum over runs of (length - 1)."""
    d = json.loads(Path(trace_path).read_text())
    lens, cur, prev = [], 0, object()
    for e in d.get('entries') or []:
        if e.get('type') != 'tool_call':
            continue
        key = (e.get('tool'), json.dumps(e.get('args', e.get('arguments')), sort_keys=True))
        if key == prev:
            cur += 1
        else:
            if cur:
                lens.append(cur)
            cur = 1
        prev = key
    if cur:
        lens.append(cur)
    tools = [k[0] for k in keys_of_max(d)]
    return dict(max_run=max(lens, default=0), max_run_tool=tools[0] if tools else None, runs_ge3=sum(x >= 3 for x in lens),
                runs_ge5=sum(x >= 5 for x in lens), repeated_calls=sum(x - 1 for x in lens))


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
        d4rows = unique_map(d4['rows'], d4path)
        a2rows = unique_map(a2['rows'], a2path)
        assert len(d4['rows']) == len(a2['rows']) == len(trows)
        assert set(d4rows) == set(a2rows) == {r['instance_id'] for r in trows}
        assert len(d4rows) == len(trows)
        for t in trows:
            c = d4rows[t['instance_id']]
            assert_paired(c, t)
            assert_paired(a2rows[t['instance_id']], t)
            rows.append((part, t, c, a2rows[t['instance_id']]))
        inputs.append(dict(part=part, timing=tpath, timing_sha256=sha(tpath),
                           d4cdf0f0=d4path, a208a023=a2path, n=len(trows)))

    order = ids_file(ARM_IDS)
    got = [t['instance_id'] for _, t, _, _ in rows]
    assert got == order, 'row order/ids differ from the fixed arm-1 order'
    n = len(rows)

    def res(t):
        return t.get('resolved') is True

    def is_h(c):
        return c['h'] is not None

    ep = {t['instance_id'] for _, t, c, _ in rows if is_h(c) and is_h_verify_empty_patch(c, t)}

    def strip_known_diag(c):
        # dec 069 item 1 line (d'): the literal predicate applied to a COPY whose reasons omit 'known_diag:*' flags
        # (plan l.51: a flag, never gating). is_h_verify_empty_patch itself is unchanged.
        return dict(c, reasons=[x for x in c['reasons'] if not str(x).startswith('known_diag:')])

    ep_prime = {t['instance_id'] for _, t, c, _ in rows if is_h(c) and is_h_verify_empty_patch(strip_known_diag(c), t)}
    assert ep <= ep_prime
    non_h_but_ep_prime = [t for _, t, c, _ in rows if not is_h(c) or t['instance_id'] in ep_prime]
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

    screened = ids_file(SCREENED_IDS)
    assert len(screened) == len(set(screened)) == 8 and set(screened) <= set(order)
    unscreened = [t for _, t, _, _ in rows if t['instance_id'] not in set(screened)]
    assert len(unscreened) == n - 8

    run_dir = {part: str(Path(tp).parent) for part, tp, _, _ in PARTS}
    rep_rows, th_rows = [], []
    for p, t, _, _ in rows:
        tr = Path(run_dir[p]) / 'runs' / t['instance_id'] / 'trace.json'
        assert tr.is_file(), f'missing trace for {t["instance_id"]}'
        rep_rows.append(dict(instance_id=t['instance_id'], **identical_runs(tr)))
        th = thinking_task(str(tr))
        th_rows.append(dict(instance_id=t['instance_id'], thinking_blocks=th['thinking_blocks'],
                            max_thinking_chars=th['max_thinking_chars'],
                            total_thinking_chars=sum(len(e.get('content') or '') for e in
                                                     json.loads(tr.read_text()).get('entries') or []
                                                     if e.get('author') == 'swe_baseline_agent'
                                                     and e.get('type') == 'thinking')))

    out = {
        '_schema': 'plan007_arm1_summary/v2',
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
        'd_prime_sens_excl_h_except_empty_patch_ignoring_known_diag': dict(
            source='dec 069 item 1 (POST-HOC, plan 007 Addendum C); line (d) above stays literal',
            h_verify_empty_patch_ids_ignoring_known_diag=sorted(ep_prime),
            resolved=rate(sum(res(t) for t in non_h_but_ep_prime), len(non_h_but_ep_prime))),
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
                                literal_verdict='INVALID' if sum(is_h(c) for _, _, c, _ in rows) >= 5 else 'VALID',
                                ruling='VALID by Director ruling dec 069 (POST-HOC; plan 007 Addendum C): all H rows are '
                                       'empty-patch (FAIL in any env), so not env-induced false negatives of the primary'),
        'unscreened_25': dict(ids_file=SCREENED_IDS, note='dev minus the 8 plan-005/006 screen ids (tuned-on); descriptive',
                              resolved=rate(sum(res(t) for t in unscreened), len(unscreened)),
                              screened_8_resolved=rate(sum(res(t) for _, t, _, _ in rows
                                                           if t['instance_id'] in set(screened)), 8)),
        'dec060_identical_runs': dict(
            definition='consecutive tool_call entries, same tool + byte-identical args (sort_keys JSON); '
                       'repeated_calls = sum over runs of (len - 1)',
            tasks_run_ge3=sum(r['max_run'] >= 3 for r in rep_rows),
            tasks_run_ge5=sum(r['max_run'] >= 5 for r in rep_rows),
            max_run_max=max(r['max_run'] for r in rep_rows),
            total_repeated_calls=sum(r['repeated_calls'] for r in rep_rows),
            max_run_tool_tasks_ge5=dict(Counter(r['max_run_tool'] for r in rep_rows if r['max_run'] >= 5)),
            empty_patch_and_run_ge5=sum(r['max_run'] >= 5 for r in rep_rows
                                        if r['instance_id'] in {t['instance_id'] for _, t in empty}),
            rows=rep_rows),
        'dec062_thinking_blocks': dict(
            definition='root (swe_baseline_agent) thinking entries with non-empty content (eval/thinking_bound.py)',
            tasks_with_blocks=sum(r['thinking_blocks'] > 0 for r in th_rows),
            total_blocks=sum(r['thinking_blocks'] for r in th_rows),
            total_chars=sum(r['total_thinking_chars'] for r in th_rows), rows=th_rows),
    }
    Path(argv[1]).write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps({k: out[k] for k in ('a_primary', 'b_d4cdf0f0_counts', 'c_sens_excl_all_h',
                                          'd_sens_excl_h_except_empty_patch',
                                          'd_prime_sens_excl_h_except_empty_patch_ignoring_known_diag', 'invalidity_rule')}, indent=1))
    hp = out['headline_empty_patch']
    print('empty_patch', hp['all'], 'timeout', hp['timeout'], 'non_timeout', hp['non_timeout'],
          'submit_called', hp['empty_with_submit_patch_called'])
    print('secondary', json.dumps(out['secondary']))
    print('unscreened_25', json.dumps(out['unscreened_25']))
    print('dec060', json.dumps({k: v for k, v in out['dec060_identical_runs'].items() if k not in ('rows', 'definition')}))
    print('dec062', json.dumps({k: v for k, v in out['dec062_thinking_blocks'].items() if k not in ('rows', 'definition')}))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
