#!/usr/bin/env python3
"""Plan 008 D73 metrics. CPU/offline only; output contains counts, never task text.

Usage: plan008_metrics.py base OUT_JSON | smoke RUN_DIR OUT_JSON | arm2 RUN_DIR OUT_JSON

Exit: 0 ok, 2 usage, 3 incomplete arm2 inventory, 4 builtin arm2 run holds a non-root
submit_patch response (dec 077 failure-safe; STOP and report). 3/4 write no results.

Smoke loads task.test_files with swegemma.models.load_tasks, as both eval runners do.
Tasks default to data/raw/tasks.jsonl (local) or the Kaggle competition tasks.jsonl;
PLAN008_TASKS_PATH overrides that location for downloaded runs. Missing tasks fail smoke.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from collections import defaultdict, deque

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan007_arm1_summary as base

ROOT = 'swe_baseline_agent'
GATE_YAML = Path('bundles/31b/v010/sub_agents/submit_gate.yaml')
SMOKE_IDS = Path('eval/plans/008-smoke-ids.txt')
ARM2_IDS = Path('eval/plans/007-arm1-ids.txt')
# Authoritative bundle identity = kernel header agent_yaml_sha256 (agent_timing.extract_bundle).
# v011 agent.yaml is byte-identical to v009 (arm 1), so arm-1 runs identify as builtin.
BUNDLE_YAMLS = {'v010': Path('bundles/31b/v010/agent.yaml'), 'v011': Path('bundles/31b/v011/agent.yaml')}
TEST = re.compile(r'\bpytest\b|-m\s+unittest\b|\btox\b')
BOUNCE = ('NOT SUBMITTED: no non-test source file is changed. Make your source edit with '
          'edit_file (or a /tmp Python script), confirm it with git diff --stat, then call submit_patch again.')
DEFINITIONS = {
    'mechanism1_empty': 'verified_patch_bytes == 0 (plan007 empty definition)',
    'mechanism2': 'rows with max_run >= 5; root-author tool calls only; same tool and sort_keys JSON args; nested calls excluded before runs',
    'repeated_calls': 'sum(length - 1) over root identical runs',
    'submitted_without_test': 'PRIMARY total (ship rule, D73.5) = observed rows (successful root submit with no prior root run_command matching \\bpytest\\b|-m\\s+unittest\\b|\\btox\\b) PLUS every submit_unverifiable row without a root test run before its earliest candidate boundary; submitted_without_test_observed = observed rows only, no-success rows excluded there and counted in count_no_successful_submit_observed',
    'count_no_successful_submit': 'PRIMARY total (D73.5) = verifiable rows with no successful submit PLUS unverifiable rows whose patch_submitted is not True; *_observed = rows with no observed successful submit',
    'inventory': 'smoke requires exactly the ids in eval/plans/008-smoke-ids.txt (else overall FAIL); arm2 requires exactly the 33 ids in eval/plans/007-arm1-ids.txt (else no output, exit 3)',
    'selected_bundle': 'header agent_yaml_sha256 matched against bundles/31b/v010|v011/agent.yaml; only if absent/unrecognized, gate event evidence; free-text header/dir labels never used',
    'success': 'first root harness patch_size response (builtin), or gate-authored inner harness patch_size response attributed to its enclosing root submit; acknowledgement not required',
    'submit_unverifiable': 'inner/builtin success vs explicit patch_submitted mismatch, or flag unavailable; missing flag derived from harness response only, not acknowledgement; rows counted and listed',
    'smoke': '008.md D73.2 i-v; missing evidence UNVERIFIABLE; overall PASS requires every criterion PASS',
    'gate_descriptives': 'root submit calls; reply-prefix bounces/failures; gate run_command response forced/check_error counts; terminal bounces; internal visibility',
    'gate_llm_limit': 'gate-authored limit evidence, or an unacknowledged enclosing gate with the runner turns-budget error; inferred from saved evidence',
    'gate_detection': 'selected_bundle v010 = gate, v011 = builtin; unidentified -> gate request/reply/child events; otherwise builtin layout and gate counts n/a',
    'untracked_only': 'D72.2: canonical SUBMITTED reply and nonempty scored patch with all sections declaring new file mode; absent scored-patch evidence reported separately',
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


def gate_invocations(entries):
    """Legacy traces lack event IDs: enclose children by root call/reply interval.

    A missing acknowledgement ends at the next root call or trace end. This retains
    inner captures interrupted by a deadline, without assigning them to a later call.
    Only the root tool_response is a canonical gate reply.
    """
    pairs = _pairs(entries)
    roots = [c for c in pairs if c.get('author') == ROOT]
    gates = []
    for i, c in enumerate(roots):
        if c.get('tool') != 'submit_patch':
            continue
        end = roots[i + 1]['entry_index'] if i + 1 < len(roots) else len(entries)
        reply_index = c['response_index']
        canonical = (reply_index is not None and reply_index < end
                     and entries[reply_index].get('type') == 'tool_response')
        if canonical:
            end = reply_index
        children = [dict(p, response=None, response_index=None)
                    if p['response_index'] is not None and p['response_index'] >= end else p
                    for p in pairs if p.get('author') == 'submit_patch'
                    and c['entry_index'] < p['entry_index'] < end]
        inner = [p for p in children if p.get('tool') == 'submit_patch'
                 and p['response_index'] is not None and p['response_index'] < end
                 and _patch_size(p['response']) is not None]
        gates.append(dict(c, root_index=i, children=children, inner_successes=inner,
                          canonical_reply=_reply(c['response']) if canonical else '',
                          canonical_index=reply_index if canonical else None))
    return gates


def successful_submit_index(entries, gate_mode=None):
    gates = {g['entry_index']: g for g in gate_invocations(entries)}
    for i, c in enumerate(root_tool_calls(entries)):
        if c.get('tool') != 'submit_patch':
            continue
        gate = gates[c['entry_index']]
        args = c.get('args', c.get('arguments'))
        is_gate = gate_mode if gate_mode is not None else bool(
            gate['children'] or isinstance(args, dict) and 'request' in args
            or gate['canonical_reply'] in ('SUBMITTED', BOUNCE)
            or gate['canonical_reply'].startswith('SUBMIT FAILED'))
        if (gate['inner_successes'] if is_gate else _patch_size(c['response']) is not None):
            return i
    return None


def _terminal_flag(row, entries):
    if type(row.get('patch_submitted')) is bool:
        return row['patch_submitted'], 'row'
    flags = [e['patch_submitted'] for e in entries if type(e.get('patch_submitted')) is bool]
    return (flags[-1], 'trace') if flags else (None, 'derived_from_harness_response')


def submit_evidence(row, entries, gate_mode=None, trace_loaded=True):
    observed = successful_submit_index(entries, gate_mode) is not None
    flag, source = _terminal_flag(row, entries)
    known = type(flag) is bool
    return dict(submit_unverifiable=not trace_loaded or not known or flag != observed,
                patch_submitted=flag if known else observed,
                patch_submitted_source=source,
                successful_submit=observed)


def submitted_without_test(entries, gate_mode=None):
    index = successful_submit_index(entries, gate_mode)
    if index is None:
        return None
    return not any(c.get('tool') == 'run_command' and TEST.search(_command(c))
                   for c in root_tool_calls(entries)[:index])


def earliest_candidate_index(entries):
    """D73.5 boundary, independent of successful-root attribution: the earliest of
    (a) any gate-authored inner submit_patch harness response carrying patch_size,
    (b) the root submit call enclosing such a response (gate_invocations interval),
    (c) any root submit_patch call whose own response carries patch_size (builtin).
    Extra candidates only move the boundary earlier (stricter). None = no candidate."""
    cands = [p['response_index'] for p in _pairs(entries)
             if p.get('author') == 'submit_patch' and p.get('tool') == 'submit_patch'
             and p['response_index'] is not None and _patch_size(p['response']) is not None]
    cands += [g['entry_index'] for g in gate_invocations(entries) if g['inner_successes']]
    cands += [c['entry_index'] for c in root_tool_calls(entries)
              if c.get('tool') == 'submit_patch' and _patch_size(c['response']) is not None]
    return min(cands, default=None)


def tested_before(entries, index):
    return index is not None and any(
        c.get('tool') == 'run_command' and TEST.search(_command(c)) and c['entry_index'] < index
        for c in root_tool_calls(entries))


def d735_counts(r, entries):
    """D73.5 (dec 074 item 2): a submit_unverifiable row counts as submitted_without_test
    unless a root test run precedes the earliest candidate boundary (computed from the
    trace, not from the observed success; the observed success is itself a candidate, so
    the boundary is never later than it). No candidate = worst case = counted. If
    patch_submitted is not True it ALSO counts in no_successful_submit. Verifiable rows keep the observed D73.3 values.
    Mutates and returns the row."""
    obs = r['submitted_without_test']
    if r['submit_unverifiable']:
        boundary = earliest_candidate_index(entries)
        r['d735_boundary_entry'] = boundary
        r['swt_d735'] = not tested_before(entries, boundary)
        r['no_submit_d735'] = r['patch_submitted'] is not True
    else:
        r['swt_d735'] = obs is True
        r['no_submit_d735'] = obs is None
    return r


def registered_ids(path):
    return [l.strip() for l in Path(path).read_text().splitlines() if l.strip() and not l.lstrip().startswith('#')]


def expected_ids(kind):
    return registered_ids(SMOKE_IDS if kind == 'smoke' else ARM2_IDS)


def inventory(ids, expected):
    seen = set(ids)
    out = dict(expected=len(expected), observed=len(ids),
               missing=[i for i in expected if i not in seen],
               extra=sorted(seen - set(expected)),
               duplicates=sorted({i for i in ids if ids.count(i) > 1}),
               order_matches=list(ids) == list(expected))
    out['complete'] = not (out['missing'] or out['extra'] or out['duplicates'])
    return out


def selected_bundle(headers):
    """(name, source). Only the kernel header agent_yaml_sha256 is authoritative."""
    shas = {h['agent_yaml_sha256'] for h in headers if isinstance(h.get('agent_yaml_sha256'), str)}
    known = {hashlib.sha256(p.read_bytes()).hexdigest(): n for n, p in BUNDLE_YAMLS.items() if p.is_file()}
    if len(shas) == 1 and next(iter(shas)) in known:
        return known[next(iter(shas))], 'header.agent_yaml_sha256'
    return None, 'unidentified (%s)' % ('no agent_yaml_sha256' if not shas else 'unrecognized or conflicting agent_yaml_sha256')


def _command(c):
    args = c.get('args', c.get('arguments'))
    return args.get('command', '') if isinstance(args, dict) and isinstance(args.get('command', ''), str) else ''


def _response_text(value):
    return value if isinstance(value, str) else json.dumps(value)


def gate_descriptives(entries, row=None):
    roots = root_tool_calls(entries)
    gates = gate_invocations(entries)
    cmds = [c for g in gates for c in g['children'] if c.get('tool') == 'run_command']
    limit = any('LlmCallsLimitExceeded' in _response_text(e) for e in entries
                if e.get('author') == 'submit_patch')
    if row and gates and gates[-1]['canonical_index'] is None and gates[-1]['root_index'] == len(roots) - 1:
        limit |= row.get('agent_outcome') == 'turns'
        limit |= any(re.search(r'LlmCallsLimitExceeded|exceeded turns budget|maximum allowed LLM turns', str(row.get(k, ''))) is not None
                     for k in ('agent_error', 'agent_error_text', 'result_error', 'error'))
    return dict(gate_calls=len(gates),
                bounces=sum(g['canonical_reply'].startswith('NOT SUBMITTED') for g in gates),
                forced=sum('reason=forced' in _response_text(c['response']) for c in cmds),
                check_error=sum('reason=check_error' in _response_text(c['response']) for c in cmds),
                submit_failed=sum(g['canonical_reply'].startswith('SUBMIT FAILED') for g in gates),
                bounce_no_followup=sum(g['root_index'] == len(roots) - 1 and
                                       g['canonical_reply'].startswith('NOT SUBMITTED') for g in gates),
                gate_llm_limit=int(limit),
                unacknowledged_inner_submits=sum(len(g['inner_successes']) for g in gates
                                                if g['canonical_reply'] != 'SUBMITTED'),
                gate_run_cmds=[_command(c) for c in cmds],
                gate_internal_visible=any(g['children'] for g in gates))


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


def smoke_check(row, entries, gate_yaml_path, scored_patch=None, test_files_loaded=False):
    """D73.2 i..v. scored_patch must already be stripped with task.test_files.

    Missing evidence is UNVERIFIABLE, which is FAIL for the overall smoke.
    Reasons are fixed descriptions; commands, patches and task text are never emitted.
    """
    out = {}
    gates = gate_invocations(entries)
    desc = gate_descriptives(entries, row)
    expected = _gate_command(gate_yaml_path)
    failures, missing = [], []
    captures = []
    if not gates:
        failures.append('no gate invocation in task')
    for gate in gates:
        children = gate['children']
        if not children:
            missing.append('gate internals absent')
            continue
        if gate['canonical_index'] is None:
            missing.append('canonical gate response absent')
        cmds = [c for c in children if c.get('tool') == 'run_command']
        subs = [c for c in children if c.get('tool') == 'submit_patch']
        captures.extend(gate['inner_successes'])
        if len(cmds) != 1 or _command(cmds[0]) != expected:
            failures.append('gate check command differs or count differs')
        elif cmds[0]['response_index'] is None:
            missing.append('gate check response absent')
        else:
            text = _response_text(cmds[0]['response'])
            need_submit = 'VERDICT=SUBMIT' in text or 'VERDICT=EDIT_FIRST' not in text
            if need_submit and (len(subs) != 1 or subs[0]['entry_index'] <= cmds[0]['response_index']
                                or not gate['inner_successes']):
                failures.append('successful inner submit absent or out of order')
            if not need_submit and subs:
                failures.append('inner submit after EDIT_FIRST')
        if gate['canonical_reply'] == 'SUBMITTED':
            for e in entries[gate['canonical_index'] + 1:]:
                if e.get('author') != ROOT or e.get('type') in ('tool_response', 'tool_result'):
                    continue
                if e.get('type') == 'final' and e.get('content') == gate['canonical_reply']:
                    continue  # legacy recorder's mirrored function-response display
                failures.append('root model event after successful gate response')
                break
    if gates and not captures:
        missing.append('no successful inner submit evidence')
    flag, _ = _terminal_flag(row, entries)
    if flag is False:
        failures.append('run did not end with patch_submitted true')
    elif flag is not True:
        missing.append('terminal patch_submitted flag absent')
    out['i'] = _criterion('FAIL' if failures else 'UNVERIFIABLE' if missing else 'PASS',
                          '; '.join(failures or missing) or 'gate sequence and termination observed')

    actual = row.get('verified_patch_bytes')
    if not test_files_loaded or scored_patch is None or not captures or type(actual) is not int:
        out['ii'] = _criterion('UNVERIFIABLE', 'task test_files, saved patch or capture evidence missing')
    else:
        size = _patch_size(captures[-1]['response'])
        agrees = len(scored_patch) == size and len(scored_patch.encode('utf-8')) == actual
        out['ii'] = _criterion('PASS' if agrees else 'FAIL',
                               'stripped patch characters and UTF-8 bytes agree' if agrees else 'stripped patch sizes differ')

    errors = bool(desc['check_error'] or desc['submit_failed'])
    for key in ('agent_error', 'agent_error_text', 'result_error', 'error'):
        err = row.get(key)
        if err and (re.search(r'unknown[ _-]tool|ToolErrorPlugin|compile|validator', str(err), re.I)
                    or not re.search(r'budget|timeout|timed out', str(err), re.I)):
            errors = True
    for e in entries:
        if e.get('author') not in (ROOT, 'submit_patch'):
            continue
        if e.get('type') in ('tool_response', 'tool_result'):
            text = _response_text(e.get('result', ''))
            errors |= _has_error(text) or bool(re.search(r'unknown[ _-]tool|ToolErrorPlugin|compile error|validator error', text, re.I))
    malformed = False
    for gate in gates:
        args = gate.get('args', gate.get('arguments'))
        malformed |= not (isinstance(args, dict) and set(args) == {'request'}
                          and isinstance(args['request'], str) and bool(args['request']))
        malformed |= gate['canonical_reply'] not in ('SUBMITTED', BOUNCE)
        for c in gate['children']:
            args = c.get('args', c.get('arguments'))
            if c.get('tool') == 'run_command':
                malformed |= args != {'command': expected}
            elif c.get('tool') == 'submit_patch':
                malformed |= args != {}
            else:
                malformed = True
    out['iii'] = _criterion('FAIL' if errors or malformed else 'PASS',
                            'error or malformed gate call/reply observed' if errors or malformed else 'no errors or malformed gate calls/replies observed')
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
                             submitted_without_test=submitted_without_test(entries, gate_mode=False)))
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
    assert totals['submitted_without_test'] == 23, 'arm-1 safety baseline changed'
    assert totals['count_no_successful_submit'] == 7, 'arm-1 no-submit baseline changed'
    return dict(_schema=_schema('base', paths), n_rows=len(rows), totals=totals, rows=rows)


def load_task_test_files(tasks_path):
    # Match agent_timing.evaluate / run_agent_eval.run: the Task property derives
    # these paths from test_patch. Never use gold patch or test text as agent input.
    from swegemma.models import load_tasks
    tasks = load_tasks(Path(tasks_path))
    inventory = {t.instance_id: list(t.test_files) for t in tasks}
    if len(inventory) != len(tasks):
        raise ValueError('duplicate task IDs')
    return inventory


def _tasks_path():
    if os.environ.get('PLAN008_TASKS_PATH'):
        return Path(os.environ['PLAN008_TASKS_PATH'])
    kaggle = Path('/kaggle/input/competitions/gemma-4-developer-agent/tasks.jsonl')
    return kaggle if kaggle.is_file() else Path('data/raw/tasks.jsonl')


def _artifacts(run_dir, iid):
    # Kaggle: runs/<iid>; local eval runner: <iid>.
    nested = Path(run_dir) / 'runs' / iid
    return nested if nested.is_dir() else Path(run_dir) / iid


def smoke_metrics(run_dir, tasks_path=None):
    timing = Path(run_dir) / 'timing.jsonl'
    paths, rows = [timing, GATE_YAML], []
    tasks_path = Path(tasks_path) if tasks_path is not None else _tasks_path()
    if tasks_path.is_file():
        paths.append(tasks_path)
    try:
        test_files = load_task_test_files(tasks_path)
    except Exception:
        test_files = {}  # criterion ii is UNVERIFIABLE for every missing task
    for row in base.load_rows(timing):
        artifacts = _artifacts(run_dir, row['instance_id'])
        trace, patch = artifacts / 'trace.json', artifacts / 'agent.patch'
        if trace.is_file():
            paths.append(trace)
        entries = json.loads(trace.read_text()).get('entries', []) if trace.is_file() else []
        scored = None
        loaded = row['instance_id'] in test_files
        if patch.is_file():
            paths.append(patch)
            if loaded:
                from swegemma.harness.verification import strip_protected_files_from_patch
                try:
                    scored = strip_protected_files_from_patch(patch.read_bytes().decode('utf-8'),
                                extra_protected_paths=test_files[row['instance_id']])
                except (OSError, UnicodeError, ValueError):
                    scored = None
        desc = gate_descriptives(entries, row)
        desc.pop('gate_run_cmds')
        rows.append(dict(instance_id=row['instance_id'],
                         criteria=smoke_check(row, entries, GATE_YAML, scored, loaded), **desc))
    inv = inventory([r['instance_id'] for r in rows], expected_ids('smoke'))
    passed = inv['complete'] and bool(rows) and all(c['status'] == 'PASS' for r in rows for c in r['criteria'].values())
    return dict(_schema=_schema('smoke', paths), n_rows=len(rows), inventory=inv,
                overall='PASS' if passed else 'FAIL', rows=rows)


GATE_COUNTS = ('gate_calls', 'bounces', 'forced', 'check_error', 'submit_failed',
               'bounce_no_followup', 'gate_llm_limit', 'unacknowledged_inner_submits', 'untracked_only_submits')


class IncompleteRun(ValueError):
    pass


class GateResponseInBuiltinRun(ValueError):
    """Dec 077 item 2: B3 (unpaired gate-authored inner responses) is unfixed, so the
    builtin (v011) arm-2 path refuses any non-root submit_patch response. STOP, report."""


def nonroot_submit_responses(entries):
    """Raw scan, independent of call pairing: indices of submit_patch responses whose
    author is not the root agent (missing author counts as non-root)."""
    return [i for i, e in enumerate(entries)
            if e.get('type') in ('tool_response', 'tool_result')
            and e.get('tool') == 'submit_patch' and e.get('author') != ROOT]


def arm2_metrics(run_dir):
    timing = Path(run_dir) / 'timing.jsonl'
    paths, rows, inputs = [timing], [], []
    for row in base.load_rows(timing):
        artifacts = _artifacts(run_dir, row['instance_id'])
        trace = artifacts / 'trace.json'
        if trace.is_file():
            paths.append(trace)
        entries = json.loads(trace.read_text()).get('entries', []) if trace.is_file() else []
        inputs.append((row, entries, artifacts))
    # Builtin responses carry patch_size; gate requests carry request, children
    # have author submit_patch. Header/directory labels cover runs with no calls.
    headers = [json.loads(line) for line in timing.read_text().splitlines() if line.strip()
               and 'instance_id' not in json.loads(line)]
    inv = inventory([row['instance_id'] for row, _, _ in inputs], expected_ids('arm2'))
    if not inv['complete']:
        raise IncompleteRun(inv)
    bundle, bundle_source = selected_bundle(headers)
    gate_events = (any(
        e.get('author') == 'submit_patch' or
        (e.get('author') == ROOT and e.get('tool') == 'submit_patch' and
         (isinstance(e.get('args'), dict) and 'request' in e['args'] or
          _reply(e.get('result')) in ('SUBMITTED', BOUNCE)))
        for _, entries, _ in inputs for e in entries))
    has_gate = bundle == 'v010' if bundle else gate_events
    if not has_gate:
        bad = [row['instance_id'] for row, entries, _ in inputs if nonroot_submit_responses(entries)]
        if bad:
            raise GateResponseInBuiltinRun(dict(rows=bad, selected_bundle=bundle))
    for row, entries, artifacts in inputs:
        rep = identical_runs_root(entries)
        desc = gate_descriptives(entries, row) if has_gate else {}
        desc.pop('gate_run_cmds', None)
        if has_gate:
            # D72's untracked-only descriptive requires a canonical acknowledgement;
            # the D73 SAFETY boundary below needs only an inner harness capture.
            acknowledged = any(g['canonical_reply'] == 'SUBMITTED' for g in gate_invocations(entries))
            desc['untracked_only_submits'] = None if acknowledged else False
            if acknowledged:
                result = artifacts / 'result.json'
                if not result.is_file():
                    result = artifacts / 'output.json'
                scored = None
                if result.is_file():
                    paths.append(result)
                    scored = json.loads(result.read_text()).get('agent_patch')
                patch = artifacts / 'agent.patch'
                if scored is None and patch.is_file():
                    paths.append(patch)
                    try:
                        from swegemma.harness.verification import strip_protected_files_from_patch
                        tasks_path = _tasks_path()
                        if tasks_path.is_file():
                            paths.append(tasks_path)
                        tests = load_task_test_files(tasks_path)[row['instance_id']]
                        scored = strip_protected_files_from_patch(patch.read_bytes().decode('utf-8'), extra_protected_paths=tests)
                    except Exception:
                        scored = None
                if isinstance(scored, str):
                    desc['untracked_only_submits'] = untracked_only(scored)
        else:
            desc = dict.fromkeys((*GATE_COUNTS, 'gate_internal_visible'), 'n/a (no gate)')
        rows.append(dict(instance_id=row['instance_id'], **rep, mechanism2=rep['max_run'] >= 5,
                         mechanism1_empty=row.get('verified_patch_bytes') == 0,
                         submitted_without_test=submitted_without_test(entries, has_gate),
                         **submit_evidence(row, entries, has_gate, (artifacts / 'trace.json').is_file()), **desc))
    for r, (_, entries, _) in zip(rows, inputs):
        d735_counts(r, entries)
    totals = dict(mechanism2=sum(r['mechanism2'] for r in rows),
                  mechanism1_empty=sum(r['mechanism1_empty'] for r in rows),
                  # D73.5 (ship-rule numbers): unverifiable rows count against arm 2.
                  submitted_without_test=sum(r['swt_d735'] for r in rows),
                  count_no_successful_submit=sum(r['no_submit_d735'] for r in rows),
                  submitted_without_test_observed=sum(r['submitted_without_test'] is True for r in rows),
                  count_no_successful_submit_observed=sum(r['submitted_without_test'] is None for r in rows),
                  max_run=max((r['max_run'] for r in rows), default=0),
                  runs_ge3=sum(r['runs_ge3'] for r in rows), runs_ge5=sum(r['runs_ge5'] for r in rows),
                  repeated_calls=sum(r['repeated_calls'] for r in rows),
                  submit_unverifiable=sum(r['submit_unverifiable'] for r in rows))
    for key in GATE_COUNTS:
        totals[key] = (sum(r[key] for r in rows if r[key] is not None) if has_gate else 'n/a (no gate)')
    totals['untracked_only_unverifiable'] = sum(r.get('untracked_only_submits') is None for r in rows) if has_gate else 'n/a (no gate)'
    return dict(_schema=_schema('arm2', paths), n_rows=len(rows), inventory=inv,
                selected_bundle=bundle, selected_bundle_source=bundle_source,
                gate_layout=has_gate, gate_events_observed=gate_events,
                bundle_identity_conflict=bundle is not None and gate_events != has_gate,
                totals=totals,
                submit_unverifiable_rows=[r['instance_id'] for r in rows if r['submit_unverifiable']],
                d735_rule='submit_unverifiable rows: submitted_without_test unless root test before earliest candidate boundary (none = counted); patch_submitted not True -> also no_successful_submit',
                rows=rows)


def main(argv=None):
    argv = sys.argv if argv is None else argv
    if len(argv) == 3 and argv[1] == 'base':
        out = base_metrics()
    elif len(argv) == 4 and argv[1] in ('smoke', 'arm2'):
        try:
            out = (smoke_metrics if argv[1] == 'smoke' else arm2_metrics)(argv[2])
        except IncompleteRun as e:
            print('INCOMPLETE arm2 inventory; no results written:', json.dumps(e.args[0]))
            return 3
        except GateResponseInBuiltinRun as e:
            print('STOP: gate-authored submit_patch response in builtin arm2 run (dec 077); '
                  'no results written; report to Director:', json.dumps(e.args[0]))
            return 4
    else:
        print(__doc__)
        return 2
    Path(argv[-1]).write_text(json.dumps(out, indent=2) + '\n')
    print(json.dumps(out.get('totals', dict(n_rows=out['n_rows'], overall=out.get('overall')))))
    return 0


if __name__ == '__main__':
    sys.exit(main())
