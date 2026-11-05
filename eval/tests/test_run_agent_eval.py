"""Fast offline contracts; the real harness smoke test is explicitly opt-in."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import types
import uuid

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from eval import run_agent_eval as runner
from eval.stub_openai import make_server


def header(**kwargs):
    return dict(_schema='agent_eval_v1', bundle='bundle', bundle_sha256='sha',
                caps={'max_turns': 3}, split={'path': 'dev', 'sha256': 'split'},
                created_utc=kwargs.pop('created_utc', 'today'), **kwargs)


def test_binding_assertion_catches_late_unpatched_module(monkeypatch):
    patched = lambda: None
    for name in runner.BINDINGS:
        monkeypatch.setitem(sys.modules, name, types.SimpleNamespace(install_test_dependencies=patched))
    runner.assert_dependency_bindings(patched)
    monkeypatch.setitem(sys.modules, 'swegemma.extra',
                        types.SimpleNamespace(install_test_dependencies=lambda: None))
    with pytest.raises(RuntimeError, match='swegemma.extra'):
        runner.assert_dependency_bindings(patched)


def test_patch_updates_every_original_binding(monkeypatch, tmp_path):
    # No real harness import or filesystem setup is needed to exercise binding replacement.
    swe = types.ModuleType('swegemma')
    harness = types.ModuleType('swegemma.harness')
    swe.harness = harness
    monkeypatch.setitem(sys.modules, 'swegemma', swe)
    monkeypatch.setitem(sys.modules, 'swegemma.harness', harness)
    orig = lambda: None
    for name in runner.BINDINGS + ('swegemma.cli', 'swegemma.extra'):
        module = types.ModuleType(name)
        module.install_test_dependencies = orig
        monkeypatch.setitem(sys.modules, name, module)
        parent, attr = name.rsplit('.', 1)
        setattr(sys.modules[parent], attr, module)
    patched = runner.patch_subprocess_deps(tmp_path)
    runner.assert_dependency_bindings(patched)
    assert patched is not orig


def test_header_written_once_resume_failures_and_successes(tmp_path):
    path = tmp_path / 'r.jsonl'
    journal = runner.Journal(path, header())
    for iid, resolved in [('a', True), ('b', False)]:
        journal.append(dict(instance_id=iid, resolved=resolved))
    journal.close()
    journal = runner.Journal(path, header(created_utc='tomorrow'))
    assert journal.finished == {'a', 'b'}
    assert sorted({'a', 'b', 'c'} - journal.finished) == ['c']
    journal.close()
    lines = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(lines) == 3
    assert sum('_schema' in row for row in lines) == 1


@pytest.mark.parametrize('key,value', [('bundle', 'other'), ('bundle_sha256', 'new'),
                                     ('caps', {}), ('split', {})])
def test_header_mismatch_and_force_new(tmp_path, key, value):
    path = tmp_path / 'r.jsonl'
    runner.Journal(path, header()).close()
    changed = dict(header(), **{key: value})
    with pytest.raises(ValueError, match='header mismatch'):
        runner.Journal(path, changed)
    journal = runner.Journal(path, changed, force=True)
    assert not journal.finished
    journal.close()
    assert len(path.read_text().splitlines()) == 1


def test_torn_append_repaired_but_complete_corruption_rejected(tmp_path):
    path = tmp_path / 'r.jsonl'
    runner.Journal(path, header()).close()
    with path.open('a') as stream:
        stream.write('{"instance_id":')
    journal = runner.Journal(path, header())
    journal.append(dict(instance_id='b', resolved=False))
    journal.close()
    assert len(path.read_text().splitlines()) == 2
    with path.open('a') as stream:
        stream.write('invalid\n')
    with pytest.raises(ValueError):
        runner.Journal(path, header())


def diff(path, old='a', new='b', added=False):
    return (f'diff --git a/{path} b/{path}\n' + ('new file mode 100644\n' if added else '') +
            f'--- {"/dev/null" if added else "a/" + path}\n+++ b/{path}\n' +
            f'@@ -{0 if added else 1},{0 if added else 1} +1 @@\n' +
            ('' if added else '-' + old + '\n') + '+' + new + '\n')


def test_patch_classification():
    paths = ['requests/api.py', 'requests/new.py', 'src/requests/module.py', 'scratch.py',
             'notes.txt', 'tests/test_api.py', 'test_x.py', 'foo_test.py', 'conftest.py']
    patch = ''.join(diff(p, added=p != 'requests/api.py') for p in paths)
    result = runner.classify_patch(patch, 'psf/requests')
    assert result['patch_files'] == sorted(paths)
    assert result['test_files_edited'] == sorted(paths[-4:])
    assert result['stray_files'] == sorted(paths[3:])
    assert result['patch_bytes'] == len(patch.encode())
    assert not result['empty_patch']
    assert runner.classify_patch('', 'psf/requests')['empty_patch']


def test_patch_deletion_rename_and_hunk_header_lookalikes():
    patch = ('diff --git a/old.py b/old.py\ndeleted file mode 100644\n--- a/old.py\n'
             '+++ /dev/null\n@@ -1 +0,0 @@\n-old\n'
             'diff --git a/before.py b/after.py\nsimilarity index 100%\n'
             'rename from before.py\nrename to after.py\n')
    patch += diff('requests/file.py', new='++ b/fake.py')
    result = runner.classify_patch(patch, 'psf/requests')
    assert result['patch_files'] == ['after.py', 'before.py', 'old.py', 'requests/file.py']
    assert result['stray_files'] == []


def test_harness_protected_rule_and_extra_targets():
    protected = lambda p: p == 'pyproject.toml'
    result = runner.classify_patch(diff('pyproject.toml') + diff('checks/custom.py'),
                                   'org/pkg', protected, ['checks/custom.py'])
    assert result['test_files_edited'] == ['checks/custom.py', 'pyproject.toml']


def test_trace_usage_is_only_recorded_values():
    entry = lambda **kw: types.SimpleNamespace(event_type='tool_call', tool_name='read_file', timestamp=0.0, **kw)
    counts, tokens, _ = runner.trace_counts(types.SimpleNamespace(entries=[
        entry(usage={'prompt_tokens': 3}), entry(usage={'prompt_tokens': 0})]))
    assert counts == {'read_file': 2}
    assert tokens == dict(prompt_tokens=3, completion_tokens=None)
    assert runner.trace_counts(None)[1] == dict(prompt_tokens=None, completion_tokens=None)


def test_tool_seconds_pairs_calls_fifo_per_tool():
    e = lambda t, name, ts: types.SimpleNamespace(event_type=t, tool_name=name, timestamp=ts, usage=None)
    out = runner.tool_seconds([e('tool_call', 'run_tests', 10.0), e('tool_call', 'read_file', 10.5),
                               e('tool_response', 'read_file', 11.0), e('tool_response', 'run_tests', 14.0),
                               e('tool_call', 'run_tests', 20.0), e('tool_response', 'run_tests', 21.0),
                               e('tool_response', 'orphan', 30.0)])
    assert out == {'run_tests': dict(n=2, total=5.0, max=4.0), 'read_file': dict(n=1, total=0.5, max=0.5)}


def test_env_guard(monkeypatch):
    monkeypatch.setattr(sys, '_base_executable', '/usr/bin/python3')
    with pytest.raises(ValueError, match='pyimg'):
        runner.guard_python()
    runner.guard_python(True)


def test_stub_tool_calls_and_models(tmp_path, monkeypatch):
    script = tmp_path / 'script.json'
    call = dict(id='call_1', type='function', function=dict(name='get_status', arguments='{}'))
    script.write_text(json.dumps([dict(content=None, tool_calls=[call]), dict(content='Done')]))
    # Exercise the actual HTTP handlers with in-memory streams; no socket permissions needed.
    monkeypatch.setattr('eval.stub_openai.ThreadingHTTPServer', lambda address, handler: handler)
    handler_class = make_server(script)
    handler = handler_class.__new__(handler_class)
    handler.send_response = lambda status: None
    handler.send_header = lambda *args: None
    handler.end_headers = lambda: None
    handler.wfile = io.BytesIO()
    handler.path = '/v1/models'
    handler.do_GET()
    assert json.loads(handler.wfile.getvalue())['object'] == 'list'
    for expected in ('tool_calls', 'stop'):
        body = b'{"model":"stub"}'
        handler.path = '/v1/chat/completions'
        handler.headers = {'Content-Length': str(len(body))}
        handler.rfile, handler.wfile = io.BytesIO(body), io.BytesIO()
        handler.do_POST()
        payload = json.loads(handler.wfile.getvalue())
        assert payload['choices'][0]['finish_reason'] == expected
        if expected == 'tool_calls':
            assert payload['choices'][0]['message']['tool_calls'] == [call]
        assert 'usage' not in payload  # Never invent token counts.


@pytest.mark.skipif(os.environ.get('RUN_AGENT_EVAL_E2E') != '1', reason='opt-in real harness smoke test')
def test_e2e(tmp_path):
    iid = sorted(runner.read_ids(ROOT / 'eval/splits/dev.txt') &
                 runner.read_ids(ROOT / 'eval/splits/clean.txt'))[0]
    name = 'test-agent-eval-' + uuid.uuid4().hex[:10]
    script = tmp_path / 'script.json'
    # A harmless source addition exercises tool execution, patch fallback and verification.
    script.write_text(json.dumps([
        dict(content=None, tool_calls=[dict(id='call_1', type='function', function=dict(
            name='run_command', arguments=json.dumps({'command': 'printf "# stub smoke\\n" > stub_smoke.py'})))]),
        dict(content=None, tool_calls=[dict(id='call_2', type='function', function=dict(
            name='submit_patch', arguments='{}'))]), dict(content='Done.')]))
    try:
        server = make_server(script)
    except PermissionError:
        pytest.skip('Sandbox denied localhost socket creation')
    with server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with (tmp_path / 'runner.log').open('w') as log:
                proc = subprocess.run([sys.executable, str(ROOT / 'eval/run_agent_eval.py'),
                    '--bundle', str(ROOT / 'bundles/e4b/v000'), '--data-dir', str(ROOT / 'data/raw'),
                    '--split', str(ROOT / 'eval/splits/dev.txt'), '--ids', iid, '--run-name', name,
                    '--concurrency', '1', '--skip-selfcheck', '--max-turns', '4',
                    '--session-minutes', '1', '--endpoint', f'http://127.0.0.1:{server.server_port}/v1'],
                    cwd=ROOT, stdout=log, stderr=log, timeout=240)
            assert proc.returncode == 0, (tmp_path / 'runner.log').read_text()[-2000:]
            path = ROOT / 'results' / f'{name}.jsonl'
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            assert len(rows) == 2 and rows[1]['instance_id'] == iid
            assert rows[1]['llm_turns'] >= 2 and rows[1]['patch_bytes'] > 0
            assert Path(ROOT / rows[1]['trace_path']).is_file()
        finally:
            server.shutdown()
            thread.join()
            (ROOT / 'results' / f'{name}.jsonl').unlink(missing_ok=True)


def test_observe_patch_before_repeated_stripping():
    from contextvars import ContextVar
    state = ContextVar('test_state')
    strip = runner.observe_patch_strip(lambda patch, **kw: patch.replace('TEST', ''), state)
    assert strip('GOLDTEST') == 'GOLD'  # Self-check has no agent context.
    current = {'agent_active': True}
    state.set(current)
    assert strip('SOURCETEST') == 'SOURCE'
    assert strip('SOURCE') == 'SOURCE'  # Harness strips a submitted patch a second time.
    assert current['raw_patch'] == 'SOURCETEST'
    current['agent_active'] = False
    strip('VERIFICATIONTEST')
    assert current['raw_patch'] == 'SOURCETEST'


def test_host_package_isolation_removes_only_harness_pth(tmp_path, monkeypatch):
    pth = tmp_path / 'lib/python3.13/site-packages/_host_env.pth'
    pth.parent.mkdir(parents=True)
    pth.write_text('/harness/site-packages\n')
    image_pth = pth.with_name('image.pth')
    image_pth.write_text('keep')

    class SubprocessManager:
        def start(self):
            self.sandboxes = {'id': {'venv': tmp_path}}
            return 'id'

    monkeypatch.setitem(sys.modules, 'swegemma.sandbox',
                        types.SimpleNamespace(SubprocessManager=SubprocessManager))
    runner.isolate_host_packages()
    runner.isolate_host_packages()  # Idempotent across repeated evaluations.
    assert SubprocessManager().start() == 'id'
    assert not pth.exists() and image_pth.read_text() == 'keep'
