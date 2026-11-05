"""Offline load check for a bundle (dec 032 item 2): compiles agent.yaml with the real
adk_submission compiler + swegemma generation constraints, then prints the effective
max_output_tokens per agent and the effective session timeout from eval_config.yaml via EvalConfig.
Usage: python bundle_load_check.py <bundle_dir>  (CPU only, no model calls; stub tools)."""
import json, sys, tempfile
from pathlib import Path
import yaml
from adk_submission.compiler import compile_submission
from adk_submission.registry import ModelRegistry
from swegemma.config import EvalConfig, build_submission_limits

bundle = Path(sys.argv[1]).resolve()
TOOLS = ['run_command', 'submit_patch', 'get_status', 'read_file', 'edit_file', 'write_file',
         'get_code_neighbors', 'search_similar_code', 'get_code_subgraph']

def make_stub(name):
    def stub(x: str = '') -> str:
        return ''
    stub.__name__ = name
    stub.__doc__ = f'stub {name}'
    return stub

models = ModelRegistry()
for m in ('gemma-4-e4b-it-qat-w4a16-ct', 'gemma-4-31b-it-qat-w4a16-ct'):
    models.register(m, m)
limits, constraints = build_submission_limits()
agent = compile_submission(submission_dir=bundle, tool_registry={t: make_stub(t) for t in TOOLS},
                           model_registry=models, limits=limits, generation_constraints=constraints)
out = {'bundle': str(bundle), 'agents': []}
def walk(a, depth=0):
    gcc = getattr(a, 'generate_content_config', None)
    tc = getattr(gcc, 'thinking_config', None) if gcc else None
    out['agents'].append(dict(name=a.name, depth=depth, model=str(getattr(a, 'model', None)),
        max_output_tokens=getattr(gcc, 'max_output_tokens', None) if gcc else None,
        thinking_budget=getattr(tc, 'thinking_budget', None) if tc else None))
    for sub in getattr(a, 'sub_agents', []) or []:
        walk(sub, depth + 1)
    for t in getattr(a, 'tools', []) or []:
        inner = getattr(t, 'agent', None)
        if inner is not None:
            walk(inner, depth + 1)
walk(agent)
raw = yaml.safe_load((bundle / 'eval_config.yaml').read_text()) or {}
sec = raw.get('evaluation', raw)
with tempfile.TemporaryDirectory() as d:
    cfg = EvalConfig(tasks_path=Path(d) / 't.jsonl', snapshots_dir=Path(d), results_dir=Path(d),
                     submission_dir=bundle, models=models, max_time_minutes=float(sec['max_time_minutes']),
                     timeout_seconds=int(sec['timeout_seconds']), max_tool_calls=int(sec['max_tool_calls']),
                     max_turns=int(sec['max_turns']))
    out['eval'] = dict(raw=sec, budget_time_minutes=cfg.budget.time_minutes,
                       session_timeout_seconds=cfg.budget.time_minutes * 60,  # agent_runner.py:718 rule
                       budget_tool_calls=cfg.budget.tool_calls, budget_turns=cfg.budget.turns)
print(json.dumps(out, indent=1, default=str))
