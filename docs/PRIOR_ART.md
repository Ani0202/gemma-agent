# Prior art (scout 2026-11-04; via WebFetch summaries, low-medium confidence, no hidden-set evidence)
Do NOT copy code unless a LICENSE file is verified; log any reuse in docs/ATTRIBUTION.md.
- jwj1342/gemma-agent-lab (no license: ideas only): locate/edit/focused-check/export/verify loop, code graphs; 31B baseline 0.12 public; its naive SFT LoRA scored 2/11 vs 4/11 baseline (LoRA can hurt -> gate on paired comparison). Cached gold/baseline controls saved ~18 min/batch.
- sagarml4949/gemma4-swe-agent (no license): mines (problem, patch, test_patch) from public git history of the 4 repos (~1522 instances); read-only sub-agent. No solve rates.
- ennydev-2026/gemma-4-developer-agent (MIT): contract-first system prompt, thinking with budget, local harness with gold-fix mode, zip validator.
- YufanPeter/Gemma-4-Developer-Agent (license unchecked): reported caps 5 min/task, 100 s/command, 40 tool calls, 60 turns.
- emamira02/gemma4-swe-agent: Apache-2.0 per snippet, unverified.
- kawchar85/gemma4-agent-leaderboard (MIT): public LB snapshots, scoring-time estimates (useful for slot planning).
Public scores seen are low (0.06-0.2). Claim that graph tools "measurably help" has no public measurement found; test it ourselves.
