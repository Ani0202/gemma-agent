# Paper outline (draft 1, 2026-11-04; due Nov 6 23:59 UTC)

Evidence status today: `results/` is EMPTY. Gold calibration kernel is running (Kaggle CPU); splits, timing and
paired comparisons do not exist yet. Every claim below is tagged with the file that must exist by Nov 10.
If the file does not exist by then, the claim is cut or written as "planned", never estimated.

## Candidate theses
**A (chosen, default): "Evaluating small-model SWE agents under a hard wall-clock budget: calibration, noise, and
the timing cliff."** An honest methods and measurement paper on Gemma 4 (E4B and 31B QAT) agents for repo-level bug fixing.
- Hits Verifiability (every number from a released file; pre-registered plans), Quality/generality (leave-one-repo-out,
  since no public repo is in the hidden set), Relevance (practical recipe for budgeted local agents), Novelty (quantified
  noise and cliff effects that public leaderboards ignore).
- Evidence needed: gold-patch calibration (clean list, hash, excluded count and cause), frozen repo-stratified splits, paired
  statistics on dev, per-task wall time and p90 cap rule, failure taxonomy from traces.
**B: "Do graph/localization tools help a small model? A paired ablation with leave-one-repo-out."** Tests the public claim that graph
tools help (docs/PRIOR_ART.md says no public measurement found). Needs >= 2 bundle variants, k>=2 samples, dev and LORO runs.
Folded into A as the main experiment if Builder's P1 data (Nov 7-18 plan) arrives by Nov 9; otherwise omitted, only noted as planned.
**C: "LoRA rejection-sampling SFT for E4B."** Weakest: P2 begins Nov 12, after our deadline, and GPU is limited (decision 003). Mention only as future work
(plus the public report that a naive SFT LoRA lowered score, docs/PRIOR_ART.md, cited as external).

Decision: write A. Upgrade the experimental section with B only if paired results exist by Nov 9. Fallback is complete and honest either way.

## Structure (body <= 2,800 words; references and appendix excluded, open question in RULES.md)
Word budget in brackets.
1. Title/subtitle, Abstract [150]
2. Introduction: problem, contributions (3 bullets), what is measured vs planned [300]
3. Setting and related work: task format, harness tools, scorer constraints (12 h incl. startup, no partial credit), Gemma 4 variants; prior public
   agents and scores (docs/PRIOR_ART.md, cited with attribution) [350]
4. Evaluation protocol [550]
   - Gold-patch calibration: how many tasks are unsolvable in the sandbox and why (e.g. missing test deps); clean list + sha256. [results/gold_calibration*]
   - Repo-stratified dev/holdout split, frozen before tuning; holdout use counted. [eval/splits/]
   - Paired design: same tasks and seeds, Wilson CIs, discordant pairs, exact sign test; how much +-3 tasks of 30 means. [eval/ stats code, results/]
   - Pre-registration: plans written before runs. [eval/plans/*.md]
5. The timing cliff [400]: cap rule `cap*125+30 <= 660 min`, p90 rule, measured startup and per-task wall time at concurrency 1 on L4x4 Kaggle, Kaggle-vs-concurrent-run distinction. [results/timing*, eval/plans/001.md]
6. Harness failure modes and fixes [450]: taxonomy of failed traces (malformed edit calls, scratch files in the repo, context overflow, thinking loops, empty diffs), frequency, effect of each fix on paired dev. Counts only; no task text. [results/failure_taxonomy*]
7. E4B vs 31B trade-off [300]: pass rate, wall time and cost per track on the same dev tasks, with LORO. [results/]
8. Limitations and threats to validity [200] (small n, no hidden-set access, single run, Kaggle quota limits)
9. Conclusion + reproducibility statement + AI-assistance disclosure [150]
References, appendix (protocol details, tables), artifact links [not counted]

## Figures/tables (<= 4)
T1 calibration funnel; T2 paired comparison table (n, k, pass rate, Wilson CI, A-only/B-only, p); F1 per-task wall time distribution with cap lines; T3 failure taxonomy counts before/after fixes.

## Evidence request list (Builder, at most one batched message/day; none sent yet)
Figure-ready CSVs of: calibration per-task outcomes (instance id hashed or repo-level counts), timing per-task, paired results, failure counts. All files with schema header (per decision 005).

## Integrity rules for the draft
No task text, patches, test code or repo code; repo names and aggregates only. Each number carries an HTML comment `<!-- src: results/... -->`. No Claude/Codex-written trajectories are used for training (Hard rule 2): state this.

## Code release (needs Aniket's OK at the final gate; Director decision 006 item 4)
Public Apache-2.0 repo (new, outside this working tree, e.g. exported from selected paths) containing ONLY:
- `eval/` runners, stats code (paired tests, Wilson CI), tests; `eval/plans/*.md`; `eval/kaggle/gold_calibration.py` (no wheel/data blobs)
- `bin/pack` + `docs/PACK.md` (bundle validator/zipper); `docs/HARNESS_NOTES.md` summary (check it quotes no competition data)
- `bundles/*/vNNN` prompts/skills/agent.yaml for the submitted versions (check: no task content)
- `results/` aggregate files; LICENSE (Apache-2.0), README with exact reproduction steps; attribution file
EXCLUDES: `data/`, `runs/`, `dist/`, `ops/` (mail, decisions, budget, logs), config with project IDs, anything under `~/.kaggle` etc., any trajectory containing task text.
Pre-release scan: grep for task ids/issue text, secrets; codex-review pass. Alternative if Aniket declines: attach as a Kaggle public notebook with the same contents.

## AI-assistance disclosure (draft paragraph)
"Disclosure: The experiments were run by an automated engineering workflow built on Claude (Anthropic) and Codex (OpenAI) coding assistants under the supervision of the author(s), who set the research questions and constraints. These assistants wrote code, analysis scripts and drafts of this text. No model-written trajectories or patches from proprietary models were used to train the Gemma models. All reported numbers come from the released result files; the author(s) reviewed the paper and take responsibility for its content."
(Aniket to confirm wording and the "own original work" warranty at sign-off.)

## Next
Nov 5-6: skeleton sections 1-4 in `paper/draft.md` (protocol is already fixed, needs no results); Nov 7-9: fill from results; Nov 10: full draft; Nov 11: compliance pass.
