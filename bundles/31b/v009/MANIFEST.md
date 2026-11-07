# 31b-v009-p7a1: SUBMISSION CANDIDATE per dec 083 (conditional Nov 8 primary; first hint-free 31B). Originally PLAN 007 ARM-1 quality-eval bundle (dec 062 item 4). In-zip eval_config comment still says "NOT a submission candidate": left unchanged on purpose (changing it changes the sha).
- Name: 31b-v009-p7a1 (directory bundles/31b/v009, file dist/31b-v009.zip).
- parent: 31b-v006-p5d (dist/31b-v006.zip sha256=b7b2eb3d139629a5893647546348c1b436c1ff94c786cbdf4e6ec1be12f660a0) = plan 005 arm D (thinking off).
- changes (EXACTLY one file besides MANIFEST): eval_config.yaml max_time_minutes 4.0 -> 3.5 (= 31b-v002 cap; FINALS RULE max if v002 scores) + header comment.
- unchanged: prompts (plan-005 arm-B prompt; no repo-named hint, grep -i fastapi = 0), root temperature 0.2, root thinking_budget 0,
  analyzer sub-agent (temperature 0.2, own thinking_budget 4096), max_output_tokens 8192 x2, 40 calls / 50 turns.
- status: UNVALIDATED locally (plan 007 arm 1: 4/33, ENV CONTROL caveat). Gate-2 submission review: job review-31b-v009-submit-light (pending). Submit route: aniket0202/gemma-submit-31b v2 (pushed 2026-11-07T06:34:57Z).
zip sha256: d38c55c79103950d6d269a722bd0c9db9db22e1c0ec96be230f6c24a332d130d
- packed 2026-11-06T06:28Z with bin/pack --zip (PASS, 9067 unpacked bytes, zip 5365 bytes). zip sha256: d38c55c79103950d6d269a722bd0c9db9db22e1c0ec96be230f6c24a332d130d
