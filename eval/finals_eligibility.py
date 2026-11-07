#!/usr/bin/env python3
"""Mechanical FINALS RULE check (dec 087 item 1, clause (b)), v2 (strict; codex review 091327).

A candidate final qualifies via a COMPLETE-scored reference bundle only if the two zips are
byte-identical except for single-line value changes of these knobs, each <= the reference value:
  eval_config.yaml (zip root)   evaluation.max_time_minutes / max_tool_calls / max_turns
  agent config documents         generate_content_config.max_output_tokens /
  (agent.yaml + every sub-agent  generate_content_config.thinking_config.thinking_budget
   reached via agent_tool         (inline, or in the file named by a top-level
   config_path, recursively)      `generate_content_config: !include F`: max_output_tokens /
                                  thinking_config.thinking_budget at that file's top level)
Rules (all conservative -> INELIGIBLE):
- Zip entries: unique names (also case-folded), normalized relative POSIX paths, regular files only
  (no directory entries, symlinks or other types, no encryption), no file/directory conflicts.
  The candidate and reference must have the same entry names.
- Every file not listed above must be byte-identical. A listed file may differ only on lines of the
  form `<indent><knob>: <number><trailing>` with identical prefix/suffix bytes, same line count; the
  changed value node must sit exactly at an allowed path (checked on the composed YAML node tree;
  duplicate mapping keys rejected). Comments, quoting, anchors, aliases, flow style: must be identical.
- Domains: max_output_tokens, max_tool_calls, max_turns int >= 1; thinking_budget int >= 0;
  max_time_minutes number > 0. No leading zeros, no sign, no exponent/underscore.
- Include / config_path targets are resolved both root-relative and relative to the containing
  document; if both resolutions exist as different entries the target is ambiguous and gets no
  allowance (must stay byte-identical).

Clause (a) (the candidate itself scored COMPLETE) is not checked here; --reference-lb checks that
the reference has status COMPLETE and that its sha256 matches the reference zip.

Usage: eval/finals_eligibility.py CANDIDATE.zip REFERENCE.zip [--reference-lb results/lb_X.json]
                                  [--out results/finals_eligibility_X_vs_Y.json]
Exit 0 = ELIGIBLE, 1 = INELIGIBLE, 2 = usage/input error.
"""
import argparse
import hashlib
import json
import posixpath
import re
import stat
import sys
import unicodedata
import zipfile

import yaml

EVAL_CONFIG = 'eval_config.yaml'
ROOT_AGENT = 'agent.yaml'
SCHEMA = 'finals_eligibility_v2'
INT_TAG = 'tag:yaml.org,2002:int'
FLOAT_TAG = 'tag:yaml.org,2002:float'
# knob -> (value regex, minimum, allow_float, strict minimum)
DOMAINS = {
    'max_time_minutes': (r'(?:0|[1-9][0-9]*)(?:\.[0-9]+)?', 0, True, True),
    'max_tool_calls': (r'[1-9][0-9]*', 1, False, False),
    'max_turns': (r'[1-9][0-9]*', 1, False, False),
    'max_output_tokens': (r'[1-9][0-9]*', 1, False, False),
    'thinking_budget': (r'0|[1-9][0-9]*', 0, False, False),
}
EVAL_PATHS = {('evaluation', k): k for k in ('max_time_minutes', 'max_tool_calls', 'max_turns')}
GCC_REL = {('max_output_tokens',): 'max_output_tokens',
           ('thinking_config', 'thinking_budget'): 'thinking_budget'}
LINE_RE = re.compile(rb'^([ ]*)([a-z_]+)(:[ ]+)([0-9.]+)([ \t]*\r?\n?)$')


class ZipProblem(Exception):
    pass


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read_zip(path):
    """Return ({name: bytes}, [problems]). Problems make the zip unusable for clause (b)."""
    files, problems, seen_fold = {}, [], {}
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        for i in infos:
            n = i.filename
            if n in files:
                problems.append(f'duplicate entry {n!r}')
                continue
            fold = unicodedata.normalize('NFC', n).casefold()
            if fold in seen_fold:
                problems.append(f'entry {n!r} collides with {seen_fold[fold]!r} (case/unicode fold)')
            seen_fold[fold] = n
            if n.endswith('/') or i.is_dir():
                problems.append(f'directory entry {n!r}')
                continue
            parts = n.split('/')
            if ('\\' in n or n.startswith('/') or any(p in ('', '.', '..') for p in parts)
                    or posixpath.normpath(n) != n or '\x00' in n):
                problems.append(f'non-normalized path {n!r}')
                continue
            mode = (i.external_attr >> 16) & 0xFFFF
            if mode and stat.S_IFMT(mode) not in (0, stat.S_IFREG):
                problems.append(f'entry {n!r} is not a regular file (mode {oct(mode)})')
                continue
            if i.flag_bits & 0x1:
                problems.append(f'entry {n!r} is encrypted')
                continue
            files[n] = z.read(i)
    names = set(files)
    for n in names:
        parts = n.split('/')
        for k in range(1, len(parts)):
            if '/'.join(parts[:k]) in names:
                problems.append(f'file/directory conflict: {"/".join(parts[:k])!r} vs {n!r}')
    return files, problems


class StrictComposer(yaml.SafeLoader):
    pass


def compose(data, name):
    """Composed YAML node tree (no construction, so custom tags are kept). Raises ValueError."""
    try:
        return yaml.compose(data.decode('utf-8'), Loader=StrictComposer)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f'{name}: YAML compose failed: {e}') from e


def walk_paths(root):
    """Yield (path tuple, node) for every node; alias cycles cut by node identity on the path.
    Raises ValueError on duplicate mapping keys."""
    stack = [((), root, frozenset())]
    while stack:
        path, node, onpath = stack.pop()
        yield path, node
        if id(node) in onpath:
            continue
        onpath = onpath | {id(node)}
        if isinstance(node, yaml.MappingNode):
            keys = []
            for k, v in node.value:
                key = (k.tag, k.value) if isinstance(k, yaml.ScalarNode) else ('<complex>', id(k))
                if key in keys:
                    raise ValueError(f'duplicate mapping key {k.value!r} at {"/".join(map(str, path))}')
                keys.append(key)
                label = k.value if isinstance(k, yaml.ScalarNode) else '<complex>'
                stack.append((path + (label,), v, onpath))
        elif isinstance(node, yaml.SequenceNode):
            for idx, v in enumerate(node.value):
                stack.append((path + (idx,), v, onpath))


def resolve(target, containing, names):
    """Resolve an include/config_path value; None if missing or ambiguous."""
    if not isinstance(target, str) or not target:
        return None
    cands = set()
    for base in ('', posixpath.dirname(containing)):
        p = posixpath.normpath(posixpath.join(base, target))
        if p in names:
            cands.add(p)
    return cands.pop() if len(cands) == 1 else None


def allowed_files(ref):
    """{file: {path tuple: knob}} for files whose knob lines may change (derived from REFERENCE)."""
    names, out, notes = set(ref), {}, []
    if EVAL_CONFIG in names:
        out[EVAL_CONFIG] = dict(EVAL_PATHS)
    todo, done = [ROOT_AGENT] if ROOT_AGENT in names else [], set()
    while todo:
        doc = todo.pop()
        if doc in done:
            continue
        done.add(doc)
        try:
            root = compose(ref[doc], doc)
            nodes = list(walk_paths(root)) if root is not None else []
        except ValueError as e:
            notes.append(f'agent doc {doc} not analyzable, no allowance: {e}')
            continue
        perms = out.setdefault(doc, {})
        for path, node in nodes:
            if (len(path) >= 2 and path[-1] == 'config_path' and 'agent_tool' in path
                    and isinstance(node, yaml.ScalarNode)):
                t = resolve(node.value, doc, names)
                if t is None:
                    notes.append(f'{doc}: config_path {node.value!r} missing/ambiguous')
                else:
                    todo.append(t)
        for path, node in nodes:
            if path == ('generate_content_config',):
                if isinstance(node, yaml.MappingNode):
                    for rel, knob in GCC_REL.items():
                        perms[('generate_content_config',) + rel] = knob
                elif isinstance(node, yaml.ScalarNode) and node.tag == '!include':
                    t = resolve(node.value, doc, names)
                    if t is None:
                        notes.append(f'{doc}: gcc include {node.value!r} missing/ambiguous, no allowance')
                    else:
                        out.setdefault(t, {}).update(GCC_REL)
    return out, notes


def parse_value(knob, text):
    pat, lo, allow_float, strict = DOMAINS[knob]
    if not re.fullmatch(pat, text):
        return None
    v = float(text) if allow_float else int(text)
    if (strict and v <= lo) or v < lo:
        return None
    return v


def compare_allowed(name, cdata, rdata, perms, knobs, violations):
    def bad(reason, line=None):
        violations.append({'file': name, 'path': [] if line is None else [f'line {line}'], 'reason': reason})

    cl, rl = cdata.splitlines(keepends=True), rdata.splitlines(keepends=True)
    if len(cl) != len(rl):
        return bad(f'line count {len(cl)} != reference {len(rl)}')
    changed = []
    for i, (c, r) in enumerate(zip(cl, rl)):
        if c == r:
            continue
        mc, mr = LINE_RE.match(c), LINE_RE.match(r)
        if not (mc and mr) or mc.group(1, 2, 3, 5) != mr.group(1, 2, 3, 5):
            return bad('non-knob line differs', i + 1)
        knob = mc.group(2).decode()
        if knob not in DOMAINS:
            return bad(f'key {knob!r} is not a knob', i + 1)
        changed.append((i, knob, mc.group(4).decode(), mr.group(4).decode()))
    if not changed:
        return None
    trees = {}
    for side, data in (('candidate', cdata), ('reference', rdata)):
        try:
            root = compose(data, f'{side} {name}')
            trees[side] = list(walk_paths(root)) if root is not None else []
        except ValueError as e:
            return bad(str(e))
    for i, knob, ctext, rtext in changed:
        for side, text in (('candidate', ctext), ('reference', rtext)):
            hits = [(p, n) for p, n in trees[side]
                    if isinstance(n, yaml.ScalarNode) and n.start_mark.line == i and n.value == text]
            if len(hits) != 1 or hits[0][1].style is not None or hits[0][1].tag not in (INT_TAG, FLOAT_TAG):
                return bad(f'{side} value {text!r} is not a single plain numeric scalar', i + 1)
            path = hits[0][0]
            same = [p for p, n in trees[side] if n is hits[0][1]]
            if any(perms.get(p) != knob for p in same):
                return bad(f'{side} {knob} at {["/".join(map(str, p)) for p in same]} is not an allowed path', i + 1)
        cv, rv = parse_value(knob, ctext), parse_value(knob, rtext)
        entry = {'file': name, 'path': list(path), 'knob': knob, 'candidate': ctext, 'reference': rtext}
        if cv is None or rv is None:
            entry['status'] = 'NOT_COMPARABLE'
            knobs.append(entry)
            bad(f'knob {knob} outside valid domain: {ctext!r} vs {rtext!r}', i + 1)
        elif cv <= rv:
            entry['status'] = 'EQUAL' if cv == rv else 'DECREASE'
            knobs.append(entry)
        else:
            entry['status'] = 'INCREASE'
            knobs.append(entry)
            bad(f'knob {knob} increased: {ctext} > {rtext}', i + 1)
    return None


def check(cand_zip, ref_zip):
    cand, cprob = read_zip(cand_zip)
    ref, rprob = read_zip(ref_zip)
    violations, knobs, files = [], [], {}
    for side, probs in (('candidate', cprob), ('reference', rprob)):
        for p in probs:
            violations.append({'file': f'<{side} zip>', 'path': [], 'reason': p})
    for name in sorted(set(cand) - set(ref)):
        violations.append({'file': name, 'path': [], 'reason': 'file only in candidate'})
        files[name] = 'ONLY_CANDIDATE'
    for name in sorted(set(ref) - set(cand)):
        violations.append({'file': name, 'path': [], 'reason': 'file only in reference'})
        files[name] = 'ONLY_REFERENCE'
    allowed, notes = allowed_files(ref)
    for name in sorted(set(cand) & set(ref)):
        if cand[name] == ref[name]:
            files[name] = 'BYTE_IDENTICAL'
            continue
        if name not in allowed:
            files[name] = 'DIFFERS'
            violations.append({'file': name, 'path': [], 'reason': 'not byte-identical (no knob allowance)'})
            continue
        before = len(violations)
        compare_allowed(name, cand[name], ref[name], allowed[name], knobs, violations)
        files[name] = 'DIFFERS' if len(violations) > before else 'KNOB_ONLY'
    return {'files': files, 'knobs': knobs, 'violations': violations,
            'allowed_files': {k: sorted('/'.join(map(str, p)) for p in v) for k, v in sorted(allowed.items())},
            'notes': notes, 'verdict': 'INELIGIBLE' if violations else 'ELIGIBLE'}


def check_reference_lb(lb_path, ref_sha):
    with open(lb_path) as f:
        lb = json.load(f)
    problems = []
    if lb.get('status') != 'COMPLETE':
        problems.append(f"reference lb status {lb.get('status')!r} != 'COMPLETE'")
    if lb.get('public_score') is None:
        problems.append('reference lb public_score missing')
    if lb.get('sha256') != ref_sha:
        problems.append(f"reference lb sha256 {lb.get('sha256')!r} != reference zip {ref_sha}")
    return {'path': lb_path, 'status': lb.get('status'), 'public_score': lb.get('public_score'),
            'submission_ref': lb.get('submission_ref'), 'problems': problems}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('candidate')
    ap.add_argument('reference')
    ap.add_argument('--reference-lb')
    ap.add_argument('--out')
    a = ap.parse_args(argv)
    try:
        res = check(a.candidate, a.reference)
    except (OSError, zipfile.BadZipFile, ValueError) as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 2
    out = {'_schema': SCHEMA, 'rule': 'ops/decisions/087-20261107T090954-880-from-builder.md item 1 (b)',
           'candidate': {'zip': a.candidate, 'sha256': sha256_file(a.candidate)},
           'reference': {'zip': a.reference, 'sha256': sha256_file(a.reference)}, **res}
    if a.reference_lb:
        out['reference_lb'] = check_reference_lb(a.reference_lb, out['reference']['sha256'])
        if out['reference_lb']['problems']:
            out['verdict'] = 'INELIGIBLE'
    text = json.dumps(out, indent=1, default=repr)
    if a.out:
        with open(a.out, 'w') as f:
            f.write(text + '\n')
    print(f"{out['verdict']}: {a.candidate} vs {a.reference} "
          f"({len(out['violations'])} violations"
          f"{', ref-lb problems ' + str(len(out['reference_lb']['problems'])) if a.reference_lb else ''})")
    for v in out['violations'][:20]:
        print(f"  - {v['file']} {'/'.join(map(str, v['path']))}: {v['reason']}")
    return 0 if out['verdict'] == 'ELIGIBLE' else 1


if __name__ == '__main__':
    sys.exit(main())
