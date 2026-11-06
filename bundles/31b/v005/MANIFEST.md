# 31b-v005-p5c (SCREEN bundle ONLY for plan 005 Addendum C, cap 4.0). NOT a submission candidate.
- Name: 31b-v005-p5c (directory bundles/31b/v005, file dist/31b-v005.zip). v004 stays reserved (dec 056 item 5) for v002 + prompt.
- parent: 31b-v003-p5t4 (dist/31b-v003.zip sha256=e9e603ab7decd589f5ea040579a5facf9c88858986039690ae8053df3e1f4d2f) = arm B,
  paired baseline runs/31b-v003-p5t4-timing.
- built from repo git SHA: see the commit that adds this file (parent commit a7d124b).
- changes (EXACTLY one file): configs/sampling.yaml thinking_config.thinking_budget 4096 -> 1024. Prompt, caps, analyzer unchanged.
  Inherits v003's prompt (generic line; no FastAPI/docs_src hint).
- status: UNVALIDATED.
zip sha256: e8fbcfdc5800d927e6f6e7522b98f252766c6f85a72dcf67adbcc3abc00344f3
- packed 2026-11-06T02:20Z with bin/pack --zip (PASS, 9094 unpacked bytes, zip 5352 bytes). zip sha256: e8fbcfdc5800d927e6f6e7522b98f252766c6f85a72dcf67adbcc3abc00344f3
