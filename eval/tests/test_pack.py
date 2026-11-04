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
    add(bundle, 'sub_agents/child.yaml', text)
    invalid(bundle, 'model')


@pytest.mark.parametrize('size', ['31b', '12b', 'e4b', 'e2b'])
def test_allowed_models(bundle, size):
    add(bundle, 'agent.yaml', f'model: gemma-4-{size}-it-qat-w4a16-ct\n')
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
    add(bundle, 'agent.yaml', f'model: {MODEL}\ninstruction: Fix {{problem_description}}\nglobal_instruction: |-\n  Work in /tmp.\n  Return a patch.\n')
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
