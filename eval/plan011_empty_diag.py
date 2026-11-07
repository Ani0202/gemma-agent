"""Plan 011 CPU diagnosis (dec 081 item 5 / dec 089 item 6 / dec 090 item 2): per-row tally of empty patches.

v2 (dec 090 item 2, fixes codex review 20261107T121430 non-blocking 1-3):
  - empty = agent_patch is None or exactly zero bytes (same as plan007_arm1_summary.py verified_patch_bytes == 0).
  - edit success = tool_response for edit_file/write_file parses as a JSON object with status == "ok".
    empty_edit_failed now requires >= 1 edit attempt and 0 successful edits; an empty row with a successful
    edit is its own class empty_edited_ok.
  - inventory: classifier ids must be unique and equal the --ids file(s); every trace/result must exist,
    else exit 2 (no counts printed).
  - rule tally (dec 090 item 2): target rows = empty AND (edit_failed OR call_exhausted), whatever the
    agent_end label (overlap rows count, as in report 023). call_exhausted = tool calls >= --max-tool-calls
    OR any get_status response with tool_calls_remaining == 0.

Usage (prints counts and per-row metadata only, no task text):
  python3 eval/plan011_empty_diag.py --max-tool-calls 40 \
      --pair RUN_DIR CLASSIFIER_JSON IDS_FILE [--pair ...]
"""
import argparse, collections, json, os, sys

EDIT_TOOLS = ('edit_file', 'write_file')


def read_ids(path):
    with open(path) as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith('#')]


def parse(s):
    try:
        j = json.loads(s) if isinstance(s, str) else s
    except (TypeError, ValueError):
        return None
    return j if isinstance(j, dict) else None


def diag_row(run, iid, c, max_calls):
    t = json.load(open(f'{run}/runs/{iid}/trace.json'))
    r = json.load(open(f'{run}/runs/{iid}/result.json'))
    calls = []  # [tool, args, parsed_response_or_None]
    for e in t['entries']:
        if e['type'] == 'tool_call':
            calls.append([e['tool'], e.get('args') or {}, None])
        elif e['type'] == 'tool_response' and calls:
            calls[-1][2] = parse(e.get('result'))
    eds = [k for k in calls if k[0] in EDIT_TOOLS]
    ed_ok = sum(1 for k in eds if k[2] is not None and k[2].get('status') == 'ok')
    malformed = sum(1 for k in eds if k[0] == 'edit_file' and ('old_string' not in k[1] or 'new_string' not in k[1]))
    status_zero = any(k[0] == 'get_status' and k[2] is not None and k[2].get('tool_calls_remaining') == 0 for k in calls)
    call_exhausted = len(calls) >= max_calls or status_zero
    patch = r.get('agent_patch')
    empty = patch is None or len(patch.encode('utf-8')) == 0
    edit_failed = bool(eds) and ed_ok == 0
    timeout = c['agent_end'] == 'timeout'
    cls = ('resolved' if r['resolved'] else
           'empty_timeout' if empty and timeout else
           'empty_never_edited' if empty and not eds else
           'empty_edit_failed' if empty and edit_failed else
           'empty_edited_ok' if empty else
           'patch_timeout' if timeout else 'patch_wrong')
    first_edit = next((k + 1 for k, x in enumerate(calls) if x[0] in EDIT_TOOLS), None)
    return dict(id=iid, cls=cls, end=c['agent_end'], calls=len(calls), edits=len(eds), edit_ok=ed_ok,
                edit_err=len(eds) - ed_ok, malformed=malformed, call_exhausted=call_exhausted,
                rule_target=empty and (edit_failed or call_exhausted),
                first_edit_call=first_edit, dur_s=round(r['duration_seconds']))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--pair', nargs=3, action='append', required=True, metavar=('RUN_DIR', 'CLASSIFIER_JSON', 'IDS_FILE'))
    ap.add_argument('--max-tool-calls', type=int, required=True)
    a = ap.parse_args(argv)
    errs, rows, seen = [], [], set()
    for run, clf, idf in a.pair:
        crows = json.load(open(clf))['rows']
        cids = [x['instance_id'] for x in crows]
        exp = read_ids(idf)
        if len(cids) != len(set(cids)):
            errs.append(f'{clf}: duplicate classifier ids')
        if len(exp) != len(set(exp)):
            errs.append(f'{idf}: duplicate expected ids')
        if set(cids) != set(exp):
            errs.append(f'{clf}: ids != {idf} (missing {len(set(exp) - set(cids))}, extra {len(set(cids) - set(exp))})')
        if seen & set(cids):
            errs.append(f'{clf}: ids overlap an earlier --pair')
        seen |= set(cids)
        for iid in cids:
            for fn in ('trace.json', 'result.json'):
                if not os.path.isfile(f'{run}/runs/{iid}/{fn}'):
                    errs.append(f'{run}: missing artifact for one id ({fn})')
        if errs:
            continue
        C = {x['instance_id']: x for x in crows}
        rows += [dict(diag_row(run, iid, C[iid], a.max_tool_calls), run=run) for iid in sorted(C)]
    if errs:
        print('INVENTORY FAIL:\n' + '\n'.join(errs), file=sys.stderr)
        return 2
    tally = collections.Counter(x['cls'] for x in rows)
    extra = dict(n=len(rows), malformed_edit_calls=sum(x['malformed'] for x in rows),
                 edit_errors=sum(x['edit_err'] for x in rows),
                 empty=sum(1 for x in rows if x['cls'].startswith('empty_')),
                 empty_call_exhausted=sum(1 for x in rows if x['cls'].startswith('empty_') and x['call_exhausted']),
                 rule_target=sum(1 for x in rows if x['rule_target']))
    extra['rule_verdict'] = 'PROPOSE_PLAN011' if extra['rule_target'] >= 3 else 'STAY_SHELVED'
    out = dict(script='eval/plan011_empty_diag.py v2', pairs=a.pair, max_tool_calls=a.max_tool_calls,
               counts=dict(tally), summary=extra, rows=rows)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
