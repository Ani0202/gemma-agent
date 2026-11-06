Fix the 3 BLOCKING findings of codex review ops/codex/review-20261106T151940.md against the plan 009 arm3/arm3smoke modes in
eval/plan008_metrics.py (main 7e47b5c; identity_check ~l.732, arm3 smoke binding ~l.1010-1030). eval/plans/009.md GOVERNS (SMOKE
l.38-58, IDENTITY l.45-55). Legacy base/smoke/arm2 modes must stay byte-identical (eval/tests/test_plan008_metrics.py unchanged and
passing). Keep all previous fixes (B1-B3 of review 150446, base=arm2 only on SHIP-ELIGIBLE). No task text in outputs. Fail closed.

F1 ONE IDENTITY RECORD PER PUSH.
 - New REQUIRED repeated arg for arm3smoke and arm3: --push-event DIR=EVENT (one per arm-3 run dir, like --transport). EVENT matches
   ^(smoke|main|chunk[1-9][0-9]*)$. arm3smoke: exactly one dir, event must be 'smoke'. arm3: exactly one 'smoke' dir (the dir the 2
   counted smoke rows came from), exactly one 'main', chunk events unique; no two dirs may share an event; any dir without
   --push-event, or a --push-event/--transport naming a dir not in the run-dir list -> argparse/usage error (non-zero exit).
 - Delete the 'chunkN' wildcard and the main_index heuristic. Each dir is checked ONLY against identity records whose 'event' equals
   that dir's EVENT exactly. A record for one push never authorizes another push.
F2 COMPLETE IDENTITY RECORDS + ONE REGISTERED ZIP.
 - A record proof for --bundle counts only if ALL hold: pass, zip_ok, content_ok are True; zip_sha256, manifest_zip_sha256,
   agent_yaml_sha256 are 64-hex strings; zip_sha256 == manifest_zip_sha256; only_in_zip, only_in_dir, byte_mismatch,
   duplicate_members are all present as lists and empty; zip_path is a string ending in '31b-<bundle>.zip'.
 - Across ALL counted pushes (smoke, main, chunks) zip_sha256 must be one single value, AND equal the 'zip sha256: <hex>' in
   bundles/31b/<bundle>/MANIFEST.md (read it; missing/unparseable -> not checked); agent_yaml_sha256 must be one single value and equal
   every header's agent_yaml_sha256 in every dir. TRANSPORT stays separate: header bundle_sha256 == that dir's --transport only; never
   compare TRANSPORT with ZIP/CONTENT. Hash the MANIFEST.md into _schema inputs. Per-dir output lists event, zip_sha256, failure reasons.
 - If a dir has several matching-event records, it passes if the LATEST (last in file) is complete+passing and consistent (report count).
 - Update the fixture in eval/tests/test_plan009_metrics.py (~l.67) to write complete v2 records (and a synthetic MANIFEST via a
   patchable bundles-root, e.g. module constant or env override used only by tests; default = repo bundles/31b).
F3 SMOKE BOUND TO CURRENT CLASSIFIER + CURRENT MECHANICS.
 - arm3smoke output _schema input_shas must already include the classifier path; verify it does (add if missing).
 - arm3 mode: the smoke json's _schema.input_shas must contain the CURRENT counted smoke classifier (the one arm3 uses for the smoke
   rows) with the same sha256 as now; else 'INVALID (smoke evidence not bound)'.
 - arm3 mode RECOMPUTES the full smoke verdict: call arm3smoke_metrics on the smoke dir with the current classifier, identity json,
   bundle, transport and push-event; if its overall != 'PASS' -> 'INVALID (smoke recomputed: <failed criteria>)', regardless of the
   saved smoke json. Keep the saved-json checks too (overall PASS + bound), both must hold.
ACCEPTANCE (offline, synthetic fixtures in eval/tests/test_plan009_metrics.py):
 a) review reproductions fail closed: 33-row fixture with smoke/main/chunk1/chunk2 dirs but identity records only for
    smoke/main/chunk1 -> INVALID (identity mismatch) naming chunk2; partial records lacking zip/manifest hashes -> INVALID;
    complete smoke/main records with different zip_sha256 (same agent.yaml) -> INVALID; zip_sha256 != MANIFEST zip sha -> INVALID;
    passing fixture with first counted smoke row flipped to H in the classifier -> INVALID (smoke recomputed ...) and arm3smoke FAIL;
    smoke json missing the classifier sha -> INVALID (smoke evidence not bound); missing --push-event for a dir, duplicate event,
    two 'main' dirs -> non-zero exit or INVALID.
 b) a fully consistent fixture still yields each of ON-ADOPT, KEEP-OFF, NO-DIFFERENCE, ON-BETTER-VETOED; all earlier fail-closed
    regressions (31 cases) still pass; arm-1 self-pair stays INVALID (7 H rows).
 c) update the arm3 CLI usage docstring/eval/plans docs line that lists required args (add --push-event).
 d) full suite: PYTHONPATH=/home/ubuntu/gemma-local/venv/lib/python3.13/site-packages PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 LITELLM_LOCAL_MODEL_COST_MAP=True /home/ubuntu/gemma-local/pyimg/cpython-3.13-linux-x86_64-gnu/bin/python3 -m pytest eval/tests -q   (report counts; all previously passing tests pass)
