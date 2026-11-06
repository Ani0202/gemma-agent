"""Runs the exact gate command from bundles/31b/v010/sub_agents/submit_gate.yaml in temp git repos (CPU only)."""
import os, shutil, subprocess
from pathlib import Path
import pytest
import yaml

GATE = Path(__file__).resolve().parents[2] / 'bundles/31b/v010/sub_agents/submit_gate.yaml'


def gate_cmd(ws, counter):
    ins = yaml.safe_load(GATE.read_text())['instruction']
    lines = ins.splitlines()
    cmd = lines[lines.index(next(l for l in lines if 'exactly this command' in l)) + 1].strip()
    assert cmd.startswith('cd /workspace && ') and '/tmp/.submit_gate_n' in cmd
    return cmd.replace('/workspace', str(ws)).replace('/tmp/.submit_gate_n', str(counter))


def make_repo(tmp_path):
    ws = tmp_path / 'ws'
    for f in ['src/a.py', 'tests/test_a.py', 'pyproject.toml', 'src/latest_x.py']:
        (ws / f).parent.mkdir(parents=True, exist_ok=True)
        (ws / f).write_text('x\n')
    subprocess.run('git init -q && git add -A && git -c user.email=a@b -c user.name=a commit -qm i',
                   shell=True, check=True, cwd=ws)
    return ws


def run(cmd):
    return subprocess.run(['bash', '-c', cmd], capture_output=True, text=True).stdout.strip()


CASES = [([], ['EDIT_FIRST', 'EDIT_FIRST', 'SUBMIT', 'SUBMIT']), (['src/a.py'], ['SUBMIT']),
         (['tests/test_a.py'], ['EDIT_FIRST']), (['pyproject.toml'], ['EDIT_FIRST']),
         (['src/latest_x.py'], ['SUBMIT']), (['src/new.py'], ['SUBMIT']), (['tests/test_new.py'], ['EDIT_FIRST']),
         (['test_repro.py'], ['EDIT_FIRST']), (['DEL src/a.py'], ['SUBMIT']), (['conftest.py'], ['EDIT_FIRST']),
         (['src/tests/x.py'], ['EDIT_FIRST']), (['test/x.py'], ['EDIT_FIRST']), (['src/my file.py'], ['SUBMIT']),
         (['docs/x.md'], ['SUBMIT']), (['tests/test_a.py', 'src/a.py'], ['SUBMIT'])]


@pytest.mark.parametrize('edits,expected', CASES)
def test_gate(tmp_path, edits, expected):
    ws = make_repo(tmp_path)
    for e in edits:
        if e.startswith('DEL '):
            (ws / e[4:]).unlink()
        else:
            (ws / e).parent.mkdir(parents=True, exist_ok=True)
            with open(ws / e, 'a') as fh:
                fh.write('y\n')
    cmd = gate_cmd(ws, tmp_path / 'n')
    assert [run(cmd).replace('VERDICT=', '') for _ in expected] == expected


def test_no_braces_in_prompts():
    root = GATE.parents[1]
    for p in [GATE, root / 'prompts/system.md']:
        t = p.read_text().replace('{problem_description}', '')
        assert '{' not in t and '}' not in t, p
