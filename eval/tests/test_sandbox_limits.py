"""Offline, bounded process-tree regression tests; no competition tasks."""
import os
from pathlib import Path
import shlex
import sys
import time
from dataclasses import replace
from types import SimpleNamespace

import pytest

os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'

from eval import proctree, sandbox_env
from adk_eval_core.sandbox.subprocess_sandbox import execute_subprocess_command as original


@pytest.fixture
def execute(tmp_path, monkeypatch):
    import swegemma.sandbox.subprocess as sb
    monkeypatch.setattr(sb, 'execute_subprocess_command', original)
    sandbox_env.apply_isolation([], [])
    metrics = {}
    token = sandbox_env.command_metrics.set(metrics)
    def run(command, **kwargs):
        return sb.execute_subprocess_command(command=command, cwd=tmp_path,
                                             env=dict(os.environ), **kwargs)
    yield run, metrics
    sandbox_env.command_metrics.reset(token)


def python(code):
    return [sys.executable, '-c', code]


def assert_dead(path):
    pid = int(path.read_text())
    p = proctree.snapshot().get(pid)
    assert p is None or p.state in ('Z', 'X')


@pytest.mark.parametrize('detach', [False, True])
def test_timeout_orphans(execute, tmp_path, detach):
    run, metrics = execute
    if detach:
        code = ("import os,time; p=os.fork(); "
                "os._exit(0) if p else None; os.setsid(); "
                "open('child.pid','w').write(str(os.getpid())); time.sleep(600)")
        cmd = ['/bin/bash', '-c', shlex.join(python(code)) + '; sleep 600']
    else:
        cmd = ['/bin/bash', '-c', '(sleep 600 & echo $! > child.pid); sleep 600']
    start = time.monotonic()
    result = run(cmd, timeout=1)
    assert result.status == 'timeout' and result.exit_code == 124
    assert metrics['cmd_timeouts'] == 1
    assert_dead(tmp_path / 'child.pid')
    assert time.monotonic() - start < 5


def test_memory_tree(execute, monkeypatch):
    run, metrics = execute
    monkeypatch.setenv('GEMMA_SANDBOX_MEM_BYTES', str(300 * 1024**2))
    code = ("import time; chunks=[]\nfor _ in range(60):\n"
            " chunks.append(bytearray(10*1024**2)); time.sleep(.04)\ntime.sleep(600)")
    # Allocate in a child, so accounting must include descendants.
    result = run(['/bin/bash', '-c', shlex.join(python(code)) + ' & wait'], timeout=8)
    assert result.status == 'error' and result.exit_code == 137
    assert 'killed: sandbox memory limit' in result.stderr
    assert metrics['mem_kills'] == 1
    assert metrics['peak_rss_bytes'] > 300 * 1024**2


@pytest.mark.parametrize('command,kwargs', [
    (['/bin/bash', '-c', 'echo hello'], {}),
    (['/bin/bash', '-c', 'exit 3'], {}),
    (['/bin/bash', '-c', 'exit 137'], {}),
    (['/bin/bash', '-c', 'echo err >&2'], {}),
    ('printf hello', {}),
    (['/bin/bash', '-c', 'printf abcdef'], {'max_output_chars': 3}),
    (python("import os; os.write(1, b'\\xff')"), {}),
])
def test_original_output_contract(execute, tmp_path, command, kwargs):
    run, metrics = execute
    expected = original(command, tmp_path, dict(os.environ), **kwargs)
    actual = run(command, **kwargs)
    assert type(actual) is type(expected)
    assert (actual.status, actual.exit_code, actual.stdout, actual.stderr) == (
        expected.status, expected.exit_code, expected.stdout, expected.stderr)
    assert metrics['peak_rss_bytes'] > 0


def test_normal_exit_daemon(execute, tmp_path):
    run, metrics = execute
    result = run(['/bin/bash', '-c', 'sleep 600 >/dev/null 2>&1 & echo $! > child.pid'], timeout=3)
    assert result.status == 'ok' and result.exit_code == 0
    assert metrics['orphan_kills'] >= 1
    assert_dead(tmp_path / 'child.pid')


def test_pid_reuse_is_not_a_survivor():
    p = proctree.snapshot()[os.getpid()]
    stale = replace(p, starttime=p.starttime - 1)
    assert proctree.survivors({p.pid: stale}) == {}
    assert proctree.kill_tree({p.pid: stale}) == 0
    assert proctree.tree_rss({p.pid: p}) > 0


def test_without_prlimit(execute, monkeypatch):
    run, metrics = execute
    source = proctree.supervisor_source().replace(
        "prlimit = shutil.which('prlimit')", 'prlimit = None')
    monkeypatch.setattr(proctree, 'supervisor_source', lambda: source)
    result = run(['/bin/bash', '-c', 'echo fallback'])
    assert result.status == 'ok' and result.stdout == 'fallback\n'
    assert metrics['peak_rss_bytes'] > 0


@pytest.mark.parametrize('without_prlimit', [False, True])
def test_submillisecond_command_rss_without_polling(execute, monkeypatch, without_prlimit):
    run, metrics = execute
    # /bin/true does sub-millisecond work. Force all tree RSS samples to miss
    # it, regardless of host scheduling or the overhead of starting a process.
    source = proctree.supervisor_source().replace(
        'rss = tree_rss(live, processes)', 'rss = 0')
    if without_prlimit:
        source = source.replace("prlimit = shutil.which('prlimit')", 'prlimit = None')
    monkeypatch.setattr(proctree, 'supervisor_source', lambda: source)
    result = run(['/bin/true'])
    assert result.status == 'ok' and result.exit_code == 0
    assert metrics['peak_rss_bytes'] > 0
    assert metrics['mem_kills'] == 0


@pytest.mark.parametrize('method', ['poll', 'wait', 'communicate'])
def test_direct_child_wait4_rss(method):
    # Verify all Popen reaping paths, including communicate's internal wait.
    proc = proctree.RusagePopen(['/bin/true'])
    try:
        if method == 'poll':
            deadline = time.monotonic() + 5
            while proc.poll() is None:
                assert time.monotonic() < deadline
                time.sleep(.001)
        else:
            getattr(proc, method)(timeout=5)
        assert proc.returncode == 0
        assert proc.peak_rss_bytes > 0
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()


@pytest.mark.parametrize('polled_rss', [0, 5 * 1024**2])
def test_reaped_rss_is_maximum_not_sum_or_kill_trigger(monkeypatch, tmp_path, polled_rss):
    import io
    runner = proctree.snapshot()[os.getpid()]
    parent = replace(runner, pid=runner.pid + 100000, ppid=runner.pid, rss=polled_rss)
    processes = {runner.pid: runner, parent.pid: parent}

    class ExitingParent:
        pid = parent.pid
        returncode = None
        peak_rss_bytes = 3 * 1024**2
        stdout, stderr = io.StringIO(), io.StringIO()

        def poll(self):
            return self.returncode

        def communicate(self, timeout=None):
            processes.pop(parent.pid, None)
            self.returncode = 0
            return '', ''

    # Two adopted children with peaks of 4 and 2 MiB. Their peaks must be
    # converted from Linux KiB and maximized with the direct child's 3 MiB.
    reaped = iter([(parent.pid + 1, 0, SimpleNamespace(ru_maxrss=4096)),
                   (parent.pid + 2, 0, SimpleNamespace(ru_maxrss=2048))])

    def wait_children(pid, flags):
        assert (pid, flags) == (-1, os.WNOHANG)
        try:
            return next(reaped)
        except StopIteration:
            raise ChildProcessError() from None

    monkeypatch.setenv('GEMMA_SANDBOX_MEM_BYTES', str(polled_rss + 1))
    monkeypatch.setattr(proctree, 'enable_subreaper', lambda: None)
    monkeypatch.setattr(proctree, 'snapshot', lambda: processes.copy())
    monkeypatch.setattr(proctree, 'RusagePopen', lambda *a, **kw: ExitingParent())
    monkeypatch.setattr(proctree.os, 'wait4', wait_children)
    def kill(live):
        assert live == {}
        return 0

    monkeypatch.setattr(proctree, 'kill_tree', kill)
    result = proctree.run_limited(['fake'], tmp_path, {})
    assert result['status'] == 'ok' and result['exit_code'] == 0
    assert result['metrics']['peak_rss_bytes'] == max(polled_rss, 4 * 1024**2)
    assert result['metrics']['mem_kills'] == 0


def test_envless_double_fork_is_reaped(execute, tmp_path):
    run, metrics = execute
    code = """
import os, time
r, w = os.pipe()
if os.fork():
    os.close(w)
    os.read(r, 1)
    os._exit(0)
os.close(r)
if os.fork():
    os._exit(0)
os.environ.clear()
os.setsid()
os.close(1)
os.close(2)
open('child.pid', 'w').write(str(os.getpid()))
os.write(w, b'1')
os.close(w)
time.sleep(600)
"""
    result = run(python(code), timeout=3)
    assert result.status == 'ok' and result.exit_code == 0
    assert metrics['orphan_kills'] >= 1
    # The adopted grandchild must be reaped, not merely left as a zombie.
    assert int((tmp_path / 'child.pid').read_text()) not in proctree.snapshot()


def test_pid_reuse_during_pidfd_open(monkeypatch):
    p = proctree.snapshot()[os.getpid()]
    processes = {p.pid: p}
    events = []

    def open_fd(pid):
        processes[pid] = replace(p, starttime=p.starttime + 1)
        events.append('open')
        return 123

    monkeypatch.setattr(proctree.os, 'pidfd_open', open_fd)
    monkeypatch.setattr(proctree, 'snapshot', lambda: processes)
    monkeypatch.setattr(proctree.signal, 'pidfd_send_signal', lambda *a: pytest.fail('reused pid signaled'))
    monkeypatch.setattr(proctree.os, 'close', lambda fd: events.append(('close', fd)))
    assert proctree.kill_tree({p.pid: p}) == 0
    assert events == ['open', ('close', 123)]


def test_reuse_after_verification_signals_bound_fd(monkeypatch):
    p = proctree.snapshot()[os.getpid()]
    events = []
    monkeypatch.setattr(proctree.os, 'pidfd_open', lambda pid: 123)

    def scan():
        events.append('verify')
        return {p.pid: p}

    def send(fd, sig):
        # A pid may now refer to another process; signaling the previously
        # opened fd still targets only the old identity (or returns ESRCH).
        assert events == ['verify']
        assert fd == 123 and sig == proctree.signal.SIGKILL
        events.append('signal fd')
        raise ProcessLookupError()

    monkeypatch.setattr(proctree, 'snapshot', scan)
    monkeypatch.setattr(proctree.signal, 'pidfd_send_signal', send)
    monkeypatch.setattr(proctree.os, 'kill', lambda *a: pytest.fail('bare pid signal'))
    monkeypatch.setattr(proctree.os, 'killpg', lambda *a: pytest.fail('group signal'))
    monkeypatch.setattr(proctree.os, 'close', lambda fd: events.append('close'))
    assert proctree.kill_tree({p.pid: p}) == 0
    assert events == ['verify', 'signal fd', 'close']


def test_stale_tracked_identity_replaced():
    runner = proctree.snapshot()[os.getpid()]
    child = replace(runner, pid=runner.pid + 100000, ppid=runner.pid)
    stale = replace(child, starttime=child.starttime - 1)
    tracked = {child.pid: stale}
    live = proctree.track_descendants(tracked, runner, {runner.pid: runner, child.pid: child})
    assert tracked[child.pid] == child
    assert live == {child.pid: child}
    with pytest.raises(RuntimeError, match='identity changed'):
        proctree.track_descendants(tracked, stale, {runner.pid: runner, child.pid: child})


def test_memory_excess_first_seen_in_cleanup(monkeypatch, tmp_path):
    import io
    runner = proctree.snapshot()[os.getpid()]
    parent = replace(runner, pid=runner.pid + 100000, ppid=runner.pid, rss=1024)
    child = replace(parent, pid=parent.pid + 1, rss=301 * 1024**2)
    processes = {runner.pid: runner, parent.pid: parent}

    class ExitingParent:
        pid = parent.pid
        returncode = None
        peak_rss_bytes = 4096
        stdout, stderr = io.StringIO(), io.StringIO()

        def poll(self):
            return self.returncode

        def communicate(self, timeout=None):
            # Parent exits 0 between live scan and cleanup. Only the cleanup
            # scan sees its adopted child above the 300 MiB aggregate limit.
            if self.returncode is None:
                processes.pop(parent.pid)
                self.returncode = 0
            return '', ''

    def kill(identities):
        if not identities:
            return 0
        assert identities == {child.pid: child}
        processes.pop(child.pid)
        return 1

    monkeypatch.setenv('GEMMA_SANDBOX_MEM_BYTES', str(300 * 1024**2))
    monkeypatch.setattr(proctree, 'enable_subreaper', lambda: None)
    monkeypatch.setattr(proctree, 'snapshot', lambda: processes.copy())
    monkeypatch.setattr(proctree, 'RusagePopen', lambda *a, **kw: ExitingParent())
    monkeypatch.setattr(proctree, 'kill_tree', kill)
    waits = 0

    def wait_children(pid, flags):
        nonlocal waits
        assert pid == -1
        waits += 1
        if waits == 1:
            # Simulate /proc missing a child during a fork/reparent race.
            # wait4 still sees it, so cleanup must scan again before success.
            processes[child.pid] = child
            return 0, 0, None
        raise ChildProcessError()

    monkeypatch.setattr(proctree.os, 'wait4', wait_children)
    result = proctree.run_limited(['fake'], tmp_path, {})
    assert result['status'] == 'error' and result['exit_code'] == 137
    assert 'killed: sandbox memory limit' in result['stderr']
    assert result['metrics']['mem_kills'] == 1
    assert result['metrics']['peak_rss_bytes'] > 300 * 1024**2
    assert result['metrics']['orphan_kills'] == 1


def test_threaded_supervisors_are_independent(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    def task(name, timeout):
        metrics = {}
        token = sandbox_env.command_metrics.set(metrics)
        try:
            code = ("import os,time; "
                    f"open('{name}.pid','w').write(str(os.getpid())); "
                    "time.sleep(.8); print('survived')")
            result = sandbox_env.execute_limited(python(code), tmp_path,
                                                  dict(os.environ), timeout=timeout)
            return result, metrics
        finally:
            sandbox_env.command_metrics.reset(token)

    with ThreadPoolExecutor(max_workers=2) as pool:
        fast = pool.submit(task, 'fast', .3)
        slow = pool.submit(task, 'slow', 3)
        fast_result, fast_metrics = fast.result()
        slow_result, slow_metrics = slow.result()
    assert fast_result.status == 'timeout'
    assert slow_result.status == 'ok' and slow_result.stdout == 'survived\n'
    assert fast_metrics['peak_rss_bytes'] > 0
    assert slow_metrics['peak_rss_bytes'] > 0
    assert_dead(tmp_path / 'fast.pid')
    assert_dead(tmp_path / 'slow.pid')


def test_real_memory_child_on_parent_exit(execute, tmp_path, monkeypatch):
    run, metrics = execute
    monkeypatch.setenv('GEMMA_SANDBOX_MEM_BYTES', str(300 * 1024**2))
    code = """
import os, time
r, w = os.pipe()
if os.fork():
    os.close(w)
    os.read(r, 1)
    os._exit(0)
os.close(r)
os.environ.clear()
os.setsid()
os.close(1)
os.close(2)
chunks = bytearray(320 * 1024**2)
open('child.pid', 'w').write(str(os.getpid()))
os.write(w, b'1')
os.close(w)
time.sleep(600)
"""
    result = run(python(code), timeout=5)
    assert result.status == 'error' and result.exit_code == 137
    assert 'killed: sandbox memory limit' in result.stderr
    assert metrics['mem_kills'] >= 1
    assert metrics['peak_rss_bytes'] > 300 * 1024**2
    assert_dead(tmp_path / 'child.pid')
