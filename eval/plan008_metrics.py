#!/usr/bin/env python3
"""Plan 008 D73 metrics. CPU/offline only; output contains counts, never task text.

Usage: plan008_metrics.py base OUT_JSON | smoke RUN_DIR OUT_JSON | arm2 RUN_DIR OUT_JSON
       plan008_metrics.py arm3smoke RUN_DIR CLASSIFIER_D4_JSON OUT_JSON
       plan008_metrics.py arm3 {arm1,arm2} OUT_JSON --arm3 DIR [DIR ...]
           [--base-dirs DIR ...] --classifiers DIR=D4_JSON,A2_JSON [--classifiers ...]
           --smoke-json PATH [--base-verdict-json PATH]
       Dirs are supplied in push order: smoke, main, chunk1, chunk2, ...
       Both arm3 modes require --identity-json PATH --bundle v01N --transport DIR=SHA256 --push-event DIR=EVENT (each arm3 dir).
       --base-verdict-json (base arm2) = the journaled plan-008 ruling file, {"verdict": "<plan 008 verdict>"};
       the raw arm2-mode output carries no verdict and therefore fails closed. Only SHIP-ELIGIBLE is a valid arm2 base.

Exit: 0 ok, 2 usage, 3 incomplete arm2/arm3 inventory, 4 builtin arm2 run holds a non-root
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

BUNDLES_ROOT = Path(__file__).resolve().parents[1] / 'bundles/31b'
PUSH_EVENT = re.compile(r'(smoke|main|chunk[1-9][0-9]*)')

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
    cands = [i for i in nonroot_submit_responses(entries)
             if _patch_size(entries[i].get('result', '')) is not None]
    cands += [p['response_index'] for p in _pairs(entries)
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
    # Legacy modes retain the frozen pre-extension implementation fingerprint to
    # honor their byte-identical output contract. New modes hash this full script.
    return dict(name='plan008_metrics/v1', mode=mode, definitions=dict(DEFINITIONS, **ARM3_DEFINITIONS) if mode in ('arm3', 'arm3smoke') else DEFINITIONS,
                script_sha256=(base.sha(__file__) if mode in ('arm3', 'arm3smoke') else
                               'b9c2cb5efed8a5d2e0e3b0bcbb0f530f4cc8ab59dcb3daa0d414c42dabe4557a'),
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


# Separate definitions keep the legacy modes' schema bytes stable.
ARM3_DEFINITIONS = {
    'primary': 'resolved is True, including H rows; paired by exact registered instance_id set',
    'sign_test': 'exact two-sided Binomial(n discordants, p=0.5), doubled smaller tail capped at 1; no discordants -> 1',
    'resolved': 'k/n and Wilson 95% CI; plan007_arm1_summary.rate/wilson',
    'h_rows': 'governing d4cdf0f0 h is not None; H>=5 invalid without exemptions; a208a023 alongside',
    'sensitivity': 'resolved over each arm non-H rows; denominator stated separately',
    'known_diag': 'count of truthy governing classifier known_diag; null if unavailable',
    'timing': 'each arm3 row: finite nonnegative agent_clock_seconds <=220 and finalization_seconds <=30; absent evidence fails',
    'timeouts': 'bool(timed_out) or bool(agent_timeout_fired), plan007 definition',
    'safety': 'arm3 test_files_edited and stray_files zero rows; total wall p90 <=1.10*base; empty and submitted_without_test <=base+3; missing evidence fails',
    'thinking': 'thinking_bound.task: root author swe_baseline_agent, type thinking, nonempty content; blocks/chars per task and tasks>0',
    'arm3smoke': 'first two registered ids exactly; i each >=1 thinking block and sum>=5; ii timing; iii vLLM startup, verification verdict, zero H, ZIP/CONTENT event proof and per-push TRANSPORT/header identity',
    'aggregation': 'exact registered 33-id union; earliest supplied dir wins; duplicate attempts listed; within-dir duplicates fail inventory; identity-rejected runs only in uncounted_sensitivity',
    'calls': 'timing llm_turns/tool_calls.total if present; otherwise trace root usage-bearing turns/root tool calls; linear percentiles from plan007.pct',
    'descriptive': 'per repo uses timing repo, fallback id prefix before __; unscreened excludes 004-gpu-retime ids; context overflow unavailable in plan007',
    'env_drift': 'header environment values, null if absent; setup/verification wall p50/p90 from timing; differences reported only',
    'kernel_code': 'header kernel_code and agent/verification path hashes when present; differing values void pairing',
    'decision': 'INVALID for voided pairing, identity mismatch, invalid/unruled base (arm2 base needs ruled SHIP-ELIGIBLE), unbound/failed smoke or H>=5; on ahead p<0.2 adopts only with timeout/timing/all safety; otherwise veto; off>=on KEEP-OFF; else NO-DIFFERENCE',
}


def sign_test(on_only, off_only):
    n = on_only + off_only
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(min(on_only, off_only) + 1)) / 2**n) if n else 1.0


def _headers(timing):
    return [r for r in map(json.loads, filter(str.strip, Path(timing).read_text().splitlines())) if '_schema' in r]


def _finite_number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def arm3_timing(rows):
    bad = []
    for row in rows:
        fields = [k for k, limit in (('agent_clock_seconds', 220), ('finalization_seconds', 30))
                  if not _finite_number(row.get(k)) or row[k] > limit]
        if fields:
            bad.append(dict(instance_id=row['instance_id'], fields=fields))
    return dict(violations=bad, timing_pass=not bad)


def thinking_criterion(trace_paths):
    """Smoke (i), deliberately independent of the registered-id inventory."""
    counts = [base.thinking_task(str(p))['thinking_blocks'] if Path(p).is_file() else None
              for p in trace_paths]
    status = ('UNVERIFIABLE' if not counts or None in counts else
              'PASS' if all(n >= 1 for n in counts) and sum(counts) >= 5 else 'FAIL')
    return dict(status=status, blocks=counts, total_blocks=sum(n for n in counts if n is not None))


def _classifier(timing, path, sha, rows):
    c = json.loads(Path(path).read_text())
    assert c['classifier_sha256'] == sha
    assert c['input_sha256'] == base.sha(timing)
    by_id = base.unique_map(c['rows'], path)
    assert set(by_id) == {r['instance_id'] for r in rows}
    for r in rows:
        base.assert_paired(by_id[r['instance_id']], r)
    return by_id


def _read_json(path):
    try:
        value = json.loads(Path(path).read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _readable_file(path):
    try:
        base.sha(path)
        return True
    except (OSError, TypeError):
        return False


def _manifest_path(bundle):
    return BUNDLES_ROOT / bundle / 'MANIFEST.md' if isinstance(bundle, str) and re.fullmatch(r'v01[0-9]+', bundle) else None


def _push_errors(dirs, push_events, smoke_dirs, smoke_only=False):
    dirs = [str(Path(d)) for d in dirs]
    errors = []
    if len(set(dirs)) != len(dirs) or set(push_events) != set(dirs):
        errors.append('push-event dirs must match run dirs exactly')
    events = list(push_events.values())
    if any(not isinstance(e, str) or not PUSH_EVENT.fullmatch(e) for e in events):
        errors.append('invalid push event')
    if len(set(events)) != len(events):
        errors.append('duplicate push event')
    if smoke_only:
        if len(dirs) != 1 or events != ['smoke']:
            errors.append('arm3smoke requires one smoke push')
    elif events.count('smoke') != 1 or events.count('main') != 1:
        errors.append('arm3 requires exactly one smoke and one main push')
    if {d for d, e in push_events.items() if e == 'smoke'} != smoke_dirs:
        errors.append('smoke push must supply both counted smoke rows')
    return errors


def identity_check(dirs, identity_json, bundle, transports, smoke_dirs, push_events=None, *, smoke_only=False):
    """Only the latest exact-event proof can authorize a push; hash types stay separate."""
    push_events = push_events or {}
    mapping_errors = _push_errors(dirs, push_events, smoke_dirs, smoke_only)
    if set(transports) != {str(Path(d)) for d in dirs}:
        mapping_errors.append('transport dirs must match run dirs exactly')
    records = _read_json(identity_json).get('records', [])
    records = records if isinstance(records, list) else []
    manifest = _manifest_path(bundle)
    try:
        matches = re.findall(r'^zip sha256:\s*([0-9a-fA-F]{64})[ \t]*$', manifest.read_text(), re.MULTILINE)
        registered_zip = matches[0].lower() if len(matches) == 1 else None
    except (OSError, AttributeError, UnicodeError):
        registered_zip = None
    results = []
    for directory in dirs:
        directory = str(Path(directory))
        event = push_events.get(directory)
        matching = [r for r in records if isinstance(r, dict) and event is not None and r.get('event') == event]
        latest = matching[-1] if matching else {}
        bundles = latest.get('bundles', {})
        proof = bundles.get(bundle, {}) if isinstance(bundles, dict) else {}
        proof = proof if isinstance(proof, dict) else {}
        reasons = list(mapping_errors)
        if not matching:
            reasons.append('missing event record')
        for key in ('pass', 'zip_ok', 'content_ok'):
            if proof.get(key) is not True:
                reasons.append(key + ' must be true')
        hashes = {}
        for key in ('zip_sha256', 'manifest_zip_sha256', 'agent_yaml_sha256'):
            value = proof.get(key)
            hashes[key] = value.lower() if isinstance(value, str) and re.fullmatch('[0-9a-fA-F]{64}', value) else None
            if hashes[key] is None:
                reasons.append(key + ' missing/invalid')
        if hashes['zip_sha256'] != hashes['manifest_zip_sha256']:
            reasons.append('ZIP differs from proof manifest')
        if registered_zip is None or hashes['zip_sha256'] != registered_zip:
            reasons.append('registered MANIFEST ZIP missing/mismatched')
        for key in ('only_in_zip', 'only_in_dir', 'byte_mismatch', 'duplicate_members'):
            if not isinstance(proof.get(key), list) or proof[key]:
                reasons.append(key + ' must be an empty list')
        if not isinstance(proof.get('zip_path'), str) or not proof['zip_path'].endswith(f'31b-{bundle}.zip'):
            reasons.append('zip_path missing/invalid')
        timing = Path(directory) / 'timing.jsonl'
        headers = _headers(timing) if timing.is_file() else []
        transport = transports.get(directory)
        if not headers:
            reasons.append('missing headers')
        if not isinstance(transport, str) or not re.fullmatch('[0-9a-f]{64}', transport) or any(h.get('bundle_sha256') != transport for h in headers):
            reasons.append('transport header mismatch')
        if any(h.get('agent_yaml_sha256') != hashes['agent_yaml_sha256'] for h in headers):
            reasons.append('agent header mismatch')
        results.append(dict(dir=directory, event=event, record_count=len(matching),
                            zip_sha256=hashes['zip_sha256'], agent_yaml_sha256=hashes['agent_yaml_sha256'],
                            transport_sha256=transport, failure_reasons=reasons))
    for key in ('zip_sha256', 'agent_yaml_sha256'):
        if len({r[key] for r in results if r[key] is not None}) > 1:
            for r in results:
                r['failure_reasons'].append(key + ' differs across pushes')
    for r in results:
        r['checked'] = not r['failure_reasons']
    return dict(checked=bool(results) and all(r['checked'] for r in results), runs=results,
                mismatching_dirs=[r['dir'] for r in results if not r['checked']])


def arm3smoke_metrics(run_dir, classifier, identity_json=None, bundle=None, transports=None, push_events=None):
    timing = Path(run_dir) / 'timing.jsonl'
    paths = [base.ARM_IDS, base.__file__, 'eval/plan007_report.py', 'eval/thinking_bound.py']
    expected = base.ids_file(base.ARM_IDS)[:2]
    rows = base.load_rows(timing) if timing.is_file() else []
    if timing.is_file():
        paths.append(timing)
    inv = inventory([r['instance_id'] for r in rows], expected)
    traces = [Path(run_dir) / 'runs' / iid / 'trace.json' for iid in expected]
    paths.extend(p for p in traces if p.is_file())
    ci = thinking_criterion(traces)
    ti = arm3_timing(rows)
    missing_time = not rows or any(not _finite_number(r.get(k)) for r in rows
                                 for k in ('agent_clock_seconds', 'finalization_seconds'))
    cii = dict(status='UNVERIFIABLE' if missing_time else 'PASS' if ti['timing_pass'] else 'FAIL', **ti)
    headers = _headers(timing) if timing.is_file() else []
    identity = {k: [h.get(k) for h in headers] for k in ('agent_yaml_sha256', 'bundle_sha256')}
    checked_identity = identity_check([run_dir], identity_json, bundle, transports or {}, {str(Path(run_dir))}, push_events, smoke_only=True)
    if identity_json and _readable_file(identity_json):
        paths.append(identity_json)
    manifest = _manifest_path(bundle)
    if manifest and _readable_file(manifest):
        paths.append(manifest)
    startup = [r.get('_vllm') for r in map(json.loads, filter(str.strip, timing.read_text().splitlines())) if '_vllm' in r] if timing.is_file() else []
    vllm_up = any(isinstance(v, dict) and _finite_number(v.get('startup_seconds'))
                  and v['startup_seconds'] > 0 for v in startup)
    identity_missing = not headers or any(not v for vals in identity.values() for v in vals)
    identity_conflict = any(len(set(vals)) > 1 for vals in identity.values())
    hs = None
    if timing.is_file() and Path(classifier).is_file():
        paths.append(classifier)
        cs = _classifier(timing, classifier, base.D4_SHA, rows)
        hs = ([r['instance_id'] for r in rows if cs[r['instance_id']]['h'] is not None]
              if all('h' in cs[r['instance_id']] for r in rows) else None)
    verdict_missing = any(type(r.get('resolved')) is not bool or r.get('verification_skipped') is True for r in rows)
    missing = bool(inv['missing']) or not rows or hs is None or identity_missing or verdict_missing or not vllm_up
    ciii = dict(status='FAIL' if inv['extra'] or inv['duplicates'] or identity_conflict or not checked_identity['checked'] or hs else
                'UNVERIFIABLE' if missing else 'PASS', h_rows=hs, identity_headers=identity,
                identity=checked_identity, vllm_up=vllm_up)
    criteria = dict(i=ci, ii=cii, iii=ciii)
    overall = 'PASS' if all(c['status'] == 'PASS' for c in criteria.values()) else 'FAIL'
    return dict(_schema=_schema('arm3smoke', paths), n_rows=len(rows), inventory=inv,
                criteria=criteria, overall=overall,
                verdict='INVALID (smoke i)' if ci['status'] != 'PASS' else overall,
                label='thinking ACTIVE != budget enforced')


def aggregate_arm(dirs, classifiers):
    """Inventory first, before loading classifier/trace evidence. Never drop a row."""
    selected, occurrences, paths, headers = {}, defaultdict(list), [], []
    for directory in dirs:
        timing = Path(directory) / 'timing.jsonl'
        if not timing.is_file():
            raise IncompleteRun(dict(dir=str(directory), missing_timing=True))
        try:
            rows = base.load_rows(timing)
        except AssertionError:
            raw = [json.loads(l) for l in timing.read_text().splitlines() if l.strip()]
            inv = inventory([r['instance_id'] for r in raw if 'instance_id' in r], base.ids_file(base.ARM_IDS))
            raise IncompleteRun(dict(dir=str(directory), inventory=inv))
        paths.append(timing)
        headers.extend(_headers(timing))
        for row in rows:
            iid = row['instance_id']
            occurrences[iid].append(dict(dir=str(directory), resolved=row.get('resolved'),
                                         timeout=bool(row.get('timed_out') or row.get('agent_timeout_fired')),
                                         empty_patch=row.get('verified_patch_bytes') == 0))
            selected.setdefault(iid, (row, str(directory)))
    inv = inventory(list(selected), base.ids_file(base.ARM_IDS))
    inv['duplicates'] = [dict(instance_id=i, dirs=[a['dir'] for a in ds], attempts=ds) for i, ds in occurrences.items() if len(ds) > 1]
    if not inv['complete']:
        raise IncompleteRun(inv)
    classified = {}
    for directory in dirs:
        timing = Path(directory) / 'timing.jsonl'
        d4, a2 = classifiers[str(Path(directory))]
        rows = base.load_rows(timing)
        classified[str(directory)] = _classifier(timing, d4, base.D4_SHA, rows)
        _classifier(timing, a2, base.A2_SHA, rows)
        paths.extend((d4, a2))
    records = []
    for iid in base.ids_file(base.ARM_IDS):
        row, directory = selected[iid]
        trace = Path(directory) / 'runs' / iid / 'trace.json'
        entries = json.loads(trace.read_text()).get('entries') or []
        paths.append(trace)
        records.append((row, classified[directory][iid], trace, entries))
    return records, inv, paths, headers


def _quantiles(values):
    return [base.pct(values, q) for q in (.5, .9)]


def _id_count(ids):
    return dict(count=len(ids), instance_ids=ids)


def summarize_arm(records, arm1=False):
    rows = [r for r, _, _, _ in records]
    ids = lambda predicate: [r['instance_id'] for r in rows if predicate(r)]
    hs = [r['instance_id'] for r, c, _, _ in records if c['h'] is not None]
    non_h = [r for r in rows if r['instance_id'] not in hs]
    rate = lambda rs: base.rate(sum(r.get('resolved') is True for r in rs), len(rs))
    thinking, repeats, llm, tools, swt = [], [], [], [], []
    for row, _, trace, entries in records:
        iid = row['instance_id']
        th = base.thinking_task(str(trace))
        thinking.append(dict(instance_id=iid, thinking_blocks=th['thinking_blocks'], total_thinking_chars=sum(
            len(e.get('content') or '') for e in entries if e.get('author') == ROOT and e.get('type') == 'thinking')))
        repeats.append(dict(instance_id=iid, **identical_runs_root(entries)))
        llm.append(row.get('llm_turns') if row.get('llm_turns') is not None else th['root_usage_turns'])
        tc = row.get('tool_calls')
        tools.append(tc['total'] if isinstance(tc, dict) and tc.get('total') is not None else len(root_tool_calls(entries)))
        observed = submitted_without_test(entries, gate_mode=False)
        count = observed is True
        if not arm1:
            evidence = dict(submitted_without_test=observed, **submit_evidence(row, entries, False))
            count = d735_counts(evidence, entries)['swt_d735']
        if count:
            swt.append(iid)
    safety = {}
    for key in ('test_files_edited', 'stray_files'):
        safety[key] = (_id_count(ids(lambda r: bool(r.get(key)))) if all(key in r and r[key] is not None for r in rows)
                       else 'not available')
    safety.update(total_wall_p90=base.pct([(r.get('wall_seconds') or {}).get('total') for r in rows], .9),
                  total_wall_complete=all(_finite_number((r.get('wall_seconds') or {}).get('total')) for r in rows),
                  empty_patch=_id_count(ids(lambda r: r.get('verified_patch_bytes') == 0)),
                  empty_patch_complete=all(type(r.get('verified_patch_bytes')) is int for r in rows),
                  submitted_without_test=_id_count(swt),
                  submitted_without_test_definition='plan007 observed' if arm1 else 'plan008 D73.5 total')
    screened = set(base.ids_file(base.SCREENED_IDS))
    unseen = [r for r in rows if r['instance_id'] not in screened]
    return dict(n_rows=len(rows), resolved=rate(rows), h_rows=_id_count(hs), sensitivity=rate(non_h),
                known_diag=sum(bool(c['known_diag']) for _, c, _, _ in records) if all('known_diag' in c for _, c, _, _ in records) else None,
                timeouts=_id_count(ids(lambda r: bool(r.get('timed_out')) or bool(r.get('agent_timeout_fired')))),
                safety=safety, timing=arm3_timing(rows), descriptive=dict(
                    thinking=dict(rows=thinking, tasks_with_blocks=sum(t['thinking_blocks'] > 0 for t in thinking),
                                  total_blocks=sum(t['thinking_blocks'] for t in thinking),
                                  total_chars=sum(t['total_thinking_chars'] for t in thinking)),
                    context_overflow='not available',
                    repeat=dict(rows=repeats, mechanism2=_id_count([r['instance_id'] for r in repeats if r['max_run'] >= 5]),
                                max_run=max(r['max_run'] for r in repeats), repeated_calls=sum(r['repeated_calls'] for r in repeats)),
                    llm_calls_p50_p90=_quantiles(llm), tool_calls_p50_p90=_quantiles(tools),
                    per_repo={repo: rate([r for r in rows if (r.get('repo') or r['instance_id'].split('__')[0]) == repo])
                              for repo in sorted({r.get('repo') or r['instance_id'].split('__')[0] for r in rows})},
                    unscreened_25=dict(instance_ids=[r['instance_id'] for r in unseen], resolved=rate(unseen))))


def environment_metrics(headers, records):
    aliases = dict(docker_image_digest=('docker_image_digest', 'docker_image'),
                   vllm_version=('vllm_version',), google_adk_version=('google_adk_version', 'google-adk'),
                   swegemma_version=('swegemma_version',), model_id=('model_id', 'model'),
                   gpu_names=('gpu_names',), gpu_count=('gpu_count',))
    def values(keys):
        vals = []
        for h in headers:
            val = next((h[k] for k in keys if k in h), None)
            if val not in vals:
                vals.append(val)
        return vals[0] if len(vals) == 1 else vals or None
    out = {key: values(keys) for key, keys in aliases.items()}
    for package in ('vllm', 'google-adk', 'swegemma'):
        key = package.replace('-', '_') + '_version'
        if out[key] is None:
            values_from_versions = []
            for h in headers:
                val = (h.get('versions') or {}).get(package)
                if val not in values_from_versions:
                    values_from_versions.append(val)
            out[key] = values_from_versions[0] if len(values_from_versions) == 1 else values_from_versions or None
    for field, wall in (('setup_wall_p50_p90', None), ('verification_wall_p50_p90', 'verification')):
        out[field] = _quantiles([r.get('sandbox_setup_seconds') if wall is None else
                                 (r.get('wall_seconds') or {}).get(wall) for r, _, _, _ in records])
    kernel_keys = sorted({k for h in headers for k in h if k.startswith('kernel_code') or
                          (('agent' in k or 'verification' in k) and ('sha' in k) and k != 'agent_yaml_sha256')})
    out['kernel_code'] = {k: values((k,)) for k in kernel_keys} or None
    return out


def arm3_decision(on, off, p, h_count, smoke_invalid, vetoes, *, pairing_void_reason=None,
                  base_valid=True, identity_valid=True, smoke_bound=True, thinking_pass=True):
    if pairing_void_reason:
        return 'INVALID (pairing voided: ' + pairing_void_reason + ')'
    if not base_valid:
        return 'INVALID (base invalid/unruled)'
    if not identity_valid:
        return 'INVALID (identity mismatch)'
    if not thinking_pass:
        return 'INVALID (smoke i)'
    if not smoke_bound:
        return 'INVALID (smoke evidence not bound)'
    if smoke_invalid or h_count >= 5:
        return 'INVALID'
    if off >= on:
        return 'KEEP-OFF'
    if p >= .2:
        return 'NO-DIFFERENCE'
    return 'ON-BETTER-VETOED' if vetoes else 'ON-ADOPT'


def arm3_metrics(base_name, arm3_dirs, base_dirs, classifiers, smoke_json=None, *, base_verdict_json=None,
                 identity_json=None, bundle=None, transports=None, push_events=None):
    paths = [base.ARM_IDS, base.SCREENED_IDS, base.__file__, 'eval/plan007_report.py', 'eval/thinking_bound.py']
    if base_name == 'arm1':
        base_dirs = [str(Path(t).parent) for _, t, _, _ in base.PARTS]
        classifiers = dict(classifiers, **{str(Path(t).parent): (d, a) for _, t, d, a in base.PARTS})
    arms, envs, inventories = {}, {}, {}
    all_records = {}
    for name, dirs in (('arm3', arm3_dirs), ('base', base_dirs)):
        rec, inv, inputs, headers = aggregate_arm(dirs, classifiers)
        paths.extend(inputs)
        all_records[name] = rec
        inventories[name] = inv
        arms[name] = summarize_arm(rec, arm1=name == 'base' and base_name == 'arm1')
        envs[name] = environment_metrics(headers, rec)
    a, b = arms['arm3'], arms['base']
    on, off = [], []
    for (r, _, _, _), (s, _, _, _) in zip(all_records['arm3'], all_records['base']):
        base.assert_paired(r, s)
        if r.get('resolved') is True and s.get('resolved') is not True:
            on.append(r['instance_id'])
        if s.get('resolved') is True and r.get('resolved') is not True:
            off.append(r['instance_id'])
    p = sign_test(len(on), len(off))
    sa, sb = a['safety'], b['safety']
    checks = {key: isinstance(sa[key], dict) and sa[key]['count'] == 0 for key in ('test_files_edited', 'stray_files')}
    checks.update(total_wall_p90=sa['total_wall_complete'] and sb['total_wall_complete'] and
                  sa['total_wall_p90'] <= 1.10 * sb['total_wall_p90'],
                  empty_patch=sa['empty_patch_complete'] and sb['empty_patch_complete'] and sa['empty_patch']['count'] <= sb['empty_patch']['count'] + 3,
                  submitted_without_test=sa['submitted_without_test']['count'] <= sb['submitted_without_test']['count'] + 3)
    vetoes = [k for k, passed in checks.items() if not passed]
    if a['timeouts']['count'] > b['timeouts']['count'] + 2:
        vetoes.append('timeouts')
    if not a['timing']['timing_pass']:
        vetoes.append('timing')
    smoke = _read_json(smoke_json)
    smoke_invalid = smoke.get('overall') != 'PASS'
    for path in (smoke_json, base_verdict_json, identity_json):
        if path and _readable_file(path):
            paths.append(path)
    smoke_records = all_records['arm3'][:2]
    traces = [r[2] for r in smoke_records]
    smoke_dirs = {str(t.parent.parent.parent) for t in traces}
    schema = smoke.get('_schema')
    evidence = schema.get('input_shas', {}) if isinstance(schema, dict) else {}
    if not isinstance(evidence, dict):
        evidence = {}
    required_evidence = [*(classifiers[d][0] for d in smoke_dirs), *traces, *(Path(d) / 'timing.jsonl' for d in smoke_dirs)]
    smoke_bound = all(evidence.get(str(p)) == base.sha(p) for p in required_evidence)
    # A smoke report must name exactly the timing files that supplied the counted rows.
    smoke_bound = smoke_bound and {str(Path(p)) for p in evidence if Path(p).name == 'timing.jsonl'} == {
        str(Path(d) / 'timing.jsonl') for d in smoke_dirs}
    ci = thinking_criterion(traces)
    identity = identity_check(arm3_dirs, identity_json, bundle, transports or {}, smoke_dirs, push_events)
    recomputed = None
    if len(smoke_dirs) == 1:
        smoke_dir = next(iter(smoke_dirs))
        recomputed = arm3smoke_metrics(smoke_dir, classifiers[smoke_dir][0], identity_json, bundle,
                                      {smoke_dir: (transports or {}).get(smoke_dir)},
                                      {smoke_dir: (push_events or {}).get(smoke_dir)})
    failed_smoke = [k for k, c in recomputed['criteria'].items() if c['status'] != 'PASS'] if recomputed else ['iii']
    manifest = _manifest_path(bundle)
    if manifest and _readable_file(manifest):
        paths.append(manifest)
    base_verdict = _read_json(base_verdict_json)
    verdicts = [base_verdict[k] for k in ('decision', 'verdict') if k in base_verdict]
    # Plan 009 l.17-19: base = arm 2 iff plan 008 returned SHIP-ELIGIBLE; any other verdict means base = arm 1.
    base_valid = base_name == 'arm1' or bool(verdicts) and all(v == 'SHIP-ELIGIBLE' for v in verdicts)
    differences = [k for k in envs['arm3'] if envs['arm3'][k] != envs['base'][k]]
    envs.update(differences=differences, pairing_void_candidate='kernel_code' in differences)
    inputs = dict(arm3_timeouts=a['timeouts']['count'], base_timeouts=b['timeouts']['count'],
                  on_only=len(on), off_only=len(off), p=p, arm3_h=a['h_rows']['count'],
                  smoke_invalid=smoke_invalid, smoke_bound=smoke_bound, smoke_thinking=ci,
                  base_valid=base_valid, identity=identity, timeouts_pass='timeouts' not in vetoes,
                  timing_pass=a['timing']['timing_pass'], safety_checks=checks, vetoes=vetoes)
    result = dict(_schema=_schema('arm3', paths), n_rows=a['n_rows'], base_arm=base_name, inventory=inventories,
                base_validity=('VALID by dec069; ENV CONTROL: environment agreement with local gold calibration unmeasured'
                               if base_name == 'arm1' else verdicts if base_valid else 'INVALID (base invalid/unruled)'),
                primary=dict(on_only=_id_count(on), off_only=_id_count(off), p=p,
                             arm3_resolved=a['resolved'], base_resolved=b['resolved']), arms=arms,
                validity_literal='INVALID (H>=5)' if a['h_rows']['count'] >= 5 else 'VALID-pending-director',
                env_drift=envs, decision=arm3_decision(len(on), len(off), p, a['h_rows']['count'], smoke_invalid, vetoes,
                    pairing_void_reason='kernel agent/verification path differs' if envs['pairing_void_candidate'] else None,
                    base_valid=base_valid, identity_valid=identity['checked'], smoke_bound=smoke_bound,
                    thinking_pass=ci['status'] == 'PASS'),
                decision_inputs=inputs, label='thinking ACTIVE != budget enforced')
    if identity['checked'] and base_valid and not envs['pairing_void_candidate'] and failed_smoke:
        result['decision'] = 'INVALID (smoke recomputed: ' + ','.join(failed_smoke) + ')'
    inputs['smoke_recomputed'] = recomputed
    if not identity['checked']:
        # Rejected pushes are visible as first-attempt sensitivity, never counted.
        excluded = set(identity['mismatching_dirs'])
        counted = [r['instance_id'] for r, _, trace, _ in all_records['arm3']
                   if str(trace.parent.parent.parent) not in excluded]
        result['uncounted_sensitivity'] = dict(primary=result.pop('primary'), arms=result.pop('arms'))
        result['n_rows'] = len(counted)
        inventories['arm3'].update(complete=False, counted_instance_ids=counted,
                                  identity_excluded_dirs=identity['mismatching_dirs'],
                                  counted_missing=[i for i in base.ids_file(base.ARM_IDS) if i not in counted])
    return result


def arm3_cli(argv):
    import argparse
    parser = argparse.ArgumentParser(description='Plan 009 CPU/offline metrics')
    parser.add_argument('mode', choices=['arm3', 'arm3smoke'])
    parser.add_argument('--identity-json', required=True)
    parser.add_argument('--bundle', required=True)
    parser.add_argument('--transport', action='append', required=True)
    parser.add_argument('--push-event', action='append', required=True)
    def transports_for(args, dirs):
        transports = {}
        for value in args.transport:
            if '=' not in value:
                parser.error('--transport requires DIR=SHA256')
            directory, sha = value.rsplit('=', 1)
            if not re.fullmatch('[0-9a-f]{64}', sha):
                parser.error('--transport requires a SHA256')
            if str(Path(directory)) in transports:
                parser.error('duplicate --transport dir')
            transports[str(Path(directory))] = sha
        if set(transports) != {str(Path(d)) for d in dirs}:
            parser.error('--transport required for every arm3 dir')
        if not re.fullmatch(r'v01[0-9]+', args.bundle):
            parser.error('--bundle requires v01N')
        return transports
    def events_for(args, dirs):
        events = {}
        for value in args.push_event:
            if '=' not in value:
                parser.error('--push-event requires DIR=EVENT')
            directory, event = value.rsplit('=', 1)
            directory = str(Path(directory))
            if directory in events:
                parser.error('duplicate --push-event dir')
            events[directory] = event
        errors = _push_errors(dirs, events, {d for d, e in events.items() if e == 'smoke'}, args.mode == 'arm3smoke')
        if errors:
            parser.error('; '.join(errors))
        return events
    if argv[1] == 'arm3smoke':
        parser.add_argument('run_dir')
        parser.add_argument('classifier')
        parser.add_argument('out_json')
        args = parser.parse_args(argv[1:])
        out = arm3smoke_metrics(args.run_dir, args.classifier, args.identity_json, args.bundle,
                                 transports_for(args, [args.run_dir]), events_for(args, [args.run_dir]))
    else:
        parser.add_argument('base', choices=['arm1', 'arm2'])
        parser.add_argument('out_json')
        parser.add_argument('--arm3', nargs='+', required=True)
        parser.add_argument('--base-dirs', nargs='+', default=[])
        parser.add_argument('--classifiers', action='append', default=[])
        parser.add_argument('--smoke-json', required=True)
        parser.add_argument('--base-verdict-json')
        args = parser.parse_args(argv[1:])
        classifiers = {}
        for value in args.classifiers:
            if '=' not in value:
                parser.error('--classifiers requires DIR=D4_JSON,A2_JSON')
            directory, pair = value.split('=', 1)
            files = pair.split(',')
            if len(files) != 2:
                parser.error('--classifiers requires DIR=D4_JSON,A2_JSON')
            classifiers[str(Path(directory))] = files
        required = args.arm3 + (args.base_dirs if args.base == 'arm2' else [])
        if any(str(Path(d)) not in classifiers for d in required):
            parser.error('--classifiers required for every arm3 and arm2-base dir')
        if args.base == 'arm2' and not args.base_dirs:
            parser.error('--base-dirs required for arm2')
        try:
            out = arm3_metrics(args.base, args.arm3, args.base_dirs, classifiers, args.smoke_json,
                               base_verdict_json=args.base_verdict_json, identity_json=args.identity_json,
                               bundle=args.bundle, transports=transports_for(args, args.arm3),
                               push_events=events_for(args, args.arm3))
        except IncompleteRun as exc:
            print('INCOMPLETE arm3 inventory; no results written:', json.dumps(exc.args[0]))
            return 3
    Path(args.out_json).write_text(json.dumps(out, indent=2) + '\n')
    print(json.dumps({k: out[k] for k in ('n_rows', 'decision', 'overall', 'verdict') if k in out}))
    return 0


def main(argv=None):
    argv = sys.argv if argv is None else argv
    if len(argv) > 1 and argv[1] in ('arm3', 'arm3smoke'):
        return arm3_cli(argv)
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
