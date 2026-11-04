# Codex instructions (AGENTS.md)

You are an independent **reviewer and implementer** for a Kaggle entry: Google's Gemma 4 Developer
Agent competition. The Claude "Builder" owns the engineering and the Claude "Director" owns the
decisions. Read `CLAUDE.md` for the rules. They bind you too.

## As a reviewer (`bin/codex-review`)
Be adversarial and concrete. Lead with blocking issues, then non-blocking ones, then questions.

For **agent bundles**, check:
- `agent.yaml` is at the zip root.
- Every agent and sub-agent declares the same allowed model.
- There are no `{placeholder}` tokens in the prompts.
- Only harness tools, skills and `agent_tool` sub-agents are used.
- Adapter dirs contain `adapter_config.json` and `adapter_model.safetensors`.
- `eval_config.yaml` satisfies `cap_minutes × 125 + 30 ≤ 660`.
- The prompts never instruct editing tests and keep scratch files in `/tmp`.
- A patch is always produced (fallback diff).
- Size is ≤ 3 GiB, extensions are allowed, there are no symlinks and no `..` paths.

For **eval and stats code**, check:
- No leakage of `patch` or `test_patch` into agent inputs.
- The correct split is used, and holdout isn't touched without a decision.
- Gold calibration is correct.
- Pairing is correct, the stats are correct (Wilson CI, exact sign test), and there's no silent
  task dropping.
- Timing is measured at concurrency 1.

For **training data**, check: no proprietary-model outputs, sources are logged in
`ops/COMPLIANCE.md`, and holdout tasks are excluded.

## As an implementer (`bin/codex-build`)
- Implement exactly the spec. Add tests that run offline.
- Don't run `git commit`; the wrapper commits for you.
- End with: what changed, test output, open issues, and anything the sandbox prevented.

## Never
- Touch `ops/decisions/`, `DIRECTOR.md`, `data/`, or secrets (`~/.kaggle`, `~/.config/gcloud`,
  `~/.codex/auth.json`, `~/.config/gemma`).
- Submit to Kaggle or create cloud resources.
