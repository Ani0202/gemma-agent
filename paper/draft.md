<!-- DRAFT v0.4, 2026-11-05 (forum refs titled; §4.1 strict-isolation rerun + EV-1; §5 rule written, measurements PENDING). Sections 1-5 and 8. [[PENDING: file]] marks text that needs a results file; cut if absent by Nov 9.
     Word budget: body <= 2,800. Cite forum statements as (handle, thread id); no Competition Data. -->

# Measuring Small-Model Software Agents Under a Hard Wall-Clock Budget
### Calibration, paired statistics and the timing cliff for Gemma 4 agents on repository-level bug fixing

## Abstract
Small open models that fit on a single accelerator are attractive for offline coding assistance, but progress on them is hard to
measure. Benchmark environments can make a large share of tasks unsolvable even with the reference patch, public scores for
identical submissions vary by several tasks, and a fixed total wall-clock budget turns slow tasks into a cliff rather than a
smooth cost. We describe an evaluation protocol for Gemma 4 (E4B and 31B, QAT w4a16) agents on repository-level bug fixing under a 12-hour scorer limit.
It has four parts: gold-patch calibration of the task list, repository-stratified frozen splits, pre-registered paired comparisons with exact tests, and a worst-case timing rule
derived from measured per-task wall time. We report [[PENDING: results/gold_calibration*, results/timing*, results/failure_taxonomy*]]
and release the harness, statistics code and bundle sources under Apache-2.0. Our contribution is a reproducible measurement recipe, not a new state of the art.

## 1. Introduction
Agentic software engineering is dominated by large hosted models. The Gemma 4 Developer Agent competition asks a different question: how well can an
agent built on a small open model, running offline on four 24 GB GPUs, resolve real issues in unseen repositories? An agent is a declarative bundle
(prompts, sub-agents, skills, optional LoRA adapters) run inside a fixed harness; a hidden set of about 120 tasks is run sequentially, and a task counts only if the hidden tests pass.

Three properties of this setting make naive iteration unreliable.
1. *The environment can be wrong.* In community reports, gold patches pass on only 52 of 129 public tasks in a plain notebook but 127 in a calibrated
   scorer-like sandbox (Zbigniew Kirchner, thread 751487), and 43 with the public kit (aefinityaiinc, thread 747248), mainly from missing test dependencies. A local "failure" may say nothing about the agent.
2. *Scores are noisy.* A byte-identical submission scored 0.18 and 0.01 on two public runs (fan yunsheng, thread 750521), another team reports that 1 task equals 0.017 of the public score with a per-run standard deviation of about 2 tasks (Adam Johnson, thread 753524). Differences of a few tasks cannot rank configurations.
3. *Time is a cliff.* All tasks share a 12-hour limit including model startup and sandbox setup. Staff noted that simply scoring unfinished tasks as zero could make public and private scores inconsistent and that they were considering alternatives (Ryan Holbrook, thread 749597); One participant reports that a configuration differing from a scoring agent only by an extra test re-run step ended in a notebook timeout after about 12 hours with no partial score, although the step had cost only about 5% median time per task locally on the public repositories (Nir Aberman, thread 752017). We therefore treat overrun as a risk to be ruled out by construction, not estimated, and we measure the share of task time spent running tests.

**Contributions.** (i) A four-step protocol that addresses these three problems and is cheap enough for a team with a few GPU-hours per week. (ii) A worst-case timing rule linking per-task caps to the scorer budget. (iii) [[PENDING: results/*]] measurements with this protocol on two model sizes, including a failure taxonomy of agent traces and the effect of harness fixes. (iv) Open code for all of it.
We state clearly what is measured and what is only planned; the limitations section lists what we could not run.

## 2. Setting
**Task and harness.** Each task provides a repository snapshot, an issue statement and hidden tests. The agent has file read/edit/write, a shell with 5,000-character output and 300 s command caps, a submit tool, and code-graph tools (neighbours, similar code, subgraph) <!-- src: docs/HARNESS_NOTES.md -->.
Grading applies the agent's source diff in a fresh container, resets test files, applies the hidden test patch and requires pytest exit 0. Edits to tests are discarded, so protocol hygiene (scratch files outside the repository, no test edits) is part of correctness.
**Scorer constraints.** Four L4 GPUs, no internet, 32k context, 2 vCPU and 4 GiB per sandbox, a single model for all agents in a bundle, and about 120 hidden tasks run sequentially in 12 hours.
Staff stated that no repository of the public training tasks appears in the hidden set (Ryan Holbrook, thread 747248), so generalization to unseen repositories is the goal.
**Models.** We use the permitted QAT w4a16 Gemma 4 variants: E4B (one L4 suffices for development) and 31B (tensor parallel over four L4).

## 3. Related work
*Agentic SWE benchmarks.* SWE-bench [1] established issue-to-patch evaluation against repository tests. Agent scaffolds such as SWE-agent [2] and OpenHands [3] and the fixed localize-repair-validate pipeline of Agentless [4] were mostly reported with large hosted models. SWE-Gym [5] trains open-weight agents on their own trajectories, which is the route we keep for adapters. None of these work under a fixed total wall-clock budget for the whole task set.
*Evaluation reliability.* Benchmark quality is a known problem. SWE-bench Verified [6] came from human screening that flagged many samples for underspecified issues or overly strict tests. SWE-Bench+ [7] reports solution leakage and weak tests among passing patches, and PatchDiff [8] finds plausible but incorrect patches that the benchmark tests accept. Miller [9] argues for standard errors and paired, question-level tests in LLM evaluation. We apply the same caution one step earlier, to whether the environment can pass the reference patch at all, and add a hard time constraint.
*Competition community work.* Public notebooks and posts for this competition report a scorer-like sandbox (thread 751487), leaderboard noise simulations (thread 753524) and agent scaffolds with a locate/edit/check/submit loop and code graphs <!-- src: docs/PRIOR_ART.md (secondary summaries; re-verify licences and cite handles before use) -->. One public report finds that a naive SFT adapter lowered score relative to its base agent; we use this as a caution rather than a result [[CITE with handle and thread after verification]].
We build on these observations by combining them in one pre-registered protocol and measuring the quantities (calibration funnel, discordant pairs, wall-time quantiles) that decisions depend on.

## 4. Evaluation protocol
**4.1 Gold-patch calibration.** For every public task we apply the reference patch and hidden tests in our sandbox and keep only tasks that pass; failures are classified by cause (missing dependency, test shadowing by a bundled wheel, flaky). This yields the *clean list*, identified by a sha256 of sorted task ids.
Our first pass, a subprocess sandbox on Kaggle CPU, kept 52 of 129 tasks. Almost all failures came from the environment, mainly test packages missing from the offline wheel set and an unrelated pytest plugin, not from the tasks <!-- src: results/gold_calibration_summary.json; results/gold_failure_causes.jsonl; ops/journal.md 2026-11-05T02:57Z, 07:33Z -->. We then rebuilt the scorer's dependency installation locally, which cut a calibration round from hours to seconds per task <!-- src: ops/journal.md 2026-11-05T14:15Z; docs/GOLD_CALIBRATION.md -->. The 127/129 community figure comes from an environment that adds test packages not in the competition wheel set and pins period-correct versions (thread 751487). The published harness installs the highest available version of each package without a resolver, so we tag tasks that fail for these reasons as assumed scorer failures, not agent failures <!-- src: docs/GOLD_CALIBRATION.md 'Reconciliation' -->. This emulation first passed the same 52 tasks. A re-run with stricter sandbox isolation then showed that one of those passes depended on a leak: the sandbox Python could import packages from our harness's own environment. With the leak removed, gold passes fell from 52 to 43, all 9 losses in fastapi. Test collection failed because the bundled pydantic needs `typing_inspection`, and the offline wheel set does not include it <!-- src: results/gold_rerun_b5_compare.json (old_pass 52, new_pass 43, old_only 9 fastapi, new_only 0); ops/reports/002 -->. The hidden set shares no repositories with the public one, so we keep the frozen splits and add that single package to the evaluation sandbox for all tasks, as a logged, evaluation-only deviation (EV-1). It is never part of a submitted bundle. EV-1 is accepted only if gold passes all clean tasks and the empty patch passes none [[PENDING: results/gold_calibration_ev1.jsonl]] <!-- src: ops/decisions/019 items 1-2 -->. The lesson generalizes: isolating the harness from the task environment is part of calibration, and a leak can make an unsolvable task look solvable. Of the 77 first-pass gold failures, 34 lack test packages (inline_snapshot, dirty_equals), 21 need an older Starlette, 7 differ in Pygments output, 8 lack an httpbin fixture, 2 differ in Python version or harness setup and 5 are unexplained <!-- src: results/gold_failure_causes.jsonl (v2, sha256 c0958fc5); results/gold_calibration_per_task.jsonl exclusion_cause -->. Another participant observed that some tasks pass with an *empty* patch because a bundled wheel shadows the repository (aefinityaiinc, thread 747248). Our empty-patch control on the 52 gold passers confirmed this for 4 tasks (3 of 3 passing requests tasks, 1 fastapi), and an import probe showed requests and httpx loading from the installed wheel rather than the workspace <!-- src: results/gold_null_control.jsonl; results/gold_import_probe.jsonl -->. We exclude every empty-patch pass, since such a test cannot tell a fix from no fix, and drop requests and httpx as unmeasurable locally <!-- src: ops/decisions/014; ops/journal.md 2026-11-05T14:54Z -->. Table 1 gives the funnel. Community figures differ (127/129, thread 751487; 43, thread 747248) because environments differ.

*Table 1. Gold-patch calibration funnel (129 public tasks).*

| Repository | Tasks | Gold pass | Gold pass, strict isolation | Empty-patch pass | Clean | Holdout |
|---|---|---|---|---|---|---|
| Textualize/rich | 48 | 39 | 39 | 0 | 39 | 12 |
| fastapi/fastapi | 67 | 10 | 1 | 1 | 9 (EV-1) | 3 |
| psf/requests | 13 | 3 | 3 | 3 | 0 (dropped) | 0 |
| encode/httpx | 1 | 0 | 0 | 0 | 0 (dropped) | 0 |
| **Total** | 129 | 52 | 43 | 4 | 48 | 15 |

*"Strict isolation" removes the harness-environment leak. Clean fastapi tasks are evaluated under deviation EV-1 (§4.1).*
<!-- src: results/gold_calibration_summary.json (schema gold-calibration-splits-v2); results/gold_calibration_per_task.jsonl; results/gold_null_control.jsonl; strict column: results/gold_rerun_b5_compare.json new_pass_by_repo (httpx absent = 0; new_only empty). [[PENDING: results/gold_calibration_ev1.jsonl; if any clean task fails gold or passes null under EV-1, splits become v2.1 and Clean/Holdout change (dec 019 item 2)]] -->

**4.2 Splits.** Clean tasks are stratified by repository into *dev* (all tuning) and *holdout* (ship decisions only, each use counted and logged). Splits are frozen and hashed before any agent run: 33 dev and 15 holdout tasks, with holdout uses logged (zero so far) <!-- src: eval/splits/MANIFEST.json v2; results/gold_calibration_summary.json sha256 clean=637228f6 dev=b8d07c85 holdout=e6e14acd; ops/journal.md 2026-11-05T14:54:28Z [[PENDING: update holdout-use count at final]] -->. Because no public repository is in the hidden set, every ship decision also requires a leave-one-repository-out (LORO) check, repo-specific prompt content is rejected, and repositories are weighted equally. With only two measurable repositories, LORO is a weak check; we report it but do not lean on it <!-- src: ops/decisions/014 item 3 -->.
**4.3 Paired comparisons.** Two bundles are compared on the same tasks and seeds with k >= 2 samples per task. We report pass rate with Wilson 95% intervals, the numbers of discordant tasks (A-only, B-only) and an exact two-sided sign test on discordant tasks. Motivated by thread 750521 and 753524, a change of +-3 tasks on about 30 is treated as noise. Same-bundle repeat runs estimate the noise floor [[PENDING: results/ repeat-run file, else describe as planned]].
**4.4 Pre-registration.** Each experiment has a plan file with hypothesis, measurements and decision rule written before the run <!-- src: eval/plans/001.md (example) -->, so that analysis cannot drift toward favourable outcomes. Plans, code and results carry git SHAs.
**4.5 Statistics code.** Wilson, sign test and bootstrap utilities are in `eval/`, with unit tests, and were reviewed by an independent coding assistant before use [[PENDING: eval/ stats module path]].

## 5. The timing cliff
**5.1 A worst-case rule.** An overrun forfeits the whole run, so we bound the worst case instead of the expected case. Every bundle sets a hard per-task wall-clock cap *c* (minutes) in its evaluation config and must satisfy
*c* × 125 + 30 ≤ 660.
Here 125 is the roughly 120 hidden tasks plus a margin, 30 minutes covers model-server startup and sandbox setup, and 660 minutes leaves one hour of the 12-hour limit unused as a safety margin. Our baseline bundles use *c* = 5, so the worst case is 655 minutes. They also cap tool calls (40), turns (50) and each command (60 s) <!-- src: bundles/e4b/v000/eval_config.yaml (max_time_minutes 5, max_tool_calls 40, max_turns 50, timeout_seconds 60); bundles/31b/v000/eval_config.yaml identical -->. The rule assumes nothing about the hidden repositories. It costs score only if a solvable task needs more than *c* minutes.
**5.2 Measured wall time.** The cap bounds the worst case, but the typical case decides whether the cap is too tight. Before any submission, a pre-registered gate measures model startup, per-task sandbox setup and per-task wall time at concurrency 1 on four L4 GPUs. The gate passes only if p90 × 125 + startup ≤ 660 minutes as well <!-- src: eval/plans/001.md 'Decision rule' -->. Following the report that test re-runs drove a timeout on hidden repositories (thread 752017), we also log the share of task time spent running tests and the number of test runs per task <!-- src: eval/plans/001.md (amendment, thread 752017) -->. [[PENDING: results/ e4b timing file from runs/e4b-timing: startup, setup, per-task p50/p90, test-time share; Table 2]]
**5.3 Measure on the right hardware.** One of our early timing runs asked for an accelerator shape the platform did not recognize. The platform silently fell back to different GPUs instead of failing, and the run crashed in model loading <!-- src: ops/journal.md 2026-11-05T15:18Z; runs/e4b-timing-v2-failed/ -->. Our timing kernel now checks the GPU count and type and aborts before measuring anything if they don't match <!-- src: ops/journal.md 2026-11-05T15:20Z; eval/kaggle/agent_timing.py -->. Timing numbers from the wrong hardware are worse than none, because they look valid.

<!-- Sections 6 (failure modes) and 7 (E4B vs 31B, conditional on results by Nov 9) are written after results exist. -->

## 8. Limitations and threats to validity
(i) Public tasks are few and dev/holdout/LORO subsets are small, so most intervals are wide and we do not claim small effects. (ii) We have no access to the hidden set and make no prediction about it. (iii) Calibration reflects our sandbox, which may differ from the official scorer (a community member notes it is unclear whether scoring uses a Docker or subprocess sandbox, thread 751487). (iv) Throughput and wall time measured on Kaggle L4x4 may differ from the scorer. (v) Compute was limited to a weekly Kaggle quota and a small cloud budget, so some planned experiments (e.g. adapter training) are not reported. (vi) The workflow used AI agents to propose and select experiments, which can introduce selection effects; we mitigate with pre-registration and report all runs [[PENDING: confirm no runs dropped]].

## Disclosure (draft)
The experiments and this text were produced by an automated engineering workflow built on Claude (Anthropic) and Codex (OpenAI) coding assistants. These assistants wrote code, analysis scripts and drafts, and AI agents also proposed and selected experiments, under goals, constraints and approvals set by the author. No trajectories, patches or reasoning from proprietary models were used as training targets for Gemma weights. Reported numbers come from the released result files. The author reviewed the paper and takes responsibility for its content. <!-- Aniket to confirm wording at sign-off -->

## References
<!-- verified 2026-11-05 via web search (arXiv abstract pages) -->
[1] C. E. Jimenez, J. Yang, A. Wettig, S. Yao, K. Pei, O. Press, K. Narasimhan. SWE-bench: Can Language Models Resolve Real-World GitHub Issues? ICLR 2024. arXiv:2310.06770.
[2] J. Yang, C. E. Jimenez, A. Wettig, K. Lieret, S. Yao, K. Narasimhan, O. Press. SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering. NeurIPS 2024. arXiv:2405.15793.
[3] X. Wang et al. OpenHands: An Open Platform for AI Software Developers as Generalist Agents. ICLR 2025. arXiv:2407.16741.
[4] C. S. Xia, Y. Deng, S. Dunn, L. Zhang. Agentless: Demystifying LLM-based Software Engineering Agents. arXiv:2407.01489 (2024); Proc. ACM Softw. Eng. (FSE) 2025.
[5] J. Pan et al. Training Software Engineering Agents and Verifiers with SWE-Gym. ICML 2025. arXiv:2412.21139.
[6] OpenAI and SWE-bench authors. Introducing SWE-bench Verified. Blog post, Aug 2024. https://openai.com/index/introducing-swe-bench-verified/
[7] R. Aleithan et al. SWE-Bench+: Enhanced Coding Benchmark for LLMs. arXiv:2410.06992 (2024).
[8] Y. Wang, M. Pradel, Z. Liu. Are "Solved Issues" in SWE-bench Really Solved Correctly? An Empirical Study. ICSE 2026. arXiv:2503.15223.
[9] E. Miller. Adding Error Bars to Evals: A Statistical Approach to Language Model Evaluations. arXiv:2411.00640 (2024).
Competition forum (Kaggle, gemma-4-developer-agent discussion; cited in text by handle and thread id; titles and post dates from the Kaggle CLI, 2026-11-05):
- 742807: "Clarification on distillation from external LLMs", 2026-09-23.
- 747248: "fastapi tasks can't pass even with the gold patch", 2026-10-08.
- 749597: "Could the 12 h be one budget for the whole run, instead of a per-task cap?", 2026-10-15.
- 750521: "Different public scores from an identical submission ZIP - reproducibility question", 2026-10-18.
- 751487: "Local eval in a scorer-like sandbox: gold patches pass on 127/129 public tasks (was 52)", 2026-10-21.
- 752017: "Current scorer contract: charged time limit, compaction settings, and repository split", 2026-10-23.
- 753524: "How noisy is the public score? 58 tasks, 1 task = 0.017 (simulation + leaderboard stats)", 2026-10-28.
<!-- 742807 is not yet cited in the body; cite it in the Disclosure (training-data policy) or drop it at final. -->
