"""Tests for the pre-registered H-VERIFY(empty-patch) sub-case (dec 068 item 1)."""
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'eval'))
from plan007_report import is_h_verify_empty_patch, assert_paired, VERIFY_AGENT_PREFIXES  # noqa: E402


def cls(**upd):
    r = dict(instance_id='t1', h='H-VERIFY', reasons=['verify:contradictory_failure_evidence'])
    r.update(upd)
    return r


def tim(**upd):
    r = dict(instance_id='t1', verified_patch_bytes=0, exit_code=1, resolved=False,
             result_error=None, agent_error_text=None)
    r.update(upd)
    return r


def test_match_basic():
    assert is_h_verify_empty_patch(cls(), tim())


@pytest.mark.parametrize('code', [1, 2, 4, 5, 124, 137])
def test_match_exit_codes(code):
    assert is_h_verify_empty_patch(cls(), tim(exit_code=code))


def test_match_empty_strings():
    assert is_h_verify_empty_patch(cls(), tim(result_error='', agent_error_text='  '))


@pytest.mark.parametrize('c', [
    dict(h=None), dict(h='H-ROW'), dict(h='H-SETUP'),
    dict(reasons=[]), dict(reasons=['verify:unexpected_exit_code']),
    dict(reasons=['verify:contradictory_failure_evidence', 'known_diag:record_chain']),
])
def test_cls_mismatch(c):
    assert not is_h_verify_empty_patch(cls(**c), tim())


@pytest.mark.parametrize('t', [
    dict(verified_patch_bytes=1), dict(verified_patch_bytes=None), dict(verified_patch_bytes=0.0),
    dict(verified_patch_bytes=False),
    dict(exit_code=0), dict(exit_code=-1), dict(exit_code=None), dict(exit_code='1'), dict(exit_code=True),
    dict(resolved=True), dict(resolved=None), dict(resolved=0),
    dict(result_error='boom'), dict(agent_error_text='Agent timed out'),
    dict(exit_code=1.0), dict(exit_code=2.0),
])
def test_timing_mismatch(t):
    assert not is_h_verify_empty_patch(cls(), tim(**t))


def test_instance_id_not_in_predicate():
    # B1: predicate is ID-agnostic; pairing is checked by assert_paired.
    assert is_h_verify_empty_patch(cls(instance_id='other'), tim())
    assert is_h_verify_empty_patch(cls(), tim(instance_id=None))


def test_assert_paired():
    assert_paired(cls(), tim())
    for c, t in [(cls(instance_id='x'), tim()), (cls(instance_id=None), tim(instance_id=None)), (cls(), {})]:
        with pytest.raises(ValueError):
            assert_paired(c, t)


@pytest.mark.parametrize('key', ['result_error', 'agent_error_text', 'verified_patch_bytes', 'exit_code', 'resolved'])
def test_missing_keys_rejected(key):
    t = tim()
    del t[key]
    assert not is_h_verify_empty_patch(cls(), t)


@pytest.mark.parametrize('ws', ['\t', '\n', ' \t\n '])
def test_whitespace_variants_match(ws):
    assert is_h_verify_empty_patch(cls(), tim(result_error=ws, agent_error_text=ws))


@pytest.mark.parametrize('p', VERIFY_AGENT_PREFIXES)
def test_verify_messages_excluded(p):
    assert not is_h_verify_empty_patch(cls(), tim(result_error=p + ' x'))
    assert not is_h_verify_empty_patch(cls(), tim(agent_error_text=p))


def test_smoke_rich_3063_if_present():
    res = ROOT / 'results' / 'plan007_arm1_smoke_d4cdf0f0.json'
    tj = ROOT / 'runs' / '31b-v009-p7a1-smoke' / 'timing.jsonl'
    if not (res.exists() and tj.exists()):
        pytest.skip('smoke artefacts not present')
    rows = {r['instance_id']: r for r in json.loads(res.read_text())['rows']}
    trows = {}
    for line in tj.read_text().splitlines():
        r = json.loads(line)
        if 'instance_id' in r:
            trows[r['instance_id']] = r
    hits = []
    for i in sorted(rows):
        if i in trows:
            assert_paired(rows[i], trows[i])
            if is_h_verify_empty_patch(rows[i], trows[i]):
                hits.append(i)
    assert hits == ['rich_3063']
