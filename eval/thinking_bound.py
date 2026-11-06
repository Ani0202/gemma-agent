"""Per-task lower bound on ROOT thinking tokens per turn (plan 005 Addenda C/D correction 2).
A turn = a root usage-bearing entry plus the root entries sharing its timestamp. Every token decodes to >= 1 char, so
non-thinking tokens <= chars(visible text) + chars(json tool args) + OVERHEAD per tool call; hence
thinking_tokens >= completion_tokens - those chars - OVERHEAD*n_calls. Also reports max thinking-text chars.
Usage: thinking_bound.py <run_dir> [<out.json>]"""
import json, sys, glob, os
ROOT = "swe_baseline_agent"; OVERHEAD = 32
def turns(entries):
    out = []
    for i, e in enumerate(entries):
        if e.get("author") == ROOT and e.get("usage"):
            grp = [x for x in entries if x.get("author") == ROOT and x.get("timestamp") == e.get("timestamp")]
            out.append((e, grp))
    return out
def task(path):
    d = json.load(open(path)); E = d.get("entries") or []
    res = {"has_summary": isinstance(d.get("summary"), dict), "root_usage_turns": 0, "max_completion": 0,
           "max_thinking_chars": 0, "max_thinking_lb": 0, "thinking_blocks": 0}
    for e in E:
        if e.get("author") == ROOT and e.get("type") == "thinking" and (e.get("content") or ""):
            res["thinking_blocks"] += 1; res["max_thinking_chars"] = max(res["max_thinking_chars"], len(e["content"]))
    for e, grp in turns(E):
        res["root_usage_turns"] += 1
        comp = e["usage"].get("completion_tokens") or 0
        other = 0; ncalls = 0
        for x in grp:
            if x.get("type") == "tool_call":
                ncalls += 1; other += len(json.dumps(x.get("args"), ensure_ascii=False)) + len(x.get("tool") or "")
            elif x.get("type") not in ("thinking", "tool_call", "tool_response") and isinstance(x.get("content"), str):
                other += len(x["content"])
        lb = comp - other - OVERHEAD * max(ncalls, 1)
        res["max_completion"] = max(res["max_completion"], comp); res["max_thinking_lb"] = max(res["max_thinking_lb"], lb)
    return res
if __name__ == "__main__":
    run = sys.argv[1]; rows = {}
    for p in sorted(glob.glob(os.path.join(run, "runs", "*", "trace.json"))):
        rows[p.split(os.sep)[-2]] = task(p)
    out = {"_schema": "thinking_bound_v1", "run": run, "overhead_tokens_per_call": OVERHEAD,
           "fields": {"max_thinking_lb": "max over root turns of completion_tokens - chars(visible text + tool name + json args) - 32*max(calls,1); a proven lower bound on thinking tokens",
                      "max_thinking_chars": "longest root thinking block (chars)", "thinking_blocks": "root thinking entries with non-empty content",
                      "max_completion": "max root per-turn completion_tokens", "root_usage_turns": "root usage-bearing turns", "has_summary": "trace summary present"},
           "tasks": rows}
    s = json.dumps(out, indent=1)
    if len(sys.argv) > 2: open(sys.argv[2], "w").write(s + "\n")
    for k, v in rows.items(): print(k, v)
