"""Offline identity/membership tests; opt-in live allocation test (under bin/job, <3 GiB)."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace
import uuid

import pytest

REPO = Path(__file__).resolve().parents[2]
MG = REPO / "bin/memguard"


@pytest.fixture
def mg():
    loader = importlib.machinery.SourceFileLoader("memguard", str(MG))
    spec = importlib.util.spec_from_loader("memguard", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture
def args():
    return SimpleNamespace(marker="GEMMA_JOB_CAP", unmarked_rss=3 * 1024**3,
                           roots=["/tmp", "/home/ubuntu/work/gemma"])


def proc(pid, ppid=1, pgid=10, starttime=123, comm="python", rss=1024, uid=None):
    return dict(pid=pid, ppid=ppid, pgid=pgid, starttime=starttime, comm=comm,
                rss=rss, uid=os.getuid() if uid is None else uid, state="S")


def mock_world(monkeypatch, mg, initial, markers, records=()):
    world = dict(initial)
    monkeypatch.setattr(mg, "snapshot", lambda: dict(world))
    monkeypatch.setattr(mg, "marker_value", lambda p, _: markers.get(p))
    monkeypatch.setattr(mg, "cwd_of", lambda p: "/tmp/test")
    monkeypatch.setattr(mg, "running_jobs", lambda: list(records))
    monkeypatch.setattr(mg, "proc_stat", lambda p: world.get(p))
    clock = [0.0]
    monkeypatch.setattr(mg.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(mg.time, "sleep", lambda t: clock.__setitem__(0, clock[0] + t))
    return world


def select(mg, args):
    _, jobs = mg.find_jobs(mg.snapshot(), args, set())
    assert len(jobs) == 1
    return next(iter(jobs.values()))


def test_unmarked_small_child_is_never_signalled(monkeypatch, mg, args):
    world = mock_world(monkeypatch, mg, {10: proc(10), 11: proc(11, ppid=10)}, {10: b"cap"})
    sent = []

    def kill(d, log):
        sent.append(d["pid"])
        world.pop(d["pid"])
        return True

    monkeypatch.setattr(mg, "send_kill", kill)
    killed, survivors = mg.kill_tree(select(mg, args), args, set(), lambda _: None)
    assert killed == sent == [10]
    assert survivors == []
    assert 11 in world


@pytest.mark.parametrize("pidfd", [False, True])
def test_pid_reuse_is_not_signalled(monkeypatch, mg, pidfd):
    calls = []
    monkeypatch.setattr(mg, "proc_stat", lambda p: proc(p, starttime=999))
    monkeypatch.setattr(mg.os, "kill", lambda *a: calls.append(a))
    if pidfd:
        monkeypatch.setattr(mg.os, "pidfd_open", lambda p: 42)
        monkeypatch.setattr(mg.signal, "pidfd_send_signal", lambda *a: calls.append(a))
        closed = []
        monkeypatch.setattr(mg.os, "close", closed.append)
    else:
        monkeypatch.delattr(mg.os, "pidfd_open", raising=False)
    assert not mg.send_kill(proc(10), lambda _: None)
    assert calls == []
    if pidfd:
        assert closed == [42]


def test_pidfd_is_opened_before_identity_check(monkeypatch, mg):
    calls = []
    monkeypatch.setattr(mg.os, "pidfd_open", lambda p: calls.append("open") or 42)
    monkeypatch.setattr(mg, "proc_stat", lambda p: calls.append("check") or proc(p))
    monkeypatch.setattr(mg.signal, "pidfd_send_signal", lambda *a: calls.append("signal"))
    monkeypatch.setattr(mg.os, "close", lambda fd: calls.append("close"))
    assert mg.send_kill(proc(10), lambda _: None)
    assert calls == ["open", "check", "signal", "close"]


def test_oom_write_skips_reused_identity(monkeypatch, mg):
    import io
    class File(io.StringIO):
        def close(self):
            pass
    output = File()
    monkeypatch.setattr("builtins.open", lambda *a, **k: output)
    monkeypatch.setattr(mg, "proc_stat", lambda p: proc(p, starttime=999))
    assert mg.raise_oom_adj({10: proc(10)}, False) == 0
    assert output.getvalue() == ""


def test_marked_orphans_and_separate_wrappers(monkeypatch, mg, args):
    records = [dict(name="a", pid=10, pgid=10), dict(name="b", pid=20, pgid=20)]
    world = mock_world(monkeypatch, mg, {
        11: proc(11, pgid=10), 21: proc(21, pgid=20), 31: proc(31, pgid=30)},
        {11: b"cap", 21: b"cap", 31: b"cap"}, records)
    _, jobs = mg.find_jobs(world, args, set())
    assert sorted(sorted(j["pids"]) for j in jobs.values()) == [[11], [21], [31]]
    for j in list(jobs.values()):
        monkeypatch.setattr(mg, "send_kill", lambda d, log: world.pop(d["pid"]) is not None)
        assert mg.kill_tree(j, args, set(), lambda _: None) == (j["pids"], [])
    assert not world


def test_fork_during_kill_is_found_after_root_grace(monkeypatch, mg, args):
    records = [dict(name="job", pid=10, pgid=10)]
    world = mock_world(monkeypatch, mg, {10: proc(10), 11: proc(11, ppid=10)},
                       {10: b"cap", 11: b"cap", 12: b"cap"}, records)
    sent = []

    def kill(d, log):
        sent.append(d["pid"])
        world.pop(d["pid"])
        if d["pid"] == 10:
            world[12] = proc(12)  # new orphan discovered after wrapper grace/kill
        return True

    monkeypatch.setattr(mg, "send_kill", kill)
    assert mg.kill_tree(select(mg, args), args, set(), lambda _: None) == ([10, 11, 12], [])
    assert sent == [11, 10, 12]


def test_survivors_use_independent_final_inventory(monkeypatch, mg, args):
    mock_world(monkeypatch, mg, {10: proc(10)}, {10: b"cap", 99: b"cap"})
    job = select(mg, args)
    inventories = iter([{}, {}, {99: proc(99)}])
    monkeypatch.setattr(mg, "inventory", lambda *a: next(inventories))
    monkeypatch.setattr(mg, "send_kill", lambda *a: pytest.fail("no signal expected"))
    assert mg.kill_tree(job, args, set(), lambda _: None) == ([], [99])


@pytest.mark.parametrize("comm", ["claude", "node", "codex", "tmux", "bash"])
def test_markers_do_not_override_session_exclusion(monkeypatch, mg, args, comm):
    world = mock_world(monkeypatch, mg, {9: proc(9, comm="claude"),
                       10: proc(10, ppid=9, comm=comm)}, {10: b"cap"})
    assert mg.find_jobs(world, args, set())[0] == {}


def test_legacy_status_and_job_names(monkeypatch, mg, args, tmp_path):
    directory = tmp_path / "ops/jobs"
    directory.mkdir(parents=True)
    (directory / "legacy.status").write_text("running 10 2026-11-05T00:00:00Z\n")
    (directory / "current.status").write_text("running 20 now 20\n")
    (directory / "done.status").write_text("done 0 now\n")
    monkeypatch.setattr(mg, "REPO", str(tmp_path))
    records = mg.running_jobs()
    assert records == [dict(name="current", pid=20, pgid=20), dict(name="legacy", pid=10, pgid=None)]
    world = {10: proc(10), 11: proc(11, ppid=10), 21: proc(21, pgid=20)}
    monkeypatch.setattr(mg, "marker_value", lambda *a: b"cap")
    targets, jobs = mg.find_jobs(world, args, set())
    assert set(targets) == {10, 11, 21}
    assert {j["name"]: sorted(j["pids"]) for j in jobs.values()} == {"legacy": [10, 11], "current": [21]}


def test_job_name_matches_pid_and_process_group(mg):
    records = [dict(name="wrapper", pid=10, pgid=20), dict(name="legacy", pid=30, pgid=None)]
    procs = {10: proc(10, pgid=20), 11: proc(11, pgid=20), 31: proc(31, pgid=30)}
    assert mg.job_name(10, procs, records) == "wrapper"
    assert mg.job_name(11, procs, records) == "wrapper"
    assert mg.job_name(20, procs, records) == "wrapper"
    assert mg.job_name(31, procs, records) == "legacy"
    assert mg.job_name(99, procs, records) is None


@pytest.mark.parametrize("failure", [7, "timeout"])
def test_mail_failure_is_bounded_and_logged(monkeypatch, mg, failure):
    def run(*a, **kw):
        assert kw["timeout"] == 10
        if failure == "timeout":
            raise subprocess.TimeoutExpired(a[0], 10)
        return SimpleNamespace(returncode=failure)
    monkeypatch.setattr(mg.subprocess, "run", run)
    messages = []
    mg.send_mail("test", messages.append)
    assert len(messages) == 1 and "mail failed" in messages[0]



def test_final_root_is_reclassified_before_signal(monkeypatch, mg, args):
    world = mock_world(monkeypatch, mg, {10: proc(10), 11: proc(11, ppid=10)},
                       {10: b"cap", 11: b"cap"})
    job = select(mg, args)
    sent = []

    def kill(d, log):
        sent.append(d["pid"])
        world.pop(d["pid"])
        # The wrapper execs a protected session process during its grace period.
        world[10] = proc(10, comm="node")
        return True

    monkeypatch.setattr(mg, "send_kill", kill)
    assert mg.kill_tree(job, args, set(), lambda _: None) == ([11], [])
    assert sent == [11]


def test_other_uid_and_small_unmarked_are_excluded(monkeypatch, mg, args):
    world = mock_world(monkeypatch, mg, {
        10: proc(10, uid=os.getuid() + 1), 11: proc(11),
        12: proc(12, rss=4 * 1024**3)}, {10: b"cap"})
    assert set(mg.find_jobs(world, args, set())[0]) == {12}


def test_self_job_siblings_are_excluded(monkeypatch, mg, args):
    records = [dict(name="guard", pid=10, pgid=10), dict(name="work", pid=20, pgid=20)]
    world = mock_world(monkeypatch, mg, {
        10: proc(10), 11: proc(11, ppid=10), 12: proc(12, ppid=10), 20: proc(20, pgid=20)},
        {p: b"cap" for p in (10, 11, 12, 20)}, records)
    assert set(mg.find_jobs(world, args, {10, 11})[0]) == {20}


def test_failed_signal_stops_at_deadline_and_reports_survivor(monkeypatch, mg, args):
    mock_world(monkeypatch, mg, {10: proc(10)}, {10: b"cap"})
    monkeypatch.setattr(mg, "send_kill", lambda *a: False)
    assert mg.kill_tree(select(mg, args), args, set(), lambda _: None) == ([], [10])
    assert 5 <= mg.time.monotonic() < 5.3


def test_proc_stat_field_22_and_allowed_reads(monkeypatch, mg):
    fields = ["S", "1", "10"] + ["0"] * 16 + ["987654"]
    reads = []

    def read(path, mode="r"):
        reads.append(path)
        if path.endswith("/stat"):
            return "10 (name with ) spaces) " + " ".join(fields)
        if path.endswith("/status"):
            return f"Name: python\nUid: {os.getuid()}\nVmRSS: 4 kB\n"
        pytest.fail(f"forbidden read: {path}")

    monkeypatch.setattr(mg, "read", read)
    monkeypatch.setattr(mg.os, "stat", lambda p: SimpleNamespace(st_uid=os.getuid()))
    info = mg.proc_info(10)
    assert info["starttime"] == 987654
    assert info["pgid"] == 10
    assert info["rss"] == 4096
    assert set(reads) == {"/proc/10/stat", "/proc/10/status"}

STEP = 200 * 1024 * 1024
ALLOC = f"""
import time
held = []
for _ in range(6):
    held.append(b"\\x01" * {STEP})
    time.sleep(0.4)
time.sleep(120)
"""
CHILD = f"""
import subprocess, sys, time
subprocess.Popen([sys.executable, "-c", {ALLOC!r}])
time.sleep(120)
"""


def marked_live(mg, marker):
    return {p for p, d in mg.snapshot().items()
            if d["state"] not in {"Z", "X"} and mg.marker_value(p, marker) is not None}


@pytest.mark.skipif(os.environ.get("MEMGUARD_LIVE") != "1", reason="set MEMGUARD_LIVE=1 under bin/job")
def test_memguard_kills_job_tree_and_spares_dummy(tmp_path, mg):
    assert "GEMMA_JOB_CAP" in os.environ, "run the live test under bin/job"
    marker = "GEMMA_MGTEST_" + uuid.uuid4().hex
    root = tmp_path / "jobcwd"
    root.mkdir()
    rcfile = tmp_path / "rc"
    log = tmp_path / "memguard.log"
    env_clean = {k: v for k, v in os.environ.items()
                 if k != "GEMMA_JOB_CAP" and not k.startswith("GEMMA_MGTEST_")}
    # Both allocators peak at 1.2 GiB each, with only small interpreter/wrapper overhead.
    dummy = subprocess.Popen([sys.executable, "-c", ALLOC], cwd="/", env=env_clean)
    baseline = Path(f"/proc/{dummy.pid}/oom_score_adj").read_text().strip()
    job = subprocess.Popen(["bash", "-c", '"$PYTHON" -c "$CHILD_SRC"; echo $? > "$RCFILE"'],
                           cwd=root, start_new_session=True,
                           env={**env_clean, marker: "test", "CHILD_SRC": CHILD,
                                "PYTHON": sys.executable, "RCFILE": str(rcfile)})
    guard = None
    try:
        time.sleep(3)
        assert len(marked_live(mg, marker)) >= 3
        guard = subprocess.Popen(
            [sys.executable, str(MG), "--marker", marker, "--max-total", "0.8", "--min-available", "0",
             "--unmarked-rss", "0.5", "--interval", "0.5", "--roots", str(tmp_path),
             "--log", str(log), "--no-mail"], env=env_clean,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and "survivors=" not in (log.read_text() if log.exists() else ""):
            time.sleep(0.2)
        text = log.read_text()
        assert "KILL" in text and "survivors=[]" in text, text
        job.wait(timeout=10)
        assert marked_live(mg, marker) == set(), "fresh inventory found marked survivors"
        assert rcfile.read_text().strip() == "137"
        assert mg.proc_info(dummy.pid)["state"] not in {"Z", "X"}
        assert mg.marker_value(dummy.pid, "GEMMA_JOB_CAP") is None
        assert Path(f"/proc/{dummy.pid}/oom_score_adj").read_text().strip() == baseline
        assert text.count("KILL") == 1, text
    finally:
        if guard and guard.poll() is None:
            guard.kill()
            guard.wait(timeout=5)
        # Discover descendants and marked orphans BEFORE killing their parents.
        procs = mg.snapshot()
        cleanup = set(mg.descendants(job.pid, procs)) | marked_live(mg, marker)
        for p in sorted(cleanup - {job.pid}):
            d = procs.get(p)
            if d:
                mg.send_kill(d, lambda _: None)
        for child in (dummy, job):
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)
