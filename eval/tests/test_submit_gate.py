"""Runs the exact gate command from bundles/31b/v010/sub_agents/submit_gate.yaml in temp git repos (CPU only).

Eligibility must equal the harness rule: a path counts iff swegemma.harness.verification._is_protected_test_or_config_path
is False for it (task-specific extra test_files are unknown to the gate; residual, see eval/plans/008.md D72)."""
import os, subprocess
from pathlib import Path
import pytest
import yaml

GATE = Path(__file__).resolve().parents[2] / 'bundles/31b/v010/sub_agents/submit_gate.yaml'


def gate_cmd(ws, counter):
    ins = yaml.safe_load(GATE.read_text())['instruction']
    lines = ins.splitlines()
    cmd = lines[lines.index(next(l for l in lines if 'exactly this command' in l)) + 2].strip()
    assert cmd.startswith('cd /workspace && ') and cmd.count('/tmp/.submit_gate_n') == 2
    return cmd.replace('/workspace', str(ws)).replace('/tmp/.submit_gate_n', str(counter))


BASE_FILES = ['src/a.py', 'tests/test_a.py', 'pyproject.toml', 'src/latest_x.py', 'tox.ini', 'testing/helper.py',
              'Tests/helper.py', 'tests/data.json', 'docs/x.md']


def make_repo(tmp_path, tag=True):
    ws = tmp_path / 'ws'
    for f in BASE_FILES:
        (ws / f).parent.mkdir(parents=True, exist_ok=True)
        (ws / f).write_text('x\n')
    subprocess.run('git init -q && git add -A && git -c user.email=a@b -c user.name=a commit -qm i'
                   + (' && git tag _swegemma_baseline' if tag else ''), shell=True, check=True, cwd=ws)
    return ws


def run(cmd):
    p = subprocess.run(['bash', '-c', cmd], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    out = p.stdout.strip().splitlines()
    assert len(out) == 2 and out[0].startswith('GATE call='), p.stdout
    return out


def verdict(out):
    v = out[1].replace('VERDICT=', '')
    return v.replace(' reason=', ':')


def apply(ws, edits):
    for e in edits:
        if e.startswith('DEL '):
            (ws / e[4:]).unlink()
        elif e.startswith('MV '):
            a, b = e[3:].split(' -> ')
            (ws / b).parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['git', 'mv', a, b], check=True, cwd=ws)
        else:
            (ws / e).parent.mkdir(parents=True, exist_ok=True)
            with open(ws / e, 'a') as fh:
                fh.write('y\n')


S, E, F = 'SUBMIT:changes', 'EDIT_FIRST', 'SUBMIT:forced'
CASES = [([], [E, E, F, F]), (['src/a.py'], [S]),
         (['tests/test_a.py'], [E]), (['pyproject.toml'], [E]), (['tox.ini'], [E]),
         (['testing/helper.py'], [E]), (['Tests/helper.py'], [E]), (['tests/test a.py'], [E]),
         (['src/latest_x.py'], [S]), (['src/new.py'], [S]), (['tests/test_new.py'], [E]),
         (['test_repro.py'], [E]), (['DEL src/a.py'], [S]), (['conftest.py'], [E]), (['x.pth'], [E]),
         (['src/tests/x.py'], [E]), (['test/x.py'], [E]), (['src/my file.py'], [S]), (['src/a test_b.py'], [S]),
         (['src/dir with space/test_q.py'], [E]), (['src/sp ace.py'], [S]), (['src/ünï.py'], [S]),
         # non-.py files under tests/ are NOT protected by the harness, so they stay in the patch: eligible
         (['tests/data.json'], [S]),
         # prose/doc files stay in the patch (harness keeps them): eligible by design, not a "source" check
         (['docs/x.md'], [S]),
         (['tests/test_a.py', 'src/a.py'], [S]),
         (['MV src/a.py -> tests/a.py'], [S]),  # old path src/a.py deleted -> kept in patch
         ]


@pytest.mark.parametrize('edits,expected', CASES)
def test_gate(tmp_path, edits, expected):
    ws = make_repo(tmp_path)
    apply(ws, edits)
    cmd = gate_cmd(ws, tmp_path / 'n')
    got = [verdict(run(cmd)) for _ in expected]
    assert got == expected


@pytest.mark.parametrize('edits', [c[0] for c in CASES])
def test_parity_with_harness(tmp_path, edits):
    """Gate kept_files == number of changed paths the harness would keep (same rule function)."""
    from swegemma.harness.verification import _is_protected_test_or_config_path as prot
    ws = make_repo(tmp_path)
    apply(ws, edits)
    subprocess.run('git add -N .', shell=True, cwd=ws, check=True)
    names = subprocess.run(['git', 'diff', '--no-renames', '--name-only', '-z', '_swegemma_baseline'],
                           capture_output=True, text=True, cwd=ws, check=True).stdout.split('\0')
    want = sum(1 for f in names if f and not prot(f))
    out = run(gate_cmd(ws, tmp_path / 'n'))
    assert out[0] == f'GATE call=1 kept_files={want}'


def test_no_baseline_tag_falls_back_to_head(tmp_path):
    ws = make_repo(tmp_path, tag=False)
    apply(ws, ['src/a.py'])
    assert verdict(run(gate_cmd(ws, tmp_path / 'n'))) == S


def test_counter_unwritable_forces_submit(tmp_path):
    ws = make_repo(tmp_path)
    cmd = gate_cmd(ws, tmp_path / 'nodir' / 'n')  # parent missing -> write fails -> n=9
    assert [verdict(run(cmd)) for _ in range(2)] == [F, F]


def test_counter_garbage_is_reset(tmp_path):
    ws = make_repo(tmp_path)
    (tmp_path / 'n').write_text('abc\n')
    cmd = gate_cmd(ws, tmp_path / 'n')
    assert [verdict(run(cmd)) for _ in range(3)] == [E, E, F]


def test_check_error_fails_open(tmp_path):
    ws = make_repo(tmp_path)
    cmd = gate_cmd(ws, tmp_path / 'n').replace('python3 -c', 'false_python3_missing -c')
    assert verdict(run(cmd)) == 'SUBMIT:check_error'


def test_not_a_git_repo_fails_open(tmp_path):
    ws = tmp_path / 'plain'
    ws.mkdir()
    assert verdict(run(gate_cmd(ws, tmp_path / 'n'))) == 'SUBMIT:check_error'


def test_no_braces_in_prompts():
    root = GATE.parents[1]
    for p in [GATE, root / 'prompts/system.md']:
        t = p.read_text().replace('{problem_description}', '')
        assert '{' not in t and '}' not in t, p
