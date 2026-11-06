Fix the 3 BLOCKING findings of codex review ops/codex/review-20261106T150446.md against the plan 009 arm3/arm3smoke modes in
eval/plan008_metrics.py (merged on main at b92f8f4). eval/plans/009.md GOVERNS (IDENTITY block ~l.43-55, SMOKE l.38-58, VALIDITY,
Decision rule INVALID line ~l.104). Do NOT change legacy base/smoke/arm2 modes: their outputs must stay byte-identical on the existing
tests (eval/tests/test_plan008_metrics.py must pass unchanged except where it already changed in b92f8f4). No task text in outputs.

B1 VOIDED PAIRING / BASE VALIDITY -> INVALID.
 - If env_drift.pairing_void_candidate is true (any kernel agent/verification-path difference) the decision MUST be
   'INVALID (pairing voided: <reason>)', never ON-ADOPT/ON-BETTER-VETOED/KEEP-OFF/NO-DIFFERENCE.
 - Base validity is CONSUMED by arm3_decision: base=arm1 -> VALID (dec 069, keep the ENV CONTROL caveat string). base=arm2 ->
   require a new --base-verdict-json = the plan008 arm2-mode output file; hash it into _schema inputs; if missing, unreadable, or its
   decision/verdict is INVALID / absent / not one of plan 008's ruled verdicts -> 'INVALID (base invalid/unruled)'.
 - Fix eval/tests/test_plan009_metrics.py (~l.252): differing agent-path hashes must expect INVALID, not KEEP-OFF.
B2 SMOKE EVIDENCE BOUND TO COUNTED ROWS.
 - arm3 mode: --smoke-json becomes REQUIRED. Additionally RECOMPUTE smoke criterion (i) (thinking_criterion) from the trace files of
   the rows actually selected for the first 2 ids of eval/plans/007-arm1-ids.txt (from the dir aggregate_arm selected them).
 - The smoke json's _schema input list must contain the sha256 of exactly the timing.jsonl of the dir the counted smoke rows came
   from (and the same trace sha256s); otherwise INVALID ('smoke evidence not bound'). smoke-json overall != PASS -> INVALID.
   Recomputed (i) != PASS -> 'INVALID (smoke i)'. Missing smoke json -> argparse error (non-zero exit).
B3 IDENTITY + MECHANICS ENFORCED.
 - New required args for BOTH arm3smoke and arm3: --identity-json results/plan009_bundle_identity.json (format: see eval/plan009_identity.py
   SCHEMA) and --bundle v01N, and --transport DIR=SHA256 (one per arm-3 run dir; the journaled TRANSPORT sha of that push).
   Hash identity json into _schema. Require: a record for that bundle with pass true (zip_ok and content_ok) whose event matches each push
   (smoke for arm3smoke; for arm3, a passing record exists for the smoke and main events at minimum - accept 'chunkN' for extra dirs);
   every header in each dir has bundle_sha256 == that dir's --transport sha; every header in EVERY arm-3 dir has agent_yaml_sha256 ==
   the identity record's agent_yaml_sha256 (so conflicting headers across dirs fail). A dir with no --transport -> error.
 - Smoke mismatch -> criterion (iii) FAIL; main/chunk mismatch -> that run is not counted -> decision 'INVALID (identity mismatch)'
   (plan says run not counted; with exactly-33 aggregation that makes the arm incomplete, so INVALID with the mismatching dirs listed).
 - Remove the unconditional identity_checked_externally=True; replace with the actual checked fields.
 - vLLM up: (iii) requires vLLM startup evidence, using the same definition as eval/plan007_blind_gate.py (a '_vllm' record with
   positive startup seconds in timing.jsonl); absent -> (iii) UNVERIFIABLE (not PASS).
Non-blocking (do it): duplicate listing in aggregate_arm also gives each attempt's compact outcome (dir, resolved, timeout, empty_patch).

ACCEPTANCE (offline tests in eval/tests/test_plan009_metrics.py, synthetic fixtures only):
 a) the review's reproductions all fail closed: differing agent-path hashes -> INVALID; arm3 without --smoke-json -> non-zero exit;
    smoke json from another run (different timing sha) -> INVALID; zero-thinking arm-3 smoke rows with a PASS smoke json -> INVALID (smoke i);
    smoke without _vllm record -> not PASS; conflicting agent_yaml_sha256 across arm-3 dirs -> INVALID; bundle_sha256 != --transport -> INVALID
    / smoke (iii) FAIL; identity json missing record or pass false -> INVALID / FAIL; base=arm2 with INVALID or missing base verdict -> INVALID.
 b) a fully consistent synthetic fixture still yields each of ON-ADOPT, KEEP-OFF, NO-DIFFERENCE, ON-BETTER-VETOED as before.
 c) arm-1 self-pair stays INVALID (7 H rows) as now.
 d) full suite: PYTHONPATH=/home/ubuntu/gemma-local/venv/lib/python3.13/site-packages PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 LITELLM_LOCAL_MODEL_COST_MAP=True /home/ubuntu/gemma-local/pyimg/cpython-3.13-linux-x86_64-gnu/bin/python3 -m pytest eval/tests -q   (all previously passing tests still pass; report counts)
