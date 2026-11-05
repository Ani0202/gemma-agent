# 31b-v001-t4 (TIMING bundle ONLY for plan 006, cap 4.0; dec 034 item 2, name per dec 036 item 2)
- Name: 31b-v001-t4 (directory bundles/31b/v001, file dist/31b-v001.zip). NOT a submission candidate.
- parent: 31b v000 (dist/31b-v000.zip sha256=4a23e14a1aae077161cb137b5ff72afe91ee2acb1d1fdbaf2e322abb6efae161)
- built from repo git SHA: see the commit that adds this file (parent commit 219ad9f)
- changes (EXACTLY two):
  1. eval_config.yaml `evaluation.max_time_minutes` 5 -> 4.0 (dec 034 item 2: plan-006 run at cap 4.0).
     NOT submittable as-is: under H3 (S 221.6 s) worst = (240+7+221.6)/60x125+30 = 1006 min > 660.
     A submission needs G1 (dec 034 item 3): a SEPARATE bundle 31b-v002, cap <= 3.5, byte-identical to this one except the
     eval_config cap and its comment (dec 036 item 2); no re-time needed, since the cap-4.0 run bounds it (H2 check with S 60 s = 607 min).
  2. max_output_tokens 16384 -> 8192 at both occurrences (configs/sampling.yaml:3, sub_agents/code_analyzer.yaml:21), same as e4b-v002
     (plan 006 addendum; the 32k context overflow seen on rich_3930).
- no prompt edits. `diff -r bundles/31b/v000 bundles/31b/v001` shows only the lines above (+ this MANIFEST).
- status: UNVALIDATED.
- packed 2026-11-05T21:30Z with bin/pack (PASS, 6634 unpacked bytes, zip 4244 bytes): dist/31b-v001.zip
- load check: results/bundle_load_check_31b_v001.json (both agents 8192, thinking 4096; session timeout 240 s).
- review: codex-review together with the P1-P3 kernel change (after fix5c + v002 reviews, dec 034 item 7).
zip sha256: 3c3a264652ab1d72ff6b9c5609c482c34a2ab7af37eb600689e5cfa0bf810f6a
