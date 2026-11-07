#!/usr/bin/env python3
"""Plan 008 arm-2 summary: the plan-007 arm-1 summary code applied to the arm-2 run, plus PRIMARY pairing.

Reuses eval/plan007_arm1_summary.py unchanged (same resolved rule, same classifiers, same empty / identical-run /
safety code) by swapping its PARTS to the single arm-2 session, then rewrites the arm-1-specific header strings and
adds the plan 008 PRIMARY (paired resolved discordants vs arm 1, exact two-sided sign test) and the SAFETY wall rule.
Guard metrics (mechanism 1/2, submitted-without-test) come from eval/plan008_metrics.py (results/plan008_arm2.json).
Counts and ids only; no task text.

usage: plan008_arm2_summary.py OUT_JSON
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan007_arm1_summary as base  # noqa: E402

ARM2_RUN = 'runs/31b-v011-p8b-arm2/timing.jsonl'
ARM1_RUNS = ['runs/31b-v009-p7a1-smoke/timing.jsonl', 'runs/31b-v009-p7a1-main/timing.jsonl']
ARM1_TOTAL_WALL_P90 = 796.8  # plan 008 SAFETY: arm-1 total_wall p90; rule p90 <= 1.10 x this
CAP_SECONDS = 3.5 * 60


def sign_test_two_sided(a, b):
    n = a + b
    if n == 0:
        return 1.0
    k = min(a, b)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def resolved_map(paths):
    out = {}
    for p in paths:
        for t in base.load_rows(p):
            assert t['instance_id'] not in out, f'duplicate {t["instance_id"]}'
            out[t['instance_id']] = t.get('resolved') is True
    return out


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    base.PARTS = [('arm2', ARM2_RUN, 'results/plan008_arm2_d4cdf0f0.json', 'results/plan008_arm2_a208a023.json')]
    rc = base.main(argv)
    if rc:
        return rc
    out = json.loads(Path(argv[1]).read_text())
    out['_schema'] = 'plan008_arm2_summary/v1 (body = plan007_arm1_summary/v2 layout)'
    h = out['header']
    h['arm'] = '31b-v011-p8b (v009 + prompt-level repeat/empty guards; dist/31b-v011.zip 4f5b078a...)'
    h['kernel_code_sha'] = 'gemma-31b-passrate v3 pushed from main cefb420; eval/kaggle kernel files == 078f4ea except classify_rows.py'
    h['fastapi_hint_caveat'] = 'v011 descends from v009/v006: no repo-named hint added (dec 057)'
    h['wrapper_script_sha256'] = base.sha(__file__)
    h['wrapper_note'] = 'summary_script_sha256 = the reused plan-007 arm-1 summary code, run with PARTS = arm-2 session'
    inv = out['invalidity_rule']
    inv['text'] = 'plan 007 rule reused descriptively (H rows >= 5 of 33); arm-1 VALID ruling (dec 069) basis: all H rows empty-patch'
    inv.pop('ruling', None)

    a1 = resolved_map(ARM1_RUNS)
    a2 = resolved_map([ARM2_RUN])
    order = base.ids_file(base.ARM_IDS)
    assert set(a1) == set(a2) == set(order) and len(order) == 33
    a_only = sorted(i for i in order if a2[i] and not a1[i])   # arm 2 resolved, arm 1 not
    b_only = sorted(i for i in order if a1[i] and not a2[i])
    both = sorted(i for i in order if a1[i] and a2[i])
    k2 = sum(a2.values())
    out['plan008_primary'] = dict(
        definition='resolved = timing row resolved is True (same rule as arm-1 PRIMARY 4/33); A = arm 2, B = arm 1',
        arm1_resolved=sum(a1.values()), arm2_resolved=k2, n=33,
        arm2_wilson95=base.wilson(k2, 33), arm1_wilson95=base.wilson(sum(a1.values()), 33),
        a_only=len(a_only), b_only=len(b_only), both=len(both), a_only_ids=a_only, b_only_ids=b_only,
        sign_test_two_sided_p=sign_test_two_sided(len(a_only), len(b_only)),
        pass_delta_ge0=(len(b_only) - len(a_only)) <= 0)
    sec = out['secondary']
    p90 = sec['total_wall_p50_p90_max'][1]
    out['plan008_safety'] = dict(
        test_files_edited_rows=sec['test_files_edited_rows'], stray_files_rows=sec['stray_files_rows'],
        agent_clock_max=sec['agent_clock_max'], cap_seconds=CAP_SECONDS,
        total_wall_p90=p90, total_wall_p90_limit=round(1.10 * ARM1_TOTAL_WALL_P90, 2),
        met=dict(test_edits=sec['test_files_edited_rows'] == 0, stray=sec['stray_files_rows'] == 0,
                 agent_clock=(sec['agent_clock_max'] or 0) <= CAP_SECONDS,
                 total_wall_p90=p90 is not None and p90 <= 1.10 * ARM1_TOTAL_WALL_P90),
        note='submitted-without-test rule (<= arm-1 + 3) is in results/plan008_arm2.json (plan008_metrics.py)')
    Path(argv[1]).write_text(json.dumps(out, indent=1) + '\n')
    print('plan008_primary', json.dumps({k: v for k, v in out['plan008_primary'].items() if not k.endswith('_ids')}))
    print('plan008_safety', json.dumps(out['plan008_safety']))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
