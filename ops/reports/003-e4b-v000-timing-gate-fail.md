# Report 003: E4B v000 fails the plan-001 runtime gate. Harness sandbox setup (~3.5 min/task) is outside the time cap.

## 1. Question for the Director
(a) Do you approve the corrected timing formula (validation excluded, uncapped setup included), plus an e4b-v001 that differs only in `max_time_minutes` 5 -> 1.4, then a Kaggle re-time? (b) The OOM incident: what local-job policy applies before I relaunch anything, including the EV-1 gold/null job from dec 019?

## 2. Pre-registration (plan 001, eval/plans/001-*.md, written 2026-11-04 before any run)
Pass iff p90*125 + startup <= 660 min AND cap_minutes*125+30 <= 660. Else lower caps in eval_config.yaml, repack, re-measure. No pass-rate claims (n too small). Any test edit or empty diff => fix before submit.

## 3. What I did
- Fetched Kaggle kernel aniket0202/gemma-e4b-timing v3 output (COMPLETE): E4B v000, 8 dev ids, concurrency 1, repo 178e273.
- **Dec 018 check: the guard saw 4 x "NVIDIA L4"** (gpu_count 4) and mcp_import_ok=true, so this is the right hardware.
- Ran `eval/kaggle/timing_summary.py` -> results/kaggle_timing_e4b_v000.json.
- Derived per-task setup time: agent wall minus the harness's own budget clock (the evaluator panel's "XmYs"). That clock starts after sandbox setup. Output: results/kaggle_timing_e4b_v000_setup.json.
- Code reading of swegemma (`harness/container_setup.py`): setup is the competition's own wheel staging and site-packages injection (`_ensure_container_site_packages`, `_build_unpacked_wheels_tar`) plus `sandbox/setup.py` from competition data. Bundles can't control it.

## 4. Results (n=8 tasks, 1 sample each; all files in results/)
| quantity | value | file |
|---|---|---|
| vLLM startup | 5.39 min | kaggle_timing_e4b_v000.json |
| setup per task (outside cap) | 208-212 s (mean 209.5); flat across rich and fastapi | kaggle_timing_e4b_v000_setup.json |
| agent budget-clock time | 25-184 s, p90 144 s (cap 300 s never hit) | same |
| agent wall incl. setup, p90 | 353.9 s | same |
| verification (excluded from 12 h per evaluation page) | ~410 s flat | kaggle_timing_e4b_v000.json |
| projection, plan-001 as coded (total incl. verification) | 1599 min: FAIL | kaggle_timing_e4b_v000.json |
| projection, corrected (agent wall p90 x125 + startup) | **742.7 min: FAIL** | _setup.json |
| cap worst case, constitution formula (cap only) | 655: nominal pass, but it ignores setup | _setup.json |
| cap worst case incl. setup, (5+3.53)x125+30 | **1097 min: FAIL** | _setup.json |
| max cap_minutes for 660, incl. setup | **1.51 min** | _setup.json |
| resolved | 1/8 (Wilson 95% 2.2-47.1%). No claim | kaggle_timing_e4b_v000.json |
| empty patch / test edits / stray files | 0 / 0 / 0 | same |

Failures, reported as prominently as the timing:
- rich_3043 patched only `.pre-commit-config.yaml` (no source change).
- fastapi_15800 produced a 190 KB diff (probably a whole-file rewrite).
- rich_3938 hit a harness "Error during sandbox execution" with no submit_patch, but a diff was still collected.
- Both fastapi tasks exited 2. That looks like the collection-time ImportError class from dec 019 item 4.
- Completion throughput was only 7-36 tok/s per agent-second. The prompts run 45k-278k tokens per task, so time goes to prefill and turns.

Caveats:
- n=8 from 2 public repos. The flat ~210 s setup suggests a cost that doesn't depend on the repo (the base wheel tar of all wheels under 16 MB). Hidden repos with large deps may add more on top.
- I haven't yet verified whether the base-tar cache is meant to persist across tasks. If it is, the scorer could be faster than our kernel.
- The plan-001 formula and the constitution's `cap*125+30` both assume the cap covers the whole task. It doesn't. Fixing that changes the eval protocol, hence this question.

## OOM incident (16:45Z), my read
gold-rerun-b5's null phase had reached 39/52. Its last two results were exit 124 timeouts on null-patch runs (rich_3480, rich_3772), and then the VM stalled. Most likely cause: a test that runs away on unpatched code, with no per-sandbox memory limit locally (the scorer caps sandboxes at 4 GiB). Proposed fix, before any relaunch: run local sandboxes under `prlimit --as=4GiB` (scorer-faithful), cap per-test time, and rely on bin/job's new 5G job cap. I've launched no local jobs since the reboot. Both dead jobs are marked failed (255).

## 5. Options
A. **e4b-v001 = v000 with max_time_minutes 1.4** (worst case (1.4+3.53)x125+30 = 646 min), plus a Kaggle re-time on 8 new dev ids. To keep quota low, the re-time skips verification (~1.2 L4x4 h, about 2.4 quota-h). Safe, but the cap truncates 5 of 8 observed runs (agent clock over 84 s), so quality drops unless truncated runs still yield a diff. rich_3938 suggests they do; I'd verify it.
B. **Root-cause setup first** (codex-ask, code reading only, about 20 min): is the 210 s intrinsic, or a cache miss in our kernel? If it's a cache miss, the cap could stay near 4 min. Risk: a wrong conclusion leads to a timeout, and a timeout scores zero.
C. **A now, B in parallel.** Ship-safe v001 as the first-submission candidate. Raise the cap later only with evidence.
Separately, either way: cut prompt tokens per turn (tool-output trimming), which is the main lever for fitting work into ~84 s.

## 6. Recommendation
C. Adopt the corrected rule: worst case = (cap_minutes + measured max setup x1.0) x 125 + 30 <= 660, validation excluded. Re-time within the weekly plan (≤10 L4x4 h; 1.74 used). The same correction applies to 31B: its re-time needs the same setup measurement, and its per-turn cost is higher.
Requests: approval of the formula change; a local-job policy for the OOM incident (proposed: prlimit 4 GiB per sandbox, then rerun the EV-1 gold+null job from dec 019 item 2). No SUBMIT and no GPU spend requested.
