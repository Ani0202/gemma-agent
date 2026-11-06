#!/usr/bin/env python3
"""Plan 005 dec 059 item 4 CPU checks (counts and hashes only, no task text written).

Usage: shell_error_causes.py <out.json> <runA_dir> <labelA> <runB_dir> <labelB> <id> [<id> ...]
(a) sha256 of <run>/runs/<id>/agent.patch for each listed id in both runs, and whether A == B byte-identical.
(b) for run B: every run_command response classified cmd_error_shell by eval/trace_tool_errors.py, broken down by cause:
    quoting_heredoc  bash "unexpected EOF while looking for matching", "here-document", "unexpected token", "unexpected end of file"
    missing_binary   "command not found" / "No such file or directory" on the command itself
    syntax_other     any other message containing "syntax error"
    other            anything else
    plus per-task counts, distinct command strings (by sha256), and the max identical-command repeat count.
"""
import hashlib, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_tool_errors import _load, classify


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


def cause(msg):
    if "command not found" in msg:
        return "missing_binary"
    if any(s in msg for s in ("looking for matching", "here-document", "unexpected token", "unexpected end of file")):
        return "quoting_heredoc"
    if "syntax error" in msg:
        return "syntax_other"
    return "other"


def shell_errors(run_dir):
    base = os.path.join(run_dir, "runs")
    causes, per_task, cmds = {}, {}, {}
    for t in sorted(os.listdir(base)):
        p = os.path.join(base, t, "trace.json")
        if not os.path.isfile(p):
            continue
        pend = []
        for e in json.load(open(p))["entries"]:
            if e["type"] == "tool_call" and e.get("tool") == "run_command":
                pend.append(e)
            elif e["type"] == "tool_response" and e.get("tool") == "run_command":
                c = pend.pop(0) if pend else {}
                r = _load(e.get("result", ""))
                cls, _ = classify("run_command", r)
                if "cmd_error_shell" not in cls:
                    continue
                k = cause(str(r.get("error_message") or r.get("error") or ""))
                causes[k] = causes.get(k, 0) + 1
                per_task[t] = per_task.get(t, 0) + 1
                h = hashlib.sha256(json.dumps(c.get("args", c), sort_keys=True).encode()).hexdigest()[:12]
                cmds[h] = cmds.get(h, 0) + 1
    return {"total": sum(causes.values()), "by_cause": causes, "tasks_with_errors": len(per_task),
            "per_task": per_task, "distinct_commands": len(cmds), "max_identical_repeats": max(cmds.values(), default=0)}


def main(out, ra, la, rb, lb, *ids):
    a = {}
    for i in ids:
        ha, hb = sha(os.path.join(ra, "runs", i, "agent.patch")), sha(os.path.join(rb, "runs", i, "agent.patch"))
        a[i] = {la: ha, lb: hb, "identical": ha is not None and ha == hb}
    res = {"_schema": "shell_error_causes_v1", "generator": "eval/shell_error_causes.py", "decision": "059 item 4",
           "runs": {la: ra, lb: rb},
           "a_patch_sha256": a, "a_identical_count": sum(v["identical"] for v in a.values()), "a_n": len(ids),
           "b_shell_errors": {la: shell_errors(ra), lb: shell_errors(rb)}}
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps({"a_identical": res["a_identical_count"], "n": len(ids),
                      "b": {k: {x: v[x] for x in ("total", "by_cause", "tasks_with_errors", "distinct_commands", "max_identical_repeats")}
                            for k, v in res["b_shell_errors"].items()}}))


if __name__ == "__main__":
    main(*sys.argv[1:])
