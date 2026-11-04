# Compliance log
Each rule is listed with how we comply and its source. External data sources go here **before**
we use them.

- Training targets come from Gemma's own outputs, scripted trajectories built from public
  reference patches, or logged public data. No proprietary-model outputs.
- Competition Data never leaves our VMs, Kaggle, and the coding tools. `data/` and `runs/` are
  gitignored.
- One Kaggle account (Aniket's). No private sharing.

## Rules status (2026-11-04) — see docs/RULES_FINDINGS.md (secondary sources, UNCONFIRMED)
- External data/models: allowed if public/free or "Reasonableness Standard". No external data used yet; log each source here BEFORE use.
- LLM-generated training data: no official ruling found; we still forbid Claude/GPT/proprietary outputs as training targets (Hard rule 2).
- Reused code: only with a verified Apache-2.0/MIT LICENSE file + docs/ATTRIBUTION.md entry. Unlicensed repos (jwj1342, sagarml4949): ideas only.
- Winners must supply Apache-2.0 code/docs (third-party report): keep bundle contents ours or Apache/MIT.
- TODO (needs browser/human): read official Rules tab + threads on multiple runs, unfinished tasks, LLM data.

## Official rulings (2026-11-04, decision 004-002-001; docs/RULES_FINDINGS.md)
- (a) LLM-generated training data: allowed only per the source model's licence terms (staff Ashley Oldacre, thread 742807). Claude/GPT/Codex forbid it, so Hard rule 2 stands. Open-weight teachers whose licence permits training other models are legal (not scheduled; cost out when LoRA work starts).
- (b) External data/models: public, equally accessible, no/minimal cost (Rules §2.6). Competition Data not to be given to non-participants (§2.4.b). Hosted-LLM-API use for data: OPEN (thread 755542). Practice: no new third-party services for task data.
