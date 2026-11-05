"""Offline isolation, protocol identity and real ADK execution contracts."""
import asyncio
import base64
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import tarfile
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from eval import run_agent_eval as runner, sandbox_env as env, tool_timing as timing
from eval.kaggle.stage_kernel import stage_kernel


@pytest.fixture
def harness():
    pytest.importorskip('swegemma')


def test_bwrap_argv_masks_before_reexposing_runtime(tmp_path):
    root = tmp_path / 'box'
    workspace = root / 'workspace'
    argv = env.bwrap_argv(['/bin/bash', '-c', 'true'], workspace,
                          ['/home/ubuntu/repo', '/home/ubuntu'], ['/opt/python'])
    assert argv[:11] == env.BWRAP_TEMPLATE[:11]
    assert argv[11:15] == ['--tmpfs', '/home/ubuntu', '--tmpfs', '/home/ubuntu/repo']
    assert argv[15:20] == ['--tmpfs', '/tmp', '--bind', str(root), str(root)]
    assert argv[20:23] == ['--ro-bind', '/opt/python', '/opt/python']
    assert argv[-5:] == ['--chdir', str(workspace), '/bin/bash', '-c', 'true']
    for path in ['/x/tasks.jsonl', '/x/splits', '/x/runs', '/x/results']:
        with pytest.raises(ValueError, match='Forbidden'):
            env.bwrap_argv(['/bin/bash', '-c', 'true'], workspace, [], [path])


def test_runtime_paths_include_prefix_and_wheel_symlink_targets(tmp_path, monkeypatch):
    root = tmp_path / 'box'
    (root / 'venv').mkdir(parents=True)
    (root / 'venv/pyvenv.cfg').write_text('home = /opt/pyimg/bin\n')
    monkeypatch.setattr(env.sys, 'base_prefix', '/opt/pyimg')
    (root / 'wheels').mkdir()
    wheel = tmp_path / 'wh/pkg.whl'
    wheel.parent.mkdir()
    wheel.touch()
    (root / 'wheels/pkg.whl').symlink_to(wheel)
    assert env.runtime_ro_paths(root / 'workspace', [wheel.parent]) == {
        Path('/opt/pyimg'), wheel.parent, wheel}
    (root / 'wheels/escape').symlink_to(Path.home(), target_is_directory=True)
    with pytest.raises(ValueError, match='Untrusted wheel symlink'):
        env.runtime_ro_paths(root / 'workspace', [wheel.parent])
    (root / 'wheels/escape').unlink()
    (root / 'venv/pyvenv.cfg').write_text('home = /home/ubuntu/bin\n')
    with pytest.raises(ValueError, match='python prefix differs'):
        env.runtime_ro_paths(root / 'workspace', [wheel.parent])


@pytest.mark.parametrize('exit_code,write,ok', [(0, True, True), (1, True, False), (0, False, False)])
def test_probe_logic_fake_executor(tmp_path, exit_code, write, ok):
    class Manager:
        sandboxes = {'id': {'workspace': tmp_path}}
        cleaned = False

        def start(self):
            return 'id'

        def exec(self, sid, command, timeout):
            assert base64.b64encode(b'/hidden/tasks.jsonl').decode() in command
            assert 'test ! -e "$inventory"' in command
            assert 'contents=$(ls -A "$data") && test -z "$contents"' in command
            assert "import pytest" in command and '/tmp/y' in command and '/workspace/x' in command
            if write:
                (tmp_path / 'x').touch()
            return SimpleNamespace(exit_code=exit_code, stderr='probe failure')

        def cleanup_all(self):
            self.cleaned = True

    manager = Manager()
    if ok:
        env.probe_isolation(manager, Path('/hidden/tasks.jsonl'), Path('/hidden'))
    else:
        with pytest.raises(RuntimeError, match='probe failed'):
            env.probe_isolation(manager, Path('/hidden/tasks.jsonl'), Path('/hidden'))
    assert manager.cleaned


@pytest.mark.parametrize('failure', ['missing', 'probe'])
def test_setup_fails_closed_and_explicit_optout(monkeypatch, tmp_path, harness, failure):
    calls = []
    monkeypatch.setattr(env, 'isolate_host_packages', lambda: calls.append('pth'))
    monkeypatch.setattr(env, 'isolate_gold_tempfiles', lambda: calls.append('gold'))
    patched = object()
    monkeypatch.setattr(env, 'patch_subprocess_deps', lambda p: patched)
    monkeypatch.setattr(env.shutil, 'which', lambda p: None if failure == 'missing' else '/usr/bin/bwrap')
    monkeypatch.setattr(env, 'apply_isolation', lambda hidden, ro: calls.append(list(hidden)))
    monkeypatch.setattr(env, 'probe_isolation', lambda *args: (_ for _ in ()).throw(RuntimeError('probe failed')))
    with pytest.raises(RuntimeError):
        env.setup_scorer_env(tmp_path, out_dir=tmp_path / 'out')
    result = env.setup_scorer_env(tmp_path, out_dir=tmp_path / 'out', allow_unsandboxed=True)
    assert result['sandbox'] == 'none' and result['patched'] is patched
    assert result['bwrap_argv_template'] is None and calls[-1] == []


def test_setup_probes_empty_data_then_full_runtime_mounts(tmp_path, monkeypatch, harness):
    import swegemma.harness.container_setup as cs
    calls = []
    for name in ('isolate_host_packages', 'isolate_gold_tempfiles'):
        monkeypatch.setattr(env, name, lambda: None)
    monkeypatch.setattr(env, 'patch_subprocess_deps', lambda p: 'patched')
    monkeypatch.setattr(env.shutil, 'which', lambda p: '/usr/bin/bwrap')
    wheels = tmp_path / 'inventory/wheels'
    monkeypatch.setattr(cs, 'resolve_wheels_dir', lambda config: wheels)
    def apply(hidden, ro):
        assert set(map(Path, hidden)) >= {Path.home(), tmp_path / 'repo', tmp_path / 'inventory',
                                          tmp_path / 'output', Path('/home/ubuntu/work/gemma-wt')}
        calls.append(('mounts', ro))
        return env.BWRAP_TEMPLATE
    monkeypatch.setattr(env, 'apply_isolation', apply)
    monkeypatch.setattr(env, 'probe_isolation', lambda *args, **kw: calls.append(('probe', kw.get('empty_data', True))))
    result = env.setup_scorer_env(tmp_path / 'inventory', out_dir=tmp_path / 'output', repo_root=tmp_path / 'repo')
    assert calls == [('mounts', []), ('probe', True), ('mounts', [wheels]), ('probe', False)]
    assert result['sandbox'] == 'bwrap' and result['bwrap_argv_template'] == env.BWRAP_TEMPLATE


def test_executor_wraps_translated_commands_and_counts_timeouts(tmp_path, monkeypatch, harness):
    import swegemma.sandbox.subprocess as sb
    seen = []
    def execute(**kwargs):
        seen.append(kwargs)
        return SimpleNamespace(status='timeout', exit_code=124)
    monkeypatch.setattr(sb, 'execute_subprocess_command', execute)
    monkeypatch.setattr(env, 'runtime_ro_paths', lambda *args: [Path('/opt/python')])
    env.apply_isolation(['/home/ubuntu'], [])
    state = {}
    token = env.command_metrics.set(state)
    try:
        for _ in range(2):
            sb.execute_subprocess_command(command=['/bin/bash', '-c', 'translated'],
                                          cwd=tmp_path / 'workspace', env={}, timeout=3, shell=False)
        assert state['cmd_timeouts'] == 2
        assert seen[0]['command'][0] == 'bwrap'
        assert seen[0]['command'][-1] == 'translated'
        assert seen[0]['timeout'] == 3 and seen[0]['shell'] is False
    finally:
        env.command_metrics.reset(token)


def test_real_bwrap_probe(tmp_path, monkeypatch, harness):
    if not shutil.which('bwrap'):
        pytest.skip('bubblewrap not installed')
    preflight = subprocess.run(env.BWRAP_TEMPLATE[:11] + ['/bin/true'], capture_output=True, text=True)
    if preflight.returncode:
        pytest.skip('bubblewrap blocked by sandbox: ' + preflight.stderr.strip())
    import swegemma.sandbox.subprocess as sb
    monkeypatch.setattr(sb, 'execute_subprocess_command', sb.execute_subprocess_command)
    (tmp_path / 'tasks.jsonl').write_text('hidden inventory')
    env.isolate_host_packages()
    env.apply_isolation([Path.home(), ROOT, tmp_path], [])
    env.probe_isolation(sb.SubprocessManager(), tmp_path / 'tasks.jsonl', tmp_path)


def test_config_forwards_fields_and_resolves_graph_paths(tmp_path, caplog, harness):
    from swegemma.context import SwegemmaContext
    args = SimpleNamespace(data_dir=tmp_path / 'other-data', bundle=tmp_path / 'bundle', concurrency=1)
    config = runner.build_config(dict(verification_timeout_seconds=17, max_llm_calls=9,
                                      enable_sandbox_testing=False, graph_dir='mygraphs',
                                      embeddings_dir='myembeddings', future_option=42),
                                 args, {}, tmp_path / 'out', {})
    assert config.harness.verification_timeout_seconds == 17
    assert config.max_llm_calls == 9 and not config.enable_sandbox_testing
    assert 'Unknown EvalConfig key: future_option' in caplog.text
    context = SwegemmaContext(docker_manager=None, container_id='',
                             graph_dir=config.graph_dir, embeddings_dir=config.embeddings_dir)
    assert context.graph_dir == str(args.data_dir / 'mygraphs')
    assert context.embeddings_dir == str(args.data_dir / 'myembeddings')
    assert runner.config_snapshot(config)['verification_timeout_seconds'] == 17
    json.dumps(runner.config_snapshot(config))


@pytest.mark.parametrize('key,value', [('runner_source_sha256', 'new-source'),
    ('tasks_sha256', 'new-inventory'), ('versions', {'swegemma': '99'}),
    ('wheels_listing_sha256', 'new-wheels'), ('sandbox', 'none'), ('python_version', '99')])
def test_resume_identity_refuses_changed_environment(tmp_path, key, value):
    header = dict(_schema='agent_eval_v2', runner_source_sha256='old-source',
                  provenance=dict(git_sha='old-sha', git_dirty=False),
                  tasks_sha256='old-inventory', versions={'swegemma': '0.2.11'},
                  wheels_listing_sha256='old-wheels', sandbox='bwrap', python_version='3.13')
    path = tmp_path / 'run.jsonl'
    runner.Journal(path, header).close()
    with pytest.raises(ValueError, match='header mismatch') as exc:
        runner.Journal(path, dict(header, **{key: value}))
    assert key in str(exc.value) and '--force-new-out' in str(exc.value)


def test_inventory_duplicate_scanned_before_harness_deduplication(tmp_path):
    path = tmp_path / 'tasks.jsonl'
    path.write_text('\n'.join(json.dumps(dict(instance_id=i, patch=p)) for i, p in
                              [('one', 'A'), ('two', 'B'), ('one', 'C')]))
    with pytest.raises(ValueError, match='Duplicate inventory IDs at line 3'):
        runner.validate_inventory_ids(path)


def test_git_c_quoted_utf8_octal_paths_and_diag_failure(monkeypatch):
    patch = ('diff --git "a/caf\\303\\251.py" "b/caf\\303\\251.py"\n'
             '--- "a/caf\\303\\251.py"\n+++ "b/caf\\303\\251.py"\n@@ -1 +1 @@\n-a\n+b\n')
    assert runner.classify_patch(patch, 'org/pkg')['patch_files'] == ['café.py']
    monkeypatch.setattr(runner, 'classify_patch', lambda *args: 1 / 0)
    out = runner.task_diagnostics(None, patch, 'org/pkg', None, [], Path('/inventory'))
    assert out['diag_error'] == 'ZeroDivisionError' and out['patch_bytes'] > 0


def test_leak_scan_records_tokens_only():
    trace = SimpleNamespace(entries=[SimpleNamespace(event_type='tool_call', tool_name='run_command',
        usage=None, tool_args={'command': f'cat /inventory/tasks.jsonl # test_patch FAIL_TO_PASS {ROOT} secret contents'})])
    out = runner.task_diagnostics(trace, '', 'org/pkg', None, [], Path('/inventory'))
    assert out['leak_suspect']
    assert out['leak_hits'] == [str(ROOT), '/inventory', 'tasks.jsonl', 'test_patch', 'FAIL_TO_PASS']
    assert 'secret contents' not in json.dumps(out)


def test_shared_module_embedded_in_kernel(tmp_path):
    staged = tmp_path / 'gold_calibration.py'
    stage_kernel(staged)
    # Import the staged single file without the repo on sys.path or any harness.
    result = subprocess.run([sys.executable, '-I', '-c',
        "import runpy, sys; m=runpy.run_path(sys.argv[1]); "
        "assert m['setup_scorer_env'].__module__ == 'sandbox_env'; "
        "assert m['patch_subprocess_deps'].__globals__ is m['setup_scorer_env'].__globals__",
        str(staged)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_dependency_setup_preserves_gold_probe_log(tmp_path, monkeypatch, harness):
    import swegemma.harness.container_setup as cs
    # Restore all bindings changed by the shared setup after this test.
    for name, module in list(sys.modules.items()):
        if name.startswith('swegemma') and hasattr(module, 'install_test_dependencies'):
            monkeypatch.setattr(module, 'install_test_dependencies', module.install_test_dependencies)
    archive = tmp_path / 'empty.tar'
    with tarfile.open(archive, 'w'):
        pass
    (tmp_path / 'wheels').mkdir()
    site = tmp_path / 'venv/lib/python3.13/site-packages'
    site.mkdir(parents=True)
    monkeypatch.setattr(cs, '_inspect_wheels_dir', lambda p: ([], {}, {}, {}))
    monkeypatch.setattr(cs, '_build_unpacked_wheels_tar', lambda *a: archive)
    log = tmp_path / 'probe.jsonl'
    monkeypatch.setenv('GOLD_PROBE_LOG', str(log))
    class SubprocessManager:
        sandboxes = {'id': {'venv': tmp_path / 'venv'}}
        def copy_to(self, *args):
            pass
        def exec(self, *args, **kwargs):
            return 'synthetic import path'
    install = env.patch_subprocess_deps(tmp_path)
    install(SubprocessManager(), 'id', 'org/pkg')
    assert json.loads(log.read_text())['probe'] == 'synthetic import path'


def test_gold_temp_patch_files_and_sandbox_roots_live_under_out(tmp_path, monkeypatch, harness):
    import swegemma.harness.verification as vf
    from swegemma.sandbox import SubprocessManager
    monkeypatch.setattr(vf, 'tempfile', vf.tempfile)
    env.isolate_gold_tempfiles()
    env.isolate_host_packages()
    token = env.gold_artifact_dir.set(tmp_path)
    manager = SubprocessManager()
    try:
        with vf.tempfile.NamedTemporaryFile('w', suffix='.patch') as stream:
            stream.write('synthetic gold patch')
            assert Path(stream.name).is_relative_to(tmp_path)
        sid = manager.start()
        assert manager.sandboxes[sid]['root'].is_relative_to(tmp_path)
        assert not list(manager.sandboxes[sid]['venv'].glob('lib/python*/site-packages/_host_env.pth'))
    finally:
        manager.cleanup_all()
        env.gold_artifact_dir.reset(token)


def test_timing_call_ids_errors_and_pending(monkeypatch):
    now = iter([0, 0.1, 0.2, 0.5, 0.6])
    monkeypatch.setattr(timing.time, 'monotonic', lambda: next(now))
    state = timing.ToolTiming()
    state.before('slow', 'same_name')
    state.before('fast', 'same_name')
    state.after('fast')
    state.after('slow')
    state.after('slow')  # error recovery's after callback doesn't count twice
    state.before('pending', 'interrupted')
    state.after('orphan')
    assert state.seconds['same_name'] == dict(n=2, total=0.6, max=0.5)
    assert state.metrics()['tool_seconds_unmatched'] == 2


def test_real_adk_parallel_tool_timings_and_concurrent_task_contexts(harness):
    from google.adk.agents import LlmAgent
    from google.adk.apps import App
    from google.adk.models.base_llm import BaseLlm
    from google.adk.models.llm_response import LlmResponse
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    class StubModel(BaseLlm):
        calls: int = 0

        async def generate_content_async(self, llm_request, stream=False):
            self.calls += 1
            await asyncio.sleep(0.1)  # model overhead, included in agent wall time
            if self.calls == 1:
                parts = [types.Part(function_call=types.FunctionCall(id=n, name=n, args={}))
                         for n in ('fast', 'slow')]
            else:
                parts = [types.Part(text='Done')]
            yield LlmResponse(content=types.Content(role='model', parts=parts), finish_reason=types.FinishReason.STOP)

    async def fast() -> dict:
        await asyncio.sleep(0.05)
        return {'ok': True}

    async def slow() -> dict:
        await asyncio.sleep(0.5)
        return {'ok': True}

    async def one(name):
        state = timing.ToolTiming()
        token = timing.current_timing.set(state)
        service = InMemorySessionService()
        session = await service.create_session(app_name=name, user_id='u')
        app = App(name=name, root_agent=LlmAgent(name='agent', model=StubModel(model='stub'),
                                                tools=[fast, slow]),
                  plugins=[timing.make_timing_plugin()])
        runner_ = Runner(app=app, session_service=service)
        start = time.monotonic()
        try:
            async for _ in runner_.run_async(user_id='u', session_id=session.id,
                                             new_message=types.Content(role='user', parts=[types.Part(text='Go')])):
                pass
        finally:
            timing.current_timing.reset(token)
        return state.metrics(), time.monotonic() - start

    async def both():
        return await asyncio.gather(one('first'), one('second'))

    for metrics, wall in asyncio.run(both()):
        assert metrics['tool_calls_timed'] == 2 and metrics['tool_seconds_unmatched'] == 0
        assert 0.04 <= metrics['tool_seconds']['fast']['total'] <= 0.2
        assert 0.45 <= metrics['tool_seconds']['slow']['total'] <= 0.7
        assert sum(v['total'] for v in metrics['tool_seconds'].values()) <= wall


def test_bwrap_binds_symlinked_ro_path_at_alias(tmp_path):
    # uv's pyimg exposes cpython-3.13 -> cpython-3.13.18; venv symlinks use the alias.
    real = tmp_path / 'cpython-3.13.18'
    real.mkdir()
    alias = tmp_path / 'cpython-3.13'
    alias.symlink_to(real)
    ws = tmp_path / 'sb' / 'workspace'
    ws.mkdir(parents=True)
    argv = env.bwrap_argv(['/bin/bash', '-c', 'true'], ws, [tmp_path], [alias])
    pairs = {(argv[i + 1], argv[i + 2]) for i, a in enumerate(argv) if a == '--ro-bind'}
    assert (str(real), str(real)) in pairs and (str(real), str(alias)) in pairs


def test_resume_ignores_provenance_only_changes(tmp_path):
    header = dict(_schema='agent_eval_v2', runner_source_sha256='src',
                  provenance=dict(git_sha='old-sha', git_dirty=False))
    path = tmp_path / 'run.jsonl'
    runner.Journal(path, header).close()
    runner.Journal(path, dict(header, provenance=dict(git_sha='new-sha', git_dirty=True))).close()


def _source_repo(tmp_path, monkeypatch):
    repo = tmp_path / 'repo'
    (repo / 'eval' / 'tests').mkdir(parents=True)
    (repo / 'results').mkdir()
    (repo / 'eval' / 'impl.py').write_text('X = 1\n')
    (repo / 'eval' / 'tests' / 'test_x.py').write_text('pass\n')
    (repo / '.gitignore').write_text('__pycache__/\n')
    git = lambda *a: subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t', *a],
                                    cwd=repo, check=True, capture_output=True)
    git('init', '-q'); git('add', '-A'); git('commit', '-qm', 'init')
    monkeypatch.setattr(runner, 'ROOT', repo)
    return repo


def test_source_hash_distinguishes_dirty_implementations(tmp_path, monkeypatch):
    repo = _source_repo(tmp_path, monkeypatch)
    clean = runner.runner_source_sha()
    (repo / 'eval' / 'impl.py').write_text('X = 2\n')
    dirty_a = runner.runner_revision()
    (repo / 'eval' / 'impl.py').write_text('X = 3\n')
    dirty_b = runner.runner_revision()
    assert dirty_a['provenance'] == dirty_b['provenance']  # the old identity collided here
    assert len({clean, dirty_a['runner_source_sha256'], dirty_b['runner_source_sha256']}) == 3
    (repo / 'eval' / 'new_helper.py').write_text('Y = 1\n')  # untracked source counts
    assert runner.runner_source_sha() != dirty_b['runner_source_sha256']
    path = tmp_path / 'run.jsonl'
    runner.Journal(path, dict(_schema='agent_eval_v2', **dirty_a)).close()
    with pytest.raises(ValueError, match='runner_source_sha256'):
        runner.Journal(path, dict(_schema='agent_eval_v2', **dirty_b))


def test_source_hash_ignores_journal_tests_and_caches(tmp_path, monkeypatch):
    repo = _source_repo(tmp_path, monkeypatch)
    before = runner.runner_revision()
    path = repo / 'results' / 'run.jsonl'  # default, unignored journal location
    runner.Journal(path, dict(_schema='agent_eval_v2', **before)).close()
    (repo / 'eval' / 'tests' / 'test_x.py').write_text('assert True\n')
    (repo / 'eval' / '__pycache__').mkdir()
    (repo / 'eval' / '__pycache__' / 'impl.cpython-313.pyc').write_bytes(b'x')
    after = runner.runner_revision()
    assert after['provenance']['git_dirty'] and not before['provenance']['git_dirty']
    assert after['runner_source_sha256'] == before['runner_source_sha256']
    runner.Journal(path, dict(_schema='agent_eval_v2', **after)).close()  # resume accepted


def _cap_args(**kw):
    base = dict(max_tool_calls=None, max_turns=None, session_minutes=None, command_timeout=None)
    return SimpleNamespace(**dict(base, **kw))


def test_caps_respect_nested_bundle_settings(harness):
    defaults = dict(budget=dict(time_minutes=2), harness=dict(command_timeout_seconds=7))
    caps = runner.resolve_caps(defaults, _cap_args())
    assert caps['max_time_minutes'] is None and caps['timeout_seconds'] is None
    args = SimpleNamespace(data_dir=Path('/d'), bundle=Path('/b'), concurrency=1)
    config = runner.build_config(defaults, args, None, Path('/r'), caps)
    assert config.budget.time_minutes == 2
    assert config.harness.command_timeout_seconds == 7


def test_caps_precedence_cli_flat_fallback():
    assert runner.resolve_caps({}, _cap_args())['max_time_minutes'] == 5
    assert runner.resolve_caps({}, _cap_args())['timeout_seconds'] == 60
    flat = dict(max_time_minutes=3, budget=dict(time_minutes=2))
    assert runner.resolve_caps(flat, _cap_args())['max_time_minutes'] == 3
    assert runner.resolve_caps(flat, _cap_args(session_minutes=4))['max_time_minutes'] == 4


def test_setup_script_identity_tracks_selected_script(tmp_path):
    from eval import sandbox_env
    script = tmp_path / 'sandbox' / 'setup.py'
    script.parent.mkdir()
    script.write_text('print(1)\n')
    first = sandbox_env.setup_script_identity(tmp_path)
    assert first['path'] == str(script.resolve()) and first['sha256']
    assert sandbox_env.setup_script_path(tmp_path) == script
    script.write_text('print(2)\n')
    second = sandbox_env.setup_script_identity(tmp_path)
    assert second['sha256'] != first['sha256']
    header = dict(_schema='agent_eval_v2', runner_source_sha256='src', setup_script=first)
    path = tmp_path / 'run.jsonl'
    runner.Journal(path, header).close()
    with pytest.raises(ValueError, match='setup_script'):
        runner.Journal(path, dict(header, setup_script=second))
    runner.Journal(path, dict(header)).close()  # unchanged script resumes


def test_setup_script_fallback_is_recursive_and_hashed(tmp_path):
    from eval import sandbox_env
    script = tmp_path / 'x' / 'sandbox' / 'setup.py'
    script.parent.mkdir(parents=True)
    script.write_text('a')
    assert sandbox_env.setup_script_identity(tmp_path)['path'] == str(script.resolve())
    assert sandbox_env.setup_script_identity(tmp_path / 'missing')['sha256'] is None


@pytest.mark.parametrize('section,key,value', [('budget', 'time_minutes', 0),
    ('harness', 'command_timeout_seconds', -7), ('budget', 'time_minutes', float('inf')),
    ('harness', 'command_timeout_seconds', 'abc'), ('budget', 'tool_calls', -7),
    ('budget', 'turns', True), ('budget', 'turns', 2.5), ('budget', 'tool_calls', 'x')])
def test_nested_caps_are_validated_after_merge(harness, section, key, value):
    defaults = {section: {key: value}}
    caps = runner.resolve_caps(defaults, _cap_args())
    runner.validate_caps(caps.values())  # flat caps fine; nested left to config
    args = SimpleNamespace(data_dir=Path('/d'), bundle=Path('/b'), concurrency=1)
    try:
        config = runner.build_config(defaults, args, None, Path('/r'), caps)
    except (TypeError, ValueError):
        return  # rejected at construction is also acceptable
    with pytest.raises(ValueError, match='positive'):
        runner.validate_effective_caps(config)


def test_valid_nested_and_flat_caps_pass_validation(harness):
    defaults = dict(budget=dict(time_minutes=2), harness=dict(command_timeout_seconds=7))
    caps = runner.resolve_caps(defaults, _cap_args())
    args = SimpleNamespace(data_dir=Path('/d'), bundle=Path('/b'), concurrency=1)
    runner.validate_effective_caps(runner.build_config(defaults, args, None, Path('/r'), caps))
    with pytest.raises(ValueError):
        runner.validate_caps([True])


@pytest.mark.parametrize('value', ['abc', 0, -1, True, 3.5])
def test_flat_max_llm_calls_is_validated(harness, value):
    defaults = dict(max_llm_calls=value)
    caps = runner.resolve_caps(defaults, _cap_args())
    args = SimpleNamespace(data_dir=Path('/d'), bundle=Path('/b'), concurrency=1)
    try:
        config = runner.build_config(defaults, args, None, Path('/r'), caps)
    except (TypeError, ValueError):
        return
    with pytest.raises(ValueError):
        runner.validate_effective_caps(config)


def test_valid_count_caps_pass(harness):
    defaults = dict(max_llm_calls=40, budget=dict(tool_calls=100, turns=50))
    caps = runner.resolve_caps(defaults, _cap_args())
    args = SimpleNamespace(data_dir=Path('/d'), bundle=Path('/b'), concurrency=1)
    runner.validate_effective_caps(runner.build_config(defaults, args, None, Path('/r'), caps))
