"""Plan 011 CPU diagnosis (dec 081 item 5 / dec 089 item 6): per-row tally of empties on a run dir.
Usage: python3 eval/plan011_empty_diag.py <run_dir> <classifier_json>   (prints counts only, no task text)."""
import json, sys, collections
run, clf = sys.argv[1], sys.argv[2]
C = {r['instance_id']: r for r in json.load(open(clf))['rows']}
tally = collections.Counter(); rows = []
for iid, c in sorted(C.items()):
    try:
        t = json.load(open(f'{run}/runs/{iid}/trace.json')); r = json.load(open(f'{run}/runs/{iid}/result.json'))
    except FileNotFoundError:
        tally['missing'] += 1; continue
    calls = []
    for e in t['entries']:
        if e['type'] == 'tool_call': calls.append([e['tool'], e.get('args') or {}, None])
        elif e['type'] == 'tool_response' and calls: calls[-1][2] = str(e.get('result'))[:300].lower()
    eds = [c for c in calls if c[0] in ('edit_file', 'write_file')]
    ed_err = sum(1 for c in eds if 'error' in (c[2] or ''))
    malformed = sum(1 for c in eds if c[0] == 'edit_file' and ('old_string' not in c[1] or 'new_string' not in c[1]))
    empty = not (r.get('agent_patch') or '').strip()
    first_edit = next((k + 1 for k, c in enumerate(calls) if c[0] in ('edit_file', 'write_file')), None)
    cls = ('resolved' if r['resolved'] else
           'empty_timeout' if empty and c['agent_end'] == 'timeout' else
           'empty_never_edited' if empty and not eds else
           'empty_edit_failed' if empty else
           'patch_timeout' if c['agent_end'] == 'timeout' else 'patch_wrong')
    tally[cls] += 1; tally['malformed_edit_calls'] += malformed; tally['edit_errors'] += ed_err
    rows.append(dict(id=iid, cls=cls, end=c['agent_end'], calls=len(calls), edits=len(eds), edit_err=ed_err,
                     malformed=malformed, first_edit_call=first_edit, dur_s=round(r['duration_seconds'])))
print(json.dumps(dict(run=run, classifier=clf, counts=dict(tally), rows=rows), indent=1))
