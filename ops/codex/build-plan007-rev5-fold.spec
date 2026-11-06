Fold EVERY item of the codex review ops/codex/review-20261106T071306.md (rev-5 exhaustive review of eval/kaggle/classify_rows.py) into the classifier, in ONE change. Read that review file first; it is the spec. Also read eval/plans/007.md lines 45-100 (row classification rules) and the row producer eval/kaggle/agent_timing.py (around line 1096 and wherever setup_calls / subprocesses / header records / _done are emitted) so every rule matches what the producer actually emits. Do NOT edit eval/plans/007.md or any results/ file other than regenerating results/plan007_classifier_armF_check.json via its existing generator/CLI.

Principle: invalid, missing, or contradictory evidence => H-* (fail closed), never PASS/FAIL. Legitimate producer shapes must keep their current class.

Required fixes (numbering = review's BLOCKING items):
1. resolved=True with a nonempty result_error (any text) => H-VERIFY (descriptive agent_error_text on success stays allowed).
2. If result_error and agent_error_text are both nonempty and recognized but name different categories (e.g. turns vs timeout, or two different verification-message families), => H-ROW.
3. JUnit/required-node failure messages require exit_code == 0 (int); any other exit (1-5, 124, null, -1) => H-VERIFY. Fix the existing test at eval/tests/test_classify_rows.py:94 that blesses JUnit + exit 1.
4. PATCH_APPLY ("Failed to apply agent patch:") requires verified_patch_bytes > 0 and an exit_code consistent with the producer's apply-failure branch (check agent_timing.py / stock verification for the actual value: null/-1/nonzero); exit 0 or zero patch bytes with that message => H-VERIFY.
5. verified_patch_bytes == 0 => exit_code must be null or -1 (whatever the producer emits for no-patch); anything else => H-VERIFY.
6. Add error, setup_failed, missing_tool_deps to REQUIRED (key presence, explicit null still allowed where the producer emits null); missing => H-ROW. Distinguish missing from explicit null (no .get() conflation).
7. setup_calls entries: require presence of every key the producer always emits (step, rc, duration_s, stdout, stderr - verify against producer); explicit null allowed where producer emits null; missing => H-ROW. Missing subprocess rc => never a known diagnostic.
8. step must be one of the producer's known step names (exact, non-blank); subprocesses only allowed on steps the producer attaches them to; argv must be a non-empty list of non-blank strings; violations => H-ROW.
9. instance_id and repo must be non-empty str (strip-blank rejected) => else H-ROW (direct call) and CLI likewise.
10. Generic not-run predicate requires rc null AND duration 0 AND empty stdout AND empty stderr.
11. Known-diagnostic exemption requires an int rc != 0 on the executed attempt; null/missing rc never qualifies.
12. Marker matching per stream (stdout and stderr separately), never on a concatenation.
13. Known editable diagnostic requires argv to match the producer's actual offline editable command shape exactly (derive the exact form from agent_timing.py / swegemma setup code), not mere presence of "-e" and "--no-index".
14. An offline diagnostic record excuses only the immediately following online fallback with the same command/target identity, and is consumed (reset) after use; any later failure is not excused.
15. CLI: skip only recognized metadata records (the producer's header record with _schema, and the _done record); every other JSON value (lists, task-shaped dicts missing instance_id, etc.) must go through validation and cause a non-zero CLI exit with a clear error (consistent with existing dup-ID rejection).
16. Parse JSONL with object_pairs_hook rejecting duplicate keys => non-zero CLI exit.
17. CLI journal accounting: if header task_ids present, row ids must be an in-order prefix of task_ids (no unexpected ids, no interior gaps); if _done.n present it must equal the row count; violation => non-zero exit. A legitimate completed prefix without _done (unrun suffix) stays allowed.
18. Header with vllm_startup_seconds null (vLLM not up) or mcp_import_ok false => kernel void: CLI output marks kernel_void=true with reason and every row is H-ROW with reason kernel:void (no PASS counted).
19. Non-finite/overflowing numbers (e.g. 10**400) must not crash: catch OverflowError/ValueError/TypeError in numeric checks => H-ROW.
False-H 1-2: setup.py and workspace_editable entries with rc null, duration 0, empty stdout and stderr are legitimate not-run entries => no H-SETUP.

Acceptance:
- Add one regression test per item above (1-19 plus both false-H), using the review's synthetic B row and the exact override given in the review, asserting the H class (or exact non-H class for false-H), or non-zero CLI exit for 15/16/17. Keep the review's "no false H" shapes as tests too: NO_PATCH/PATCH_APPLY legit null/-1 exits, EXIT0_UNRESOLVED, VERIFY_TIMEOUT_124, recognized agent-end messages under "Harness task failure", empty setup_calls, generic not-run entries.
- All of eval/tests passes (run via the repo's documented pytest invocation; see memory note: pyimg python + harness PYTHONPATH, or however eval/tests currently runs). Report exact counts.
- Regenerate results/plan007_classifier_armF_check.json with the new sha; report the arm-F counts (expected unchanged: 8 H-ROW, 7 known diagnostics, 0 H-SETUP) and explain any change.
- Print the new sha256 of eval/kaggle/classify_rows.py.
- In your final message list, per item, the rule implemented and the test name; and list anything you could NOT fold (with why) as RESIDUAL.
