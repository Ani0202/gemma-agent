# 31b-v012-p9a (PLAN 009 arm-3 candidate; runs ONLY if BASE = arm 1 per eval/plans/009.md Base selection). CPU DRAFT, UNVALIDATED.
packed: dist/31b-v012.zip sha256=78a8fd30389ec3acf58b44bc8743d750b496041f5c8d2b35790f0d913130ede5 (bin/pack PASS).
- parent: 31b-v009-p7a1 (dist/31b-v009.zip sha256=d38c55c79103950d6d269a722bd0c9db9db22e1c0ec96be230f6c24a332d130d).
- change vs parent: ONLY configs/sampling.yaml l.5 root thinking_budget 0 -> 4096 (diff -r vs bundles/31b/v009: that one line + this MANIFEST).
- unchanged: T 0.2, top_p 0.95, max_output_tokens 8192, include_thoughts true, analyzer sub-agent (thinking 4096), eval_config (cap 3.5, 40 calls / 50 turns).
- load check: results/bundle_load_check_31b_v012.json (root + analyzer 8192 / thinking 4096, session timeout 210 s).
- git SHA: see the commit that adds this file. Light codex review: pending.
zip sha256: 78a8fd30389ec3acf58b44bc8743d750b496041f5c8d2b35790f0d913130ede5

- Review: codex ops/codex/review-20261106T144907.md CLEAN (light one-knob; parent diff = thinking_budget 0->4096 only; zip sha re-verified).
