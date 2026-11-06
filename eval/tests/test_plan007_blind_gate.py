"""Synthetic tests for eval/plan007_blind_gate.py (dec 066 item 1: codex review 072941 BLOCKING 1-4)."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / 'eval' / 'plan007_blind_gate.py'
CLS = ROOT / 'eval' / 'plan007_pinned' / 'classify_rows_a208a023.py'
SHA = 'a208a02343b43556e990271b8757044fdf51515f27ff9a067cd3af14c1fd4e6b'
ALLOWED = ('vllm_up ', 'rows ', 'rows_parse ', 'wall ', 'max_total ', 'h_count ', 'mechanical_gate ', 'usage')


def row(iid='task-1', total=100.25, **upd):
    r = dict(instance_id=iid, repo='example/repo', result_error=None, agent_error_text=None,
             verified_patch_bytes=10, setup_calls=[], exit_code=0, resolved=False, error=None,
             setup_failed=False, wall_seconds=dict(agent=50.0, verification=40.0, total=total))
    r.update(upd)
    return r


VLLM = {'_vllm': {'startup_seconds': 300.0}}


def run(tmp_path, recs, expected='3', raw=None):
    p = tmp_path / 'timing.jsonl'
    p.write_text(raw if raw is not None else ''.join(json.dumps(r) + '\n' for r in recs))
    cp = subprocess.run([sys.executable, '-I', str(GATE), str(p), str(CLS), SHA, expected],
                        capture_output=True, text=True)
    lines = cp.stdout.splitlines()
    assert cp.stderr == ''
    for ln in lines:
        assert ln.startswith(ALLOWED), ln
    return cp.returncode, lines


def gate(lines):
    return lines[-1]


def test_hold_clean(tmp_path):
    rc, lines = run(tmp_path, [VLLM, row('a-1'), row('a-2', total=120.4), row('a-3')])
    assert rc == 0 and gate(lines) == 'mechanical_gate HOLD'
    assert 'h_count 0' in lines and 'max_total 120.4 seed_max_ceil 121' in lines
    assert not any('resolved' in ln or 'PASS' in ln or 'True' in ln for ln in lines)


def test_expected_rows_required(tmp_path):
    p = tmp_path / 't.jsonl'
    p.write_text(json.dumps(VLLM) + '\n')
    cp = subprocess.run([sys.executable, '-I', str(GATE), str(p), str(CLS), SHA],
                        capture_output=True, text=True)
    assert cp.returncode == 2 and 'HOLD' not in cp.stdout


def test_zero_rows_fails(tmp_path):
    rc, lines = run(tmp_path, [VLLM])
    assert rc == 3 and gate(lines) == 'mechanical_gate FAIL'


@pytest.mark.parametrize('exp', ['0', '-1', 'x', '3.0'])
def test_bad_expected(tmp_path, exp):
    rc, lines = run(tmp_path, [VLLM, row()], expected=exp)
    assert rc == 2 and not any('HOLD' in ln for ln in lines)


def test_count_mismatch(tmp_path):
    rc, lines = run(tmp_path, [VLLM, row('a'), row('b')])
    assert gate(lines) == 'mechanical_gate FAIL'


def test_newline_id_injection(tmp_path):
    rc, lines = run(tmp_path, [VLLM, row('a\nPRIVATE resolved=True'), row('b'), row('c')])
    assert gate(lines) == 'mechanical_gate FAIL'
    assert not any('PRIVATE' in ln for ln in lines)


@pytest.mark.parametrize('bad', [['x'], 5, None, {'a': 1}, ''])
def test_nonstring_id(tmp_path, bad):
    rc, lines = run(tmp_path, [VLLM, row(bad), row('b'), row('c')])
    assert rc == 3 and gate(lines) == 'mechanical_gate FAIL'


def test_nonfinite_total(tmp_path):
    raw = json.dumps(VLLM) + '\n' + ''.join(
        json.dumps(row(i)).replace('100.25', 'Infinity') + '\n' for i in ('a', 'b', 'c'))
    rc, lines = run(tmp_path, None, raw=raw)
    assert rc == 3 and gate(lines) == 'mechanical_gate FAIL'


def test_missing_total_fails(tmp_path):
    rc, lines = run(tmp_path, [VLLM, row('a'), row('b'), row('c', wall_seconds={})])
    assert gate(lines) == 'mechanical_gate FAIL'


def test_no_vllm(tmp_path):
    rc, lines = run(tmp_path, [row('a'), row('b'), row('c')])
    assert 'vllm_up n' in lines and gate(lines) == 'mechanical_gate FAIL'


def test_parse_error_no_diag(tmp_path):
    raw = json.dumps(VLLM) + '\n{bad json\n' + ''.join(json.dumps(row(i)) + '\n' for i in 'abc')
    rc, lines = run(tmp_path, None, raw=raw)
    assert 'rows_parse n' in lines and gate(lines) == 'mechanical_gate FAIL'


def test_duplicates(tmp_path):
    rc, lines = run(tmp_path, [VLLM, row('a'), row('a'), row('c')])
    assert gate(lines) == 'mechanical_gate FAIL' and not any('duplicate' in ln for ln in lines)


def test_h_row_counted_not_named(tmp_path):
    rc, lines = run(tmp_path, [VLLM, row('a'), row('b', result_error='weird wrapper failure'), row('c')])
    assert 'h_count 1' in lines and gate(lines) == 'mechanical_gate FAIL'
    assert not any('H-ROW' in ln for ln in lines)


def test_sha_mismatch(tmp_path):
    p = tmp_path / 't.jsonl'
    p.write_text('')
    cp = subprocess.run([sys.executable, '-I', str(GATE), str(p), str(CLS), '0' * 64, '3'],
                        capture_output=True, text=True)
    assert cp.returncode == 2 and 'HOLD' not in cp.stdout and '0' * 64 not in cp.stdout
