"""Tests for eval/finals_eligibility.py (dec 087 FINALS RULE clause (b))."""
import json
from pathlib import Path
import sys
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import finals_eligibility as fe  # noqa: E402

AGENT = """name: a
model: m
instruction: !include prompts/system.md
tools:
  - read_file
  - agent_tool:
      config_path: sub_agents/sub.yaml
generate_content_config: !include configs/sampling.yaml
"""
SAMPLING = """temperature: 0.2
max_output_tokens: 8192
thinking_config:
  thinking_budget: 4096
  include_thoughts: true
"""
SUB = """name: s
model: m
instruction: "do analysis"
tools: [read_file]
generate_content_config:
  temperature: 0.2
  max_output_tokens: 8192
  thinking_config:
    thinking_budget: 4096
    include_thoughts: true
"""
EVAL = """# comment
evaluation:
  timeout_seconds: 60
  max_tool_calls: 40
  max_time_minutes: 3.5
  max_turns: 50
"""
BASE = {'agent.yaml': AGENT, 'configs/sampling.yaml': SAMPLING, 'sub_agents/sub.yaml': SUB,
        'eval_config.yaml': EVAL, 'prompts/system.md': 'You are an agent.\n'}


def mkzip(tmp_path, name, files):
    p = tmp_path / name
    with zipfile.ZipFile(p, 'w') as z:
        for k, v in files.items():
            z.writestr(k, v)
    return str(p)


def run(tmp_path, **changes):
    files = dict(BASE)
    for k, v in changes.items():
        files[k] = v
    return fe.check(mkzip(tmp_path, 'c.zip', files), mkzip(tmp_path, 'r.zip', BASE))


def edit(name, old, new):
    assert old in BASE[name]
    return BASE[name].replace(old, new)


def test_identical_is_eligible(tmp_path):
    r = fe.check(mkzip(tmp_path, 'c.zip', BASE), mkzip(tmp_path, 'r.zip', BASE))
    assert r['verdict'] == 'ELIGIBLE'
    assert all(st == 'BYTE_IDENTICAL' for st in r['files'].values())
    assert r['knobs'] == []
    assert set(r['allowed_files']) == {'eval_config.yaml', 'agent.yaml', 'configs/sampling.yaml',
                                       'sub_agents/sub.yaml'}


@pytest.mark.parametrize('name,old,new', [
    ('eval_config.yaml', 'max_time_minutes: 3.5', 'max_time_minutes: 3.0'),
    ('eval_config.yaml', 'max_tool_calls: 40', 'max_tool_calls: 30'),
    ('eval_config.yaml', 'max_turns: 50', 'max_turns: 49'),
    ('configs/sampling.yaml', 'thinking_budget: 4096', 'thinking_budget: 0'),
    ('configs/sampling.yaml', 'max_output_tokens: 8192', 'max_output_tokens: 4096'),
    ('sub_agents/sub.yaml', 'thinking_budget: 4096', 'thinking_budget: 1024'),
    ('sub_agents/sub.yaml', 'max_output_tokens: 8192', 'max_output_tokens: 2048'),
])
def test_knob_decrease_eligible(tmp_path, name, old, new):
    r = run(tmp_path, **{name: edit(name, old, new)})
    assert r['verdict'] == 'ELIGIBLE', r['violations']


@pytest.mark.parametrize('name,old,new', [
    ('eval_config.yaml', 'max_time_minutes: 3.5', 'max_time_minutes: 4.0'),
    ('eval_config.yaml', '# comment', '# other comment'),  # v2: comments must be byte-identical
    ('eval_config.yaml', 'max_time_minutes: 3.5', 'max_time_minutes: 0'),
    ('eval_config.yaml', 'max_time_minutes: 3.5', 'max_time_minutes: 3.0  # note'),
    ('eval_config.yaml', 'max_tool_calls: 40', 'max_tool_calls: 0'),
    ('eval_config.yaml', 'max_tool_calls: 40', 'max_tool_calls: 030'),  # YAML 1.1 octal
    ('eval_config.yaml', 'max_turns: 50', 'max_turns: 4.5e1'),
    ('configs/sampling.yaml', 'max_output_tokens: 8192', 'max_output_tokens: 4095.5'),
    ('configs/sampling.yaml', 'max_output_tokens: 8192', 'max_output_tokens: 0'),
    ('configs/sampling.yaml', 'thinking_budget: 4096', 'thinking_budget: 1024.5'),
    ('configs/sampling.yaml', 'max_output_tokens: 8192', 'max_output_tokens: 1_000'),
    ('eval_config.yaml', 'max_tool_calls: 40', 'max_tool_calls: 41'),
    ('eval_config.yaml', 'max_turns: 50', 'max_turns: 60'),
    ('eval_config.yaml', 'timeout_seconds: 60', 'timeout_seconds: 30'),  # not a listed knob
    ('configs/sampling.yaml', 'thinking_budget: 4096', 'thinking_budget: 8192'),
    ('configs/sampling.yaml', 'thinking_budget: 4096', 'thinking_budget: -1'),  # dynamic
    ('configs/sampling.yaml', 'max_output_tokens: 8192', 'max_output_tokens: "4096"'),
    ('configs/sampling.yaml', 'temperature: 0.2', 'temperature: 0.1'),
    ('configs/sampling.yaml', 'include_thoughts: true', 'include_thoughts: false'),
    ('sub_agents/sub.yaml', 'max_output_tokens: 8192', 'max_output_tokens: 9000'),
    ('sub_agents/sub.yaml', '"do analysis"', '"do analysis."'),
    ('sub_agents/sub.yaml', 'tools: [read_file]', 'tools: [read_file, write_file]'),
    ('agent.yaml', '  - read_file\n', '  - read_file\n  - write_file\n'),
    ('agent.yaml', 'prompts/system.md', 'prompts/other.md'),
    ('prompts/system.md', 'You are an agent.', 'You are an agent!'),
])
def test_other_change_ineligible(tmp_path, name, old, new):
    r = run(tmp_path, **{name: edit(name, old, new)})
    assert r['verdict'] == 'INELIGIBLE'


def test_thinking_key_removed_ineligible(tmp_path):
    s = BASE['configs/sampling.yaml'].replace('  thinking_budget: 4096\n', '')
    assert run(tmp_path, **{'configs/sampling.yaml': s})['verdict'] == 'INELIGIBLE'


def test_extra_file_ineligible(tmp_path):
    assert run(tmp_path, **{'skills/x.md': 'skill'})['verdict'] == 'INELIGIBLE'


def test_missing_file_ineligible(tmp_path):
    files = {k: v for k, v in BASE.items() if k != 'prompts/system.md'}
    r = fe.check(mkzip(tmp_path, 'c.zip', files), mkzip(tmp_path, 'r.zip', BASE))
    assert r['verdict'] == 'INELIGIBLE'


def test_knob_name_outside_gcc_not_allowed(tmp_path):
    # max_output_tokens under a non-generation key is not a knob.
    a = AGENT + 'meta:\n  max_output_tokens: 10\n'
    c = AGENT + 'meta:\n  max_output_tokens: 5\n'
    r = fe.check(mkzip(tmp_path, 'c.zip', {**BASE, 'agent.yaml': c}),
                 mkzip(tmp_path, 'r.zip', {**BASE, 'agent.yaml': a}))
    assert r['verdict'] == 'INELIGIBLE'


def test_cli_reference_lb(tmp_path, capsys):
    c = mkzip(tmp_path, 'c.zip', BASE)
    r = mkzip(tmp_path, 'r.zip', BASE)
    lb = tmp_path / 'lb.json'
    lb.write_text(json.dumps({'status': 'COMPLETE', 'public_score': 0.1, 'sha256': fe.sha256_file(r)}))
    out = tmp_path / 'o.json'
    assert fe.main([c, r, '--reference-lb', str(lb), '--out', str(out)]) == 0
    assert json.loads(out.read_text())['verdict'] == 'ELIGIBLE'
    lb.write_text(json.dumps({'status': 'PENDING', 'public_score': None, 'sha256': fe.sha256_file(r)}))
    assert fe.main([c, r, '--reference-lb', str(lb)]) == 1
    lb.write_text(json.dumps({'status': 'COMPLETE', 'public_score': 0.1, 'sha256': 'x'}))
    assert fe.main([c, r, '--reference-lb', str(lb)]) == 1


# ---- v2 regressions from codex review ops/codex/review-20261107T091327.md ----

def test_skill_asset_gcc_knob_not_allowed(tmp_path):  # BLOCKING 1
    a = 'parameters:\n  generate_content_config:\n    max_output_tokens: 8192\n'
    r = fe.check(mkzip(tmp_path, 'c.zip', {**BASE, 'skills/config.yaml': a.replace('8192', '1')}),
                 mkzip(tmp_path, 'r.zip', {**BASE, 'skills/config.yaml': a}))
    assert r['verdict'] == 'INELIGIBLE'


def test_gcc_knob_in_non_agent_location_of_agent_doc(tmp_path):
    a = AGENT + 'meta:\n  generate_content_config:\n    max_output_tokens: 10\n'
    r = fe.check(mkzip(tmp_path, 'c.zip', {**BASE, 'agent.yaml': a.replace(': 10', ': 5')}),
                 mkzip(tmp_path, 'r.zip', {**BASE, 'agent.yaml': a}))
    assert r['verdict'] == 'INELIGIBLE'


def test_relative_include_wrong_file(tmp_path):  # BLOCKING 2
    sub = SUB.split('generate_content_config:')[0] + 'generate_content_config: !include sampling.yaml\n'
    ref = {**BASE, 'sub_agents/sub.yaml': sub, 'sampling.yaml': SAMPLING, 'sub_agents/sampling.yaml': SAMPLING}
    cand = {**ref, 'sampling.yaml': SAMPLING.replace('8192', '4096')}
    r = fe.check(mkzip(tmp_path, 'c.zip', cand), mkzip(tmp_path, 'r.zip', ref))
    assert r['verdict'] == 'INELIGIBLE'  # ambiguous target -> no allowance for either file
    cand = {**ref, 'sub_agents/sampling.yaml': SAMPLING.replace('8192', '4096')}
    assert fe.check(mkzip(tmp_path, 'c2.zip', cand), mkzip(tmp_path, 'r.zip', ref))['verdict'] == 'INELIGIBLE'


def test_relative_include_unambiguous_doc_relative(tmp_path):
    sub = SUB.split('generate_content_config:')[0] + 'generate_content_config: !include samp2.yaml\n'
    ref = {**BASE, 'sub_agents/sub.yaml': sub, 'sub_agents/samp2.yaml': SAMPLING}
    cand = {**ref, 'sub_agents/samp2.yaml': SAMPLING.replace('8192', '4096')}
    r = fe.check(mkzip(tmp_path, 'c.zip', cand), mkzip(tmp_path, 'r.zip', ref))
    assert r['verdict'] == 'ELIGIBLE', r['violations']


@pytest.mark.parametrize('name,data', [  # BLOCKING 3
    ('skills/recipe.yaml', ['# do X\nk: 1\n', '# do Y\nk: 1\n']),
    ('agent.yaml', [AGENT, 'instruction: "DIFFERENT PROMPT"\n' + AGENT]),
    ('skills/keys.yaml', ['1: a\n', 'true: a\n']),
])
def test_yaml_asset_byte_identity(tmp_path, name, data):
    r = fe.check(mkzip(tmp_path, 'c.zip', {**BASE, name: data[1]}),
                 mkzip(tmp_path, 'r.zip', {**BASE, name: data[0]}))
    assert r['verdict'] == 'INELIGIBLE'


def test_duplicate_key_shadowing_knob(tmp_path):
    a = BASE['configs/sampling.yaml'] + 'max_output_tokens: 8192\n'
    c = BASE['configs/sampling.yaml'].replace('8192', '4096') + 'max_output_tokens: 8192\n'
    r = fe.check(mkzip(tmp_path, 'c.zip', {**BASE, 'configs/sampling.yaml': c}),
                 mkzip(tmp_path, 'r.zip', {**BASE, 'configs/sampling.yaml': a}))
    assert r['verdict'] == 'INELIGIBLE'


def _rawzip(path, entries):
    with zipfile.ZipFile(path, 'w') as z:
        for info, data in entries:
            z.writestr(info, data)
    return str(path)


def test_zip_structure_problems(tmp_path):  # BLOCKING 4
    import warnings
    ref = mkzip(tmp_path, 'r.zip', BASE)
    base = [(k, v) for k, v in BASE.items()]
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        dup = _rawzip(tmp_path / 'dup.zip', [('prompts/system.md', 'EVIL')] + base)
    assert fe.check(dup, ref)['verdict'] == 'INELIGIBLE'
    link = zipfile.ZipInfo('prompts/system.md')
    link.external_attr = (0o120777 << 16)
    sl = _rawzip(tmp_path / 'sl.zip', [(link, BASE['prompts/system.md'])] +
                 [(k, v) for k, v in base if k != 'prompts/system.md'])
    assert fe.check(sl, ref)['verdict'] == 'INELIGIBLE'
    d = _rawzip(tmp_path / 'd.zip', base + [(zipfile.ZipInfo('agent.yaml/'), '')])
    assert fe.check(d, ref)['verdict'] == 'INELIGIBLE'
    conflict = _rawzip(tmp_path / 'cf.zip', base + [('agent.yaml/x.md', 'x')])
    assert fe.check(conflict, ref)['verdict'] == 'INELIGIBLE'
    for bad in ('./x.md', 'a/../x.md', '/abs.md', 'a\\b.md', 'PROMPTS/system.md'):
        z = _rawzip(tmp_path / 'b.zip', base + [(bad, 'x')])
        assert fe.check(z, ref)['verdict'] == 'INELIGIBLE', bad


def test_recursive_alias_no_crash(tmp_path):
    a = AGENT + 'cycle: &cycle [*cycle]\n'
    e = BASE['eval_config.yaml']
    r = fe.check(mkzip(tmp_path, 'c.zip', {**BASE, 'agent.yaml': a, 'eval_config.yaml': e.replace('50', '40')}),
                 mkzip(tmp_path, 'r.zip', {**BASE, 'agent.yaml': a}))
    assert r['verdict'] == 'ELIGIBLE', r['violations']


def test_real_v002_knob_decrease(tmp_path):
    ref = Path(__file__).resolve().parents[2] / 'dist' / '31b-v002.zip'
    if not ref.exists():
        pytest.skip('dist/31b-v002.zip not present')
    with zipfile.ZipFile(ref) as z:
        files = {n: z.read(n) for n in z.namelist()}
    files['configs/sampling.yaml'] = files['configs/sampling.yaml'].replace(b'max_output_tokens: 8192', b'max_output_tokens: 4096')
    files['eval_config.yaml'] = files['eval_config.yaml'].replace(b'max_time_minutes: 3.5', b'max_time_minutes: 3.0')
    files['sub_agents/code_analyzer.yaml'] = files['sub_agents/code_analyzer.yaml'].replace(b'thinking_budget: 4096', b'thinking_budget: 2048')
    r = fe.check(mkzip(tmp_path, 'c.zip', files), str(ref))
    assert r['verdict'] == 'ELIGIBLE', r['violations']
    assert sorted(k['status'] for k in r['knobs']) == ['DECREASE'] * 3
    bad = dict(files)
    bad['agent.yaml'] = b'instruction: "DIFFERENT PROMPT"\n' + bad['agent.yaml']
    assert fe.check(mkzip(tmp_path, 'c2.zip', bad), str(ref))['verdict'] == 'INELIGIBLE'
