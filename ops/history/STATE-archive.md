# STATE.md archive: per-cycle history moved out of ops/STATE.md on 2026-11-05 (dec 017 item 1). Verbatim snapshot as of cycle 50.

# STATE (2026-11-05, cycle 50 / Phase 0) — Builder on Opus (dec 010 local-first, two-strike)
Cycle 50: e4b-timing v1 FAILED at 2 s: default Kaggle GPU image is py3.13, wheelhouse binaries cp312 (pip 'not a supported wheel').
  Starter notebook pins docker_image gcr.io/kaggle-private-byod/python@sha256:37c64f7d... (py3.12.13; from kaggle kernels pull -m).
  Fix 8b200ca: timing_push.sh pins that image + model handle casing 'Other' (starter); kernel prints python version. 11 timing tests pass.
  PUSHED v2 (same 8 ids, budget 10800). Job e4b-timing-wait2 -> runs/e4b-timing (v1 artifacts moved to runs/e4b-timing-v1-failed).
  On finish: same steps as cycle 49 below. Note for local env: scorer host python is 3.12 (starter), sandbox image per Dockerfile.public.
  Generic lesson: any future Kaggle GPU kernel (31B timing, eval) must pin the starter docker_image.
Cycle 49: timing-kernel REVIEWED (APIs verified vs swegemma 0.2.11/adk_eval_core source: context.llm_calls_used, SessionTrace.to_dict(format='legacy'),
  TaskResult pydantic, context kwarg). Raw traces (timestamps) + agent.patch + result.json saved per task to /kaggle/working/runs/<iid>/ (dec 016 OK).
  Builder fixes: None-usage guard; row-build/trace-parse exceptions can't kill the run. Merged to main (conflict: kept main gold_calibration, no diag). 382 tests pass.
  PUSHED aniket0202/gemma-e4b-timing v1: bundles/e4b/v000, 8 dev ids eval/plans/001-timing-ids.txt (Random(1): 6 rich + 2 fastapi), budget 10800s, -t 12600.
  Job e4b-timing-wait -> runs/e4b-timing. On finish: python3 eval/kaggle/timing_summary.py runs/e4b-timing/timing.jsonl results/kaggle_timing_e4b_v000.json;
  compute test-run share post-hoc from raw traces (B3: FIFO-per-name is wrong for batched calls); check header mcp_import_ok; fill ops/budget/kaggle.md actual hours.
  Model handle assumption google/gemma-4/other/<model>/2 (starter path); if kernel fails on model mount, fix metadata and re-push.
Cycle 48 (dec 016 approve-with-changes): Kaggle E4B timing (plan 001) DECOUPLED from eval-runner-fix + gold rerun.
  On codex-timing-kernel finish: review -> PUSH IMMEDIATELY (don't wait for eval-runner-fix). If eval/tool_timing.py (B3) not merged
  by push time, ship with RAW per-event traces (timestamps) saved to /kaggle/working/runs/ and compute test-run share post-hoc.
  Gate quantity = p90 per-task wall (plan 001); share is secondary. Verify kernel actually saves raw traces (spec says 'may'); add if absent.
  N2 (verification_timeout_seconds forwarded) already in eval-runner-fix spec line 8 — confirm in review; local/scorer configs must match.
  If gold rerun changes pass set: short report, keep going with timing + report 002 in parallel (can't change first-sub candidate).
Cycle 47: review-eval-runner DONE (ops/codex/review-20261105T145013.md): 5 BLOCKING. Merged codex/eval-runner -> main (8add1a5; conflict in
  gold_calibration.py resolved keeping probe-log + by-name bindings; 203 pass/170 skip under pyimg python). Numbers NOT reliable until fix merged.
  BLOCKING: B1 agent run_command can read host inventory (gold) -> bwrap isolation (verified bwrap works here; userns via apparmor OK for bwrap only);
  B2 graph/embeddings dirs not passed to SwegemmaContext; B3 tool_seconds wrong for batched calls (merged timestamps) -> exec-boundary timing
  eval/tool_timing.py (timing kernel should reuse it); B4 resume ignores git SHA/inventory/env; B5 runner removes _host_env.pth but gold
  calibration did NOT -> gold clean list computed with harness-venv pkgs visible in sandbox.
  Launched codex-build eval-runner-fix (effort high; spec ops/codex/build-eval-runner-fix.spec) covering B1-B5 + N1-N3.
  On finish: review diff; run real-bwrap tests + stub E2E myself; codex-review; merge. Then RERUN gold-local + gold-null with shared env (B5).
  Pre-registered rule (journaled): if gold pass set + null-control identical to v2 -> splits v2 stand; any change -> report to Director (no silent re-split).
Cycle 46 (dec 015 approve): critical path = review-eval-runner -> merge -> Kaggle E4B timing (plan 001) -> report 002 w/ first-sub candidate.
  Launched codex-build timing-kernel (spec ops/codex/build-timing-kernel.spec): eval/kaggle/agent_timing.py (starter-faithful vLLM+EvalConfig,
  embedded bundle b64, seq tasks, timing.jsonl w/ tool_seconds + test-run share, time-box), timing_push.sh (--accelerator NvidiaL4X4, -t, --dry-run),
  timing_summary.py (plan-001 rule). Review on finish; then pick ~6 dev ids (4 rich, 2 fastapi), push, log quota in ops/budget/kaggle.md.
  ask-shadowing done: codex agrees shadowing = harness property. Plan 002 pre-registered (import-origin check; candidate, not scheduled).
  DEFERRED (dec 015 item 3): one-page scoping note for supplementary public dev set (eval/plans/) ONLY after first sub queued; no downloads.
Cycle 45 (dec 014): shadowing RESOLVED = scorer property (container_setup.py:266 strips RECORD -> setup.py editable install fails
  uninstall-no-record-file, reproduced in scratch venv -> src-layout requests/httpx import wheel copy). Rule 2b: requests/httpx
  dropped (unmeasurable locally). null_pass excluded: fastapi_14873, requests_7309/7315/7427.
  SPLITS v2 FROZEN: clean 48 (rich 39, fastapi 9), dev 33, holdout 15; holdout uses=0. Hashes: eval/splits/MANIFEST.json + journal.
  results/gold_calibration_per_task.jsonl v2, gold_failure_causes.jsonl (81 rows), gold_calibration_summary.json = manifest copy.
  docs/GOLD_CALIBRATION.md v2 section. Scripts: tag_gold_failures.py (GOLD_NULL_RESULTS, SHADOWED_REPOS), make_splits.py
  (EXCLUDE_FILE, DROP_REPOS). ask-shadowing (codex) still running: cross-check only; decision already made, do not reopen.
  Report 002 MUST state: LORO with 2 repos is weak = known limitation for ship decision (dec 014 item 3).
  Agent-prompt idea (generic): verify pkg.__file__ under /workspace before trusting repro.
Cycle 44: (a) codex eval-runner built (branch codex/eval-runner, worktree gemma-wt/codex-eval-runner, commits 7c9a7ad + my bcdbfbd adding tool_seconds {tool:{n,total,max}} from trace call->response timestamps = plan 001 test-run share). 371 unit pass. Stub E2E initially 0 LLM calls: litellm 1.108 imports `mcp` unconditionally when tools passed; mcp not in harness venv -> installed mcp 2.3.0 into /home/ubuntu/gemma-local/venv (uv, user-space). E2E now PASS (3 LLM calls, patch captured, verif ran). CHECK on Kaggle eval kernel: `import mcp` works in scorer-like env. Job review-eval-runner (codex-review) running; merge only after review.
  (b) gold-null DONE -> BOTH pre-registered emulation triggers fired: null-patch PASS on 4/52 (requests_7427/7315/7309 = all 3 requests gold-passers; fastapi_14873) and probes show requests+httpx import from sandbox venv site-packages (wheel), fastapi+rich from workspace. results/gold_null_control.jsonl, results/gold_import_probe.jsonl. Splits v2 BLOCKED (dec 011 item 4). Job ask-shadowing (codex-ask): does official docker path also shadow (scorer property) or is it our emulation bug; minimal faithful fix; why fastapi_14873 null-passes.
  If our bug: fix emulation, rerun gold-local + gold-null, then splits v2. If scorer property: requests/httpx tasks unmeasurable -> exclude (tag scorer_fail=verified, cause wheel_shadowing), clean set ~ rich 39 + fastapi 9 -> tell Director (LORO/generalization impact).
Cycle 43 (dec 013, docs only): RULES_FINDINGS.md + COMPETITION.md updated with M1–M7 (tags official/host-forum/participant). RESOLVED: pending cap = one pending at a time (747519; ~1 scored sub per 1.5–2 days, last reliable sub ~Nov 27–28); E4B scores (intermittent 'incorrect format' 752128 OPEN). Plan 001 addendum: measure per-task test-run time share (mean/p90) + test runs per task; p90 rule unchanged. TODO when reviewing codex eval-runner: ensure per-tool-call wall time for test runs is logged so the share can be computed.
Cycle 42: gold-local DONE 52 pass/77 fail (same failing set as Kaggle gold-full). Before freezing v2, found wheelhouse ships httpx/rich/requests/fastapi wheels themselves -> risk that injected wheel shadows workspace source (httpx_3672 'no attribute Stream'). Added to gold_calibration.py: GOLD_NULL_PATCH (no-source-change control), GOLD_IDS_FILE, GOLD_PROBE_LOG (prints imported pkg __file__). Job gold-null: null control on 52 passers + gold probe on httpx_3672/rich_3486/requests_6644/fastapi_15785 -> runs/gold-null, runs/gold-probe. Early: fastapi imports from workspace; null patch fails (good).
  Prepared: eval/tag_gold_failures.py (cause + scorer_fail verified/assumed/unknown; preview: 42 verified missing-wheel, 30 assumed [starlette 21, pygments 7, py-ver 1, harness node 1], 5 unexplained [httpx 1, fastapi 2, requests 2]); make_splits.py -> schema v2 (same seed => same assignment if clean set unchanged).
  On gold-null done: if all 52 null FAIL and probes show workspace paths -> run tag_gold_failures -> results/gold_failure_causes.jsonl (v2), make_splits runs/gold-local -> splits v2 FROZEN, copy gold-local per-task to results/gold_calibration_per_task.jsonl (v2 header; dec 012 paper cites it), null-control results file, journal hashes, FYI Director per-repo counts. If any null PASS or probe shows site-packages copy -> emulation bug, fix + rerun gold-local (dec 011 item 4).
Cycle 40: session restart; gold-local 78/129 running. Launched codex-build eval-runner (spec ops/codex/build-eval-runner.spec: eval/run_agent_eval.py + eval/stub_openai.py + tests; all-bindings patch, gold self-check, resumable schema-headed results). Review on finish.
Cycle 39 (dec 011): RECONCILED thread 751487 vs our emulation -> explanation (b): their 127/129 env adds non-wheelhouse test pkgs (httpbin, inline_snapshot, dirty_equals) + per-task period-correct pins (Pygments, starlette); official harness picks highest version, no resolver (source-verified both dedupe fns). Not our bug. Exclusions tagged scorer_fail=assumed. Written: docs/GOLD_CALIBRATION.md (reconciliation), docs/EVAL_RUNNER_SPEC.md (env requirement, by-name patching of install_test_dependencies in 4 modules, startup gold self-check).
  Next on gold-local done: build clean list + splits v2 (dec 011 item 3, no approval needed), results/gold_failure_causes.jsonl with cause tag + scorer_fail verified/assumed, freeze, journal hashes, FYI Director per-repo counts. No more Kaggle gold kernels (item 5); gold-diag4 cross-check only.
Cycle 37: LOCAL gold repro built: /home/ubuntu/gemma-local (outside repo): pyimg/ = uv CPython 3.13.18 mirroring Dockerfile.public (pytest, pytest-timeout==2.1.0, typer, build backends, imp.py; EXTERNALLY-MANAGED removed); venv/ = harness (swegemma 0.2.11, adk_eval_core, adk_submission 0.2.13 --no-deps + google-adk, litellm) built on pyimg. ~10 s/task.
  ROOT CAUSE (source read): SubprocessManager venvs use system_site_packages=True, so sandbox inherits HOST python. On Kaggle that is the polluted system python (langsmith plugin etc.). Docker path (_ensure_container_site_packages) unpacks EVERY deduped highest-version py313 wheel <20MB (skips pytest/pluggy/pytest_httpbin...) into site-packages, no resolver, then setup.py --fast-path. patch_subprocess_deps now replicates exactly that.
  Finding: with faithful emulation, starlette-1.6.0 fastapi failures (on_startup) and requests httpbin recursion PERSIST, clean tasks pass => these fail in the public docker env too; legit exclusions. ONLY_IDS cleared; full local gold job gold-local -> runs/gold-local (129 tasks, conc 2, ~15-25 min).
  Caveat for agent eval later: agent_runner/evaluate import install_test_dependencies by name (not patched by our cs/vf monkeypatch) and host python must be image-clean; handle when building eval runner.
  gold-diag4-wait (Kaggle v8) still running; now redundant — results only as cross-check.
Best bundles: none validated. v000 packed + static PASS + codex static OK (repo SHA a12f0b7):
 31b dist/31b-v000.zip sha256=4a23e14a1aae077161cb137b5ff72afe91ee2acb1d1fdbaf2e322abb6efae161
 e4b dist/e4b-v000.zip sha256=cc647bfb28bc6d2db0e3ec816df084f23a91230786d8fea177e2d63d2a6940e2
Remaining codex BLOCKING: runtime budget/timing unverified (needs concurrency-1 timing on L4x4/Kaggle).
Env: x86_64 VM. GCP project gemma-agent-839566, spend $0. Kaggle quota: timing v1 failed (~0.1 quota-h est), v2 running (est ≤3.2 quota-h). Owner GPU policy (dec 001): Kaggle first.
GCP quota (dec 003): only l4x1 spot + cpu8 usable; multi-GPU -> Kaggle.
Rules (dec 004-002-001, 013): docs/RULES_FINDINGS.md; no repo overlap with hidden set; LORO mandatory for ship decisions; no partial credit on timeout (participant evidence 752017); one pending submission at a time.
Open: (1) E2 resolved (dec 005): paper session owns paper/, do not edit; keep results/ files self-describing (schema + header line). (2) Director reminder due 2026-11-06T23:02Z: GCP quota re-request line to Aniket; keep until decision marks done. (3) Hosted-LLM-API data question OPEN; no new third-party services.
Dec 012 FYI: paper §4.1 cites only the committed gold-local v2 results file -> commit it promptly when gold-local finishes.
Paper evidence (dec 007, due Nov 9 23:59Z, no extra compute): commit schema-headed results/ files for (a) gold calibration per-task outcomes+exclusion causes, (b) timing per task from Kaggle E4B smoke (31B if run), (c) failure taxonomy via trace-analyst once. Not yet produced; flag here if any won't exist by Nov 9.


Running jobs: codex-eval-runner-fix (critical path), e4b-timing-wait2 (Kaggle v2), gold-diag4-wait (cross-check, redundant).
Next 3 (dec 016: 1 and 2 in PARALLEL): (1) on e4b-timing-wait2: timing_summary + post-hoc test-run share -> results/, plan-001 rule;
  (2) review+merge eval-runner-fix (real-bwrap tests, N2 check), rerun gold-local+gold-null shared env, compare vs v2 (change => short report);
  (3) report 002 with first-submission candidate + LORO caveat.
