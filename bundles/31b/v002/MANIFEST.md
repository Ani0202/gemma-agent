# 31b-v002 (31B SUBMISSION candidate; dec 034 item 3, dec 036 item 2, dec 052 item 3)
- parent: 31b-v001-t4 (dist/31b-v001.zip sha256=3c3a264652ab1d72ff6b9c5609c482c34a2ab7af37eb600689e5cfa0bf810f6a), the plan-006 timing bundle.
- built from repo git SHA: see the commit that adds this file (parent commit d3ee405).
- changes (EXACTLY one setting + its comment): eval_config.yaml `evaluation.max_time_minutes` 4.0 -> 3.5, and the 3-line header comment.
  `diff -r bundles/31b/v001 bundles/31b/v002` shows only those lines (+ this MANIFEST). No prompt/sampling edits (max_output_tokens 8192 x2 kept).
- budget: under H1/H2 (stock-path S <= 30 s) worst = (210+7+30)/60x125+30 = 544.6 min <= 660. Under H3 (S 221.6 s) = 943.8 min > 660,
  so it is submittable ONLY if G1 holds (report 010). No re-time needed: the cap-4.0 run bounds it (dec 036 item 2).
- FINALS rule (dec 034): not a final unless this cap (or higher), same model, has SCORED on the real scorer.
- status: UNVALIDATED; NOT authorized. Submit route: CPU kernel aniket0202/gemma-submit-31b (writes this zip; staged by eval/kaggle/submit_kernel/stage.py).
zip sha256: e56a05e5701fa16a8dbbabb304d98f63a465511cefbb28d65850ea5ce086ec88
- packed 2026-11-06T00:13Z with bin/pack (PASS, 6663 unpacked bytes, zip 4281 bytes): dist/31b-v002.zip; zip members identical to
  dist/31b-v001.zip except eval_config.yaml (verified), and each member byte-identical to this directory.
- load check: results/bundle_load_check_31b_v002.json (both agents max_output_tokens 8192; session timeout 210 s).
zip sha256: e56a05e5701fa16a8dbbabb304d98f63a465511cefbb28d65850ea5ce086ec88
