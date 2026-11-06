#!/usr/bin/env python3
"""Plan 008 D71.2/D72.2 metrics. CPU/stdlib only; output contains counts, never task text.

Usage: plan008_metrics.py base OUT_JSON | smoke RUN_DIR OUT_JSON
"""
import json
import math
from pathlib import Path
import re
import sys
from collections import defaultdict, deque

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan007_arm1_summary as base

ROOT = 'swe_baseline_agent'
GATE_YAML = Path('bundles/31b/v010/sub_agents/submit_gate.yaml')
TEST = re.compile(r'\bpytest\b|-m\s+unittest\b|\btox\b')
BOUNCE = ('NOT SUBMITTED: no non-test source file is changed. Make your source edit with '
          'edit_file (or a /tmp Python script), confirm it with git diff --stat, then call submit_patch again.')
DEFINITIONS = {
    'mechanism1_empty': 'verified_patch_bytes == 0 (plan007 empty definition)',
    'mechanism2': 'rows with max_run >= 5; root-author tool calls only; same tool and sort_keys JSON args; nested calls excluded before runs',
    'repeated_calls': 'sum(length - 1) over root identical runs',
    'submitted_without_test': 'successful root submit with no prior root run_command matching \\bpytest\\b|-m\\s+unittest\\b|\\btox\\b; no success excluded and counted separately',
    'success': 'first root submit with patch_size and no error, or gate reply starting SUBMITTED',
    'smoke': '008.md D71.2 i-v and D72.2; missing evidence UNVERIFIABLE; overall PASS requires every criterion PASS',
    'gate_descriptives': 'root submit calls; reply-prefix bounces/failures; gate run_command response forced/check_error counts; terminal bounces; internal visibility',
    'untracked_only': 'nonempty patch with diff --git sections all declaring new file mode',
}


def _parsed(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            pass
    return value


def _reply(value):
    """Legacy AgentTool text is JSON {raw: text} (sometimes {result: text})."""
    value = _parsed(value)
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for k in ('raw', 'result'):
            if k in value:
                return _reply(value[k])
    return ''


def _pairs(entries):
    # Legacy trace has no call IDs. FIFO by (author, tool) also isolates nested tools.
    pending, calls = defaultdict(deque), []
    for i, e in enumerate(entries):
        key = (e.get('author'), e.get('tool'))
        if e.get('type') == 'tool_call':
            c = dict(e, entry_index=i, response=None, response_index=None)
            calls.append(c)
            pending[key].append(c)
        elif e.get('type') in ('tool_response', 'tool_result') and pending[key]:
            c = pending[key].popleft()
            c.update(response=e.get('result', ''), response_index=i)
    return calls


def root_tool_calls(entries, root=ROOT):
    """Ordered call dictionaries, enriched with response text and entry/response indices."""
    return [c for c in _pairs(entries) if c.get('author') == root]


def identical_runs_root(entries):
    lens, cur, prev = [], 0, object()
    for c in root_tool_calls(entries):
        key = (c.get('tool'), json.dumps(c.get('args', c.get('arguments')), sort_keys=True))
        if key == prev:
            cur += 1
        else:
            if cur:
                lens.append(cur)
            cur = 1
        prev = key
    if cur:
        lens.append(cur)
    return dict(max_run=max(lens, default=0), runs_ge3=sum(n >= 3 for n in lens),
                runs_ge5=sum(n >= 5 for n in lens), repeated_calls=sum(n - 1 for n in lens))


def _has_error(value):
    value = _parsed(value)
    if isinstance(value, dict):
        if value.get('error') or str(value.get('status', '')).lower() in ('error', 'failed', 'failure'):
            return True
        return any(_has_error(v) for v in value.values())
    if isinstance(value, list):
        return any(_has_error(v) for v in value)
    return False


def _patch_size(value):
    value = _parsed(value)
    if isinstance(value, dict) and not _has_error(value):
        n = value.get('patch_size')
        if type(n) is int and n >= 0:
            return n
    return None


def successful_submit_index(entries):
    for i, c in enumerate(root_tool_calls(entries)):
        if c.get('tool') == 'submit_patch' and (
                _patch_size(c['response']) is not None or _reply(c['response']).startswith('SUBMITTED')):
            return i
    return None


def submitted_without_test(entries):
    index = successful_submit_index(entries)
    if index is None:
        return None
    return not any(c.get('tool') == 'run_command' and TEST.search(_command(c))
                   for c in root_tool_calls(entries)[:index])


def _command(c):
    return (c.get('args', c.get('arguments')) or {}).get('command', '')


def _response_text(value):
    return value if isinstance(value, str) else json.dumps(value)


def gate_descriptives(entries):
    roots = root_tool_calls(entries)
    submits = [(i, c) for i, c in enumerate(roots) if c.get('tool') == 'submit_patch']
    cmds = [c for c in _pairs(entries) if c.get('author') == 'submit_patch' and c.get('tool') == 'run_command']
    return dict(gate_calls=len(submits),
                bounces=sum(_reply(c['response']).startswith('NOT SUBMITTED') for _, c in submits),
                forced=sum('reason=forced' in _response_text(c['response']) for c in cmds),
                check_error=sum('reason=check_error' in _response_text(c['response']) for c in cmds),
                submit_failed=sum(_reply(c['response']).startswith('SUBMIT FAILED') for _, c in submits),
                bounce_no_followup=sum(i == len(roots) - 1 and _reply(c['response']).startswith('NOT SUBMITTED') for i, c in submits),
                gate_run_cmds=[_command(c) for c in cmds],
                gate_internal_visible=any(e.get('author') == 'submit_patch' for e in entries))


def untracked_only(patch_text):
    sections = re.split(r'^diff --git ', patch_text, flags=re.M)[1:]
    return bool(patch_text.strip() and sections) and all(
        re.search(r'^new file mode [0-7]+\s*$', s, re.M) is not None for s in sections)


def _gate_command(path):
    # Read the literal YAML instruction block without a YAML dependency.
    lines = Path(path).read_text().splitlines()
    i = next(i for i, line in enumerate(lines) if '1. Call `run_command` ONCE' in line)
    return next(line[2:] for line in lines[i + 1:] if line.strip())


def _criterion(status, reason):
    return dict(status=status, reason=reason)


def _cap_exempt(row):
    return bool(row.get('agent_timeout_fired') or row.get('timed_out') or row.get('budget_exceeded'))


def smoke_check(row, entries, gate_yaml_path):
    """Return criteria i..v. Reasons are fixed descriptions, never trace/task text."""
    out = {}
    pairs = _pairs(entries)
    roots = root_tool_calls(entries)
    gates = [c for c in roots if c.get('tool') == 'submit_patch']
    desc = gate_descriptives(entries)
    expected = _gate_command(gate_yaml_path)
    failures, missing = [], []
    if not gates:
        out['i'] = _criterion('PASS' if _cap_exempt(row) else 'UNVERIFIABLE',
                              'cap before any gate call; exempt pending cross-task check' if _cap_exempt(row) else 'no gate call observed')
    else:
        if not desc['gate_internal_visible']:
            missing.append('gate internals absent')
        for gate in gates:
            end = gate['response_index']
            if end is None:
                missing.append('gate response absent')
                continue
            children = [c for c in pairs if c.get('author') == 'submit_patch'
                        and gate['entry_index'] < c['entry_index'] < end]
            cmds = [c for c in children if c.get('tool') == 'run_command']
            subs = [c for c in children if c.get('tool') == 'submit_patch']
            if not children:
                missing.append('gate internals absent')
                continue
            if len(cmds) != 1 or _command(cmds[0]) != expected:
                failures.append('gate check command differs or count differs')
            elif cmds[0]['response_index'] is None:
                missing.append('gate check response absent')
            else:
                text = _response_text(cmds[0]['response'])
                need_submit = 'VERDICT=SUBMIT' in text or 'VERDICT=EDIT_FIRST' not in text
                if need_submit and (len(subs) != 1 or subs[0]['entry_index'] <= cmds[0]['response_index']):
                    failures.append('inner submit absent or out of order')
                if not need_submit and subs:
                    failures.append('inner submit after EDIT_FIRST')
            if _reply(gate['response']).startswith('SUBMITTED'):
                if any(e.get('author') == ROOT and e.get('type') != 'tool_response' for e in entries[end + 1:]):
                    failures.append('root model event after successful gate response')
        if row.get('patch_submitted') is not True:
            failures.append('run did not end with patch_submitted true')
        out['i'] = _criterion('FAIL' if failures else 'UNVERIFIABLE' if missing else 'PASS',
                              '; '.join(failures or missing) or 'gate sequence and termination observed')

    sizes = [_patch_size(c['response']) for c in pairs
             if c.get('author') == 'submit_patch' and c.get('tool') == 'submit_patch']
    sizes = [s for s in sizes if s is not None]
    if not sizes and row.get('patch_submitted') is False:
        fallback = row.get('fallback_patch_bytes')
        if fallback is None:
            for e in entries:
                m = re.search(r'Captured unsubmitted working tree modifications as fallback patch \((\d+) bytes\)', e.get('content') or '')
                if m:
                    fallback = int(m[1])
        sizes = [] if fallback is None else [fallback]
    actual = row.get('verified_patch_bytes')
    out['ii'] = _criterion('UNVERIFIABLE' if not sizes or actual is None else
                           'PASS' if len(sizes) == 1 and actual == sizes[0] else 'FAIL',
                           'scored and captured patch sizes agree' if len(sizes) == 1 and actual == sizes[0]
                           else 'patch size evidence missing' if not sizes or actual is None else 'patch sizes differ or multiple captures')

    errors = bool(desc['check_error'] or desc['submit_failed'])
    for key in ('agent_error', 'agent_error_text', 'result_error'):
        err = row.get(key)
        if err and not re.search(r'budget|timeout|timed out', str(err), re.I):
            errors = True
    for e in entries:
        if e.get('author') not in (ROOT, 'submit_patch'):
            continue
        if e.get('type') in ('tool_response', 'tool_result'):
            text = _response_text(e.get('result', ''))
            errors |= _has_error(text) or bool(re.search(r'unknown[ _-]tool|ToolErrorPlugin|compile error|validator error', text, re.I))
    malformed = any(_reply(c['response']) not in ('SUBMITTED', BOUNCE) for c in gates)
    out['iii'] = _criterion('FAIL' if errors or malformed else 'PASS',
                            'error or malformed gate reply observed' if errors or malformed else 'no errors or malformed gate replies observed')
    clock = row.get('agent_clock_seconds')
    valid = type(clock) in (int, float) and math.isfinite(clock) and clock >= 0
    out['iv'] = _criterion('UNVERIFIABLE' if not valid else 'PASS' if clock <= 210 else 'FAIL',
                           'agent clock missing or invalid' if not valid else 'agent clock within 210 seconds' if clock <= 210 else 'agent clock exceeds 210 seconds')
    out['v'] = _criterion('PASS' if desc['bounces'] <= 2 else 'FAIL',
                          'at most two EDIT_FIRST replies' if desc['bounces'] <= 2 else 'more than two EDIT_FIRST replies')
    return out


def _schema(mode, paths):
    return dict(name='plan008_metrics/v1', mode=mode, definitions=DEFINITIONS,
                script_sha256=base.sha(__file__),
                input_shas={str(p): base.sha(p) for p in dict.fromkeys(map(Path, paths))})


def base_metrics():
    rows, paths = [], [base.ARM_IDS, base.__file__, 'eval/plan007_report.py']
    for part, timing, d4path, a2path in base.PARTS:
        d4, a2 = [json.loads(Path(p).read_text()) for p in (d4path, a2path)]
        assert d4['classifier_sha256'] == base.D4_SHA and a2['classifier_sha256'] == base.A2_SHA
        assert d4['input_sha256'] == base.sha(timing) == a2['input_sha256']
        ts = base.load_rows(timing)
        cs, als = base.unique_map(d4['rows'], d4path), base.unique_map(a2['rows'], a2path)
        assert set(cs) == set(als) == {r['instance_id'] for r in ts}
        paths.extend((timing, d4path, a2path))
        for t in ts:
            iid = t['instance_id']
            base.assert_paired(cs[iid], t)
            base.assert_paired(als[iid], t)
            trace = Path(timing).parent / 'runs' / iid / 'trace.json'
            entries = json.loads(trace.read_text())['entries']
            paths.append(trace)
            rep = identical_runs_root(entries)
            rows.append(dict(instance_id=iid, part=part, **rep, mechanism2=rep['max_run'] >= 5,
                             mechanism1_empty=t.get('verified_patch_bytes') == 0,
                             submitted_without_test=submitted_without_test(entries)))
    assert [r['instance_id'] for r in rows] == base.ids_file(base.ARM_IDS)
    totals = dict(mechanism2=sum(r['mechanism2'] for r in rows),
                  mechanism1_empty=sum(r['mechanism1_empty'] for r in rows),
                  submitted_without_test=sum(r['submitted_without_test'] is True for r in rows),
                  count_no_successful_submit=sum(r['submitted_without_test'] is None for r in rows),
                  max_run=max((r['max_run'] for r in rows), default=0),
                  runs_ge3=sum(r['runs_ge3'] for r in rows), runs_ge5=sum(r['runs_ge5'] for r in rows),
                  repeated_calls=sum(r['repeated_calls'] for r in rows))
    assert totals['mechanism2'] == 17, 'arm-1 mechanism2 baseline changed'
    assert totals['mechanism1_empty'] == 12, 'arm-1 empty baseline changed'
    return dict(_schema=_schema('base', paths), n_rows=len(rows), totals=totals, rows=rows)


def smoke_metrics(run_dir):
    timing = Path(run_dir) / 'timing.jsonl'
    paths, rows = [timing, GATE_YAML], []
    for row in base.load_rows(timing):
        trace = Path(run_dir) / 'runs' / row['instance_id'] / 'trace.json'
        paths.append(trace)
        entries = json.loads(trace.read_text())['entries']
        desc = gate_descriptives(entries)
        # Commands are used only for comparison, never serialized (counts-only output).
        desc.pop('gate_run_cmds')
        rows.append(dict(instance_id=row['instance_id'], criteria=smoke_check(row, entries, GATE_YAML), **desc))
    if rows and all(r['gate_calls'] == 0 for r in rows):
        for row in rows:
            row['criteria']['i'] = _criterion('UNVERIFIABLE', 'no task exercised the gate')
    passed = bool(rows) and all(c['status'] == 'PASS' for r in rows for c in r['criteria'].values())
    return dict(_schema=_schema('smoke', paths), n_rows=len(rows), overall='PASS' if passed else 'FAIL', rows=rows)


def main(argv=None):
    argv = sys.argv if argv is None else argv
    if len(argv) == 3 and argv[1] == 'base':
        out = base_metrics()
    elif len(argv) == 4 and argv[1] == 'smoke':
        out = smoke_metrics(argv[2])
    else:
        print(__doc__)
        return 2
    Path(argv[-1]).write_text(json.dumps(out, indent=2) + '\n')
    print(json.dumps(out.get('totals', dict(n_rows=out['n_rows'], overall=out.get('overall')))))
    return 0


if __name__ == '__main__':
    sys.exit(main())
