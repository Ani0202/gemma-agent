#!/usr/bin/env python3
"""Plan 005 Addendum E: arm E (31b-v007) vs arm D (31b-v006), paired on the same 8 ids, k=1.
Usage: plan005_armE_compare.py <out.json>
Agent-clock seconds of an event = elapsed_s - elapsed_s of the trace's task_prompt entry (setup excluded).
First ok edit counts edit_file AND write_file with ok status (trace_tool_errors.classify)."""
import json, sys
from math import comb
sys.path.insert(0, "eval")
from trace_tool_errors import classify, _load

RUNS = {"D": "runs/31b-v006-p5d-timing", "E": "runs/31b-v007-p5e-timing"}
CAP_S = 73.8

def first_ok_edit(run, tid):
    d = json.load(open(f"{run}/runs/{tid}/trace.json"))
    t0 = next(e["elapsed_s"] for e in d["entries"] if e["type"] == "task_prompt")
    pending = []
    for e in d["entries"]:
        if e["type"] == "tool_call":
            pending.append(e.get("tool"))
        elif e["type"] == "tool_response":
            tool = e.get("tool") or (pending.pop(0) if pending else None)
            if e.get("tool") in pending:
                pending.remove(e.get("tool"))
            if tool in ("edit_file", "write_file") and classify(tool, _load(e.get("result", "")))[1]:
                return round(float(e["elapsed_s"]) - float(t0), 3), tool
    return None, None

def max_identical_run(run, tid):
    """Longest run of consecutive byte-identical tool calls (same tool + same args JSON)."""
    d = json.load(open(f"{run}/runs/{tid}/trace.json"))
    best = cur = 0; prev = None
    for e in d["entries"]:
        if e["type"] != "tool_call":
            continue
        key = (e.get("tool"), json.dumps(e.get("args", e.get("arguments")), sort_keys=True))
        cur = cur + 1 if key == prev else 1
        prev = key; best = max(best, cur)
    return best

def main(out):
    ids = [l.strip() for l in open("eval/plans/004-gpu-retime-ids.txt") if l.strip() and not l.startswith("#")]
    tim = {k: {t["instance_id"]: t for t in json.load(open(f"results/kaggle_timing_31b_{v}.json"))["tasks"]}
           for k, v in (("D", "v006"), ("E", "v007"))}
    tte = {k: {t["instance_id"]: t for t in json.load(open(f"results/trace_tool_errors_31b_{v}.json"))["tasks"]}
           for k, v in (("D", "v006"), ("E", "v007"))}
    rows = []
    for i in ids:
        r = {"id": i}
        for k in ("D", "E"):
            s, tool = first_ok_edit(RUNS[k], i)
            r.update({f"{k}_patch_bytes": tte[k][i]["patch_bytes"], f"{k}_timeout": bool(tim[k][i]["agent_timeout_fired"]),
                      f"{k}_agent_clock_s": round(tim[k][i]["agent_clock_seconds"], 3),
                      f"{k}_first_ok_edit_s": s, f"{k}_first_ok_edit_tool": tool, f"{k}_tool_calls": tte[k][i]["tool_calls"],
                      f"{k}_max_identical_call_run": max_identical_run(RUNS[k], i)})
        rows.append(r)
    eD = sum(r["D_patch_bytes"] == 0 for r in rows); eE = sum(r["E_patch_bytes"] == 0 for r in rows)
    d_only = sum(r["D_patch_bytes"] == 0 and r["E_patch_bytes"] > 0 for r in rows)
    e_only = sum(r["E_patch_bytes"] == 0 and r["D_patch_bytes"] > 0 for r in rows)
    n = d_only + e_only
    p_one = sum(comb(n, j) for j in range(e_only, n + 1)) / 2 ** n if n else 1.0  # P(E-empty-only >= obs | p=.5)
    p_two = min(1.0, 2 * min(p_one, sum(comb(n, j) for j in range(0, e_only + 1)) / 2 ** n)) if n else 1.0
    res = {"_schema": "plan005_arm_compare_v1", "plan": "eval/plans/005.md Addendum E",
           "A": "arm D 31b-v006-p5d (cap 4.0)", "B": "arm E 31b-v007-p5e 3a62f41f (cap 1.23)",
           "generator": "eval/plan005_armE_compare.py", "n": len(rows), "k": 1,
           "empty": {"armD": eD, "armE": eE}, "discordant": {"armD_empty_only": d_only, "armE_empty_only": e_only},
           "sign_test": {"n_discordant": n, "p_one_sided_E_more_empty": p_one, "p_two_sided": p_two},
           "timeouts": {"armD": sum(r["D_timeout"] for r in rows), "armE": sum(r["E_timeout"] for r in rows)},
           "agent_clock_sum_s": {"armD": round(sum(r["D_agent_clock_s"] for r in rows), 1),
                                  "armE": round(sum(r["E_agent_clock_s"] for r in rows), 1)},
           "first_ok_edit_before_cap_73_8s": {"armD": sum(r["D_first_ok_edit_s"] is not None and r["D_first_ok_edit_s"] < CAP_S for r in rows),
                                              "armE": sum(r["E_first_ok_edit_s"] is not None and r["E_first_ok_edit_s"] < CAP_S for r in rows)},
           "tool_errors_totals": {"armD": json.load(open("results/trace_tool_errors_31b_v006.json"))["totals"],
                                  "armE": json.load(open("results/trace_tool_errors_31b_v007.json"))["totals"]},
           "tasks": rows}
    gate = json.load(open("results/kaggle_timing_31b_v007.json"))["gate"]
    tb = json.load(open("results/thinking_bound_31b_v007.json"))
    tbt = tb.get("tasks", tb)
    addon = all(v.get("has_summary") and v.get("root_usage_turns", 0) >= 1 for v in (tbt.values() if isinstance(tbt, dict) else tbt))
    res["gates_armE"] = gate; res["V_gates"] = gate["status"] == "PASS"; res["V_addon"] = addon
    V = res["V_gates"] and addon
    res["verdict_armE"] = "INVALID" if not V else ("USABLE" if eE <= 4 and e_only <= 2 else "CAP-BOUND")
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k not in ("tasks", "gates_armE")}, indent=1))
    for r in rows: print(r)

if __name__ == "__main__":
    main(sys.argv[1])
