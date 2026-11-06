# 31b-v004 (31B CANDIDATE DRAFT, dec 059 item 1; dec 057/058 item 6). CPU draft only: NO slot requested, UNVALIDATED.
- Name: 31b-v004 (directory bundles/31b/v004, file dist/31b-v004.zip).
- parent: 31b-v002 (dist/31b-v002.zip sha256=e56a05e5701fa16a8dbbabb304d98f63a465511cefbb28d65850ea5ce086ec88).
  Built by copying 31b-v007-p5e (arm E screen bundle) and adding one prompt line, so it equals the screened arm-E bundle + 1 line.
- built from repo git SHA: see the commit that adds this file.
- changes vs v002 (3 files besides MANIFEST):
  1. configs/sampling.yaml root thinking_budget 4096 -> 0 (thinking off; plan 005 arm D PASS, arm E pending).
  2. prompts/system.md = plan 005 arm-B prompt (v003; includes the /tmp contradiction fix and REMOVES the repo-named
     FastAPI/docs_src line, replaced by a generic example-code line; grep fastapi|docs_src = 0) + ONE new generic line
     (shell quoting / no unchanged re-run; dec 059 item 4b: 22/22 arm-D cmd_error_shell = quoting, one task, 21 identical repeats,
     results/shell_error_causes_31b_v005_v006.json).
     NOTE: dec 059 item 1 literally reads "v002 + thinking 0 + /tmp fix + hint removal". The arm-B prompt also carries the
     early-edit, short-anchor, small-output and submit-hygiene lines. Kept because every thinking-off screen (D, E) ran with it;
     flagged to the Director in the arm-E report (alternative: a minimal v002 prompt + /tmp lines only).
  3. eval_config.yaml max_time_minutes 3.5 -> 1.23 (FINALS RULE H3 bound; revisit only if 31b-v002 scores at 3.5, dec 059 item 1).
- unchanged: agent.yaml (max_output_tokens 8192 x2), analyzer sub-agent (own thinking_budget 4096) + prompt, 40 calls / 50 turns.
- status: UNVALIDATED. Codex review pending.
- packed 2026-11-06T04:38Z with bin/pack --zip (PASS, 9288 unpacked bytes, zip 5444 bytes). zip sha256: 50537e1ddcf13f160fcaa9b2bfa145ac13ef91d99a2ce0b27d69f54ee125f7b3
