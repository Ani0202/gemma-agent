"""Review 20261106T071306 exact reproducers (B | overrides) run against the folded classifier. Run from repo root: python3 -I eval/plan007_rev5_repro.py"""
import json, subprocess, sys, tempfile, os
sys.path.insert(0, 'eval/kaggle'); sys.path.insert(0, '.')
from eval.kaggle import classify_rows as c
B = dict(instance_id="t", repo="x/y", resolved=True, exit_code=0, verified_patch_bytes=10, result_error=None,
         agent_error_text=None, error=None, setup_calls=[], setup_failed=False, missing_tool_deps=[])
P="Failed to apply agent patch: x"; J="Required test node did not pass: t::x"; D="uninstall-no-record-file"
T="Agent exceeded turns budget (50 turns)"; U="Agent exceeded session timeout (3 min)"
def run(name, ov=None, drop=(), want_h=True):
    r = dict(B, **(ov or {}))
    for k in drop: r.pop(k)
    try:
        res = c.classify(r); out = (res.get('h'), res.get('agent'), res.get('known_diag'))
    except Exception as e:
        out = ('EXC', type(e).__name__, None)
    ok = (out[0] is not None) if want_h else (out[0] is None)
    print(('OK  ' if ok else 'BAD ') + name, out)
run('1', {"result_error": T})
run('2', {"resolved": False, "exit_code": 1, "result_error": T, "agent_error_text": U})
run('3', {"resolved": False, "exit_code": 1, "result_error": J})
run('4a', {"resolved": False, "result_error": P})
run('4b', {"resolved": False, "result_error": P, "verified_patch_bytes": 0, "exit_code": -1})
run('5', {"resolved": False, "verified_patch_bytes": 0, "exit_code": 999})
run('6', drop=('error','setup_failed','missing_tool_deps'))
run('7', {"setup_calls": [{"step": "tool_install", "duration_s": 0, "stdout": "", "stderr": ""}]})
run('8', {"setup_calls": [{"step": "setup.py", "rc": 0, "subprocesses": [{"argv": [], "rc": 1, "stderr": "failed"}]}]})
run('9', {"instance_id": None, "repo": []})
run('10', {"setup_calls": [{"step": "tool_install", "rc": None, "duration_s": 0, "stdout": "Failed to install wheels", "stderr": ""}]})
run('11', {"setup_calls": [{"step": "workspace_editable", "rc": None, "duration_s": 1, "stderr": D}]})
run('12', {"setup_calls": [{"step": "workspace_editable", "rc": 1, "stdout": "uninstall-no-", "stderr": "record-file"}]})
run('13', {"setup_failed": True, "setup_calls": [{"step": "setup.py", "rc": 0, "subprocesses": [{"argv": ["echo", "-e", "--no-index"], "rc": 1, "stderr": D}]}]})
run('14', {"setup_calls": [{"step": "setup.py", "rc": 0, "subprocesses": [
    {"argv": ["pip", "install", "-e", "/workspace", "--no-index"], "rc": 1, "stderr": D},
    {"argv": ["pip", "install", "-e", "/workspace"], "rc": 0},
    {"argv": ["pip", "install", "-e", "/other"], "rc": 1, "stderr": "No space left on device"}]}]})
run('19', {"setup_calls": [{"step": "venv", "rc": 0, "duration_s": 10**400}]})
run('FH1', {"resolved": False, "setup_calls": [{"step": "setup.py", "rc": None, "duration_s": 0, "stdout": "", "stderr": ""}]}, want_h=False)
run('FH2', {"resolved": False, "setup_calls": [{"step": "workspace_editable", "rc": None, "duration_s": 0, "stdout": "", "stderr": ""}]}, want_h=False)
for ov, nm in [({"exit_code": 0, "resolved": False}, 'L-exit0unres'), ({"resolved": False, "exit_code": 124}, 'L-124'),
               ({"resolved": False, "verified_patch_bytes": 0, "exit_code": None}, 'L-nopatch-null'),
               ({"resolved": False, "verified_patch_bytes": 0, "exit_code": -1}, 'L-nopatch-1'),
               ({"resolved": False, "result_error": P, "exit_code": -1}, 'L-apply-1'),
               ({"resolved": False, "result_error": P, "exit_code": None}, 'L-apply-null'),
               ({"resolved": False, "exit_code": 0, "result_error": J}, 'L-junit-exit0'),
               ({"resolved": False, "exit_code": 1, "agent_error_text": T}, 'L-agentend'),
               ({}, 'L-pass')]:
    run(nm, ov, want_h=False)
def cli(name, recs, raw=None):
    fd, p = tempfile.mkstemp(suffix='.jsonl'); os.close(fd)
    open(p, 'w').write(raw if raw is not None else ''.join(json.dumps(r) + '\n' for r in recs))
    cp = subprocess.run([sys.executable, 'eval/kaggle/classify_rows.py', p], capture_output=True, text=True)
    h = None
    if cp.returncode == 0:
        try: h = json.loads(cp.stdout)['counts']['h']
        except Exception: h = 'unparsed'
    ok = cp.returncode != 0 or (h and sum(h.values()) > 0)
    print(('OK  ' if ok else 'BAD ') + name, 'rc', cp.returncode, 'h', h)
cli('15a', [B, ["instance_id"]]); cli('15b', [B, {k: v for k, v in B.items() if k != 'instance_id'}])
cli('16', None, raw=json.dumps(B)[:-1] + ',"error":"Evaluation exception (X)","error":null}\n')
cli('17', [{"_schema": "kaggle_timing_v1", "task_ids": ["t", "u"]}, B, {"_done": {"n": 2}}])
cli('18', [{"_schema": "kaggle_timing_v1", "task_ids": ["t"], "vllm_startup_seconds": None, "mcp_import_ok": False}, B])
