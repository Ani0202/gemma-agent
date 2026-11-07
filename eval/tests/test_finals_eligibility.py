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
    assert all(s == 'BYTE_IDENTICAL' for s in r['files'].values())
    labels = sorted(k['knob'] for k in r['knobs'])
    assert labels == sorted(['max_time_minutes', 'max_tool_calls', 'max_turns',
                             'max_output_tokens', 'thinking_budget'] + ['max_output_tokens', 'thinking_budget'])


@pytest.mark.parametrize('name,old,new', [
    ('eval_config.yaml', 'max_time_minutes: 3.5', 'max_time_minutes: 3.0'),
    ('eval_config.yaml', 'max_tool_calls: 40', 'max_tool_calls: 30'),
    ('eval_config.yaml', 'max_turns: 50', 'max_turns: 49'),
    ('eval_config.yaml', '# comment', '# other comment'),
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
