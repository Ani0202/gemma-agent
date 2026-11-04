# Kickoff: Phase 0 (spread across several cycles)

Your first cycle has no `ops/STATE.md`. Create it, then work through the steps below. End each
cycle cleanly, as CLAUDE.md requires.

There's a daily submission slot, and an unused day is a lost slot. So get a **public-best
31B baseline** packaged and in front of the Director early (step 4), even before the local eval
exists.

1. **Environment.**
   - Report `uname -m`, `df -h ~` and `free -h`.
   - Check that `kaggle`, `gcloud`, `codex`, `jq` and `tmux` work.
   - If disk is under 60 GB free, say so; Aniket can expand the free-tier block volume.
2. **Get the facts right.**
   - Read the competition Overview, Data, Rules and the main Discussion threads with WebFetch.
     Look especially for host rulings on: allowed models, timeouts, multiple private runs,
     distillation, submission method and daily limits.
   - Download the small files first with the Kaggle CLI (`tasks.jsonl`, `HARNESS_README.md`,
     `sample_submission/`, `docker/`). Decide later where the snapshots, graphs, embeddings and
     wheels go.
   - Write `docs/HARNESS_NOTES.md` (tool signatures, limits, compaction, eval CLI, sandbox
     lifecycle).
   - Correct `docs/COMPETITION.md`.
   - Start `ops/COMPLIANCE.md` with each rule and how we comply.
3. **Learn from public work** (Apache-2.0; credit in `docs/ATTRIBUTION.md`). Skim the top-scoring
   public notebooks and these repos:
   - nakranivaibhav/gemma-4-developer-agent: a local kit, graph rebuilder, A/B results.
   - j-holou/gemma-4-developer-agent: `push_eval.py` runs a bundle in a private Kaggle L4x4 kernel.
   - HindsightWise/gemma-4-developer-agent: a list of traps.
   - Maukthik/gemma4 and Utsav-X-bit/Gemma-4-Agent: budgets, LoRA notes.

   Summarize what to reuse in `docs/PRIOR_ART.md`. Don't install or run untrusted code without
   reading it first.
4. **Baseline bundles.**
   - Build `bundles/31b/v000` as the best public-scoring 31B configuration you can verify.
   - Build `bundles/e4b/v000` as the same workflow with the E4B model and no dummy adapters.
   - Ask Codex to implement `bin/pack` (a validator mirroring the adk-submission rules, plus zip
     and sha256 into the MANIFEST), then run it.
   - Have `codex-review` check both bundles.
   - Write report 001 requesting `SUBMIT` for 31B v000.
5. **Compute.**
   - Fill in `config/gpu_profiles.json`: zone, image family and the **current hourly rates with
     their source URL and date**. Find a zone with L4 and A100 availability; spot pricing is
     preferred.
   - Test `bin/gpu` with the `cpu8` profile for 10 minutes. This needs a small Director allowance,
     so ask for about $5 in a report.
   - Determine whether the sandbox can run on ARM. If not, gold calibration and Phase-2 checks run
     on the `cpu8` x86 VM.
6. **Eval machinery** (delegate the bulk to Codex, then review it):
   - Gold calibration produces `eval/clean_tasks.txt` plus its hash.
   - Write `eval/splits/{dev,holdout}.txt`, about 70/30 and stratified by repo, then freeze them.
   - A remote eval runner that starts the GPU VM, serves the model with vLLM, runs N tasks
     concurrently through the official `swegemma`/adk-eval path, does Phase-2 verification, pulls
     back `results/<run>.jsonl` (task, pass, tool calls, tokens, wall time, failure class), and
     stops the VM.
   - `bin/kaggle-eval`, modeled on j-holou's approach, for exact-environment chunks.
   - `eval/stats.py` for Wilson CIs, paired discordant counts and an exact sign test.
7. **Gate 0 report.** Cover the clean-task count, the baseline local pass rates for both tracks
   (dev split, k=1 is fine at first), timing per task, the GPU spend so far, and the proposed P1
   experiment queue for each track, ranked.
