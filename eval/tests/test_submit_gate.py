"""Runs the exact gate command from bundles/31b/v010/sub_agents/submit_gate.yaml in temp git repos (CPU only).

Eligibility must equal the stripped patch rule: an entry counts iff every path is unprotected (task-specific extra test_files are unknown to the gate; residual, see eval/plans/008.md D72)."""
import os, subprocess
from pathlib import Path
import pytest
import yaml

GATE = Path(__file__).resolve().parents[2] / 'bundles/31b/v010/sub_agents/submit_gate.yaml'


def gate_cmd(ws, counter):
    ins = yaml.safe_load(GATE.read_text())['instruction']
    lines = ins.splitlines()
    cmd = lines[lines.index(next(l for l in lines if 'exactly this command' in l)) + 2].strip()
    assert cmd.startswith('cd /workspace && ') and cmd.count('/tmp/.submit_gate_n') == 3
    return cmd.replace('/workspace', str(ws)).replace('/tmp/.submit_gate_n', str(counter))


BASE_FILES = ['src/a.py', 'tests/test_a.py', 'pyproject.toml', 'src/latest_x.py', 'tox.ini', 'testing/helper.py',
              'Tests/helper.py', 'tests/data.json', 'docs/x.md']


def make_repo(tmp_path, tag=True, reverse=False):
    ws = tmp_path / 'ws'
    files = [f for f in BASE_FILES if not (reverse and f == 'src/a.py')]
    if reverse:
        files.append('tests/a.py')
    for f in files:
        (ws / f).parent.mkdir(parents=True, exist_ok=True)
        (ws / f).write_text(f + '\nx\n')
    subprocess.run('git init -q && git add -A && git -c user.email=a@b -c user.name=a commit -qm i'
                   + (' && git tag _swegemma_baseline' if tag else ''), shell=True, check=True, cwd=ws)
    return ws


def run(cmd):
    p = subprocess.run(['/bin/bash', '-c', cmd], capture_output=True, text=True)
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
        elif e == 'COPIES':
            subprocess.run(['git', 'config', 'diff.renames', 'copies'], check=True, cwd=ws)
        elif e.startswith('CP '):
            import shutil
            a, b = e[3:].split(' -> ')
            (ws / b).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ws / a, ws / b)
        elif e.startswith('MODE '):
            (ws / e[5:]).chmod(0o755)
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
         (['MV src/a.py -> tests/a.py'], [E]),
         (['MV tests/a.py -> src/a.py'], [E]),
         (['MV src/a.py -> src2/a.py'], [S]),
         (['CP src/a.py -> src/b.py'], [S]),
         (['COPIES', 'CP src/a.py -> src/b.py', 'src/a.py'], [S]),
         (['COPIES', 'CP tests/test_a.py -> src/b.py', 'tests/test_a.py'], [E]),
         (['DEL tests/test_a.py'], [E]),
         (['MODE src/a.py'], [S]),
         (['src/Tests/helper.py'], [E]),
         (['src/testing/helper.py'], [E]),
         ]


@pytest.mark.parametrize('edits,expected', CASES)
def test_gate(tmp_path, edits, expected):
    ws = make_repo(tmp_path, reverse='MV tests/a.py -> src/a.py' in edits)
    apply(ws, edits)
    cmd = gate_cmd(ws, tmp_path / 'n')
    got = [verdict(run(cmd)) for _ in expected]
    assert got == expected


@pytest.mark.parametrize('edits', [c[0] for c in CASES])
@pytest.mark.parametrize('baseline', ['tag', 'branch'])
def test_stripped_patch_parity(tmp_path, edits, baseline):
    from swegemma.harness.verification import strip_protected_files_from_patch
    ws = make_repo(tmp_path, tag=baseline == 'tag', reverse='MV tests/a.py -> src/a.py' in edits)
    if baseline == 'branch':
        subprocess.run(['git', 'branch', '_swegemma_baseline'], cwd=ws, check=True)
    apply(ws, edits)
    subprocess.run(['git', 'add', '-N', '.'], cwd=ws, check=True)
    patch = subprocess.run(['git', 'diff', '--binary', '_swegemma_baseline'],
                           capture_output=True, text=True, cwd=ws, check=True).stdout
    if 'COPIES' in edits:
        statuses = subprocess.run(['git', 'diff', '--name-status', '-z', '_swegemma_baseline'],
                                 capture_output=True, text=True, cwd=ws, check=True).stdout
        assert 'C100\0' in statuses, 'fixture must exercise two-path copy entries'
    want = bool(strip_protected_files_from_patch(patch))
    out = run(gate_cmd(ws, tmp_path / 'n'))
    kept = int(out[0].split('kept_files=')[1])
    assert (kept > 0) == want, 'gate/stripped patch eligibility differs'


# Keep the 26-case path-predicate parity check independently of patch section handling.
PREDICATE_PATHS = [
    'src/a.py', 'tests/test_a.py', 'pyproject.toml', 'tox.ini', 'testing/helper.py',
    'Tests/helper.py', 'tests/test a.py', 'src/latest_x.py', 'src/new.py', 'tests/test_new.py',
    'test_repro.py', 'conftest.py', 'x.pth', 'src/tests/x.py', 'test/x.py',
    'src/my file.py', 'src/a test_b.py', 'src/dir with space/test_q.py', 'src/sp ace.py',
    'src/ünï.py', 'tests/data.json', 'docs/x.md', 'setup.cfg', 'pytest.ini',
    'sitecustomize.py', 'src/a_test.py',
]


@pytest.mark.parametrize('path', PREDICATE_PATHS)
def test_predicate_parity(path):
    from swegemma.harness.verification import _is_protected_test_or_config_path as prot
    import pathlib
    ins = yaml.safe_load(GATE.read_text())['instruction']
    predicate = ins.split('P=lambda q: ', 1)[1].split('; T=iter', 1)[0]
    names = ('conftest.py', 'pytest.ini', 'pyproject.toml', 'tox.ini', 'setup.cfg',
             '.pytest.ini', 'sitecustomize.py', 'usercustomize.py', '_swegemma_stubs.py')
    assert eval(predicate, dict(q=pathlib.PurePosixPath(path), N=names)) == prot(path)


def test_no_baseline_tag_falls_back_to_head(tmp_path):
    ws = make_repo(tmp_path, tag=False)
    apply(ws, ['src/a.py'])
    assert verdict(run(gate_cmd(ws, tmp_path / 'n'))) == S


def test_counter_unwritable_forces_submit(tmp_path):
    ws = make_repo(tmp_path)
    cmd = gate_cmd(ws, tmp_path / 'nodir' / 'n')  # parent missing -> write fails -> n=9
    assert [verdict(run(cmd)) for _ in range(2)] == [F, F]


@pytest.mark.parametrize('state,first', [
    (None, E), ('', F), ('08', F), ('9', F), ('99', F), ('123', F),
    ('9223372036854775807', F), ('-1', F), ('abc', F), ('1\n\n', F), ('0x', F),
])
def test_counter_states_and_bound(tmp_path, state, first):
    ws = make_repo(tmp_path)
    counter = tmp_path / 'n'
    if state is not None:
        counter.write_text(state)
    cmd = gate_cmd(ws, counter)
    got = [verdict(run(cmd)) for _ in range(5)]
    assert got[0] == first
    assert got.count(E) <= 2
    assert got[-3:] == [F, F, F]


def test_counter_read_only_forces_submit(tmp_path):
    ws = make_repo(tmp_path)
    counter = tmp_path / 'n'
    counter.write_text('0')
    counter.chmod(0o444)
    try:
        assert [verdict(run(gate_cmd(ws, counter))) for _ in range(3)] == [F, F, F]
    finally:
        counter.chmod(0o644)


def test_counter_decimal_no_octal(tmp_path):
    ws = make_repo(tmp_path)
    counter = tmp_path / 'n'
    counter.write_text('01')
    out = run(gate_cmd(ws, counter))
    assert out[0] == 'GATE call=2 kept_files=0'
    assert verdict(out) == E


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


@pytest.mark.parametrize('state', ['', 'abc', '123', '9223372036854775807'])
def test_corrupt_counter_forces_even_with_changes(tmp_path, state):
    ws = make_repo(tmp_path)
    apply(ws, ['src/a.py'])
    counter = tmp_path / 'n'
    counter.write_text(state)
    assert verdict(run(gate_cmd(ws, counter))) == F
