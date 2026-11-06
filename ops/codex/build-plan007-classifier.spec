Plan 007 rev 2: a frozen, mechanical row classifier for Kaggle pass-rate kernel rows (fixes codex review ops/codex/review-20261106T064331.md BLOCKING 1-3). Two parts. Keep the change minimal; touch NOTHING on the agent path or the stock verification path.

PART A: eval/kaggle/agent_timing.py, the per-task row (the main `append(journal, dict(instance_id=iid, ...))` near line 1090). Add exactly three fields:
  result_error = (result.error[:4096] if result is not None and result.error else None)   # stock TaskResult.error, verbatim, truncated to 4096 chars
  agent_error_text = (evaluator.agent_error[:4096] if evaluator.agent_error else None)
  verified_patch_bytes = (len((result.agent_patch or '').encode('utf-8')) if result is not None else None)  # the patch stock Container B verified (post protected-file strip)
Also add the same three fields to the `except Exception` fallback row (computed defensively; use None if anything raises). Do not change harness_error(), the `error` field, or anything else. Bump nothing else. Add a unit test in eval/tests/test_agent_timing.py that the generated row contains these fields (follow the existing test style there for building rows; if the row is only built inside main(), a source-level test that asserts the three keys appear in both row dicts is acceptable).

PART B: new file eval/kaggle/classify_rows.py (stdlib only, python 3.10+), plus tests eval/tests/test_classify_rows.py.
API: classify(row: dict) -> dict with keys:
  h: None | 'H-ROW' | 'H-SETUP' | 'H-VERIFY'   (first match in this precedence order: H-ROW, H-SETUP, H-VERIFY)
  known_diag: bool   (a flag, orthogonal to h and agent label)
  agent: None | 'PASS' | 'NO_PATCH' | 'TIMEOUT' | 'PATCH_APPLY' | 'VERIFY_TIMEOUT_124' | 'PYTEST_1' | 'PYTEST_2_5' | 'EXIT0_UNRESOLVED' | 'OTHER_FAIL'  (None iff h is not None)
  resolved: bool(row.get('resolved'))   # ALWAYS the stock verdict, even for H rows
  reasons: list[str]  (short machine strings explaining h / known_diag; ids only, never file contents)
Meta rows (no 'instance_id' key, e.g. '_schema', '_vllm', '_stopped', '_done') are skipped by the CLI and classify() raises ValueError on them.

Marker constants (module level, frozen):
  RECORD = 'uninstall-no-record-file'
  WRAPPER_H = ('Evaluation exception (', 'Cleanup exception (', 'trace parse (', 'Row build exception (')
  AGENT_END = regexes copied from agent_timing.AGENT_OUTCOMES (timeout, turns, tool_calls, no_submit) -- import them from agent_timing if importing is side-effect free, else copy the patterns verbatim and add a test asserting equality with agent_timing.AGENT_OUTCOMES patterns.
  VERIFY_AGENT_PREFIXES (stock swegemma/harness/verification.py messages caused by the agent patch):
    'Failed to apply agent patch:'  -> PATCH_APPLY
    'Missing or empty JUnit XML report', 'Malformed JUnit XML report:', 'No <testsuite> elements found in JUnit XML',
    'No passing tests recorded in JUnit XML', 'Test failures/errors recorded in JUnit XML', 'Required test node did not pass:',
    'Pytest stdout summary indicates zero or no passing tests', 'Missing JUnit XML report (possible premature os._exit(0))'  -> verification-agent (JUnit family)
  Anything else (including 'Evaluation error:', 'Failed to apply test_patch:', 'Missing test specification') is NOT agent-caused.

Rules (frozen):
H-ROW if any of:
  (r1) row lacks any of the keys result_error, agent_error_text, verified_patch_bytes, setup_calls, exit_code, resolved (schema guard: rows from before PART A are H-ROW);
  (r2) row['error'] (string) contains any WRAPPER_H substring;
  (r3) row['error'] is non-null and is not exactly 'Harness task failure' (after the r2 check);
  (r4) row['error'] == 'Harness task failure' and some non-empty message in [result_error, agent_error_text] matches neither AGENT_END (re.match on stripped text) nor startswith any VERIFY_AGENT_PREFIXES;
  (r5) row['error'] is None but some non-empty message in [result_error, agent_error_text] matches neither AGENT_END nor VERIFY_AGENT_PREFIXES (fail closed; should not happen).
H-SETUP, evaluated over ALL entries of row['setup_calls'] (there is one entry per setup step per installation pass; a row with verification has several passes and several 'setup.py' entries):
  (s1) row.get('missing_tool_deps') non-empty;
  (s2) any entry with step not in ('pip_check', 'workspace_editable', 'setup.py') and rc != 0 (rc None counts as != 0 only if duration_s > 0 or stderr non-empty; otherwise treat None as not-run and ignore);
  (s3) any 'setup.py' entry with rc != 0;
  (s4) any 'workspace_editable' entry with rc != 0 whose stdout+stderr does not contain RECORD;
  (s5) for each 'setup.py' entry: let E = its 'subprocesses' (missing -> []) filtered to argv being a list containing '-e', in order. Every element with rc != 0 must be either
        OFFLINE_RECORD: '--no-index' in argv and RECORD in (stdout+stderr), or
        FALLBACK: '--no-index' not in argv and an OFFLINE_RECORD failure occurs EARLIER in the same entry's E.
       Any other failing editable subprocess -> H-SETUP;
  (s6) consistency: row['setup_failed'] is True but none of s1-s5 fired and known_diag is False -> H-SETUP ('setup_failed_unexplained').
known_diag = at least one OFFLINE_RECORD failure (s5) or a workspace_editable rc != 0 containing RECORD, AND no s1-s6 fired. (If any s-rule fired, known_diag False and h='H-SETUP' unless H-ROW took precedence.)
H-VERIFY: verified_patch_bytes > 0 AND not PATCH_APPLY (result_error does not start with 'Failed to apply agent patch:') AND exit_code is not an int in {0,1,2,3,4,5,124}.
AGENT label when h is None (first match):
  resolved True -> 'PASS';
  verified_patch_bytes == 0 -> 'NO_PATCH';
  result_error startswith 'Failed to apply agent patch:' -> 'PATCH_APPLY';
  exit_code == 124 -> 'VERIFY_TIMEOUT_124';
  exit_code == 1 -> 'PYTEST_1';  exit_code in 2..5 -> 'PYTEST_2_5';  exit_code == 0 -> 'EXIT0_UNRESOLVED';
  else 'OTHER_FAIL'.
  Separately expose agent_end = name of matched AGENT_END pattern on agent_error_text (None if none) in the output dict (descriptive; e.g. a timed-out agent that still produced a patch is labelled by its verification outcome, with agent_end='timeout').

CLI: python3 eval/kaggle/classify_rows.py <timing.jsonl> [--out <json>] : prints and/or writes JSON
  {_schema: 'plan007_row_classes/v1', classifier_sha256: <sha256 of this source file>, input: <path>, input_sha256, n_rows, counts: {h: {...}, agent: {...}, known_diag: n}, h_rows: [ids], rows: [{instance_id, repo, h, known_diag, agent, agent_end, resolved, reasons}]}.
  Exit 0 always on a parseable file. Must not print patches, test output or any message text (reasons are fixed short codes like 's5:unexpected_editable_failure', 'r4:unrecognized_message').

TESTS (eval/tests/test_classify_rows.py, offline, synthetic rows only, no files from runs/ or data/):
  1. RECORD chain: setup.py entry with two editable subprocesses [offline --no-index rc1 stderr containing RECORD, online fallback rc1 stdout 'subprocess-exited-with-error'], setup_failed True, editable_failed True -> h None, known_diag True.
  2. Same chain repeated in 3 setup.py entries (3 passes) -> known_diag True, h None.
  3. Offline failure WITHOUT RECORD -> H-SETUP. Fallback failure with no earlier offline-RECORD failure -> H-SETUP.
  4. Chain in pass 1 but pass 2 has a non-RECORD offline failure -> H-SETUP (later pass not overwritten).
  5. tool_deps rc -1 -> H-SETUP; missing_tool_deps ['x'] -> H-SETUP; setup_failed True with clean calls -> H-SETUP.
  6. error 'Harness task failure' + result_error 'Failed to apply agent patch: xyz' + exit_code 1, verified_patch_bytes 50 -> h None, agent PATCH_APPLY.
  7. error 'Harness task failure' + result_error 'Required test node did not pass: a::b', exit 0 -> h None, agent EXIT0_UNRESOLVED; same with 'Test failures/errors recorded in JUnit XML (failures=1, errors=0)' exit 1 -> PYTEST_1.
  8. exit_code 124, patch bytes 10 -> h None, VERIFY_TIMEOUT_124.
  9. error 'Harness task failure' + result_error 'Evaluation error: boom' -> H-ROW; 'Failed to apply test_patch: x' -> H-ROW; unknown agent_error_text 'Agent crashed' -> H-ROW.
  10. error 'Cleanup exception (OSError)' -> H-ROW even with resolved True; output resolved stays True.
  11. error None, 'Harness task failure trace parse (KeyError)' -> H-ROW.
  12. verified_patch_bytes 30, exit_code None, result_error None -> H-VERIFY; exit -1 -> H-VERIFY; verified_patch_bytes 0 exit -1 agent_error_text 'Agent exceeded turns budget' -> h None, NO_PATCH, agent_end 'turns'.
  13. row missing result_error key -> H-ROW (schema).
  14. resolved True clean -> PASS.
  15. CLI on a temp jsonl with meta rows + 3 rows: counts correct, output contains no message text (assert 'boom' not in stdout).
Run: the repo's test command is /home/ubuntu/gemma-local/venv/bin/python3 -m pytest eval/tests -q (if that interpreter is unavailable in your sandbox, use python3 -m pytest eval/tests/test_classify_rows.py eval/tests/test_agent_timing.py -q). All existing tests must still pass.
