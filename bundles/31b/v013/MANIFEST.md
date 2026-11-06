# 31b-v013-p9b (PLAN 009 arm-3 candidate; runs ONLY if BASE = arm 2 per eval/plans/009.md Base selection). CPU DRAFT, UNVALIDATED.
packed: dist/31b-v013.zip sha256=06eff226d661c0528105a14d4fe0b69f67a8fb84fc52e654a0d54b6bc59a5dbb (bin/pack PASS).
- parent: 31b-v011-p8b (dist/31b-v011.zip sha256=4f5b078a367e964ffb7d7426f4d42e13451d0c9dde79322c7fee5bd3a88f4938).
- change vs parent: ONLY configs/sampling.yaml l.5 root thinking_budget 0 -> 4096 (diff -r vs bundles/31b/v011: that one line + this MANIFEST).
- unchanged: T 0.2, top_p 0.95, max_output_tokens 8192, include_thoughts true, analyzer sub-agent (thinking 4096), eval_config (cap 3.5, 40 calls / 50 turns).
- load check: results/bundle_load_check_31b_v013.json (root + analyzer 8192 / thinking 4096, session timeout 210 s).
- git SHA: see the commit that adds this file. Light codex review: pending.
zip sha256: 06eff226d661c0528105a14d4fe0b69f67a8fb84fc52e654a0d54b6bc59a5dbb

- Review: codex ops/codex/review-20261106T144907.md CLEAN (light one-knob; parent diff = thinking_budget 0->4096 only; zip sha re-verified).
