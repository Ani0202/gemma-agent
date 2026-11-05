# e4b v002
- parent: e4b v001 (dist/e4b-v001.zip sha256=f2ced9c97ee1447cb3a78c0ebf65f4ecaff90c84b18313645d5d043c62d277e9)
- built from repo git SHA: see the commit that adds this file (parent commit 4f616da)
- changes (EXACTLY two, dec 032 item 1):
  1. eval_config.yaml `evaluation.max_time_minutes` 1.4 -> 1.0 (+ header comment with the derivation).
     Rule on TOTAL Phase-1 incl. image emulation (dec 028 item 4): worst = 60 (cap) + 1.32 (finalization F) + 221.6 (max measured non-agent overhead S, results/kaggle_timing_e4b_v001.json) = 282.9 s/task -> 282.9/60 x 125 + 30 = 619.4 min <= 660.
  2. max_output_tokens 16384 -> 8192 at EVERY occurrence (grep of the whole bundle for 16384 / max_output_tokens / max_tokens / token, case-insensitive; no other hits):
     - configs/sampling.yaml:3 (root agent, via agent.yaml `generate_content_config: !include configs/sampling.yaml`)
     - sub_agents/code_analyzer.yaml:21 (code_analyzer_agent generate_content_config)
     Reason: rich_3930 harness failure in kernel v5 = vLLM 400 (prompt + 16384 output > 32k context).
- no prompt edits, no item-4 work. `diff -r bundles/e4b/v001 bundles/e4b/v002` shows only the lines above (+ this MANIFEST).
- status: UNVALIDATED (no re-time; dec 032 item 3).
zip sha256: 60c0074684ef4f9aa9cd8744d08fa29a37f3b94fc893541a8b96ceed54944dad
- packed 2026-11-05T21:06Z with bin/pack (PASS, 6462 unpacked bytes, zip 4152 bytes): dist/e4b-v002.zip
- load check (dec 032 item 2): results/bundle_load_check_e4b_v002.json via eval/checks/bundle_load_check.py (real adk_submission compile_submission + swegemma constraints/EvalConfig): swe_baseline_agent 8192, code_analyzer_agent 8192 (v001 control: 16384/16384); budget time 1.0 min -> session timeout 60.0 s (v001 control 84.0 s).
- review: light Codex review queued (job review-e4b-v002-light, 23:09Z after the Codex limit reset).
