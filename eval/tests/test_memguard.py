"""Offline identity/membership tests; opt-in live allocation test (<3 GiB)."""
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
    return SimpleNamespace()


def proc(pid, ppid=1, pgid=10, starttime=123, comm="python", rss=1024, uid=None):
    return dict(pid=pid, ppid=ppid, pgid=pgid, starttime=starttime, comm=comm,
                rss=rss, uid=os.getuid() if uid is None else uid, state="S")


def mock_world(monkeypatch, mg, initial, markers, records=()):
    world = dict(initial)
    monkeypatch.setattr(mg, "current_boot_id", lambda: "boot-id")
    monkeypatch.setattr(mg, "snapshot", lambda: dict(world))
    # Legacy records exercise ancestry admission; record-free fixtures use job IDs.
    monkeypatch.setattr(mg, "marker_value", lambda p, marker:
                        markers.get(p) if marker == "GEMMA_JOB_CAP" or
                        (marker == "GEMMA_JOB_ID" and not records) else None)
    original_read = mg.read
    source = (REPO / "bin/job").read_text()
    script = "\n" + source.split("GEMMA_JOB_CAP=$cap setsid nohup bash -c '\n", 1)[1].split("    ' _ \"$name\"", 1)[0]
    def read(path, mode="r"):
        for record in records:
            if str(path) == f"/proc/{record['pid']}/cmdline":
                return b"\0".join([b"bash", b"-c", script.encode(), b"_", record["name"].encode(), b"command", b""])
        if str(path).startswith("/proc/") and str(path).endswith("/cmdline"):
            return b"python3\0worker.py\0"
        if str(path).startswith("/proc/") and str(path).endswith("/environ"):
            pid = int(str(path).split("/")[2])
            job_id = mg.marker_value(pid, "GEMMA_JOB_ID")
            return b"" if job_id is None else b"GEMMA_JOB_ID=" + job_id + b"\0"
        return original_read(path, mode)
    monkeypatch.setattr(mg, "read", read)
    monkeypatch.setattr(mg, "running_jobs", lambda: list(records))
    monkeypatch.setattr(mg, "proc_stat", lambda p: world.get(p))
    monkeypatch.setattr(mg, "proc_info", lambda p: world.get(p))
    monkeypatch.setattr(mg, "runs_memguard", lambda p: False)
    clock = [0.0]
    monkeypatch.setattr(mg.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(mg.time, "sleep", lambda t: clock.__setitem__(0, clock[0] + t))
    return world


def select(mg, args):
    _, jobs = mg.find_jobs(mg.snapshot(), args, set())
    assert len(jobs) == 1
    return next(iter(jobs.values()))


def test_child_without_job_provenance_is_never_signalled(monkeypatch, mg, args):
    world = mock_world(monkeypatch, mg, {10: proc(10), 11: proc(11, ppid=10)}, {10: b"cap"})
    sent = []

    def kill(d, log, args, known_jobs=None):
        sent.append(d["pid"])
        world.pop(d["pid"])
        return True

    monkeypatch.setattr(mg, "send_kill", kill)
    killed, survivors = mg.kill_tree(select(mg, args), args, set(), lambda _: None)
    assert killed == sent == [10]
    assert survivors == []
    assert 11 in world


@pytest.mark.parametrize("pidfd", [False, True])
def test_pid_reuse_is_not_signalled(monkeypatch, mg, args, pidfd):
    calls = []
    monkeypatch.setattr(mg, "proc_info", lambda p: proc(p, starttime=999))
    monkeypatch.setattr(mg.os, "kill", lambda *a: calls.append(a))
    if pidfd:
        monkeypatch.setattr(mg.os, "pidfd_open", lambda p: 42)
        monkeypatch.setattr(mg.signal, "pidfd_send_signal", lambda *a: calls.append(a))
        closed = []
        monkeypatch.setattr(mg.os, "close", closed.append)
    else:
        monkeypatch.delattr(mg.os, "pidfd_open", raising=False)
    assert not mg.send_kill(proc(10), lambda _: None, args)
    assert calls == []
    if pidfd:
        assert closed == [42]


def test_pidfd_is_opened_before_identity_check(monkeypatch, mg, args):
    calls = []
    monkeypatch.setattr(mg.os, "pidfd_open", lambda p: calls.append("open") or 42)
    monkeypatch.setattr(mg, "proc_info", lambda p: calls.append("check") or proc(p, ppid=0))
    monkeypatch.setattr(mg, "snapshot", lambda: {})
    monkeypatch.setattr(mg, "running_jobs", lambda: [])
    monkeypatch.setattr(mg, "marker_value", lambda *a: b"cap")
    monkeypatch.setattr(mg.signal, "pidfd_send_signal", lambda *a: calls.append("signal"))
    monkeypatch.setattr(mg.os, "close", lambda fd: calls.append("close"))
    monkeypatch.setattr(mg, "read", lambda path, mode="r":
                        b"GEMMA_JOB_ID=cap\0" if path.endswith("/environ") else b"")
    assert mg.send_kill(proc(10), lambda _: None, args)
    assert calls == ["open", "check", "check", "signal", "close"]


def test_oom_write_skips_reused_identity(monkeypatch, mg, args):
    import io
    class File(io.StringIO):
        def close(self):
            pass
    output = File()
    monkeypatch.setattr("builtins.open", lambda *a, **k: output)
    monkeypatch.setattr(mg, "proc_info", lambda p: proc(p, starttime=999))
    assert mg.raise_oom_adj({10: proc(10)}, False, args) == 0
    assert output.getvalue() == ""


def test_marked_orphans_and_separate_wrappers(monkeypatch, mg, args):
    records = [dict(name="a", pid=10, pgid=10), dict(name="b", pid=20, pgid=20)]
    world = mock_world(monkeypatch, mg, {
        11: proc(11, pgid=10), 21: proc(21, pgid=20), 31: proc(31, pgid=30)},
        {11: b"cap", 21: b"cap", 31: b"cap"}, records)
    monkeypatch.setattr(mg, "marker_value", lambda p, marker:
                        str(p).encode() if marker == "GEMMA_JOB_ID" else None)
    _, jobs = mg.find_jobs(world, args, set())
    assert sorted(sorted(j["pids"]) for j in jobs.values()) == [[11], [21], [31]]
    for j in list(jobs.values()):
        monkeypatch.setattr(mg, "send_kill", lambda d, log, args, known_jobs=None: world.pop(d["pid"]) is not None)
        assert mg.kill_tree(j, args, set(), lambda _: None) == (j["pids"], [])
    assert not world


def test_fork_during_kill_is_found_after_root_grace(monkeypatch, mg, args):
    records = [dict(name="job", pid=10, pgid=10)]
    world = mock_world(monkeypatch, mg, {10: proc(10), 11: proc(11, ppid=10)},
                       {10: b"cap", 11: b"cap", 12: b"cap"}, records)
    monkeypatch.setattr(mg, "marker_value", lambda p, marker:
                        b"job/boot/123" if marker == "GEMMA_JOB_ID" else b"cap")
    records[0]["job_id"] = b"job/boot/123"
    sent = []

    def kill(d, log, args, known_jobs=None):
        sent.append(d["pid"])
        world.pop(d["pid"])
        if d["pid"] == 10:
            assert mg.time.monotonic() >= 3
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
    world = mock_world(monkeypatch, mg, {
        10: proc(10), 11: proc(11, ppid=10), 20: proc(20, pgid=20),
        21: proc(21, ppid=20, pgid=20)}, {}, records)
    # The fixture supplies the actual installed wrapper body, even though status
    # records here live in a temporary repository.
    original_read = mg.read
    monkeypatch.setattr(mg, "read", lambda path, mode="r":
                        (REPO / "bin/job").read_text() if str(path) == str(tmp_path / "bin/job")
                        else original_read(path, mode))
    targets, jobs = mg.find_jobs(world, args, set())
    assert set(targets) == {10, 11, 20, 21}
    assert {j["name"]: sorted(j["pids"]) for j in jobs.values()} == {
        "legacy": [10, 11], "current": [20, 21]}



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

    def kill(d, log, args, known_jobs=None):
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
    assert mg.find_jobs(world, args, set())[0] == {}


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
import resource, time
resource.setrlimit(resource.RLIMIT_AS, (1536 * 1024**2, 1536 * 1024**2))
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


def marked_live(mg, marker, value):
    return {p for p, d in mg.snapshot().items()
            if d["state"] not in {"Z", "X"} and mg.marker_value(p, marker) == value.encode()}


@pytest.mark.skipif(os.environ.get("MEMGUARD_LIVE") != "1", reason="set MEMGUARD_LIVE=1")
def test_memguard_kills_job_tree_and_spares_dummy(tmp_path, mg, args):
    marker = "GEMMA_JOB_ID"
    job_id = "mgtest-workload/" + uuid.uuid4().hex
    root = tmp_path / "jobcwd"
    root.mkdir()
    rcfile = tmp_path / "rc"
    log = tmp_path / "memguard.log"
    env_clean = {k: v for k, v in os.environ.items()
                 if k not in {"GEMMA_JOB_CAP", "GEMMA_JOB_ID"} and not k.startswith("GEMMA_MGTEST_")}
    # Both allocators peak at 1.2 GiB each, with only small interpreter/wrapper overhead.
    dummy = subprocess.Popen([sys.executable, "-c", ALLOC], cwd="/", env=env_clean)
    baseline = Path(f"/proc/{dummy.pid}/oom_score_adj").read_text().strip()
    job = subprocess.Popen(["bash", "-c", '"$PYTHON" -c "$CHILD_SRC"; echo $? > "$RCFILE"'],
                           cwd=root, start_new_session=True,
                           env={**env_clean, marker: job_id, "CHILD_SRC": CHILD,
                                "PYTHON": sys.executable, "RCFILE": str(rcfile)})
    guard = None
    try:
        time.sleep(3)
        assert len(marked_live(mg, marker, job_id)) >= 3
        # Confine the live guard's discovery to this test's unique job identity.
        # Production admission remains fixed to GEMMA_JOB_ID; no private marker bypass.
        guard_source = f"""
import os, types
from pathlib import Path
module = types.ModuleType("memguard_test")
module.__file__ = {str(MG)!r}
exec(compile(Path(module.__file__).read_text(), module.__file__, "exec"), module.__dict__)
snapshot = module.snapshot
module.snapshot = lambda: {{p: d for p, d in snapshot().items()
    if p == os.getpid() or module.marker_value(p, "GEMMA_JOB_ID") == {job_id.encode()!r}}}
module.main()
"""
        guard = subprocess.Popen(
            [sys.executable, "-c", guard_source, "--max-total", "0.8", "--min-available", "0",
             "--interval", "0.5",
             "--log", str(log), "--no-mail"], env=env_clean,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and "survivors=" not in (log.read_text() if log.exists() else ""):
            time.sleep(0.2)
        text = log.read_text()
        assert "KILL" in text and "survivors=[]" in text, text
        job.wait(timeout=10)
        assert marked_live(mg, marker, job_id) == set(), "fresh inventory found marked survivors"
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
        cleanup = set(mg.descendants(job.pid, procs)) | marked_live(mg, marker, job_id)
        for p in sorted(cleanup - {job.pid}):
            d = procs.get(p)
            if d:
                mg.send_kill(d, lambda _: None, args)
        for child in (dummy, job):
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("survives", [False, True])
def test_escaped_members_remain_in_job(monkeypatch, mg, args, legacy, survives):
    record = dict(name="job", pid=10, pgid=None if legacy else 10)
    world = mock_world(monkeypatch, mg, {10: proc(10), 11: proc(11, ppid=10)},
                       {10: b"cap", 11: b"cap"}, [record])
    if not legacy:
        record.update(job_id=b"job/boot/123")
        monkeypatch.setattr(mg, "marker_value", lambda p, marker:
                            b"job/boot/123" if marker == "GEMMA_JOB_ID" else b"cap")
    job = select(mg, args)
    # Change membership after discovery, as setsid/reparenting would do.
    world[11] = proc(11, ppid=1, pgid=11)
    # Normal polling and the kill/final inventories must agree.
    _, jobs = mg.find_jobs(world, args, set(), known_jobs={job["key"]: job})
    assert set(jobs[job["key"]]["members"]) == {10, 11}
    sent = []

    def kill(d, log, args, known_jobs=None):
        sent.append(d["pid"])
        if survives and d["pid"] == 11:
            return False
        world.pop(d["pid"])
        return True

    monkeypatch.setattr(mg, "send_kill", kill)
    assert mg.kill_tree(job, args, set(), lambda _: None) == (
        [10] if survives else [10, 11], [11] if survives else [])
    assert 11 in sent


def test_job_id_is_exact_primary_key_and_keeps_allowlist(monkeypatch, mg, args):
    world = mock_world(monkeypatch, mg, {
        10: proc(10), 11: proc(11, pgid=99), 12: proc(12),
        13: proc(13, comm="node"), 14: proc(14)},
        {10: b"cap", 11: b"different-cap", 12: b"cap", 13: b"cap"})
    ids = {10: b"job/[boot]/123", 11: b"job/[boot]/123",
           12: b"job/[boot]/1234", 13: b"job/[boot]/123", 14: b"job/[boot]/123"}
    caps = {10: b"cap", 11: b"different-cap", 12: b"cap", 13: b"cap"}
    monkeypatch.setattr(mg, "marker_value", lambda p, marker:
                        ids.get(p) if marker == "GEMMA_JOB_ID" else caps.get(p))
    targets, jobs = mg.find_jobs(world, args, set())
    assert set(targets) == {10, 11, 12, 14}
    assert sorted(sorted(j["pids"]) for j in jobs.values()) == [[10, 11, 14], [12]]


def test_legacy_known_members_do_not_follow_reused_pid(monkeypatch, mg, args):
    world = mock_world(monkeypatch, mg, {10: proc(10), 11: proc(11, ppid=10)},
                       {10: b"cap", 11: b"cap"}, [dict(name="job", pid=10, pgid=None)])
    job = select(mg, args)
    world[11] = proc(11, pgid=11, starttime=999)
    assert set(mg.inventory(job, args, set())) == {10}


@pytest.mark.parametrize("survives", [False, True])
def test_legacy_history_survives_new_first_member_and_temporary_node(monkeypatch, mg, args, survives):
    records = [dict(name="job", pid=10, pgid=10)]
    world = mock_world(monkeypatch, mg, {
        10: proc(10), 11: proc(11, ppid=10, comm="node"),
        12: proc(12, ppid=10), 13: proc(13, ppid=10)},
        {p: b"cap" for p in (10, 11, 12, 13)}, records)
    world[11] = proc(11, ppid=10)
    _, seeded = mg.find_jobs(world, args, set())
    world[11] = proc(11, ppid=10, comm="node")
    _, jobs = mg.find_jobs(world, args, set(), known_jobs=seeded)  # poll 1
    key = next(iter(jobs))
    assert set(jobs[key]["known_members"]) == {10, 11, 12, 13}
    del world[10]
    world[11] = proc(11, comm="python")
    world[13] = proc(13, comm="node")
    _, jobs = mg.find_jobs(world, args, set(), known_jobs=jobs)  # poll 2: 11 first
    assert jobs[key]["pids"] == [11, 12]
    assert jobs[key]["known_members"][13] == 123
    assert set(mg.inventory(jobs[key], args, set())) == {11, 12}
    world[13] = proc(13, ppid=1, pgid=13)  # unchanged starttime, setsid
    _, jobs = mg.find_jobs(world, args, set(), known_jobs=jobs)  # poll 3
    assert set(jobs[key]["members"]) == {11, 12, 13}
    sent = []

    def kill(d, log, args, known_jobs=None):
        assert world[d["pid"]]["comm"] != "node"
        sent.append(d["pid"])
        if survives and d["pid"] == 13:
            return False
        del world[d["pid"]]
        return True

    monkeypatch.setattr(mg, "send_kill", kill)
    killed, survivors = mg.kill_tree(jobs[key], args, set(), lambda _: None)
    assert killed == ([11, 12] if survives else [11, 12, 13])
    assert survivors == ([13] if survives else [])
    assert 13 in sent
    assert not (13 in world and survivors == [])


def test_legacy_history_survives_poll_with_no_eligible_members(monkeypatch, mg, args):
    world = mock_world(monkeypatch, mg, {10: proc(10)}, {10: b"cap"},
                       [dict(name="job", pid=10, pgid=None)])
    _, jobs = mg.find_jobs(world, args, set())
    key = next(iter(jobs))
    world[10] = proc(10, comm="node")
    targets, jobs = mg.find_jobs(world, args, set(), known_jobs=jobs)
    assert targets == {}
    assert jobs[key]["known_members"] == {10: 123}
    assert jobs[key]["rss"] == 0
    world[10] = proc(10, pgid=99)
    targets, jobs = mg.find_jobs(world, args, set(), known_jobs=jobs)
    assert set(targets) == set(jobs[key]["members"]) == {10}


@pytest.mark.parametrize("legacy_pgid", [None, 10])
def test_old_legacy_and_new_job_id_watchdogs_are_never_victims(monkeypatch, mg, args, legacy_pgid):
    import io
    records = [dict(name="memguard", pid=10, pgid=legacy_pgid),
               dict(name="memguard-light", pid=20, pgid=20, job_id=b"memguard-light/boot/123")]
    world = mock_world(monkeypatch, mg, {
        10: proc(10, comm="bash"), 11: proc(11, ppid=10),
        20: proc(20, pgid=20, comm="bash"), 21: proc(21, ppid=20, pgid=20)},
        {p: b"cap" for p in (10, 11, 20, 21)}, records)
    monkeypatch.setattr(mg, "marker_value", lambda p, marker:
                        (b"memguard-light/boot/123" if p in {20, 21} else None)
                        if marker == "GEMMA_JOB_ID" else b"cap")
    targets, jobs = mg.find_jobs(world, args, {20, 21})
    assert targets == jobs == {}  # neither OOM candidates nor victim jobs
    assert mg.raise_oom_adj(targets, False, args) == 0
    class File(io.StringIO):
        def close(self):
            pass
    writes, sent = File(), []
    monkeypatch.setattr("builtins.open", lambda *a, **kw: writes)
    monkeypatch.delattr(mg.os, "pidfd_open", raising=False)
    monkeypatch.setattr(mg.os, "kill", lambda *a: sent.append(a))
    # Stale candidates must also be excluded at the final action-time check.
    assert mg.raise_oom_adj(world, False, args) == 0
    for d in world.values():
        assert not mg.send_kill(d, lambda _: None, args)
    assert sent == []
    assert writes.getvalue() == ""


@pytest.mark.parametrize("argv", [b"/repo/bin/memguard\0--once\0",
                                  b"/usr/bin/python3\0/repo/bin/memguard\0"])
def test_cmdline_watchdog_and_wrapper_are_protected_without_job_metadata(monkeypatch, mg, args, argv):
    runs_memguard = mg.runs_memguard
    world = mock_world(monkeypatch, mg, {10: proc(10, comm="bash"), 11: proc(11, ppid=10)},
                       {10: b"cap", 11: b"cap"})
    # Exercise the real parser with a guard which has no identifying env or status.
    monkeypatch.setattr(mg, "runs_memguard", runs_memguard)
    monkeypatch.setattr(mg, "read", lambda path, mode="r": argv if path == "/proc/11/cmdline" else b"")
    assert mg.find_jobs(world, args, set()) == ({}, {})
    assert not mg.action_eligible(world[10], args)
    assert not mg.action_eligible(world[11], args)


@pytest.mark.parametrize("job_id,protected", [(b"memguard", True), (b"memguard-other/boot/1", True),
                                               (b"xmemguard/boot/1", False), (b"Memguard/boot/1", False)])
def test_watchdog_job_id_uses_literal_prefix(monkeypatch, mg, args, job_id, protected):
    world = mock_world(monkeypatch, mg, {10: proc(10)}, {10: b"cap"})
    monkeypatch.setattr(mg, "marker_value", lambda p, marker:
                        job_id if marker == "GEMMA_JOB_ID" else b"cap")
    targets, jobs = mg.find_jobs(world, args, set())
    assert bool(targets) == bool(jobs) == (not protected)


def test_watchdog_job_id_also_protects_legacy_wrapper(monkeypatch, mg, args):
    world = mock_world(monkeypatch, mg, {10: proc(10, comm="bash"), 11: proc(11, ppid=10)},
                       {10: b"cap", 11: b"cap"})
    monkeypatch.setattr(mg, "marker_value", lambda p, marker:
                        (b"memguard-light/boot/123" if p == 11 else None)
                        if marker == "GEMMA_JOB_ID" else b"cap")
    assert mg.find_jobs(world, args, set()) == ({}, {})
    assert not mg.action_eligible(world[10], args)


@pytest.mark.parametrize("argv", [b"/bin/memguard-helper\0", b"/bin/xmemguard\0"])
def test_cmdline_watchdog_match_requires_exact_basename(monkeypatch, mg, argv):
    monkeypatch.setattr(mg, "read", lambda *a: argv)
    assert not mg.runs_memguard(10)


@pytest.mark.parametrize("action", ["signal", "oom"])
@pytest.mark.parametrize("change", ["node", "uid", "shell", "marker",
                                    "guard-id", "guard-cmd", "guard-child"])
def test_action_revalidates_allowlist_after_handle_open(monkeypatch, mg, args, action, change):
    import io
    marked = {10: b"cap"}
    world = mock_world(monkeypatch, mg, {10: proc(10)}, marked)
    targets, _ = mg.find_jobs(world, args, set())
    assert 10 in targets
    class File(io.StringIO):
        def close(self):
            pass
    writes = File()

    def change_eligibility():
        if change == "node":
            world[10] = proc(10, comm="node")
        elif change == "uid":
            world[10] = proc(10, uid=os.getuid() + 1)
        elif change == "shell":
            world[10] = proc(10, comm="bash", ppid=9)
            world[9] = proc(9, comm="claude")
        elif change == "marker":
            marked.clear()
        elif change == "guard-id":
            monkeypatch.setattr(mg, "marker_value", lambda p, marker:
                                b"memguard-light/boot/123" if marker == "GEMMA_JOB_ID" else b"cap")
        elif change == "guard-cmd":
            monkeypatch.setattr(mg, "runs_memguard", lambda p: p == 10)
        elif change == "guard-child":
            world[11] = proc(11, ppid=10)
            monkeypatch.setattr(mg, "runs_memguard", lambda p: p == 11)

    sent, closed = [], []
    def pidfd_open(p):
        change_eligibility()
        return 42
    monkeypatch.setattr(mg.os, "pidfd_open", pidfd_open)
    monkeypatch.setattr(mg.os, "close", closed.append)
    monkeypatch.setattr(mg.signal, "pidfd_send_signal", lambda *a: sent.append(a))
    monkeypatch.setattr(mg.os, "kill", lambda *a: sent.append(a))
    if action == "signal":
        assert not mg.send_kill(targets[10], lambda _: None, args)
        assert closed == [42]
    else:
        def open_oom(path, mode):
            assert path == "/proc/10/oom_score_adj"
            change_eligibility()
            return writes
        monkeypatch.setattr("builtins.open", open_oom)
        assert mg.raise_oom_adj(targets, False, args) == 0
    assert sent == []
    assert writes.getvalue() == ""


def test_six_field_status_retains_identity_and_names_escaped_job(monkeypatch, mg, args, tmp_path):
    directory = tmp_path / "ops/jobs"
    directory.mkdir(parents=True)
    (directory / "new.status").write_text("running 10 now 10 boot-id 123\n")
    monkeypatch.setattr(mg, "REPO", str(tmp_path))
    monkeypatch.setattr(mg, "current_boot_id", lambda: "boot-id")
    records = mg.running_jobs()
    assert records == [dict(name="new", pid=10, pgid=10, boot_id="boot-id",
                            starttime="123", job_id=b"new/boot-id/123")]
    monkeypatch.setattr(mg, "marker_value", lambda p, marker:
                        b"new/boot-id/123" if marker == "GEMMA_JOB_ID" else b"cap")
    _, jobs = mg.find_jobs({11: proc(11, pgid=11)}, args, set())
    job = next(iter(jobs.values()))
    assert job["name"] == "new"
    assert job["root"] == 10
    assert job["pids"] == [11]


@pytest.mark.parametrize("action", ["signal", "oom"])
@pytest.mark.parametrize("change", ["node", "reused", "missing"])
@pytest.mark.parametrize("phase", ["snapshot", "protection"])
def test_recipient_is_refreshed_after_scans(monkeypatch, mg, args, action, change, phase):
    import io
    world = mock_world(monkeypatch, mg, {10: proc(10)}, {10: b"job/boot/123"})
    candidate = world[10]
    def change_recipient():
        if change == "missing":
            world.clear()
        else:
            world[10] = proc(10, comm="node" if change == "node" else "python",
                             starttime=999 if change == "reused" else 123)
    if phase == "snapshot":
        def snapshot():
            change_recipient()
            return dict(world)
        monkeypatch.setattr(mg, "snapshot", snapshot)
    else:
        def protected(procs, records):
            change_recipient()
            return set()
        monkeypatch.setattr(mg, "protected_watchdogs", protected)
    class File(io.StringIO):
        def close(self):
            pass
    output, sent = File(), []
    monkeypatch.setattr("builtins.open", lambda *a, **kw: output)
    monkeypatch.setattr(mg.os, "pidfd_open", lambda p: 42)
    monkeypatch.setattr(mg.os, "close", lambda fd: None)
    monkeypatch.setattr(mg.signal, "pidfd_send_signal", lambda *a: sent.append(a))
    monkeypatch.setattr(mg.os, "kill", lambda *a: sent.append(a))
    if action == "signal":
        assert mg.send_kill(candidate, lambda _: None, args) is False
    else:
        assert mg.raise_oom_adj({10: candidate}, False, args) == 0
    assert sent == []
    assert output.getvalue() == ""


@pytest.mark.parametrize("record_kind", ["three", "four", "identity"])
def test_large_unrelated_process_requires_verified_wrapper(monkeypatch, mg, args, record_kind):
    import io
    record = dict(name="work", pid=20, pgid=None if record_kind == "three" else 20)
    if record_kind == "identity":
        record["starttime"] = "123"
    world = mock_world(monkeypatch, mg, {10: proc(10, rss=4 * 1024**3)}, {}, [record])
    # Its cwd is intentionally irrelevant, even when it is /tmp/other-project.
    monkeypatch.setattr(mg.os, "readlink", lambda p: "/tmp/other-project")
    assert mg.find_jobs(world, args, set()) == ({}, {})
    class File(io.StringIO):
        def close(self):
            pass
    output, sent = File(), []
    real_open = open
    def open_oom(path, *a, **kw):
        return output if str(path).endswith("oom_score_adj") else real_open(path, *a, **kw)
    monkeypatch.setattr("builtins.open", open_oom)
    monkeypatch.delattr(mg.os, "pidfd_open", raising=False)
    monkeypatch.setattr(mg.os, "kill", lambda *a: sent.append(a))
    assert mg.send_kill(world[10], lambda _: None, args) is False
    assert mg.raise_oom_adj(world, False, args) == 0
    assert sent == [] and output.getvalue() == ""
    world[20] = proc(20, comm="bash", pgid=20)
    # Sharing a PGID alone is insufficient.
    world[10] = proc(10, pgid=20, rss=4 * 1024**3)
    assert 10 not in mg.find_jobs(world, args, set())[0]
    world[10] = proc(10, ppid=20, pgid=20, rss=4 * 1024**3)
    targets, jobs = mg.find_jobs(world, args, set())
    assert set(targets) == {10, 20}
    assert mg.action_eligible(world[10], args)
    # Retained provenance survives losing both marker and wrapper ancestry.
    del world[20]
    world[10] = proc(10, pgid=99, rss=4 * 1024**3)
    targets, jobs = mg.find_jobs(world, args, set(), known_jobs=jobs)
    assert set(targets) == {10}
    assert mg.raise_oom_adj(targets, False, args, jobs) == 1
    assert mg.send_kill(targets[10], lambda _: None, args, jobs)
    assert sent == [(10, signal.SIGKILL)] and output.getvalue() == "1000"
    world[10] = proc(10, starttime=999, rss=4 * 1024**3)
    assert mg.find_jobs(world, args, set(), known_jobs=jobs) == ({}, {})


@pytest.mark.parametrize("bad_wrapper", ["dead", "reused", "cmdline", "cap-only"])
def test_status_and_cap_alone_are_not_provenance(monkeypatch, mg, args, bad_wrapper):
    record = dict(name="work", pid=20, pgid=20)
    world = mock_world(monkeypatch, mg, {10: proc(10, ppid=20), 20: proc(20)},
                       {10: b"cap", 20: b"cap"}, [record])
    if bad_wrapper == "dead":
        world[20]["state"] = "Z"
    elif bad_wrapper == "reused":
        record["starttime"] = "999"
    elif bad_wrapper == "cmdline":
        original_read = mg.read
        monkeypatch.setattr(mg, "read", lambda path, mode="r":
                            b"bash\0-c\0echo bin/job\0_\0work\0" if mode == "rb"
                            else original_read(path, mode))
    else:
        world.clear()
        world[10] = proc(10, rss=4 * 1024**3)
    assert mg.find_jobs(world, args, set()) == ({}, {})
    assert not mg.action_eligible(world[10], args)


def assert_actions_refused(monkeypatch, mg, args, candidate, known_jobs=None):
    """Exercise both pinned action paths without touching real processes."""
    import io
    class File(io.StringIO):
        def close(self):
            pass
    output, sent = File(), []
    real_open = open
    def open_oom(path, *a, **kw):
        return output if str(path).endswith("oom_score_adj") else real_open(path, *a, **kw)
    monkeypatch.setattr("builtins.open", open_oom)
    monkeypatch.setattr(mg.os, "pidfd_open", lambda p: 42)
    monkeypatch.setattr(mg.os, "close", lambda fd: None)
    monkeypatch.setattr(mg.signal, "pidfd_send_signal", lambda *a: sent.append(a))
    monkeypatch.setattr(mg.os, "kill", lambda *a: sent.append(a))
    assert mg.send_kill(candidate, lambda _: None, args, known_jobs) is False
    assert mg.raise_oom_adj({candidate["pid"]: candidate}, False, args, known_jobs) == 0
    assert sent == []
    assert output.getvalue() == ""


@pytest.mark.parametrize("change", ["job-id", "cmdline", "unreadable-cmdline", "unreadable-environ"])
def test_action_rechecks_watchdog_after_protection_scan(monkeypatch, mg, args, change):
    marked = {10: b"work/boot/123"}
    world = mock_world(monkeypatch, mg, {10: proc(10)}, marked)
    candidate = world[10]
    original_read = mg.read
    def protect(procs, records):
        # The process execs after its protection scan; its starttime is unchanged.
        if change == "job-id":
            marked[10] = b"memguard-light/boot/123"
        else:
            def read(path, mode="r"):
                if path == "/proc/10/cmdline" and change != "unreadable-environ":
                    return b"python3\0-u\0/repo/bin/memguard\0" if change == "cmdline" else None
                if path == "/proc/10/environ" and change == "unreadable-environ":
                    return None
                return original_read(path, mode)
            monkeypatch.setattr(mg, "read", read)
        return set()
    monkeypatch.setattr(mg, "protected_watchdogs", protect)
    assert_actions_refused(monkeypatch, mg, args, candidate)


@pytest.mark.parametrize("history", [False, True])
def test_previous_boot_record_cannot_admit_unmarked_child(monkeypatch, mg, args, history):
    record = dict(name="work", pid=10, pgid=10, boot_id="previous-boot",
                  starttime="123", job_id=b"work/previous-boot/123")
    world = mock_world(monkeypatch, mg, {10: proc(10), 11: proc(11, ppid=10)}, {}, [record])
    # Even a matching numeric identity must not establish ancestry after reboot.
    original_read = mg.read
    monkeypatch.setattr(mg, "read", lambda path, mode="r":
                        b"python3\0unrelated.py\0" if path == "/proc/10/cmdline" else original_read(path, mode))
    known = {("job", 10, 123): dict(key=("job", 10, 123), root=10, name="work",
             boot_id="previous-boot", known_members={10: 123, 11: 123})} if history else None
    assert mg.verified_records(world, [record]) == []
    assert mg.find_jobs(world, args, set(), known_jobs=known) == ({}, {})
    assert_actions_refused(monkeypatch, mg, args, world[11], known)


@pytest.mark.parametrize("argv", [
    b"/usr/bin/python3\0-u\0/repo/bin/memguard\0",
    b"python3\0-X\0dev\0-W\0ignore\0bin/memguard\0",
    b"env\0FOO=1\0python3\0bin/memguard\0",
])
def test_watchdog_any_argv_position_is_protected(monkeypatch, mg, args, argv):
    parser = mg.runs_memguard
    record = dict(name="watchdog-light", pid=20, pgid=20)
    world = mock_world(monkeypatch, mg, {20: proc(20, comm="bash"), 10: proc(10, ppid=20)}, {}, [record])
    original_read = mg.read
    monkeypatch.setattr(mg, "read", lambda path, mode="r":
                        argv if path == "/proc/10/cmdline" else original_read(path, mode))
    monkeypatch.setattr(mg, "runs_memguard", parser)
    assert parser(10)
    assert {10, 20} <= mg.protected_watchdogs(world, [record])
    assert mg.find_jobs(world, args, set()) == ({}, {})
    assert_actions_refused(monkeypatch, mg, args, world[10])
    assert_actions_refused(monkeypatch, mg, args, world[20])


def test_wrapper_watchdog_command_record_is_protected(monkeypatch, mg, args):
    record = dict(name="watchdog-light", pid=10, pgid=10)
    world = mock_world(monkeypatch, mg, {10: proc(10, comm="bash")}, {}, [record])
    original_read = mg.read
    monkeypatch.setattr(mg, "read", lambda path, mode="r":
                        "python3 -u /repo/bin/memguard" if str(path).endswith("watchdog-light.cmd")
                        else original_read(path, mode))
    assert 10 in mg.protected_watchdogs(world, [record])
    assert mg.find_jobs(world, args, set()) == ({}, {})
    assert_actions_refused(monkeypatch, mg, args, world[10])


def test_watchdog_argv_resolves_symlinks(monkeypatch, mg, tmp_path):
    directory = tmp_path / "bin"
    directory.mkdir()
    guard = directory / "memguard"
    guard.touch()
    alias = tmp_path / "guard-alias"
    alias.symlink_to(guard)
    assert mg.watchdog_argv(b"python3\0-u\0" + os.fsencode(alias) + b"\0")
