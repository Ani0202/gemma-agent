# 31b-v011-p8b (PLAN 008 FALLBACK arm-2 candidate, dec 071 item 3). CPU DRAFT, UNVALIDATED, PROMPT-LEVEL (dec 070 item 1).
packed: dist/31b-v011.zip sha256=4f5b078a367e964ffb7d7426f4d42e13451d0c9dde79322c7fee5bd3a88f4938 (bin/pack PASS, 6 files, 9965 bytes).
- parent: 31b-v010-p8 (dist/31b-v010.zip sha256=c7a86295a023db971bcc9d149c4e6c68674d5ea052ecdfb3c11655b535772cd8).
- changes vs v010: (1) agent.yaml = v009 agent.yaml byte-identical (harness builtin submit_patch back on root, no gate agent_tool);
  (2) sub_agents/submit_gate.yaml removed; (3) prompts/system.md l.36 submit paragraph: the dec 070 1(b) prompt rule is kept
  verbatim (git diff --stat must show a non-test source file, else edit first; skip only if the budget can't fit an edit; never
  submit an empty diff on purpose), the gate semantics sentences (NOT SUBMITTED / SUBMITTED / request "submit") are dropped and the
  v009 "call submit_patch ONCE ... freezes the patch ... cannot be recovered" text is restored.
- identical to v010: repeat ban (Option A verbatim) + edit 2-fail fallback (l.43), NB2 pipefail (l.33, UNSCREENED), eval_config
  (cap 3.5, 40 calls / 50 turns), sampling, analyzer sub-agent. No repo-named content (dec 057).
- vs v009: only system.md l.33 (pipefail), l.36 (1(b) rule), l.43 (repeat ban + edit fallback).
- load check: results/bundle_load_check_31b_v011.json (8192 x2, session timeout 210 s, 40 calls / 50 turns).
- arm-2 selection (plan 008, dec 071 item 3): this bundle runs arm 2 ONLY if the v010 smoke FAILS (or cannot run).
zip sha256: 4f5b078a367e964ffb7d7426f4d42e13451d0c9dde79322c7fee5bd3a88f4938
