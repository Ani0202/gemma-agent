"""Offline bundle validator and reproducible archive regression tests."""
import hashlib
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / 'bin/pack'
loader = importlib.machinery.SourceFileLoader('pack', str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
pack = importlib.util.module_from_spec(spec)
loader.exec_module(pack)
MODEL = 'gemma-4-31b-it-qat-w4a16-ct'


@pytest.fixture(params=['pyyaml', 'fallback'])
def backend(request, monkeypatch):
    if request.param == 'fallback':
        monkeypatch.setattr(pack, 'yaml', None)
    elif pack.yaml is None:
        pytest.skip('PyYAML not installed')


@pytest.fixture
def bundle(tmp_path, backend):
    root = tmp_path / '31b/v000'
    root.mkdir(parents=True)
    (root / 'agent.yaml').write_text(f'name: main\nmodel: {MODEL}\ninstruction: "Fix {{problem_description}}"\n')
    (root / 'eval_config.yaml').write_text('evaluation:\n  max_time_minutes: 5\n')
    return root


def add(root, name, content):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def append(root, text):
    with (root / 'agent.yaml').open('a') as stream:
        stream.write(text)


def invalid(root, match):
    with pytest.raises(pack.Invalid, match=match):
        pack.Bundle(root).validate()


def test_valid(bundle):
    assert pack.Bundle(bundle).validate() > 0


def test_missing_root(bundle):
    (bundle / 'agent.yaml').rename(bundle / 'nested.yaml')
    invalid(bundle, 'missing agent.yaml')


def test_multiple_roots(bundle):
    add(bundle, 'root_agent.yml', '{}')
    invalid(bundle, 'multiple root')


@pytest.mark.parametrize('text', ['name: [broken', 'name: first\nname: duplicate', 'name: !unknown bad'])
def test_yaml_parse_failure(bundle, text):
    add(bundle, 'bad.yaml', text)
    invalid(bundle, 'YAML|duplicate')


def test_size_strict_boundary(bundle, monkeypatch):
    current = sum(p.stat().st_size for p in bundle.rglob('*') if p.is_file())
    monkeypatch.setattr(pack, 'LIMIT', current)
    invalid(bundle, 'unpacked size')
    monkeypatch.setattr(pack, 'LIMIT', current+1)
    assert pack.Bundle(bundle).validate() == current


@pytest.mark.parametrize('name', ['weights.bin', 'file.zip', 'bad.exe', 'no_extension'])
def test_extensions(bundle, name):
    add(bundle, name, 'bad')
    invalid(bundle, 'extension')


@pytest.mark.parametrize('directory', [True, False])
def test_symlinks(bundle, directory):
    target = bundle / ('prompts' if directory else 'agent.yaml')
    if directory:
        target.mkdir()
    (bundle / 'link.md').symlink_to(target, target_is_directory=directory)
    invalid(bundle, 'symlink')


def test_special_file(bundle):
    os.mkfifo(bundle / 'pipe.txt')
    invalid(bundle, 'regular file')


@pytest.mark.parametrize('path', ['/tmp/file.md', '../file.md', 'a/../file.md', r'C:\file.md', r'a\..\file.md', '\0bad'])
def test_unsafe_paths(path):
    with pytest.raises(pack.Invalid, match='path'):
        pack.safe_path(path)


@pytest.mark.parametrize('field', ['instruction: !include', 'tools:\n  - agent_tool:\n      config_path:'])
@pytest.mark.parametrize('target', ['missing.yaml', '../outside.yaml', '/tmp/outside.yaml', '"bad\\u0000.yaml"'])
def test_reference_failures(bundle, field, target):
    # Replace the initial instruction to avoid duplicate-key failures masking paths.
    add(bundle, 'agent.yaml', f'name: main\nmodel: {MODEL}\n{field} {target}\n')
    invalid(bundle, 'missing reference|unsafe path|null bytes')


def test_include_and_subagent(bundle):
    add(bundle, 'prompts/system.md', 'Fix {problem_description}')
    add(bundle, 'configs/sampling.yaml', 'max_output_tokens: 32768\nthinking_config:\n  thinking_budget: 0\n  include_thoughts: false\n  thinking_level: none\n')
    add(bundle, 'sub_agents/child.yaml', f'name: child\nmodel: {MODEL}\n')
    add(bundle, 'agent.yaml', f'name: main\nmodel: {MODEL}\ninstruction: !include prompts/system.md\ngenerate_content_config: !include configs/sampling.yaml\ntools:\n  - agent_tool:\n      config_path: sub_agents/child.yaml\n      skip_summarization: true\n')
    assert pack.Bundle(bundle).validate()


@pytest.mark.parametrize('text', ['model: bad-model', 'name: missing_model', 'model: gemma-4-e4b-it-qat-w4a16-ct'])
def test_subagent_models(bundle, text):
    add(bundle, 'sub_agents/child.yaml', 'name: child\n' + text if not text.startswith('name:') else text)
    invalid(bundle, 'model')


@pytest.mark.parametrize('size', ['31b', '12b', 'e4b', 'e2b'])
def test_allowed_models(bundle, size):
    add(bundle, 'agent.yaml', f'name: main\nmodel: gemma-4-{size}-it-qat-w4a16-ct\n')
    assert pack.Bundle(bundle).validate()


def test_inline_agent_model(bundle):
    append(bundle, 'tools:\n  - agent_tool:\n      name: child\n      model: invalid\n')
    invalid(bundle, 'model')


def test_referenced_agent_requires_model(bundle):
    add(bundle, 'configs/child.yaml', 'name: child\n')
    append(bundle, 'sub_agents:\n  - config_path: configs/child.yaml\n')
    invalid(bundle, 'model')


@pytest.mark.parametrize('where', ['inline', 'include', 'prompt_file'])
def test_placeholder(bundle, where):
    if where == 'inline':
        append(bundle, 'global_instruction: "Use {hints}"\n')
    else:
        add(bundle, 'prompts/bad.md', 'Use {hints}')
        if where == 'include':
            append(bundle, 'global_instruction: !include prompts/bad.md\n')
    invalid(bundle, 'placeholder')


@pytest.mark.parametrize('file', ['agent.yaml', 'prompts/null.md'])
def test_null_text(bundle, file):
    with add(bundle, file, 'null').open('ab') as stream:
        stream.write(b'\0')
    invalid(bundle, 'null bytes')


@pytest.mark.parametrize('missing', ['adapter_config.json', 'adapter_model.safetensors', 'both'])
def test_adapter_missing(bundle, missing):
    append(bundle, 'adapter: main\n')
    for name in ('adapter_config.json', 'adapter_model.safetensors'):
        if name != missing and missing != 'both':
            add(bundle, f'adapters/main/{name}', '{}')
    invalid(bundle, 'missing reference')


def test_adapter_valid_binary(bundle):
    append(bundle, 'adapter: main\n')
    add(bundle, 'adapters/main/adapter_config.json', '{}')
    path = add(bundle, 'adapters/main/adapter_model.safetensors', '')
    path.write_bytes(b'\0\xff')
    assert pack.Bundle(bundle).validate()


@pytest.mark.parametrize('cap', ['6', '0', '-1', 'true', 'null', '"5"', '.nan', '.inf'])
def test_cap_invalid(bundle, cap):
    add(bundle, 'eval_config.yaml', f'evaluation:\n  max_time_minutes: {cap}\n')
    invalid(bundle, 'timing|cap')


@pytest.mark.parametrize('text', ['', 'evaluation: {}', 'evaluation: []'])
def test_cap_missing(bundle, text):
    add(bundle, 'eval_config.yaml', text)
    invalid(bundle, 'cap')


def test_eval_config_missing(bundle):
    (bundle / 'eval_config.yaml').unlink()
    invalid(bundle, 'eval_config.yaml')


def test_timing_boundary(bundle):
    add(bundle, 'eval_config.yaml', 'evaluation:\n  max_time_minutes: 5.04\n')
    assert pack.Bundle(bundle).validate()


@pytest.mark.parametrize('config', ['[]', '\n    thinking_budget: -1', '\n    thinking_budget: 32769', '\n    thinking_budget: true', '\n    thinking_level: extreme', '\n    include_thoughts: "true"', '\n    unknown: 1'])
def test_thinking_invalid(bundle, config):
    append(bundle, f'generate_content_config:\n  thinking_config: {config}\n')
    invalid(bundle, 'thinking_config')


@pytest.mark.parametrize('value', ['0', '32769', 'true'])
def test_output_limit(bundle, value):
    append(bundle, f'generate_content_config:\n  max_output_tokens: {value}\n')
    invalid(bundle, 'max_output_tokens')


def test_include_cycle(bundle):
    add(bundle, 'configs/a.yaml', 'config: !include a.yaml\n')
    invalid(bundle, 'cycle')


def test_include_depth(bundle):
    for index in range(12):
        add(bundle, f'configs/{index}.yaml', f'config: !include {index+1}.yaml\n' if index < 11 else '{}')
    invalid(bundle, 'depth')


def test_config_path_cycle(bundle):
    append(bundle, 'sub_agents:\n  - config_path: agent.yaml\n')
    invalid(bundle, 'cycle')


def test_zip_determinism_manifest_and_layout(bundle, tmp_path):
    add(bundle, 'MANIFEST.md', '# Baseline\nZip sha256: old\nzip sha256: duplicate\n')
    dist = tmp_path / 'dist'
    source = pack.Bundle(bundle)
    source.validate()
    pack.write_zip(source, dist)
    archive = dist / '31b-v000.zip'
    before = archive.read_bytes()
    for path in bundle.rglob('*'):
        os.utime(path, (1700000000, 1700000000))
    pack.write_zip(source, dist)
    assert archive.read_bytes() == before
    digest = hashlib.sha256(before).hexdigest()
    manifest = (bundle / 'MANIFEST.md').read_text()
    assert manifest.count('zip sha256:') == 1
    assert digest in manifest and '# Baseline' in manifest
    with zipfile.ZipFile(archive) as zipped:
        assert zipped.namelist() == sorted(zipped.namelist())
        assert 'agent.yaml' in zipped.namelist()
        assert 'MANIFEST.md' not in zipped.namelist()
        assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in zipped.infolist())


def test_cli_fallback_success_and_failure(bundle):
    result = subprocess.run([sys.executable, '-S', str(SCRIPT), str(bundle)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    (bundle / 'agent.yaml').unlink()
    result = subprocess.run([sys.executable, '-S', str(SCRIPT), str(bundle)], capture_output=True, text=True)
    assert result.returncode != 0 and 'FAIL:' in result.stderr and 'agent.yaml' in result.stderr


def test_plain_prompt_and_literal_block(bundle):
    add(bundle, 'agent.yaml', f'name: main\nmodel: {MODEL}\ninstruction: Fix {{problem_description}}\nglobal_instruction: |-\n  Work in /tmp.\n  Return a patch.\n')
    assert pack.Bundle(bundle).validate()


def test_non_agent_config_under_subagents(bundle):
    add(bundle, 'sub_agents/sampling.yaml', 'thinking_config:\n  thinking_budget: 32768\n  include_thoughts: true\n')
    assert pack.Bundle(bundle).validate()


def test_optional_placeholder_forbidden(bundle):
    append(bundle, 'global_instruction: "Use {hints?}"\n')
    invalid(bundle, 'placeholder')


@pytest.mark.parametrize('text', ['[]', 'null', '"hello"'])
def test_root_must_be_mapping(bundle, text):
    add(bundle, 'agent.yaml', text)
    invalid(bundle, 'mapping|YAML')


def test_decoded_null(bundle):
    append(bundle, 'global_instruction: "bad\\u0000text"\n')
    invalid(bundle, 'null bytes')


def test_manifest_reference(bundle):
    add(bundle, 'MANIFEST.md', 'instructions')
    append(bundle, 'global_instruction: !include MANIFEST.md\n')
    invalid(bundle, 'excluded from ZIP')


def test_cli_zip(bundle, tmp_path):
    script = tmp_path / 'repo/bin/pack'
    script.parent.mkdir(parents=True)
    shutil.copyfile(SCRIPT, script)
    result = subprocess.run([sys.executable, '-S', str(script), str(bundle), '--zip'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    archive = tmp_path / 'repo/dist/31b-v000.zip'
    assert archive.is_file()
    assert hashlib.sha256(archive.read_bytes()).hexdigest() in result.stdout
    assert f'size: {archive.stat().st_size} bytes' in result.stdout
    archive.unlink()
    (bundle / 'eval_config.yaml').unlink()
    result = subprocess.run([sys.executable, '-S', str(script), str(bundle), '--zip'], capture_output=True, text=True)
    assert result.returncode != 0 and not archive.exists()


def agent_config(**fields):
    return dict(name='main', model=MODEL, **fields)


def json_agent(bundle, **fields):
    import json
    add(bundle, 'agent.yaml', json.dumps(agent_config(**fields)))


@pytest.mark.parametrize('value', [None, '', ' ', 12, [], {}])
def test_agent_name_required(bundle, value):
    import json
    config = agent_config()
    if value is not None:
        config['name'] = value
    else:
        del config['name']
    add(bundle, 'agent.yaml', json.dumps(config))
    invalid(bundle, 'name required')


@pytest.mark.parametrize('location', ['tools', 'sub_agents'])
def test_nested_name_required(bundle, location):
    json_agent(bundle, **{location: [dict(model=MODEL)]})
    invalid(bundle, 'name required')


def test_harness_registry(bundle):
    assert pack.TOOLS == {'run_command', 'submit_patch', 'get_status', 'read_file',
                          'edit_file', 'write_file', 'get_code_neighbors',
                          'search_similar_code', 'get_code_subgraph'}
    json_agent(bundle, tools=sorted(pack.TOOLS))
    assert pack.Bundle(bundle).validate()


@pytest.mark.parametrize('tools', [['unknown'], ['load_skill'], {}, 'run_command', [42],
                                   [{'name': 'run_command'}]])
def test_bad_tools(bundle, tools):
    json_agent(bundle, tools=tools)
    invalid(bundle, 'tool|model')


@pytest.mark.parametrize('field', ['http_options', 'tools', 'system_instruction',
                                 'safety_settings', 'response_schema', 'unknown'])
def test_forbidden_generation_fields(bundle, field):
    json_agent(bundle, generate_content_config={field: None})
    invalid(bundle, 'generate_content_config')


@pytest.mark.parametrize('config', [[], 'bad', 4])
def test_generation_mapping(bundle, config):
    json_agent(bundle, generate_content_config=config)
    invalid(bundle, 'must be a mapping')


@pytest.mark.parametrize('skills', [['../outside'], ['/tmp'], [r'a\..\outside'],
                                    [r'C:\outside'], ['bad\0path'], [42], 'skills', {}])
def test_unsafe_skills(bundle, skills):
    json_agent(bundle, skills=skills)
    invalid(bundle, 'path|skills')


def test_missing_skill(bundle):
    json_agent(bundle, skills=['skills/example'])
    invalid(bundle, 'missing skill')
    (bundle / 'skills/example').mkdir(parents=True)
    invalid(bundle, 'SKILL.md')


def test_skill_count_boundary(bundle):
    add(bundle, 'skills/example/SKILL.md', '# Example')
    json_agent(bundle, skills=['skills/example'] * 1000)
    assert pack.Bundle(bundle).validate()
    json_agent(bundle, skills=['skills/example'] * 1001)
    invalid(bundle, 'max_skills')


def test_skill_size_boundary(bundle, monkeypatch):
    add(bundle, 'skills/example/SKILL.md', '# Example')
    resource = add(bundle, 'skills/example/resources/help.txt', 'help')
    size = len('# Examplehelp')
    monkeypatch.setattr(pack, 'MAX_SKILL_BYTES', size)
    json_agent(bundle, skills=['skills/example'])
    assert pack.Bundle(bundle).validate()
    resource.write_text('help!')
    invalid(bundle, 'skill size')


@pytest.mark.parametrize('key', ['timeout_seconds', 'max_tool_calls', 'max_turns'])
@pytest.mark.parametrize('value', ['0', '-1', 'true', '1.5', '"1"', 'null', '[]', '{}'])
def test_eval_positive_integer_invalid(bundle, key, value):
    add(bundle, 'eval_config.yaml', f'evaluation:\n  max_time_minutes: 5\n  {key}: {value}\n')
    invalid(bundle, key)


def test_eval_positive_integer_boundary(bundle):
    add(bundle, 'eval_config.yaml', 'evaluation:\n  max_time_minutes: 5\n'
        '  timeout_seconds: 1\n  max_tool_calls: 1\n  max_turns: 1\n')
    assert pack.Bundle(bundle).validate()


@pytest.mark.parametrize('value', [0, 501, True, 1.5, '2', None])
def test_loop_iterations_invalid(bundle, value):
    json_agent(bundle, agent_class='LoopAgent', max_iterations=value)
    invalid(bundle, 'max_iterations')


@pytest.mark.parametrize('value', [1, 500])
def test_loop_iterations_boundary(bundle, value):
    json_agent(bundle, agent_class='LoopAgent', max_iterations=value)
    assert pack.Bundle(bundle).validate()


def test_loop_default(bundle):
    json_agent(bundle, agent_class='LoopAgent')
    assert pack.Bundle(bundle).validate()


@pytest.mark.parametrize('field', ['sub_agents', 'tools'])
def test_agent_count_boundary_with_repeated_reference(bundle, field):
    import json
    add(bundle, 'child.yaml', json.dumps(agent_config(instruction='x')))
    reference = {'config_path': 'child.yaml'}
    if field == 'tools':
        reference = {'agent_tool': reference}
    json_agent(bundle, **{field: [reference] * 499})
    validator = pack.Bundle(bundle)
    assert validator.validate()
    assert validator.agent_count == 500
    json_agent(bundle, **{field: [reference] * 500})
    invalid(bundle, 'max_agents')


@pytest.mark.parametrize('field', ['sub_agents', 'tools'])
def test_agent_depth_boundary(bundle, field):
    import json

    def tree(depth):
        value = agent_config()
        for _ in range(depth):
            child = {'agent_tool': value} if field == 'tools' else value
            value = agent_config(**{field: [child]})
        return value

    add(bundle, 'agent.yaml', json.dumps(tree(50)))
    assert pack.Bundle(bundle).validate()
    add(bundle, 'agent.yaml', json.dumps(tree(51)))
    invalid(bundle, 'agent depth')


def test_referenced_agent_depth_boundary(bundle):
    import json
    for index in range(52):
        config = agent_config()
        if index < 51:
            config['sub_agents'] = [{'config_path': f'{index+1}.yaml'}]
        add(bundle, f'{index}.yaml', json.dumps(config))
    # Start at 1: fifty edges, with a separate standalone document containing no agent.
    add(bundle, '0.yaml', '{}')
    json_agent(bundle, sub_agents=[{'config_path': '2.yaml'}])
    assert pack.Bundle(bundle).validate()
    json_agent(bundle, sub_agents=[{'config_path': '1.yaml'}])
    invalid(bundle, 'agent depth')


def test_instruction_boundary_and_combined_fields(bundle):
    json_agent(bundle, instruction='x' * 1000000)
    assert pack.Bundle(bundle).validate()
    json_agent(bundle, instruction='x' * 1000000, global_instruction='x')
    invalid(bundle, 'instruction chars')


def test_total_instruction_boundary(bundle):
    import json
    add(bundle, 'child.yaml', json.dumps(agent_config(instruction='x' * 1000000)))
    json_agent(bundle, sub_agents=[{'config_path': 'child.yaml'}] * 10)
    validator = pack.Bundle(bundle)
    assert validator.validate()
    assert validator.instruction_chars == 10000000
    json_agent(bundle, instruction='x', sub_agents=[{'config_path': 'child.yaml'}] * 10)
    invalid(bundle, 'total instruction chars')


@pytest.mark.parametrize('constant,extra,match', [
    ('MAX_FILE_COUNT', 'extra.txt', 'max_file_count'),
    ('MAX_YAML_FILES', 'extra.yml', 'max_yaml_files'),
])
def test_file_count_boundaries(bundle, monkeypatch, constant, extra, match):
    # Exercise exact inclusive comparisons with small limits rather than 10k disk writes.
    monkeypatch.setattr(pack, constant, 2)
    assert pack.Bundle(bundle).validate()
    add(bundle, extra, '{}')
    invalid(bundle, match)


def test_yaml_size_boundary(bundle, monkeypatch):
    json_agent(bundle)
    size = (bundle / 'agent.yaml').stat().st_size
    monkeypatch.setattr(pack, 'MAX_YAML_BYTES', size)
    assert pack.Bundle(bundle).validate()
    with (bundle / 'agent.yaml').open('a') as stream:
        stream.write(' ')
    invalid(bundle, 'YAML size')


def test_cumulative_include_size_boundary(bundle, monkeypatch):
    add(bundle, 'data.txt', 'x' * 100)
    source = 'first: !include data.txt\nsecond: !include data.txt\n'
    add(bundle, 'included.yaml', source)
    size = len(source.encode()) + 200
    monkeypatch.setattr(pack, 'MAX_YAML_BYTES', size)
    assert pack.Bundle(bundle).validate()
    monkeypatch.setattr(pack, 'MAX_YAML_BYTES', size - 1)
    invalid(bundle, 'cumulative !include')


def test_nested_include_expansion(bundle, monkeypatch):
    add(bundle, 'data.txt', 'x' * 100)
    child = 'first: !include data.txt\nsecond: !include data.txt\n'
    add(bundle, 'child.yaml', child)
    parent = 'first: !include child.yaml\nsecond: !include child.yaml\n'
    add(bundle, 'included.yaml', parent)
    size = len(parent) + 2 * (len(child) + 200)
    monkeypatch.setattr(pack, 'MAX_YAML_BYTES', size)
    assert pack.Bundle(bundle).validate()
    monkeypatch.setattr(pack, 'MAX_YAML_BYTES', size - 1)
    invalid(bundle, 'cumulative !include')


def test_manifest_does_not_count_as_shipped_bytes_or_file(bundle, monkeypatch):
    current = pack.Bundle(bundle).validate()
    add(bundle, 'MANIFEST.md', 'x' * 10000)
    monkeypatch.setattr(pack, 'LIMIT', current + 1)
    monkeypatch.setattr(pack, 'MAX_FILE_COUNT', 2)
    assert pack.Bundle(bundle).validate() == current
    monkeypatch.setattr(pack, 'LIMIT', current)
    invalid(bundle, 'unpacked size')


def test_limit_constants():
    assert (pack.MAX_FILE_COUNT, pack.MAX_YAML_FILES, pack.MAX_YAML_BYTES,
            pack.MAX_SKILL_BYTES, pack.MAX_INSTRUCTION_CHARS,
            pack.MAX_TOTAL_INSTRUCTION_CHARS, pack.MAX_AGENTS, pack.MAX_DEPTH,
            pack.MAX_SKILLS) == (10000, 1000, 50 * 1024**2, 50 * 1024**2,
                                1000000, 10000000, 500, 50, 1000)


def test_existing_v000_bundles():
    if pack.yaml is None:
        pytest.skip('v000 uses multiline quoted YAML, which requires PyYAML')
    for track in ('31b', 'e4b'):
        assert pack.Bundle(SCRIPT.parent.parent / 'bundles' / track / 'v000').validate()


def test_instruction_include_character_boundary(bundle):
    # UTF-8 bytes and decoded character counts are deliberately different.
    add(bundle, 'prompt.txt', 'é' * 1000000)
    add(bundle, 'agent.yaml', f'name: main\nmodel: {MODEL}\ninstruction: !include prompt.txt\n')
    assert pack.Bundle(bundle).validate()
    add(bundle, 'prompt.txt', 'é' * 1000001)
    invalid(bundle, 'instruction chars')


def test_yaml_alias_agent_occurrences(bundle, backend):
    if pack.yaml is None:
        pytest.skip('aliases require PyYAML')
    source = f'name: main\nmodel: {MODEL}\nsub_agents:\n'
    source += f'  - &child\n    name: child\n    model: {MODEL}\n'
    source += '  - *child\n' * 498
    add(bundle, 'agent.yaml', source)
    validator = pack.Bundle(bundle)
    assert validator.validate()
    assert validator.agent_count == 500
    append(bundle, '  - *child\n')
    invalid(bundle, 'max_agents')


def test_standalone_reference_cycle(bundle):
    add(bundle, 'a.yaml', 'config_path: b.yaml\n')
    add(bundle, 'b.yaml', 'config_path: a.yaml\n')
    invalid(bundle, 'cycle')


def test_skill_count_across_referenced_agents(bundle):
    import json
    add(bundle, 'skills/example/SKILL.md', '# Example')
    add(bundle, 'child.yaml', json.dumps(agent_config(skills=['skills/example'] * 500)))
    json_agent(bundle, sub_agents=[{'config_path': 'child.yaml'}] * 2)
    assert pack.Bundle(bundle).validate()
    json_agent(bundle, skills=['skills/example'],
               sub_agents=[{'config_path': 'child.yaml'}] * 2)
    invalid(bundle, 'max_skills')


def test_referenced_name_required(bundle):
    import json
    add(bundle, 'child.yaml', json.dumps({'model': MODEL}))
    json_agent(bundle, sub_agents=[{'config_path': 'child.yaml'}])
    invalid(bundle, 'name required')


def test_standalone_reference_count_order(bundle):
    import json
    add(bundle, 'a.yaml', json.dumps(agent_config()))
    add(bundle, 'z.yaml', json.dumps(agent_config(sub_agents=[{'config_path': 'a.yaml'}])))
    validator = pack.Bundle(bundle)
    assert validator.validate()
    assert validator.agent_count == 3


def test_nested_manifest_is_shipped(bundle):
    add(bundle, 'nested/MANIFEST.md', 'included')
    validator = pack.Bundle(bundle)
    before = validator.validate()
    assert bundle / 'nested/MANIFEST.md' in validator.files
    assert before == sum(p.stat().st_size for p in validator.files)
