# 31b-v010-p8 (PLAN 008 ARM-2 candidate, dec 069 item 3). CPU DRAFT, UNVALIDATED, packed: dist/31b-v010.zip sha256=b0785a30e2ad3451f0bbb0fb574e6cde53412ca2381ab04394e66792886d33ce (bin/pack PASS, D73.4 repack). VOID (never run): fc24fcc3eeb98f1bdcd5914d61d597ed2b309d74eb64bed717a2ba5b47bd7c42, c7a86295...
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
- REPACK (plan 008 Addendum D72.1, codex review 20261106T133941 BLOCKING 1-2): gate check = harness protected-path rule (python3 one-liner
  reimplementing verification._is_protected_test_or_config_path over `git diff --name-status -z _swegemma_baseline` (D73.4: keep rename/copy entries only when neither path is protected)), outputs
  `GATE call= kept_files=` + `VERDICT=... reason=changes|forced|check_error`; counter failure-safe; SUBMIT FAILED on inner error; system.md
  "non-test source file" -> "non-test file" in the gate sentence. Previous zip c7a86295... VOID (never run). Load check PASS
  (results/bundle_load_check_31b_v010.json); tests eval/tests/test_submit_gate.py 58 pass.
- Correction: the anti-pattern line is the Option A text with its first sentence bolded, so it is not byte-verbatim (codex NB3).
zip sha256: b0785a30e2ad3451f0bbb0fb574e6cde53412ca2381ab04394e66792886d33ce
- REPACK D73.4 (plan 008 Addendum D73; merge d6174d8 of codex a9cef73): eligibility via `git diff --name-status -z` (default rename detection,
  rename/copy kept only if neither path protected); counter accepts only 1-2 digit decimal state (10#), else n=9; forced check now precedes
  changes (n>2 -> reason=forced). fc24fcc3 VOID (never run). New zip sha256 b0785a30e2ad3451f0bbb0fb574e6cde53412ca2381ab04394e66792886d33ce
  (line above); pack PASS; load check PASS (results/bundle_load_check_31b_v010.json unchanged); eval/tests 1475 pass.
