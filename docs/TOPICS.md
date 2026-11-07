Topic inventory, created 2026-11-07 by the Director on Aniket's request; the Builder maintains it.

# Topic inventory: Gemma 4 Developer Agent (status as of 2026-11-07)
Status: used now | planned | adjacent, not used.

## Strategy in brief
- 31B (main prizes): the model and the scorer are fixed, so we control only the declarative ADK bundle: prompt, sampling and thinking, per-task caps, a read-only analyzer sub-agent, and later possibly a LoRA adapter. So far the binding constraint has been the 12 h wall clock, not quality. An overrun reportedly voids the submission, and the scorer's per-task setup cost is unknown, so caps were sized to the worst case until a scored run proves otherwise. 31b-v002 (cap 3.5) was submitted on Nov 7 to test that. Quality comes from pre-registered paired evals on 33 dev tasks on Kaggle L4x4: arm 1 baseline 4/33; arm 2 (loop/empty-diff guards) running; arm 3 (thinking on) queued. A change ships only if it wins paired on dev, passes leave-one-repo-out and the timing bound, then holdout. The public LB is pooled in at lower weight, since it's one noisy ~60-task sample.
- E4B (small-model bonus): it only has to beat other E2B/E4B entries, and it must be one of our two finals. It's the cheap testbed (1xL4) for scaffold ideas that get ported to 31B, and the track where LoRA via rejection-sampling SFT should pay most. Its specific problems are context overflow and a very tight cap (1.0 min in v002, public 0.05, which also proved validator acceptance).
- Paper ($35k, due Nov 12): a separate session writes an honest methods paper on evaluating small-model SWE agents under a hard wall-clock budget. Topics: gold calibration, frozen splits, LB noise and paired statistics, the timing cliff and scorer-setup uncertainty, harness failure modes. Every number traces to results/. The graph-tool ablation goes in only if paired data exists by Nov 9; LoRA appears only as future work.

## A. Task domain: repo-level software engineering
- SWE-bench-style issue resolution | used now | Repo snapshot at base_commit plus issue text; the agent's patch is graded by hidden tests. | docs/COMPETITION.md, docs/HARNESS_NOTES.md
- Fail-to-pass / pass-to-pass semantics | used now | Phase 2 needs the full pytest exit 0 after the hidden test_patch, so a fix that breaks other tests fails. | docs/COMPETITION.md
- Unified diffs / git patches | used now | The score is the workspace source diff; test edits are stripped; scratch files in /workspace pollute it; submit_patch freezes the patch. | eval/plans/005.md
- pytest and Python packaging (editable installs, build backends, src layouts) | used now | The main source of setup cost and of wheel shadowing. | eval/plans/002.md, 003.md, ops/reports/004, 009
- Fault localization | used now | Graph tools plus the analyzer sub-agent find the files and lines to change. | bundles/31b/v011/sub_agents/code_analyzer.yaml
- Generalization to unseen repos | used now (constraint) | Staff: no public repo is in the hidden set, hence LORO and no repo-specific prompts. | docs/COMPETITION.md, dec 014
- Mining extra tasks from public git history | adjacent, not used | Prior art mined ~1.5k instances. | docs/PRIOR_ART.md

## B. Agents and tool use
- LLM agent loop (ReAct-style act/observe) | used now | ADK runs tool-calling turns until submit or a cap. | bundles/*/vNNN/agent.yaml
- Google ADK declarative config (agent.yaml, !include, generate_content_config) | used now | | docs/PACK.md
- Harness tools and their truncation (run_command 5k chars, read_file 150 lines/10k) | used now | | docs/COMPETITION.md, eval/plans/005.md
- Function calling; malformed tool calls | used now (failure mode) | | eval/trace_tool_errors.py, results/trace_tool_errors_*.json
- Code-graph tools (neighbors, subgraph, similar-code; NetworkX graphs + 256-d embeddings) | used now | Their benefit is untested by us (paper thesis B). | bundles/31b/v011/agent.yaml, docs/PRIOR_ART.md, paper/OUTLINE.md
- Sub-agent via agent_tool (read-only code_analyzer, shares the task Context) | used now | A paired value test is planned (lever 5). | bundles/31b/v011/sub_agents/code_analyzer.yaml, eval/plans/008.md
- Gate sub-agent named submit_patch (bounces premature submits) | planned, not run (v010) | Arm 2 fell back to prompt-level v011. | eval/plans/008.md, dec 070-077
- Skills (SKILL.md, scripts, resources) | planned | Test-output summarizer, localization helper, patch sanity checker; no bundle has one yet. | CLAUDE.md levers
- Bundle callbacks / tool hooks | adjacent, not usable | The scorer harness silently drops them. | eval/plans/008.md Feasibility
- Workflow prompt (localize, reproduce in /tmp, minimal fix, targeted test, submit) | used now | | bundles/31b/v011/prompts/system.md, bundles/drafts/item4-system.md
- Exact-repeat loop guard (prompt-level) | used now in v011 | Arm 2 is running. | eval/plans/007-repeat-guard.md, results/shell_error_causes_31b_v005_v006.json
- Never-empty-diff / early-edit policy | used now | | eval/plans/005.md, ops/reports/014 (CAP-BOUND)
- Episode budgets (40 calls, 50 turns, 60 s/command, max_time_minutes) | used now | | bundles/*/vNNN/eval_config.yaml
- Best-of-n / self-consistency / verifier-selected patches within a task | adjacent, not used | The time caps leave no room for multiple attempts.
- Planner/critic multi-agent designs | adjacent, not used

## C. Prompt and context engineering
- System-prompt design (contract-style rules) | used now | | bundles/31b/v011/prompts/system.md, docs/PRIOR_ART.md
- Placeholder constraint (only {problem_description}) | used now | bin/pack validates it. | docs/PACK.md
- Output bounding (narrow reads, tail/head) | used now | | bundles/31b/v011/prompts/system.md
- Edit robustness (short anchors; JSON-escape trap; write_file vs edit_file) | used now | | eval/plans/005.md, 008.md
- 32k context limit; overflow leads to an empty patch | used now (failure mode) | | ops/reports/008, results/failure_taxonomy_e4b_v001_v5.json
- ADK event compaction (interval 15, threshold 14336) | used now (harness default, untuned) | The summarizer reportedly drops tool calls. | docs/HARNESS_NOTES.md
- Context caching (min_tokens 2048) | used now (harness default) | | docs/HARNESS_NOTES.md
- Repo-agnostic prompts; v002 "FastAPI hint" caveat | used now (rule and caveat) | | dec 060, dec 004-002-001
- Import-origin check lever | planned (unscheduled) | | eval/plans/002.md

## D. Model and model internals
- Gemma 4 family (31B / 12B / E4B / E2B, instruction-tuned; one model per bundle) | used now | | docs/COMPETITION.md
- "Effective"-parameter small models (E-series) | E4B used now; internals adjacent, not studied | |
- Thinking mode (thinking_budget, include_thoughts), thinking loops | used now | Root thinking is off (budget 0) in the 31B default; the analyzer uses 4096. Plan 009 arm 3 (root 4096) resolved 10/33 vs 4/33 (6/0, p=0.031) but was VETOED by its pre-registered timeout/empty limits; decision pending (report 021). | eval/thinking_bound.py, results/thinking_bound_*.json, eval/plans/009.md, results/plan009_arm3_vs_arm1.json
- Sampling (temperature 0.2, top_p 0.95, max_output_tokens 8192; a T 0.6 arm) | used now | | bundles/31b/v011/configs/sampling.yaml, ops/reports/015, results/plan005_armF_vs_D.json
- Chat template and tool-call parsing | used now (implicitly) | | results/trace_tool_errors_*.json
- Interpretability, probing, attention internals | adjacent, not used

## E. Inference and serving
- vLLM OpenAI-compatible server | used now | Scorer and our kernels; a stub is used for CPU tests. | eval/kaggle/agent_timing.py, eval/stub_openai.py
- Tensor parallelism on 4xL4 (96 GB) | used now (scorer-controlled) | | docs/COMPETITION.md
- vLLM startup inside the 12 h | used now | 31B 364.5 s measured. | results/kaggle_timing_31b_v001.json
- KV cache vs max_model_len; LoRA memory reservation shrinking the KV cache | used now (constraint) / planned check | | CLAUDE.md levers 2, 7
- Multi-LoRA serving (per-agent adapters) | planned | |
- Throughput vs latency; concurrency for quality vs concurrency 1 for timing; tokens/sec fidelity | used now | | CLAUDE.md eval discipline, eval/run_agent_eval.py
- Prefix caching, speculative decoding, batching tuning | adjacent, not used | The scorer owns the server config.
- 12B hf-overrides | adjacent, not used | |

## F. Quantization
- QAT w4a16 checkpoints, compressed-tensors format (-qat-w4a16-ct) | used now (the only allowed weights) | | docs/COMPETITION.md
- Train in bf16, serve quantized (adapter/base mismatch) | planned check | | docs/PLAN.md P2, CLAUDE.md lever 7
- PTQ (GPTQ/AWQ), KV-cache quantization | adjacent, not used

## G. Fine-tuning and post-training
- PEFT LoRA adapters (safetensors) | planned (P2) | None built yet; there is no A100, so a feasibility costing is due first. | dec 003, docs/PLAN.md
- Multi-turn tool-use SFT on agent trajectories (loss on model turns) | planned | |
- Rejection-sampling SFT (train only on passing trajectories) | planned (P2) | |
- Scripted trajectories from reference patches | planned (P2) | Allowed by Hard rule 2. | CLAUDE.md
- Expert iteration (1-2 rounds) | planned (P2) | | docs/PLAN.md
- Open-weight teacher distillation | planned but unscheduled | Licence and GPU/API cost needed. | docs/PLAN.md
- Distillation from Claude/GPT outputs | prohibited by our rules | | CLAUDE.md Hard rule 2
- Training-data provenance logging | planned | | ops/COMPLIANCE.md
- Fine-tuning can hurt (prior art: naive SFT LoRA 2/11 vs 4/11) | known risk | | docs/PRIOR_ART.md
- Full fine-tuning, QLoRA | adjacent, not used

## H. Reinforcement learning
- Online RL on Gemma weights (PPO / GRPO / RLOO, RLVR, SWE-RL-style) | adjacent, not used | Why: $150 cap, GCP limited to 1 GPU and no A100, Kaggle quota shared with evals. Rollouts cost minutes each with a sandbox, so on-policy RL needs far more than we can afford. Only 48 clean public tasks (33 dev), unseen hidden repos, ~3.5 weeks left. The result must ship as a LoRA on a quantized base. Even SFT LoRA has hurt in prior art.
- Verifiable binary reward (tests pass) | used now as an eval signal | Every trajectory gets pass/fail. | results/gold_calibration_*, plan007/008 results
- Rejection-sampling SFT + expert iteration = filtered behaviour cloning on a 0/1 reward (STaR/ReST-like) | planned (P2) | Our only RL-flavoured training. | docs/PLAN.md
- Reward models; DPO / preference pairs from pass vs fail trajectories | adjacent, not used | Same constraints apply.
- Reward hacking prevention | used now (concept) | Tests are reset and test edits are stripped, so we check test-file edits = 0. | eval/plans/001.md
- Explore/exploit framing of daily slots | adjacent (informal, not RL) | | DIRECTOR.md slot policy
- Long-horizon credit assignment, exploration | adjacent, not used

## I. Evaluation methodology
- Gold-patch calibration and null control | used now | | docs/GOLD_CALIBRATION.md, results/gold_calibration_*.json(l), gold_null_control.jsonl, gold_failure_causes.jsonl, ops/reports/002
- Clean list hashing; frozen repo-stratified splits (dev 33 / holdout 15, 0 holdout uses) | used now | | eval/make_splits.py, eval/splits/MANIFEST.json
- Holdout discipline | used now (rule); first use planned | |
- Leave-one-repo-out | planned for every ship decision | Weak with two repos. | dec 014, docs/PLAN.md
- Pre-registration | used now | | eval/plans/*.md
- Paired arms (same tasks, same seeds) | used now | | results/plan005_arm*_vs_*.json, results/plan008_arm1_base.json
- Smoke gates and validity rules (e.g. thinking blocks > 0) | used now | | eval/plans/009.md, eval/plan007_blind_gate.py
- Hash-sealing outputs before analysis (blinding) | used now | | runs/*/SEAL.sha256, ops/budget/kaggle.md
- Metric definitions (pass rate, empty diff, config-only patch, submit-without-test, identical-run length, H rows / known-diag) | used now | | results/plan007_arm1_summary.json, eval/plan008_metrics.py, dec 072-074
- Environment fidelity (scorer setup worlds H1 subprocess / H2 Docker / H3 slow pip) | used now | | ops/reports/009, dec 034, results/setup_py_cause_v5.json, results/stock_subprocess_setup_local.json
- Timing at concurrency 1 on exact hardware; p90/max; bound cap x 125 + 30 <= 660 | used now | | eval/plans/001.md, 006.md, results/kaggle_timing_*.json, eval/tool_timing.py
- Failure taxonomy and trace analysis | used now | | results/failure_taxonomy_e4b_v001_v5.json, results/taxonomy-31b-v003-p5t4.json, .claude/agents/
- Public LB as a noisy external eval; variance repeats | used now / repeats planned | | results/lb_*.json, ops/submissions.jsonl
- Contamination (model may have seen the public repos) | adjacent | Motivates LORO.
- LLM-as-judge | adjacent, not used | Tests are the judge.
- Independent review of eval code (codex-review) | used now | | ops/codex/, ops/reviews/

## J. Statistics
- Binomial proportions, Wilson 95% CI (arm 1: 4/33, 4.8-27.3%) | used now | | results/plan007_arm1_summary.json, eval/plan007_arm1_summary.py
- Paired discordant counts, exact sign test (exact McNemar) | used now (required) | | eval/plan008_metrics.py, CLAUDE.md report format
- Small-n power ("+/-3 tasks on ~30 is noise") | used now (decision rule) | | CLAUDE.md
- Public-LB sampling noise (~60 tasks; same files 0.12-0.22) | used now | | docs/COMPETITION.md
- k >= 2 samples per task / seeds | planned where affordable | Mostly k = 1 today.
- Pooling LB with local evidence | used now (informal) | Formal Bayesian/hierarchical pooling is adjacent.
- Multiple comparisons / forking paths (pre-registration; post-hoc rulings labelled as such) | used now | | dec 069
- Sensitivity analyses (excluding H rows etc.) | used now | | results/plan007_arm1_summary.json
- Worst-case bound arithmetic; queue-time veto | used now | | ops/reports/009, dec 055
- Winner's curse / selection under public-private split for finals | planned (finals analysis) | |
- Bootstrap, Bayesian A/B, sequential testing | adjacent, not used

## K. Sandboxing, environments and packaging
- Docker vs subprocess sandboxes, network_mode none, 2 vCPU / 4 GiB | used now | | docs/HARNESS_NOTES.md, ops/reports/009
- Offline wheels, pip --no-index, build backends, RECORD stripping, wheel shadowing | used now | | eval/plans/003.md, 004.md, dec 014, results/plan003_*.json
- Two-phase grading (agent container, then verification container with reset tests) | used now | | docs/COMPETITION.md
- Protected paths, test-edit stripping | used now | | eval/plans/005.md
- CPU architecture (ARM control VM vs x86 wheels) | used now (open checklist item) | | ops/STATE.md
- Bundle packaging and validation (<= 3 GiB, extensions, no symlinks or ..) | used now | | bin/pack, docs/PACK.md, eval/checks/bundle_load_check.py, results/bundle_load_check_*.json
- Artifact hashing and per-version manifests | used now | | bundles/*/vNNN/MANIFEST.md

## L. Compute infrastructure and operations
- Kaggle GPU kernels (L4x4, internet off, pinned image, 12 h sessions, weekly quota) | used now | | eval/kaggle/push.sh, timing_push.sh, stage_kernel.py, ops/budget/kaggle.md
- Submission via notebook-output kernel (CPU) | used now | | eval/kaggle/submit_kernel, bin/kaggle-submit, ops/submissions.jsonl
- Cloud VMs with a budget ledger, spot instances, max-run-duration | available, $0 spent | | bin/gpu, ops/budget/allowance_usd, dec 003
- Detached jobs (systemd user units, low priority), memory watchdog, shared-VM hygiene | used now | | bin/job, bin/memguard, ops/jobs/
- Status waiters for LB polling | used now | | ops/jobs/lb-*-wait-light.*
- Orchestration of our own AI team (Director / Builder / Paper sessions, router, mailboxes, decisions; Codex review and build) | used now | | bin/router, bin/send, bin/decide, bin/codex-*, ops/decisions/
- Git versioning and attribution | used now | | docs/ATTRIBUTION.md

## M. Competition strategy and decision-making
- LB mechanics (public/private ~50/50, 1 submission/day, one pending, queue latency, ties to the earlier, final = better of two) | used now | | docs/COMPETITION.md, dec 013
- Slot policy (information value: baseline / improvement / variance repeat) | used now | | DIRECTOR.md, ops/drafts/nov8-slot-inputs.md
- Risk management (conditional authorizations, vetoes) | used now | | dec 055
- Finals selection (two bundles, E4B eligibility, risk profiles) | planned (Dec 1-2) | | DIRECTOR.md
- Avoiding public-LB overfitting | used now (rule) | | DIRECTOR.md

## N. Compliance, licensing and integrity
- Competition-data rules (no redistribution, no hand-labelling, no LB probing) | used now | | CLAUDE.md Hard rules, ops/COMPLIANCE.md
- Open-source licensing (Apache-2.0 reuse with attribution; OSI licence for winners) | used now | | docs/ATTRIBUTION.md, docs/COMPETITION.md
- Training-data provenance (no proprietary-model outputs) | used now (rule) | | CLAUDE.md Hard rule 2
- AI-assistance disclosure | used now (paper) | | paper/OUTLINE.md
- Secrets handling | used now | | CLAUDE.md Hard rule 6

## O. Research communication (paper)
- Methods paper, word limit, figures, reproducible public code release | used now | | paper/, ops/decisions/005-E2.md, dec 038
- Citing community prior art | used now | | docs/PRIOR_ART.md
