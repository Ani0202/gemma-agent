# e4b v000
- parent: none (derived from official sample_submission, data/raw/sample_submission)
- changes: dummy LoRA adapters removed; eval_config caps set to max_time_minutes=5, max_tool_calls=40, max_turns=50 (worst case 5*125+30=655 min); prompts/sampling unchanged from sample
- git SHA / zip sha256: pending bin/pack (codex-build pack) + codex-review
- status: UNVALIDATED, not yet proposed for submission

zip sha256 (re-packed after pack-harden, repo SHA a12f0b7): cc647bfb28bc6d2db0e3ec816df084f23a91230786d8fea177e2d63d2a6940e2
