"""bin/memguard end-to-end test (dec 021 item 1d). Run only under bin/job (allocates ~2.5G peak).

A synthetic job (bash wrapper -> python child -> python grandchild that allocates in 200M steps)
must be killed with no survivors, and the wrapper must record exit 137. A dummy non-target process
at the same RSS (no marker, cwd outside --roots) must survive with its oom_score_adj untouched.
Uses a private marker so neither this test's own bin/job nor the real memguard is involved.
"""
import os, subprocess, sys, time, uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MG = REPO / "bin" / "memguard"
STEP = 200 * 1024 * 1024

ALLOC = f"""
import time
held = []
for _ in range(6):            # up to 1.2G, touched (non-zero) so it is resident
    held.append(b"\\x01" * {STEP})
    time.sleep(0.4)
time.sleep(120)
"""

CHILD = f"""
import subprocess, sys, time
subprocess.Popen([sys.executable, "-c", {ALLOC!r}])
time.sleep(120)
"""


def alive(pid):
    try:
        st = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return False
    return st.rsplit(") ", 1)[-1][:1] != "Z"


def tree(pid):
    out, stack = [], [pid]
    while stack:
        p = stack.pop()
        try:
            kids = Path(f"/proc/{p}/task/{p}/children").read_text().split()
        except OSError:
            kids = []
        for k in map(int, kids):
            out.append(k); stack.append(k)
    return out


def test_memguard_kills_job_tree_and_spares_dummy(tmp_path):
    marker = "GEMMA_MGTEST_" + uuid.uuid4().hex[:8]
    root = tmp_path / "jobcwd"; root.mkdir()
    rcfile = tmp_path / "rc"; log = tmp_path / "memguard.log"
    env_clean = {k: v for k, v in os.environ.items() if not k.startswith("GEMMA_MGTEST_")}

    dummy = subprocess.Popen([sys.executable, "-c", ALLOC], cwd="/", env=env_clean)
    job = subprocess.Popen(
        ["bash", "-c", f'{sys.executable} -c "$CHILD_SRC"; echo $? > {rcfile}'],
        cwd=root, env={**env_clean, marker: "test", "CHILD_SRC": CHILD})
    mg = None
    try:
        time.sleep(3.0)  # dummy reaches ~1.2G; job grandchild is ramping
        pids = [job.pid] + tree(job.pid)
        assert len(pids) >= 3, f"synthetic tree not built: {pids}"
        mg = subprocess.Popen(
            [sys.executable, str(MG), "--marker", marker, "--max-total", "0.8", "--min-available", "0",
             "--unmarked-rss", "0.5", "--interval", "0.5", "--roots", str(tmp_path),
             "--log", str(log), "--no-mail"], env=env_clean,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 30
        while time.time() < deadline and "survivors=" not in (log.read_text() if log.exists() else ""):
            time.sleep(0.5)
        text = log.read_text()
        assert "KILL" in text and "survivors=[]" in text, text
        job.wait(timeout=10)
        for p in pids:
            assert not alive(p), f"survivor {p}"
        assert rcfile.read_text().strip() == "137"
        assert alive(dummy.pid), "dummy non-target was killed"
        assert Path(f"/proc/{dummy.pid}/oom_score_adj").read_text().strip() == "0"
        assert text.count("KILL") == 1, text
    finally:
        for p in ([mg] if mg else []) + [dummy, job]:
            if p.poll() is None:
                p.kill()
        for p in [job.pid] + tree(job.pid):
            try:
                os.kill(p, 9)
            except OSError:
                pass


def test_job_name_parses_bin_job_wrapper():
    import importlib.machinery, importlib.util
    loader = importlib.machinery.SourceFileLoader("memguard", str(MG))
    spec = importlib.util.spec_from_loader("memguard", loader)
    mg = importlib.util.module_from_spec(spec); loader.exec_module(mg)
    p = subprocess.Popen(["bash", "-c", "sleep 5; true # ops/jobs/", "_", "myjob", "x"])
    try:
        time.sleep(0.3)
        assert mg.job_name(p.pid) == "myjob"
        assert mg.job_name(os.getpid()) is None
    finally:
        p.kill()
