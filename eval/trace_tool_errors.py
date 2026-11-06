#!/usr/bin/env python3
"""Count tool-call errors per task in a timing run's traces (plan 005 mechanism metrics).

Usage: trace_tool_errors.py <run_dir> <bundle_label> <out.json> [<ids_file>]
With <ids_file> (one instance id per line), the run must contain EXACTLY those ids, each with trace.json and
agent.patch, else exit 2 (no output written). Responses are classified by their own tool name (fallback: the
earliest unanswered call), and paired to calls FIFO per tool for call indices.
Reads <run_dir>/runs/<task>/{trace.json,agent.patch}. Writes counts only (no task text).
Error classes (matched on the tool response, never on task content):
  write_outside_ws   write_file rejected: "escapes workspace root"
  edit_missing_param edit_file rejected: mandatory input parameters not present (mangled tool-call args)
  edit_other_error   any other edit_file error
  cmd_error_empty    unsuccessful run_command response with empty message (e.g. grep no-match exit 1)
  cmd_error_shell    unsuccessful run_command response containing "syntax error" (shell quoting)
  cmd_error_other    any other unsuccessful run_command response (any error_type except BudgetExceeded,
                     e.g. CommandError, TimeoutExceeded)
  budget_exceeded    BudgetExceeded responses
  sitecustomize_warn responses whose text mentions "Error in sitecustomize" (stderr noise, may be non-fatal)
"""
import ast, json, os, sys


def _load(v):
    if isinstance(v, dict):
        return v
    s = str(v)
    try:
        return json.loads(s)
    except Exception:
        try:
            return ast.literal_eval(s)
        except Exception:
            return {"raw": s}


def classify(tool, r):
    raw = json.dumps(r)
    cls = []
    if "Error in sitecustomize" in raw:
        cls.append("sitecustomize_warn")
    if r.get("status") == "ok":
        return cls, True
    et = r.get("error_type") or ""
    msg = str(r.get("error_message") or r.get("error") or "")
    if et == "BudgetExceeded":
        cls.append("budget_exceeded")
    elif tool == "write_file" and "escapes workspace root" in msg:
        cls.append("write_outside_ws")
    elif tool == "edit_file" and "mandatory input parameters are not present" in msg:
        cls.append("edit_missing_param")
    elif tool == "edit_file":
        cls.append("edit_other_error")
    elif tool == "run_command" and not msg.strip():
        cls.append("cmd_error_empty")
    elif tool == "run_command" and "syntax error" in msg:
        cls.append("cmd_error_shell")
    elif tool == "run_command":
        cls.append("cmd_error_other")
    else:
        cls.append(f"{tool}_error")
    return cls, False


def main(run_dir, label, out, ids_file=None):
    base = os.path.join(run_dir, "runs")
    tasks = sorted(t for t in os.listdir(base)
                   if os.path.isfile(os.path.join(base, t, "trace.json")))
    if ids_file:
        want = sorted(l.strip() for l in open(ids_file) if l.strip() and not l.startswith("#"))
        bad = [t for t in want if not (os.path.isfile(os.path.join(base, t, "trace.json"))
                                       and os.path.isfile(os.path.join(base, t, "agent.patch")))]
        extra = sorted(set(tasks) - set(want))
        if bad or extra:
            print(json.dumps({"error": "incomplete or unexpected artifacts", "missing": bad, "extra": extra}))
            sys.exit(2)
        tasks = want
    rows, tot = [], {}
    for t in tasks:
        d = json.load(open(os.path.join(base, t, "trace.json")))
        pp = os.path.join(base, t, "agent.patch")
        row = {"instance_id": t, "patch_bytes": os.path.getsize(pp) if os.path.exists(pp) else None,
               "tool_calls": 0, "tool_errors": 0, "calls_by_tool": {}, "errors": {},
               "first_ok_edit_elapsed_s": None, "first_ok_edit_call_index": None}
        pending = []  # [(call_index, tool)] unanswered calls, in order
        for e in d["entries"]:
            if e["type"] == "tool_call":
                tool = e.get("tool")
                row["tool_calls"] += 1
                row["calls_by_tool"][tool] = row["calls_by_tool"].get(tool, 0) + 1
                pending.append((row["tool_calls"], tool))
            elif e["type"] == "tool_response":
                tool = e.get("tool")
                j = next((i for i, (_, t) in enumerate(pending) if t == tool), 0 if pending else None)
                idx, ctool = pending.pop(j) if j is not None else (None, None)
                tool = tool or ctool
                cls, ok = classify(tool, _load(e.get("result", "")))
                for c in cls:
                    row["errors"][c] = row["errors"].get(c, 0) + 1
                    tot[c] = tot.get(c, 0) + 1
                if not ok:
                    row["tool_errors"] += 1
                if ok and tool == "edit_file" and row["first_ok_edit_elapsed_s"] is None:
                    row["first_ok_edit_elapsed_s"] = float(e["elapsed_s"])
                    row["first_ok_edit_call_index"] = idx
        rows.append(row)
    res = {
        "_schema": "trace_tool_errors_v1",
        "run": run_dir, "bundle": label, "n": len(rows),
        "generator": "eval/trace_tool_errors.py",
        "fields": {"patch_bytes": "size of agent.patch (0 = empty diff)",
                   "errors": "per-class counts, see generator docstring",
                   "first_ok_edit_*": "first edit_file with status ok (null = none; sed/shell edits not counted)"},
        "empty_patch_count": sum(1 for r in rows if r["patch_bytes"] == 0),
        "tasks_with_class": {c: sum(1 for r in rows if r["errors"].get(c)) for c in sorted(tot)},
        "totals": dict(sorted(tot.items())),
        "tasks": rows,
    }
    with open(out, "w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps({k: res[k] for k in ("n", "empty_patch_count", "tasks_with_class", "totals")}))


if __name__ == "__main__":
    main(*sys.argv[1:5])
