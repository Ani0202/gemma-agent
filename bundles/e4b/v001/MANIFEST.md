# e4b v001
- parent: e4b v000 (dist/e4b-v000.zip sha256=cc647bfb28bc6d2db0e3ec816df084f23a91230786d8fea177e2d63d2a6940e2)
- change (ONLY): eval_config.yaml max_time_minutes 5 -> 1.4 (dec 022 item 3). Interim rule (cap + max measured setup 212 s) x125 + 30 = (1.4 + 212/60)*125 + 30 = 646.7 min <= 660. Harness parses the field as float (adk_eval_core/sandbox/base.py:172).
- re-packed 2026-11-05T17:59Z after the codex-review nit (comment arithmetic only, 646 -> 646.7): dist/e4b-v001.zip sha256=f2ced9c97ee1447cb3a78c0ebf65f4ecaff90c84b18313645d5d043c62d277e9 (bin/pack PASS). Superseded first pack: 4d07af92...d7d7.
- status: UNVALIDATED. codex-review ops/codex/review-20261105T175327.md: no BLOCKING; float verified through EvalConfig -> 84.0 s; zip = bundle. Kaggle re-time NOT pushed: blocked on dec 022 item 2 (setup root cause).
zip sha256: f2ced9c97ee1447cb3a78c0ebf65f4ecaff90c84b18313645d5d043c62d277e9
