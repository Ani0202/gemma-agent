# e4b v001
- parent: e4b v000 (dist/e4b-v000.zip sha256=cc647bfb28bc6d2db0e3ec816df084f23a91230786d8fea177e2d63d2a6940e2)
- change (ONLY): eval_config.yaml max_time_minutes 5 -> 1.4 (dec 022 item 3). Interim rule (cap + max measured setup 212 s) x125 + 30 = (1.4+3.53)*125+30 = 646 min <= 660. Harness parses the field as float (adk_eval_core/sandbox/base.py:172).
- packed 2026-11-05T17:53Z: dist/e4b-v001.zip sha256=4d07af9211879fe0e45d2148457d4a4a7c273539063bb6f7ca6bfda15cb4d7d7 (bin/pack PASS, 4114 bytes)
- status: UNVALIDATED. codex-review queued (job review-e4b-v001). Kaggle re-time NOT pushed: blocked on dec 022 item 2 (setup root cause).
