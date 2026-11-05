"""Time the STOCK swegemma subprocess-sandbox setup sequence (agent_runner.py ~l.553-584) per task.

Report 009 evidence: what per-task setup S costs if the scorer runs sandbox='subprocess' like the
official starter notebook (setup.py is skipped there: container_setup.py:513/529). Local CPU only;
host speed differs from Kaggle, so read it as an order of magnitude. Usage:
  python3 eval/tools/stock_subprocess_setup_timing.py OUT.json TASK_ID [TASK_ID ...]
"""
import json, sys, time, shutil
from pathlib import Path
from swegemma.config import EvalConfig
from swegemma.sandbox.subprocess import SubprocessManager
from swegemma.harness import container_setup as cs

out, ids = sys.argv[1], sys.argv[2:]
data = Path('data/raw')
cfg = EvalConfig(tasks_path=data / 'tasks.jsonl', snapshots_dir=data / 'snapshots',
                 wheels_dir=data / 'wheels', sandbox='subprocess',
                 results_dir=Path('/tmp/claude-1001/stocksetup-results'), submission_dir=Path('bundles/e4b/v002'), models={})
repo_of = {}
for line in open(data / 'tasks.jsonl'):
    t = json.loads(line); repo_of[t['instance_id']] = t.get('repo', '')
rows = []
for tid in ids:
    mgr = SubprocessManager(timeout_seconds=300)
    steps = {}
    t0 = time.perf_counter()
    def step(name, fn, *a, **k):
        s = time.perf_counter(); fn(*a, **k); steps[name] = round(time.perf_counter() - s, 3)
    s = time.perf_counter(); sid = mgr.start(); steps['start_venv'] = round(time.perf_counter() - s, 3)
    step('setup_container_wheels', cs.setup_container_wheels, mgr, sid, cfg)
    step('extract_snapshot', cs.extract_snapshot, mgr, sid, data / 'snapshots' / f'{tid}.tgz')
    step('setup_git_exclude', cs.setup_git_exclude, mgr, sid)
    step('install_editable_package', cs.install_editable_package, mgr, sid)
    step('install_test_dependencies', cs.install_test_dependencies, mgr, sid, repo_of.get(tid, ''), config=cfg)
    step('setup_workspace_test_config', cs.setup_workspace_test_config, mgr, sid, repo=repo_of.get(tid, ''))
    step('setup_baseline_commit', cs.setup_baseline_commit, mgr, sid, 'baseline')
    total = round(time.perf_counter() - t0, 3)
    rows.append({'task': tid, 'total_s': total, 'steps_s': steps})
    root = mgr.sandboxes.get(sid, {}).get('root') if hasattr(mgr, 'sandboxes') else None
    try:
        mgr.stop(sid)
    except Exception:
        pass
    print(tid, total, steps, flush=True)
json.dump({'_schema': 'stock_subprocess_setup_timing_v1',
           'host': 'oracle-arm-2ocpu (control VM), NOT Kaggle hardware',
           'source': 'eval/tools/stock_subprocess_setup_timing.py; swegemma 0.2.11 stock functions, sandbox=subprocess',
           'wheels_dir': str(cfg.wheels_dir), 'rows': rows}, open(out, 'w'), indent=1)
