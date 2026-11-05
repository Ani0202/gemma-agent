"""Linux process identities and RSS, restricted to our uid (stdlib only)."""
from dataclasses import dataclass
import ctypes
import errno
import json
import os
import resource
import shutil
import subprocess
import sys
import time
from pathlib import Path
import signal


@dataclass(frozen=True)
class Process:
    pid: int
    ppid: int
    pgid: int
    sid: int
    rss: int
    starttime: int
    state: str


def snapshot():
    processes = {}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            # comm may contain spaces and parentheses.
            fields = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
            pid = int(entry.name)
            processes[pid] = Process(pid, int(fields[1]), int(fields[2]),
                                     int(fields[3]), int(fields[21]) * os.sysconf('SC_PAGE_SIZE'),
                                     int(fields[19]), fields[0])
        except (OSError, ValueError, IndexError):
            continue  # Process exited during the scan.
    return processes


def descendants(pids, processes=None):
    processes = snapshot() if processes is None else processes
    found = {pids} if isinstance(pids, int) else set(pids)
    while True:
        children = {p.pid for p in processes.values() if p.ppid in found}
        if children <= found:
            return found
        found.update(children)


def survivors(pids, processes=None):
    """Return live identities from a pid -> Process mapping, excluding zombies."""
    processes = snapshot() if processes is None else processes
    return {pid: p for pid, old in pids.items()
            if (p := processes.get(pid)) is not None
            and p.starttime == old.starttime and p.state not in ('Z', 'X')}


def tree_rss(pids, processes=None):
    return sum(p.rss for p in survivors(pids, processes).values())


def kill_tree(pids):
    """Open pidfds, then verify starttime, then signal the bound identities."""
    killed = 0
    for pid, old in pids.items():
        try:
            fd = os.pidfd_open(pid)
        except ProcessLookupError:
            continue
        try:
            if pid in survivors({pid: old}):
                signal.pidfd_send_signal(fd, signal.SIGKILL)
                killed += 1
        except ProcessLookupError:
            pass
        finally:
            os.close(fd)
    return killed


def enable_subreaper():
    if sys.platform != 'linux':
        raise RuntimeError('Sandbox supervision requires Linux')
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER, unprivileged
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))


def track_descendants(tracked, runner, processes):
    # Dedicated supervisor: no helper processes, and exactly one task. Adopted
    # orphans belong to that task regardless of their environment, pgid or sid.
    if runner.pid not in survivors({runner.pid: runner}, processes):
        raise RuntimeError('Supervisor identity changed')
    selected = descendants({runner.pid}, processes) - {runner.pid}
    for pid in selected:
        tracked[pid] = processes[pid]  # Replace stale identities on pid reuse.
    return survivors(tracked, processes)


class RusagePopen(subprocess.Popen):
    """Keep Popen's status/pipe handling while collecting the child's rusage.

    POSIX Popen reaps through both _internal_poll and _try_wait (wait and
    communicate). Both must use wait4 before the kernel discards the rusage.
    """
    peak_rss_bytes = 0

    def _waitpid(self, pid, flags):
        pid, status, usage = os.wait4(pid, flags)
        if pid:
            self.peak_rss_bytes = max(self.peak_rss_bytes, usage.ru_maxrss * 1024)
        return pid, status

    def _internal_poll(self, _deadstate=None):
        # Popen's private poll callback signature differs between Python 3.12
        # and 3.13. Keep its locking/status semantics with our wait4 callback.
        if self.returncode is None and self._waitpid_lock.acquire(False):
            try:
                if self.returncode is None:
                    pid, status = self._waitpid(self.pid, os.WNOHANG)
                    if pid == self.pid:
                        self._handle_exitstatus(status)
            except OSError as exc:
                if _deadstate is not None:
                    self.returncode = _deadstate
                elif exc.errno == errno.ECHILD:
                    self.returncode = 0
            finally:
                self._waitpid_lock.release()
        return self.returncode

    def _try_wait(self, wait_flags):
        try:
            return self._waitpid(self.pid, wait_flags)
        except ChildProcessError:
            return self.pid, 0  # Match Popen's already-reaped child behavior.


def run_limited(command, cwd, env, timeout=300, *, shell=None,
                max_output_chars=10 * 1024 * 1024):
    """Installed executor contract, with host process-tree limits and cleanup.

    peak_rss_bytes is the maximum of sampled tree RSS and reaped ru_maxrss
    (KiB on Linux, converted to bytes). The reaped value is a per-process
    peak, not a simultaneous tree sum. Only sampled tree RSS triggers kills.
    """
    enable_subreaper()
    runner = snapshot()[os.getpid()]
    start = time.perf_counter()
    metrics = dict(peak_rss_bytes=0, mem_kills=0, orphan_kills=0)
    tracked = {}
    peak = 0
    if shell is None:
        shell = isinstance(command, str)
    try:
        limit = int(os.environ.get('GEMMA_SANDBOX_MEM_BYTES', 4 * 1024**3))
        as_limit = int(os.environ.get('GEMMA_SANDBOX_AS_BYTES', 8 * 1024**3))
        # A bin/job fallback may already impose a lower hard AS cap. Raising
        # that cap requires privileges; preserve the tighter inherited limit.
        hard_as = resource.getrlimit(resource.RLIMIT_AS)[1]
        if hard_as != resource.RLIM_INFINITY:
            as_limit = min(as_limit, hard_as)
        prlimit = shutil.which('prlimit')
        if prlimit:
            # RLIMIT_AS is a backstop only: virtual space differs from RSS, and
            # a per-process cap cannot enforce aggregate process-tree memory.
            if shell:
                command = ['/bin/sh', '-c', command] if isinstance(command, str) else ['/bin/sh', '-c', *command]
            elif isinstance(command, str):
                command = [command]
            command = [prlimit, f'--as={as_limit}', '--', *command]
            shell = False
        proc = RusagePopen(command, shell=shell, cwd=str(cwd), env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding='utf-8', errors='replace',
                                start_new_session=True)
    except (RuntimeError, OSError, ValueError) as exc:
        return dict(status='error', stdout='', stderr=str(exc), exit_code=-1,
                    duration_seconds=round(time.perf_counter() - start, 3), metrics=metrics)

    status, code = None, None
    memory_killed = False

    def scan():
        nonlocal peak, status, code, memory_killed
        processes = snapshot()
        live = track_descendants(tracked, runner, processes)
        rss = tree_rss(live, processes)
        peak = max(peak, rss)
        # Every scan, including exit and cleanup, must classify memory excess.
        if rss > limit and not memory_killed:
            status, code = 'error', 137
            memory_killed = True
            metrics['mem_kills'] += 1
        return live

    def reap():
        nonlocal peak
        if proc.poll() is None:
            return False  # Popen owns the direct child's status.
        peak = max(peak, proc.peak_rss_bytes)
        # Once Popen has reaped its child, all remaining children are task
        # orphans. ECHILD confirms cleanup even if a /proc snapshot missed a
        # fork/reparent race; wait4 returning pid 0 requires another scan.
        while True:
            try:
                pid, _, usage = os.wait4(-1, os.WNOHANG)
            except ChildProcessError:
                return True
            if pid == 0:
                return False
            peak = max(peak, usage.ru_maxrss * 1024)

    def cleanup():
        seen = set()
        deadline = time.monotonic() + 2
        while True:
            live = scan()
            seen.update((p.pid, p.starttime) for p in live.values())
            kill_tree(live)
            empty = reap()
            if not live and empty:
                return len(seen)
            if time.monotonic() >= deadline:
                raise RuntimeError('Sandbox processes survived SIGKILL')
            time.sleep(0.025)

    stdout, stderr = '', ''
    try:
        while True:
            scan()
            if memory_killed:
                cleanup()
                break
            if timeout is not None and time.perf_counter() - start >= timeout:
                status, code = 'timeout', 124
                cleanup()
                break
            if proc.poll() is not None:
                count = cleanup()
                metrics['orphan_kills'] += count
                break
            wait = 0.25 if timeout is None else max(0.001, min(0.25, timeout - (time.perf_counter() - start)))
            try:
                stdout, stderr = proc.communicate(timeout=wait)
            except subprocess.TimeoutExpired:
                continue
            # Scan and clean up even if detached daemons closed their pipe fds.
            count = cleanup()
            metrics['orphan_kills'] += count
            break
        try:
            stdout, stderr = proc.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            stdout, stderr = '', ''
        if status is None:
            status, code = ('ok' if proc.returncode == 0 else 'error'), proc.returncode
        if status != 'timeout':
            if max_output_chars and len(stdout) > max_output_chars:
                stdout = stdout[:max_output_chars] + '\n...[Output truncated at 10MB limit]\n'
            if max_output_chars and len(stderr) > max_output_chars:
                stderr = stderr[:max_output_chars] + '\n...[Output truncated at 10MB limit]\n'
    except (RuntimeError, OSError, ValueError) as exc:
        status, code, stdout, stderr = 'error', 1, '', str(exc)
    finally:
        cleanup()  # Fail closed if a process cannot be killed.
        proc.stdout.close()
        proc.stderr.close()
        metrics['peak_rss_bytes'] = peak
    if memory_killed:
        status, code = 'error', 137
        stderr += '\nkilled: sandbox memory limit\n'
    return dict(status=status, stdout=stdout or '', stderr=stderr or '',
                exit_code=code, duration_seconds=round(time.perf_counter() - start, 3),
                metrics=metrics)


def supervisor_source():
    # Single-file Kaggle staging supplies SOURCE for the embedded module.
    return globals().get('SOURCE') or Path(__file__).read_text()


def supervisor_main():
    try:
        result = run_limited(**json.load(sys.stdin))
    except (RuntimeError, OSError, ValueError) as exc:
        result = dict(status='error', stdout='', stderr=str(exc), exit_code=-1,
                      duration_seconds=0, metrics={})
    print(json.dumps(result))
