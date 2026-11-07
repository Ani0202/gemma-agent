#!/usr/bin/env python3
"""Mechanical FINALS RULE check (dec 087 item 1, clause (b)).

A candidate final qualifies via a COMPLETE-scored reference bundle only if the two zips differ
ONLY in knobs that cannot lengthen a task, each <= the reference value:
  eval_config.yaml  evaluation.max_time_minutes / max_tool_calls / max_turns
  generate_content_config (inline, or a file included via `generate_content_config: !include F`)
                    max_output_tokens / thinking_config.thinking_budget
Everything else (file set, prompts, instructions, sub-agent structure, tools, skills, adapters,
every other config key and value) must be identical. Non-YAML files must be byte-identical;
YAML files are compared after parsing (comments are inert), with custom tags (!include) kept.
Negative or non-numeric knob values are not comparable -> INELIGIBLE.

Clause (a) (the candidate itself scored COMPLETE) is not checked here; --reference-lb checks that
the reference has status COMPLETE and that its sha256 matches the reference zip.

Usage: eval/finals_eligibility.py CANDIDATE.zip REFERENCE.zip [--reference-lb results/lb_X.json]
                                  [--out results/finals_eligibility_X_vs_Y.json]
Exit 0 = ELIGIBLE, 1 = INELIGIBLE, 2 = usage/input error.
"""
import argparse
import hashlib
import json
import sys
import zipfile

import yaml

EVAL_CONFIG = 'eval_config.yaml'
EVAL_CAPS = ('max_time_minutes', 'max_tool_calls', 'max_turns')
SCHEMA = 'finals_eligibility_v1'


class Tagged:
    """A YAML node with a custom tag (e.g. !include path), compared by (tag, value)."""

    def __init__(self, tag, value):
        self.tag, self.value = tag, value

    def __eq__(self, other):
        return isinstance(other, Tagged) and (self.tag, self.value) == (other.tag, other.value)

    def __repr__(self):
        return f'{self.tag} {self.value!r}'


class TagLoader(yaml.SafeLoader):
    pass


def _construct_tagged(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node, deep=True)
    else:
        value = loader.construct_mapping(node, deep=True)
    return Tagged('!' + tag_suffix, value)


TagLoader.add_multi_constructor('!', _construct_tagged)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read_zip(path):
    with zipfile.ZipFile(path) as z:
        return {i.filename: z.read(i) for i in z.infolist() if not i.is_dir()}


def is_yaml(name):
    return name.endswith(('.yaml', '.yml'))


def load_yaml(data, name):
    try:
        return yaml.load(data.decode('utf-8'), Loader=TagLoader)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f'{name}: YAML parse failed: {e}') from e


def gcc_include_targets(parsed):
    """Files included as a whole generate_content_config (`generate_content_config: !include F`)."""
    out = set()

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == 'generate_content_config' and isinstance(v, Tagged) and v.tag == '!include':
                    out.add(str(v.value))
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, Tagged):
            walk(node.value)

    for doc in parsed.values():
        walk(doc)
    return out


def knob_name(fname, path, gcc_files):
    """Return the knob label if (file, key path) is a decreasable knob, else None."""
    if fname == EVAL_CONFIG and len(path) == 2 and path[0] == 'evaluation' and path[1] in EVAL_CAPS:
        return path[1]
    # Path relative to a generate_content_config root.
    rel = None
    if fname in gcc_files:
        rel = path
    elif 'generate_content_config' in path:
        idx = len(path) - 1 - path[::-1].index('generate_content_config')
        rel = path[idx + 1:]
    if rel is None:
        return None
    if rel == ('max_output_tokens',):
        return 'max_output_tokens'
    if rel == ('thinking_config', 'thinking_budget'):
        return 'thinking_budget'
    return None


def is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def compare_tree(fname, cand, ref, path, gcc_files, knobs, violations):
    if isinstance(cand, dict) and isinstance(ref, dict):
        for k in sorted(set(cand) | set(ref), key=str):
            p = path + (k,)
            if k not in cand:
                violations.append({'file': fname, 'path': list(p), 'reason': 'key removed in candidate'})
            elif k not in ref:
                violations.append({'file': fname, 'path': list(p), 'reason': 'key added in candidate'})
            else:
                compare_tree(fname, cand[k], ref[k], p, gcc_files, knobs, violations)
        return
    if isinstance(cand, list) and isinstance(ref, list):
        if len(cand) != len(ref):
            violations.append({'file': fname, 'path': list(path),
                               'reason': f'list length {len(cand)} != reference {len(ref)}'})
            return
        for i, (c, r) in enumerate(zip(cand, ref)):
            compare_tree(fname, c, r, path + (i,), gcc_files, knobs, violations)
        return
    if isinstance(cand, Tagged) and isinstance(ref, Tagged) and cand.tag == ref.tag:
        compare_tree(fname, cand.value, ref.value, path + (cand.tag,), gcc_files, knobs, violations)
        return
    knob = knob_name(fname, path, gcc_files)
    if knob is not None:
        entry = {'file': fname, 'path': list(path), 'knob': knob, 'candidate': cand, 'reference': ref}
        if not (is_number(cand) and is_number(ref)) or cand < 0 or ref < 0:
            entry['status'] = 'NOT_COMPARABLE'
            violations.append({'file': fname, 'path': list(path),
                               'reason': f'knob {knob} not a non-negative number: {cand!r} vs {ref!r}'})
        elif cand <= ref:
            entry['status'] = 'EQUAL' if cand == ref else 'DECREASE'
        else:
            entry['status'] = 'INCREASE'
            violations.append({'file': fname, 'path': list(path),
                               'reason': f'knob {knob} increased: {cand!r} > {ref!r}'})
        knobs.append(entry)
        return
    if type(cand) is not type(ref) or cand != ref:
        violations.append({'file': fname, 'path': list(path),
                           'reason': f'value differs: {cand!r} vs reference {ref!r}'})


def check(cand_zip, ref_zip):
    cand, ref = read_zip(cand_zip), read_zip(ref_zip)
    violations, knobs, files = [], [], {}
    for name in sorted(set(cand) - set(ref)):
        violations.append({'file': name, 'path': [], 'reason': 'file only in candidate'})
        files[name] = 'ONLY_CANDIDATE'
    for name in sorted(set(ref) - set(cand)):
        violations.append({'file': name, 'path': [], 'reason': 'file only in reference'})
        files[name] = 'ONLY_REFERENCE'
    common = sorted(set(cand) & set(ref))
    parsed_c = {n: load_yaml(cand[n], n) for n in common if is_yaml(n)}
    parsed_r = {n: load_yaml(ref[n], n) for n in common if is_yaml(n)}
    gcc_c, gcc_r = gcc_include_targets(parsed_c), gcc_include_targets(parsed_r)
    if gcc_c != gcc_r:
        violations.append({'file': '*', 'path': [], 'reason':
                           f'generate_content_config include targets differ: {sorted(gcc_c)} vs {sorted(gcc_r)}'})
    for name in common:
        if cand[name] == ref[name]:
            files[name] = 'BYTE_IDENTICAL'
            if is_yaml(name):  # still record knob values (all EQUAL) for the audit trail
                compare_tree(name, parsed_c[name], parsed_r[name], (), gcc_r, knobs, [])
            continue
        if not is_yaml(name):
            files[name] = 'DIFFERS'
            violations.append({'file': name, 'path': [], 'reason': 'non-YAML file not byte-identical'})
            continue
        before = len(violations)
        compare_tree(name, parsed_c[name], parsed_r[name], (), gcc_r, knobs, violations)
        files[name] = 'DIFFERS' if len(violations) > before else 'KNOB_OR_COMMENT_ONLY'
    return {'files': files, 'knobs': knobs, 'violations': violations,
            'verdict': 'INELIGIBLE' if violations else 'ELIGIBLE'}


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
