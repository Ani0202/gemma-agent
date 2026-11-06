#!/usr/bin/env python3
"""Plan 005 Addendum F: arm F (31b-v008-p5f, temperature 0.6) vs arm D (31b-v006-p5d, temperature 0.2), same cap 4.0,
paired on the same 8 ids, k=1. Reuses first_ok_edit() and max_identical_run() from plan005_armE_compare.py unchanged
(the Addendum F metric is defined as that function).
Usage: plan005_armF_compare.py <out.json>"""
import json, sys
from math import comb
sys.path.insert(0, "eval")
import plan005_armE_compare as E

RUNS = {"D": "runs/31b-v006-p5d-timing", "F": "runs/31b-v008-p5f-timing"}
VER = {"D": "v006", "F": "v008"}
CAP_S = 240.0  # cap 4.0 min, both arms
LOOP_MIN = 5

def main(out):
    ids = [l.strip() for l in open("eval/plans/004-gpu-retime-ids.txt") if l.strip() and not l.startswith("#")]
    assert len(ids) == 8, ids
    tim = {k: {t["instance_id"]: t for t in json.load(open(f"results/kaggle_timing_31b_{v}.json"))["tasks"]} for k, v in VER.items()}
    tte = {k: {t["instance_id"]: t for t in json.load(open(f"results/trace_tool_errors_31b_{v}.json"))["tasks"]} for k, v in VER.items()}
    rows = []
    for i in ids:
        r = {"id": i}
        for k in ("D", "F"):
            s, tool = E.first_ok_edit(RUNS[k], i)
            r.update({f"{k}_patch_bytes": tte[k][i]["patch_bytes"], f"{k}_timeout": bool(tim[k][i]["agent_timeout_fired"]),
                      f"{k}_agent_clock_s": round(tim[k][i]["agent_clock_seconds"], 3),
                      f"{k}_first_ok_edit_s": s, f"{k}_first_ok_edit_tool": tool, f"{k}_tool_calls": tte[k][i]["tool_calls"],
                      **dict(zip((f"{k}_max_identical_call_run", f"{k}_max_identical_run_start_s",
                                  f"{k}_max_identical_run_end_s", f"{k}_max_identical_run_span_s"), E.max_identical_run(RUNS[k], i)))})
        rows.append(r)
    eD = sum(r["D_patch_bytes"] == 0 for r in rows); eF = sum(r["F_patch_bytes"] == 0 for r in rows)
    d_only = sum(r["D_patch_bytes"] == 0 and r["F_patch_bytes"] > 0 for r in rows)
    f_only = sum(r["F_patch_bytes"] == 0 and r["D_patch_bytes"] > 0 for r in rows)
    n = d_only + f_only
    p_one = sum(comb(n, j) for j in range(f_only, n + 1)) / 2 ** n if n else 1.0  # P(F-empty-only >= obs | p=.5)
    p_two = min(1.0, 2 * min(p_one, sum(comb(n, j) for j in range(0, f_only + 1)) / 2 ** n)) if n else 1.0
    loops = {k: sum(r[f"{k}_max_identical_call_run"] >= LOOP_MIN for r in rows) for k in ("D", "F")}
    totals = {k: json.load(open(f"results/trace_tool_errors_31b_{VER[k]}.json"))["totals"] for k in ("D", "F")}
    res = {"_schema": "plan005_arm_compare_v1", "plan": "eval/plans/005.md Addendum F",
           "A": "arm D 31b-v006-p5d b7b2eb3d (cap 4.0, temperature 0.2)", "B": "arm F 31b-v008-p5f e1513aac (cap 4.0, temperature 0.6)",
           "generator": "eval/plan005_armF_compare.py", "n": len(rows), "k": 1,
           "empty": {"armD": eD, "armF": eF}, "discordant": {"armD_empty_only": d_only, "armF_empty_only": f_only},
           "sign_test": {"n_discordant": n, "p_one_sided_F_more_empty": p_one, "p_two_sided": p_two},
           "tasks_max_identical_run_ge_5": loops,
           "timeouts": {"armD": sum(r["D_timeout"] for r in rows), "armF": sum(r["F_timeout"] for r in rows)},
           "agent_clock_sum_s": {"armD": round(sum(r["D_agent_clock_s"] for r in rows), 1),
                                  "armF": round(sum(r["F_agent_clock_s"] for r in rows), 1)},
           "first_ok_edit_before_cap_240s": {k2: sum(r[f"{k}_first_ok_edit_s"] is not None and r[f"{k}_first_ok_edit_s"] < CAP_S for r in rows)
                                             for k, k2 in (("D", "armD"), ("F", "armF"))},
           "edit_missing_param": {"armD": totals["D"].get("edit_missing_param", 0), "armF": totals["F"].get("edit_missing_param", 0)},
           "cmd_error_shell": {"armD": totals["D"].get("cmd_error_shell", 0), "armF": totals["F"].get("cmd_error_shell", 0)},
           "tool_errors_totals": {"armD": totals["D"], "armF": totals["F"]},
           "tasks": rows}
    gate = json.load(open("results/kaggle_timing_31b_v008.json"))["gate"]
    tb = json.load(open("results/thinking_bound_31b_v008.json"))
    tbt = tb.get("tasks", tb)
    tb_ids = set(tbt) if isinstance(tbt, dict) else {v["instance_id"] for v in tbt}
    assert tb_ids == set(ids), f"thinking-bound ids != planned 8 ids: {sorted(tb_ids ^ set(ids))}"
    addon = all(v.get("has_summary") and v.get("root_usage_turns", 0) >= 1 for v in (tbt.values() if isinstance(tbt, dict) else tbt))
    res["gates_armF"] = gate; res["V_gates"] = gate["status"] == "PASS"; res["V_addon"] = addon
    V = res["V_gates"] and addon
    if not V: verdict = "INVALID"
    elif eF >= 5 or f_only >= 3: verdict = "HARM"
    elif loops["F"] == 0 and eF <= 4 and f_only <= 2: verdict = "LOOP-REDUCED"
    else: verdict = "NO-EFFECT"
    res["verdict_armF"] = verdict
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k not in ("tasks", "gates_armF", "tool_errors_totals")}, indent=1))
    for r in rows: print(r)

if __name__ == "__main__":
    main(sys.argv[1])
