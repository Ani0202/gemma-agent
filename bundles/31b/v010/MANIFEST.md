# 31b-v010-p8 (PLAN 008 ARM-2 candidate, dec 069 item 3). CPU DRAFT, UNVALIDATED, packed: dist/31b-v010.zip sha256=c7a86295a023db971bcc9d149c4e6c68674d5ea052ecdfb3c11655b535772cd8 (bin/pack PASS).
- parent: 31b-v009-p7a1 (dist/31b-v009.zip sha256=d38c55c79103950d6d269a722bd0c9db9db22e1c0ec96be230f6c24a332d130d).
- WHY a gate sub-agent: the harness submit_patch cannot be wrapped from a bundle (swegemma 0.2.11 registers no callbacks:
  CallbackRegistry unused), and agent_runner breaks the session as soon as context.patch_submitted is set, even for an
  empty diff. So the root no longer has the harness submit_patch; it gets an agent_tool sub-agent NAMED submit_patch
  (sub_agents/submit_gate.yaml, same model, temp 0, thinking 0, max_output_tokens 1024) whose tools are run_command + the
  real submit_patch. The gate runs one fixed shell check: count changed/untracked paths excluding tests/, test_*.py,
  *_test.py, conftest.py, pyproject.toml, setup.cfg, pytest.ini; a /tmp counter allows at most 2 EDIT_FIRST answers per
  task, the 3rd call always submits (no loop). Unit test: eval/tests/test_submit_gate.py (runs the YAML's exact command).
- changes vs v009: (1) agent.yaml: harness submit_patch removed from root tools, agent_tool submit_gate added;
  (2) sub_agents/submit_gate.yaml NEW; (3) prompts/system.md: l.33 `set -o pipefail;` before the repro pipe (codex NB2 of
  review 043840, folded per dec 061 ii / dec 069 item 3, UNSCREENED); submit paragraph rewritten for gate semantics
  (NOT SUBMITTED -> edit, then call again) + dec 070 1(b) rule (git diff --stat must show a non-test source file, else edit first);
  anti-pattern line = design-note Option A text verbatim (dec 070 item 2) + "edit_file fails twice on the same file -> shorter
  anchor or /tmp Python script" (PROMPT-LEVEL: no tool-level hook exists, feasibility in eval/plans/008.md).
- unchanged: eval_config.yaml (cap 3.5, 40 calls / 50 turns), sampling, analyzer sub-agent. No repo-named content (dec 057).
- bundle_load_check (real adk_submission compiler, stub tools): PASS; root tools end with code_analyzer_agent, submit_patch (AgentTool).
zip sha256: c7a86295a023db971bcc9d149c4e6c68674d5ea052ecdfb3c11655b535772cd8
