# Finals checklist (FINALS RULE per dec 086 + dec 087 item 1; both tracks)

A final must satisfy ONE of:
- (a) it scored COMPLETE itself: `results/lb_<bundle>.json` has `status: COMPLETE`, a `public_score`, and a
  `sha256` equal to the final's zip sha256.
- (b) mechanical reference check PASSES against a COMPLETE-scored bundle REF:
  `python3 eval/finals_eligibility.py dist/<final>.zip dist/<REF>.zip --reference-lb results/lb_<REF>.json --out results/finals_eligibility_<final>_vs_<REF>.json`
  -> exit 0 / verdict ELIGIBLE. The script allows ONLY decreases (<=) of eval_config
  max_time_minutes / max_tool_calls / max_turns and generate_content_config max_output_tokens /
  thinking_config.thinking_budget (every agent). Every other byte (prompts, instructions, sub-agent
  structure, tools, skills, adapters, other config values incl. temperature, timeout_seconds,
  include_thoughts) must be identical. Different prompt or lineage = INELIGIBLE.
  v2 (2026-11-07, after codex review 091327 BLOCKING x5): strictly byte-level. Knob lines may change ONLY
  their numeric value (same line count, same comments; editing a comment in eval_config.yaml = INELIGIBLE),
  only in eval_config.yaml / agent docs reached from agent.yaml via agent_tool config_path / their
  `generate_content_config: !include` targets; valid domains enforced (ints >= 1, thinking_budget int >= 0,
  cap > 0); zip entries must be unique, normalized, regular files. So a knob-only final must be built by
  editing ONLY the number on the knob line of the REF bundle.

Also (dec 086): never a 31B cap > 3.5.

Checks recorded so far (2026-11-07, re-run with v2 script; verdicts unchanged; script eval/finals_eligibility.py, tests eval/tests/test_finals_eligibility.py):
| candidate | reference | verdict | file |
|---|---|---|---|
| 31b-v012 | 31b-v002 | INELIGIBLE (prompts/system.md; eval_config comment lines) | results/finals_eligibility_31b_v012_vs_31b_v002.json |
| 31b-v009 | 31b-v002 | INELIGIBLE (prompts/system.md; eval_config comment lines) | results/finals_eligibility_31b_v009_vs_31b_v002.json |
| e4b-v002h | e4b-v002 | INELIGIBLE (prompts/system.md) | results/finals_eligibility_e4b_v002h_vs_e4b_v002.json |
| 31b-v002 | 31b-v002 | ELIGIBLE (self, sanity) | results/finals_eligibility_31b_v002_vs_31b_v002.json |
| e4b-v002 | e4b-v002 | ELIGIBLE (self, sanity) | results/finals_eligibility_e4b_v002_vs_e4b_v002.json |

Consequences: v009 qualifies only via its own Nov 8 score; v012 needs its own COMPLETE score; e4b-v002h
qualifies only via its own score (Nov 9 slot). Re-run this check before proposing any final.
