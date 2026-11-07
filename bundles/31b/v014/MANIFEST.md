# 31b-v014-p10a (PLAN 010 arm 4 candidate, dec 089 item 6). CPU DRAFT, UNVALIDATED. Not authorized for submission.
packed: dist/31b-v014.zip sha256=7980846995e3acb38418427755676931fbfc7fa22998b1e9b2599da499135def (bin/pack PASS 2026-11-07).
- parent: 31b-v012-p9a (dist/31b-v012.zip sha256=78a8fd30389ec3acf58b44bc8743d750b496041f5c8d2b35790f0d913130ede5).
- change vs parent: ONLY configs/sampling.yaml l.5 root thinking_budget 4096 -> 2048 (diff -r vs bundles/31b/v012: that one line + this MANIFEST).
- unchanged: analyzer sub-agent thinking 4096, T 0.2, top_p 0.95, max_output_tokens 8192, include_thoughts true, eval_config (cap 3.5, 40 calls / 50 turns).
- dec 087 (b): knob-only <= diff vs v012 -> finals-eligible without its own slot IF v012 scores COMPLETE (confirm with eval/finals_eligibility.py).
- git SHA: see the commit that adds this file. Light codex review: pending.
zip sha256: 7980846995e3acb38418427755676931fbfc7fa22998b1e9b2599da499135def
- load check PASS 2026-11-07T12:1xZ: results/bundle_load_check_31b_v014.json == v012 except root thinking_budget 2048 (analyzer 4096, max_out 8192, cap 3.5/40/50 unchanged).
- finals pre-check: results/finals_eligibility_31b-v014_vs_31b-v012.json ELIGIBLE (0 violations), no --reference-lb yet (v012 not scored).
- arm4 metrics mode pre-data gate: codex re-review ops/codex/review-20261107T120155.md CLEAN (code 77cd97b).
