<!-- DRAFT v0.2, 2026-11-05 (refs verified). Sections 1-4 and 8 only (do not depend on results). [[PENDING: file]] marks text that needs a results file; cut if absent by Nov 9.
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
Our first pass, a subprocess sandbox on Kaggle CPU, kept 52 of 129 tasks. Almost all failures came from the environment, mainly test packages missing from the offline wheel set and an unrelated pytest plugin, not from the tasks <!-- src: results/gold_calibration_summary.json; results/gold_failure_causes.jsonl; ops/journal.md 2026-11-05T02:57Z, 07:33Z -->. We then rebuilt the scorer's dependency installation locally, which cut a calibration round from hours to seconds per task <!-- src: ops/journal.md 2026-11-05T14:15Z; docs/GOLD_CALIBRATION.md -->. The 127/129 community figure comes from an environment that adds test packages not in the competition wheel set and pins period-correct versions (thread 751487). The published harness installs the highest available version of each package without a resolver, so we tag tasks that fail for these reasons as assumed scorer failures, not agent failures <!-- src: docs/GOLD_CALIBRATION.md 'Reconciliation' -->. [[PENDING: final gold-local funnel from results/gold_calibration*/gold_failure_causes.jsonl v2: n passing, exclusion groups with counts, per repo]]. We compare our funnel with community numbers (127/129, thread 751487; 43, thread 747248). Another participant observed that a few tasks pass with an *empty* patch because a bundled wheel shadows the repository (aefinityaiinc, thread 747248); we additionally run an empty-patch control so such tasks cannot count as agent wins [[PENDING: confirm the control was run; else cut this sentence]].
**4.2 Splits.** Clean tasks are stratified by repository into *dev* (all tuning) and *holdout* (ship decisions only, each use counted and logged). Splits are frozen and hashed before any agent run [[PENDING: eval/splits/*, hashes]]. Because no public repository is in the hidden set, every ship decision also requires a leave-one-repository-out (LORO) check, repo-specific prompt content is rejected, and repositories are weighted equally.
**4.3 Paired comparisons.** Two bundles are compared on the same tasks and seeds with k >= 2 samples per task. We report pass rate with Wilson 95% intervals, the numbers of discordant tasks (A-only, B-only) and an exact two-sided sign test on discordant tasks. Motivated by thread 750521 and 753524, a change of +-3 tasks on about 30 is treated as noise. Same-bundle repeat runs estimate the noise floor [[PENDING: results/ repeat-run file, else describe as planned]].
**4.4 Pre-registration.** Each experiment has a plan file with hypothesis, measurements and decision rule written before the run <!-- src: eval/plans/001.md (example) -->, so that analysis cannot drift toward favourable outcomes. Plans, code and results carry git SHAs.
**4.5 Statistics code.** Wilson, sign test and bootstrap utilities are in `eval/`, with unit tests, and were reviewed by an independent coding assistant before use [[PENDING: eval/ stats module path]].

<!-- Sections 5 (timing cliff), 6 (failure modes), 7 (E4B vs 31B, conditional on results by Nov 9) written after results exist. -->

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
Competition forum (Kaggle, gemma-4-developer-agent discussion; cited as handle, thread id): 742807, 747248, 749597, 750521, 751487, 753524. [[TO DO: add titles and post dates from the Kaggle CLI in a later turn]]
