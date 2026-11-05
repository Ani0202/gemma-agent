# Report 009: which sandbox/setup path does the SCORER run? (dec 033 item 3; CPU-only evidence memo)
2026-11-05T21:30Z, Builder. Repo HEAD f07e5b3 plus this cycle's commit.

## 1. Question for the Director
Is S_scorer (per-task sandbox setup on the scorer) ~16 s or ~216 s? My verdict is **most likely ≤ ~16 s (subprocess backend,
setup.py skipped)**, at moderate confidence (~0.6). The main alternative is **~25-30 s** (Docker, air-gapped), at ~0.25. The
**~216 s** world (the one we have been budgeting for) gets ~0.15. Decide: (a) send the forum question in section 6 to Aniket, and (b) how and when the
31B cap may move off the conservative ~1.0-1.2 min.

## 2. Pre-registration
None (evidence memo, no experiment). The only new measurement is a local timing of stock harness functions. Caps are
unchanged and v002 is unchanged (dec 033 item 3).

## 3. What I did
- Read the stock harness (swegemma 0.2.11 in /home/ubuntu/gemma-local/venv), the official pages (re-pulled with
  `kaggle competitions pages list --content`, 21:2xZ), HARNESS_README, Dockerfile.public, setup.py, the starter notebook,
  and the public 0.10 notebook (C3; `kaggle kernels pull`, model/cap lines only).
- Timed the stock subprocess setup sequence locally (new script eval/tools/stock_subprocess_setup_timing.py, which calls
  the same functions in the same order as agent_runner.py:553-584) -> results/stock_subprocess_setup_local.json.

## 4. Evidence
| # | Evidence | Points to | Tag |
|---|---|---|---|
| E1 | swegemma/config.py:98 `sandbox: str = 'docker'  # 'docker' (default) or 'subprocess' (Kaggle/notebooks)` | subprocess on Kaggle | harness code |
| E2 | The official starter (staff) builds `EvalConfig(sandbox='subprocess')` (docs/starter_notebook.ipynb cell 10) | subprocess | official |
| E3 | Subprocess backend: `install_editable_package` and `install_test_dependencies` both `return` at once (container_setup.py:512, :529), so **setup.py never runs**. Test deps come from the host env (venv `system_site_packages=True`, swegemma/sandbox/subprocess.py:334-399) | S small under subprocess | harness code |
| E4 | The harness hardcodes scorer paths `/kaggle/input/datasets/metric/gemma-4-developer-agent-metric-data/sandbox/{setup.py,wheels}` (container_setup.py:41,74) and `/kaggle/input/datasets/metric/swegemma-evaluation` (submission.py:25). Participants report a "Notebook Timeout" failure (thread 752017) | the scorer is a Kaggle notebook, and Kaggle notebooks have no Docker daemon | harness code + participant |
| E5 | Data page: wheels "mounted read-only at /wheels/ inside the sandbox container". Harness-rules page: skill scripts "run securely inside the competition's persistent Docker container". HARNESS_README 4.1: Docker, `network_mode="none"`, 4g/2 CPU | **Docker** (counter-evidence) | official |
| E6 | Local stock subprocess sequence: **2.2 s (rich) / 4.7-4.9 s (fastapi)** per task, 5 tasks; venv start 1.5 s, snapshot extract 0.6-3.2 s, setup.py steps 0.0 s (results/stock_subprocess_setup_local.json; ARM control VM; the local wheels dir is 27 MB, while the scorer's may be bigger: setup_container_wheels copies it once per sandbox) | S_H1 ~ 2-16 s | measured |
| E7 | Kernel v5, our Dockerfile.public emulation on Kaggle: rich_3063 (no fallback) setup 16.6 s; the other 7 are 215.1-215.9 s, of which 200.7 s is ONE networked pip fallback (`pip install --no-deps -e` without `--no-index`, setup.py:208-210) waiting on a timeout (results/setup_py_cause_v5.json, results/kaggle_timing_e4b_v001.json) | the ~200 s exists only if setup.py runs on a host whose network blackholes | measured |
| E8 | Our kernel has replaced install_test_dependencies since its first build (266aa53, 2026-11-05 15:05Z). We have **never** measured the stock starter path on Kaggle | 216 s is our emulation, not an observation of the stock path | repo history |
| E9 | C3 public notebook "[0.10]": **31B**, max_time_minutes 4.5, max_tool_calls 40 (pulled 21:2xZ). If S = 216 s, 120 tasks fit in 720 min only if V + 120 x (3.6 min + mean agent) <= 720. With V ~ 10 min, that needs **mean 31B agent time <= 2.3 min at a 4.5-min cap**. With S = 16 s, any mean <= 4.5 fits | weakly favours S small, **if** 31B at 40 calls typically runs past 2.3 min (unmeasured; plan 006 telemetry will tell) and if the 0.10 was a full scored run (title only) | participant |

Reading: E1-E4 say the scorer is a Kaggle notebook running the stock harness in subprocess mode, so S is ~5-16 s.
E5 is the only official text pointing the other way. It may describe the reference Docker design rather than the scoring
host. Even under Docker (H2), `network_mode="none"` means no route, so the pip fallback should fail fast: pip's
default retries (5, backoff 0.25 s) give roughly 8 s. I could not verify this locally, because unprivileged user
namespaces are blocked here and sudo is off-limits. So S_H2 is ~25-30 s, unverified. The ~216 s world (H3) needs setup.py to run
on a host that blackholes the network, which means a non-stock scorer. Nothing seen supports that. The risk is
asymmetric (no partial credit), which is why I give it 0.15 and not ~0.

## 5. Cap arithmetic (rule (i), F = 7 s per dec 033 item 2; budget per task (660-30)/125 = 302.4 s)
| Hypothesis | S used | 31B cap bound | e4b-v002 (cap 60 s) worst case |
|---|---|---|---|
| H3 ~216 s | 221.6 s (v5 max + margin) | <= 1.23 min | 60+7+221.6 = 288.6 s -> **631 min <= 660** |
| H2 Docker air-gapped | ~26 s (unverified) | <= 4.49 min | 93 s -> 224 min |
| H1 subprocess stock | 16.6 s (v5 measured upper bound) | <= 4.64 min | 83.6 s -> 204 min |
- dec 033 item 2 check: the 5 s floor is real. In swegemma/tools/execution.py:37,
  `effective_remaining = max(5, int(remaining))`, then killpg. 7 s is used above. The post-cap fallback git uses the
  60 s/command default timeout (measured <= 0.52 s), which is an unmeasured tail. The v5 max measured overrun is 1.3 s (fastapi_14258 agent 85.3 s at an 84 s cap).
- dec 033 item 5: **CONFIRMED verbatim** on the official Evaluation page (re-pulled today): "Your agent has a limit of 12
  hours to submit patches for all tasks, inclusive of sandbox setup time, but excluding time for patch validation."
  This is consistent with the harness design: Phase 2 runs in Stage 2 `scripts/metric.py score()`, separate from Stage 1
  `scripts/inference.py` (HARNESS_README:72,597).
- Side note, a fidelity issue for later: under H1, scorer test deps come from the scorer notebook's site-packages, not from
  /wheels via setup.py. Our Dockerfile.public emulation (dec 027) would then mis-model the environment for quality too, not only for time.

## 6. Draft forum question (no task data, no numbers that help competitors much)
> **Scoring sandbox backend: subprocess or Docker?** The starter notebook runs `EvalConfig(sandbox='subprocess')`.
> In swegemma 0.2.11 that backend skips `install_editable_package`/`install_test_dependencies`, so `sandbox/setup.py`
> never runs. The data page and HARNESS_README describe a Docker sandbox with `network_mode="none"`. Could staff confirm
> which backend `scripts/inference.py` uses during scoring, and whether `sandbox/setup.py` runs per task there? This
> changes how much of the 12-hour budget per-task setup consumes. Thanks!

(Deliberately omits our ~200 s fallback finding.)

## 7. Options
A. **Stay at H3 until staff answer.** 31B cap ~1.0-1.2 min. Zero overrun risk from S. 31B gets ~60-70 s, which plan 006
   will likely show is near-useless (the main prize suffers). A staff answer may never come.
B. **Adopt H1/H2 now.** 31B cap ~3.5-4.0 min (margin under the 4.49-min H2 bound). ~4x more agent time for 31B. Roughly 15%
   risk that a submission overruns and fails. In development that costs one slot plus a ~30-40 h queue, and the failure
   itself would be the answer. This is a timing test of the scorer, not of hidden tasks, but whether it is OK under Hard
   rule 3 is your call.
C. **(Recommended) Ask, probe, then step up.** Now: send the forum question; add zero-cost probes to the plan 006 kernel
   (docker binary/socket present? network failure mode refused-vs-blackhole; stock-path S timed on Kaggle per task;
   per-turn 31B timestamps, so E9 can be computed). Then: if staff confirm subprocess, or if the probes plus E9 say S
   small, the first 31B submission goes at the H1/H2-derived cap (~3.5-4.0). With no answer by ~Nov 12, apply B with
   the Director's sign-off. e4b v002 ships unchanged either way.

## 8. Recommendation
Option C. Requests: **ESCALATE** the section-6 forum question to Aniket. **Ruling** on whether a 31B submission at the
H1/H2 cap is acceptable as the eventual test (option B fallback). No GPU or holdout request. Plan 006 addendum
(eval/plans/006.md, "Addendum 2026-11-05") keeps the conservative cap 1.0 unless you rule otherwise before the push.
